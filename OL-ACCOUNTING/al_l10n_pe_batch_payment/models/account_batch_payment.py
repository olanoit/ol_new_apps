# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.exceptions import UserError

from odoo.tools import BinaryBytes
from odoo.tools.float_utils import float_compare

from .bank_formats import FORMATS, digits, group_by_beneficiary

METHOD = 'pe_bank_txt'
# Tipo de comprobante del registro «3» del BCP según la tabla 10 de SUNAT;
# los demás (recibo por honorarios, liquidación de compra…) van como factura.
BCP_DOCUMENT_TYPES = {'01': 'F', '03': 'B', '07': 'N', '08': 'C'}


class AccountBatchPayment(models.Model):
    _inherit = 'account.batch.payment'

    l10n_pe_export_count = fields.Integer(
        string='Registros del archivo', readonly=True, copy=False,
        help='Número de abonos del último archivo generado (control con el banco). En BCP '
             'los pagos al mismo proveedor y cuenta van en un solo abono.')
    l10n_pe_export_total = fields.Monetary(
        string='Total del archivo', readonly=True, copy=False, currency_field='currency_id',
        help='Suma de los pagos del último archivo generado (control con el banco).')

    def _get_methods_generating_files(self):
        return super()._get_methods_generating_files() + [METHOD]

    # ------------------------------------------------------------------
    # Validaciones
    # ------------------------------------------------------------------
    def _l10n_pe_payment_account(self, payment):
        """(cuenta, es CCI) con la que se abona al proveedor: su cuenta en el
        mismo banco de la empresa o, si es de otro banco, su CCI."""
        bank = payment.partner_bank_id
        if bank.l10n_pe_bank_id and bank.l10n_pe_bank_id == self.journal_id.bank_account_id.l10n_pe_bank_id:
            return digits(bank.account_number), False
        return digits(bank.l10n_pe_cci), True

    def check_payments_for_errors(self):
        errors = super().check_payments_for_errors()
        if self.payment_method_code != METHOD:
            return errors
        journal = self.journal_id
        if not journal.l10n_pe_batch_format:
            errors.append({
                'title': self.env._('El banco del diario %s no tiene formato de pago masivo.',
                                    journal.display_name),
                'records': self.payment_ids,
                'help': self.env._('Elija el formato en el banco (Contabilidad ‣ '
                                   'Configuración ‣ Bancos).'),
            })
        if not journal.bank_account_id.account_number:
            errors.append({
                'title': self.env._('El diario %s no tiene la cuenta de cargo.',
                                    journal.display_name),
                'records': self.payment_ids,
            })
        payments = self.payment_ids
        no_account = payments.filtered(lambda p: not p.partner_bank_id)
        if no_account:
            errors.append({
                'title': self.env._('Pagos sin cuenta bancaria del proveedor.'),
                'records': no_account,
                'help': self.env._('Registre la cuenta del proveedor en su contacto.'),
            })
        def wrong(payment):
            account, is_cci = self._l10n_pe_payment_account(payment)
            return not account or (is_cci and len(account) != 20)

        wrong_account = (payments - no_account).filtered(wrong)
        if wrong_account:
            errors.append({
                'title': self.env._('Cuentas de otro banco sin CCI de 20 dígitos.'),
                'records': wrong_account,
                'help': self.env._('Un proveedor con cuenta en otro banco se paga por su CCI.'),
            })
        other_currency = (payments - no_account).filtered(
            lambda p: p.partner_bank_id.currency_id and p.partner_bank_id.currency_id != self.currency_id)
        if other_currency:
            errors.append({
                'title': self.env._('Cuentas del proveedor en otra moneda que el lote.'),
                'records': other_currency,
                'help': self.env._('Los pagos en soles y en dólares van en lotes distintos.'),
            })
        no_document = payments.filtered(lambda p: not (p.partner_id.commercial_partner_id.vat or '').strip())
        if no_document:
            errors.append({
                'title': self.env._('Proveedores sin RUC o documento de identidad.'),
                'records': no_document,
            })
        if 'l10n_pe_detraction_move_id' in payments._fields:
            detractions = payments.filtered('l10n_pe_detraction_move_id')
            if detractions:
                errors.append({
                    'title': self.env._('Depósitos de detracción en un lote de banco comercial.'),
                    'records': detractions,
                    'help': self.env._('La detracción se deposita en el Banco de la Nación con '
                                       'su propio archivo.'),
                })
        return errors

    # ------------------------------------------------------------------
    # Archivo
    # ------------------------------------------------------------------
    def _l10n_pe_reference(self, payment):
        invoices = payment.reconciled_bill_ids or payment.invoice_ids
        names = invoices.mapped(lambda m: m.ref or m.name)
        return ' '.join(names) or payment.memo or payment.name

    def _l10n_pe_document_code(self, move):
        return BCP_DOCUMENT_TYPES.get(move.l10n_latam_document_type_id.code, 'F')

    def _l10n_pe_payment_documents(self, payment):
        """Comprobantes que salda el pago, con el importe de cada uno en la
        moneda del pago. Con asiento, salen de la conciliación; sin asiento
        (pago en proceso sin cuenta transitoria), de los comprobantes del pago
        cuando su saldo suma el pago. Lista vacía si no cuadran."""
        amounts = {}
        counterpart = payment.move_id and payment._seek_for_lines()[1]
        if counterpart:
            for line in counterpart:
                for partial in line.matched_credit_ids:
                    move = partial.credit_move_id.move_id
                    amounts[move] = amounts.get(move, 0.0) + partial.debit_amount_currency
                for partial in line.matched_debit_ids:
                    move = partial.debit_move_id.move_id
                    amounts[move] = amounts.get(move, 0.0) - partial.credit_amount_currency
        else:
            for move in payment.invoice_ids.filtered(lambda m: m.is_purchase_document(True)):
                if move.currency_id != payment.currency_id:
                    return []
                residual = abs(move.amount_residual)
                amounts[move] = -residual if move.move_type == 'in_refund' else residual
        # Con notas de crédito el abono va sin detalle: solo se informan
        # comprobantes que suman el abono, sin restas.
        if not amounts or any(value < 0 for value in amounts.values()) \
                or float_compare(sum(amounts.values()), payment.amount, precision_digits=2):
            return []
        return [{
            'type': self._l10n_pe_document_code(move),
            'number': move.l10n_latam_document_number or move.ref or move.name,
            'amount': value,
        } for move, value in amounts.items() if value]

    def _l10n_pe_export_lines(self):
        lines = []
        for payment in self.payment_ids.sorted('id'):
            partner = payment.partner_id.commercial_partner_id
            account, is_cci = self._l10n_pe_payment_account(payment)
            lines.append({
                'doc_type': partner.l10n_pe_sunat_id_code or '6',
                'doc_number': (partner.l10n_pe_sunat_id_value or '').strip(),
                'name': partner.name,
                'account': account,
                'is_cci': is_cci,
                'account_kind': payment.partner_bank_id.l10n_pe_account_kind or 'checking',
                'amount': payment.amount,
                'reference': self._l10n_pe_reference(payment),
                'documents': self._l10n_pe_payment_documents(payment),
            })
        return lines

    def _l10n_pe_export_header(self):
        journal = self.journal_id
        company = journal.company_id
        return {
            'currency': self.currency_id.name,
            'payment_date': self.date,
            'now': fields.Datetime.context_timestamp(self, fields.Datetime.now()),
            'charge_acc': journal.bank_account_id.account_number,
            'company_name': company.name,
            'company_vat': company.vat or '',
            'reference': self.name,
            'options': {
                'service_code': journal.l10n_pe_batch_service_code,
                'company_code': journal.l10n_pe_batch_company_code,
                'process_type': journal.l10n_pe_batch_process_type,
                'itf_exempt': journal.l10n_pe_batch_itf_exempt,
                'validate_idc': journal.l10n_pe_batch_validate_idc,
                'documents': journal.l10n_pe_batch_documents,
            },
        }

    def _generate_export_file(self):
        if self.payment_method_code != METHOD:
            return super()._generate_export_file()
        bank_format = self.journal_id.l10n_pe_batch_format
        if bank_format not in FORMATS:
            raise UserError(self.env._('El banco del diario no tiene formato de pago masivo.'))
        builder, label, grouped = FORMATS[bank_format]
        lines = self._l10n_pe_export_lines()
        if grouped:
            lines = group_by_beneficiary(lines)
        text = builder(self._l10n_pe_export_header(), lines)
        self.l10n_pe_export_count = len(lines)
        self.l10n_pe_export_total = sum(line['amount'] for line in lines)
        filename = '%s_%s_%s_%s.txt' % (
            label, self.currency_id.name, self.journal_id.code,
            (self.name or '').replace('/', '-'))
        return {
            'file': BinaryBytes(text.encode('latin-1', errors='replace')),
            'filename': filename,
        }
