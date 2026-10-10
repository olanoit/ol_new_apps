# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from lxml import etree
from markupsafe import Markup
from pytz import timezone

from odoo import models
from odoo.tools import float_repr
from odoo.tools.zeep.wsse.username import UsernameToken

# Plazo máximo de envío de la factura y sus notas a SUNAT o al OSE: hasta el
# tercer día calendario siguiente a la emisión (R.S. 000003-2023/SUNAT). Fuera
# de plazo el documento no tiene calidad de factura aunque se haya entregado.
FACTURA_SEND_DAYS = 3
# Catálogo 05: código, nombre y tipo de cada tributo del resumen diario.
SUMMARY_TAXES = {'IGV': ('1000', 'IGV', 'VAT'), 'ISC': ('2000', 'ISC', 'EXC'),
                 'OTROS': ('9999', 'OTROS', 'OTH')}


class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    # Factory HKA expone el mismo billService de SUNAT (sendBill, getStatus,
    # sendSummary, getStatusCdr): basta con sus credenciales y su WSDL, y el
    # resto lo hacen los servicios comunes de l10n_pe_edi, que ``getattr``
    # elige por el nombre del proveedor.

    def _l10n_pe_edi_get_factory_hka_credentials(self, company):
        """Credenciales con la forma de las nativas, o ``{'error': …}`` si
        falta configuración (sin excepción, para no cortar el cron del EDI)."""
        self.ensure_one()
        company_sudo = company.sudo()  # credenciales con groups=base.group_system
        username = company_sudo.l10n_pe_edi_factory_hka_username
        password = company_sudo.l10n_pe_edi_factory_hka_password
        if not username or not password:
            return {'error': self.env._(
                'Faltan el usuario o la contraseña de Factory HKA de %(company)s. '
                'Configúrelos en Ajustes ▸ Contabilidad ▸ Facturación electrónica peruana.',
                company=company.display_name), 'blocking_level': 'error'}
        wsdl = company._l10n_pe_edi_factory_hka_wsdl()
        if not wsdl:
            return {'error': self.env._(
                'Falta el WSDL de producción de Factory HKA de %(company)s. '
                'Configúrelo en Ajustes o active «Entorno de prueba».',
                company=company.display_name), 'blocking_level': 'error'}
        return {'fault_ns': 'S', 'wsdl': wsdl, 'token': UsernameToken(username, password)}

    def _l10n_pe_edi_factory_hka_filename(self, edi_filename):
        """``RUC-TT-SERIE-NUMERO`` con el número en 8 dígitos, como exige HKA
        (``20524531861-01-F001-11`` → ``20524531861-01-F001-00000011``)."""
        prefix, sep, number = edi_filename.rpartition('-')
        if not sep or not number.isdigit():
            return edi_filename
        return '%s-%s' % (prefix, number.zfill(8))

    # -------------------------------------------------------------------------
    # Envío
    # -------------------------------------------------------------------------

    def _l10n_pe_edi_sign_invoices_factory_hka(self, invoice, edi_filename, edi_str):
        self._l10n_pe_edi_factory_hka_check_deadline(invoice)
        res = self._l10n_pe_edi_sign_service_factory_hka(
            invoice.company_id, edi_filename, edi_str, invoice.l10n_latam_document_type_id.code)
        if res.get('success') and res.get('cdr'):
            self._l10n_pe_edi_factory_hka_post_cdr_notes(invoice, res['cdr'])
        return res

    def _l10n_pe_edi_factory_hka_check_deadline(self, invoice):
        """Avisa en el historial si una factura (o su nota) se envía después
        del plazo de SUNAT. No bloquea: el OSE decide, y el usuario debe saber
        que ese número ya no vale como factura."""
        number = invoice.name.replace(' ', '')
        if not invoice.invoice_date or not number.startswith('F'):
            return
        today = datetime.now(tz=timezone('America/Lima')).date()
        deadline = invoice.invoice_date + timedelta(days=FACTURA_SEND_DAYS)
        if today > deadline:
            invoice.message_post(body=self.env._(
                'Envío fuera de plazo: la factura o nota emitida el %(date)s debía enviarse a SUNAT '
                'o al OSE hasta el %(deadline)s (R.S. 000003-2023/SUNAT). Fuera de plazo no tiene '
                'calidad de comprobante aunque se haya entregado al cliente.',
                date=invoice.invoice_date.strftime('%d/%m/%Y'),
                deadline=deadline.strftime('%d/%m/%Y')))

    def _l10n_pe_edi_factory_hka_post_cdr_notes(self, invoice, cdr):
        """Un CDR aceptado puede traer observaciones (``cbc:Note``): el
        comprobante es válido, pero conviene corregir el dato en los siguientes."""
        try:
            notes = [n.text for n in etree.fromstring(cdr).findall('.//{*}Note') if n.text]
        except etree.LxmlError:
            return
        if notes:
            invoice.message_post(body=Markup('%s<ul>%s</ul>') % (
                self.env._('SUNAT aceptó el comprobante con observaciones:'),
                Markup('').join(Markup('<li>%s</li>') % note for note in notes)))

    def _l10n_pe_edi_sign_service_factory_hka(self, company, edi_filename, edi_str, latam_document_type):
        """Mismo contrato que ``_l10n_pe_edi_sign_service_sunat``: lo usan
        también otros documentos (p. ej. el comprobante de retención)."""
        credentials = self._l10n_pe_edi_get_factory_hka_credentials(company)
        if credentials.get('error'):
            return credentials
        return self._l10n_pe_edi_sign_service_sunat_digiflow_common(
            company, self._l10n_pe_edi_factory_hka_filename(edi_filename), edi_str,
            credentials, latam_document_type)

    # -------------------------------------------------------------------------
    # Consulta del CDR
    # -------------------------------------------------------------------------

    def _l10n_pe_edi_get_status_cdr_factory_hka_service(self, company, serie_folio, latam_document_type):
        credentials = self._l10n_pe_edi_get_factory_hka_credentials(company)
        if credentials.get('error'):
            return credentials
        return self._l10n_pe_edi_get_status_cdr_sunat_digiflow_service_common(
            credentials, company.vat, serie_folio, latam_document_type)

    # -------------------------------------------------------------------------
    # Comunicación de baja
    # -------------------------------------------------------------------------

    def _l10n_pe_edi_cancel_invoices_step_1_factory_hka(self, company, invoices, void_filename, void_str):
        credentials = self._l10n_pe_edi_get_factory_hka_credentials(company)
        if credentials.get('error'):
            return credentials
        # La reversión del CRE también usa este paso, con pagos: solo los
        # comprobantes (account.move) pueden ir en un resumen diario.
        summary = (invoices.filtered(self._l10n_pe_edi_factory_hka_goes_in_summary)
                   if invoices._name == 'account.move' else invoices.browse())
        if summary:
            # Las boletas (y sus notas) no van en la comunicación de baja (RA):
            # se informan en un resumen diario con estado 3.
            if summary != invoices:
                return {'error': self.env._(
                    'Las boletas y sus notas se dan de baja con un resumen diario y las facturas con '
                    'una comunicación de baja: solicite su anulación por separado.'),
                    'blocking_level': 'error'}
            if len(set(invoices.mapped('invoice_date'))) > 1:
                return {'error': self.env._(
                    'Un resumen diario solo informa comprobantes de una misma fecha de emisión: '
                    'solicite la baja de cada fecha por separado.'), 'blocking_level': 'error'}
            void_filename, void_str = self._l10n_pe_edi_factory_hka_boleta_summary(company, invoices)
        return self._l10n_pe_edi_cancel_invoices_step_1_sunat_digiflow_common(
            company, invoices, void_filename, void_str, credentials)

    def _l10n_pe_edi_factory_hka_goes_in_summary(self, move):
        """Boleta (03) o nota de crédito/débito vinculada a una boleta."""
        code = move.l10n_latam_document_type_id.code
        if code == '03':
            return True
        origin = move.reversed_entry_id or move.debit_origin_id
        if code in ('07', '08'):
            if origin:
                return origin.l10n_latam_document_type_id.code == '03'
            return move.name.replace(' ', '').startswith('B')
        return False

    def _l10n_pe_edi_factory_hka_summary_line(self, move):
        """Importes de un comprobante para su línea del resumen diario, en su
        moneda: valor de venta por tipo de operación (01 gravadas, 02
        exoneradas, 03 inafectas y exportación, 05 gratuitas) y tributos."""
        currency = move.currency_id
        bases = dict.fromkeys(('01', '02', '03', '05'), 0.0)
        for line in move.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
            codes = set(line.tax_ids.tax_group_id.mapped('l10n_pe_edi_code'))
            kind = ('05' if 'GRA' in codes else '02' if 'EXO' in codes
                    else '03' if codes & {'INA', 'EXP'} else '01' if codes & {'IGV', 'IVAP'} else '03')
            bases[kind] += line.price_subtotal
        taxes = dict.fromkeys(SUMMARY_TAXES, 0.0)
        for line in move.line_ids.filtered('tax_line_id'):
            code = line.tax_line_id.tax_group_id.l10n_pe_edi_code
            key = 'IGV' if code in ('IGV', 'IVAP') else 'ISC' if code == 'ISC' else 'OTROS'
            if code != 'GRA':
                taxes[key] += abs(line.amount_currency)
        origin = move.reversed_entry_id or move.debit_origin_id
        partner = move.commercial_partner_id
        fmt = lambda amount: float_repr(currency.round(amount), currency.decimal_places)
        return {
            'document_type': move.l10n_latam_document_type_id.code,
            'number': move.name.replace(' ', ''),
            'customer_vat': partner.vat or '-',
            'customer_vat_type': partner.l10n_latam_identification_type_id.l10n_pe_vat_code or '-',
            'reference_number': origin.name.replace(' ', '') if origin else False,
            'reference_type': origin.l10n_latam_document_type_id.code if origin else False,
            'currency': currency.name,
            'total': fmt(0.0 if bases['05'] and not move.amount_total else move.amount_total),
            'payments': [(kind, fmt(amount)) for kind, amount in bases.items()
                         if kind != '05' or amount],
            'taxes': [SUMMARY_TAXES[key] + (fmt(amount),) for key, amount in taxes.items()
                      if key == 'IGV' or amount],
        }

    def _l10n_pe_edi_factory_hka_boleta_summary(self, company, moves):
        """Resumen diario RC-AAAAMMDD-N (fecha de emisión de los comprobantes)
        que da de baja las boletas y notas indicadas."""
        reference_date = moves[0].invoice_date
        number = self.env['ir.sequence'].with_context(ir_sequence_date=reference_date).next_by_code(
            'al_ose_factory_hka.boleta_summary_sequence')
        summary_str = self.env['ir.qweb']._render('al_ose_factory_hka.boleta_void_summary', {
            'company': company,
            'summary_number': number,
            'reference_date': reference_date,
            'issue_date': datetime.now(tz=timezone('America/Lima')).date(),
            'lines': [self._l10n_pe_edi_factory_hka_summary_line(move) for move in moves],
        }).encode()
        return '%s-%s' % (company.vat, number), summary_str

    def _l10n_pe_edi_cancel_invoices_step_2_factory_hka(self, company, edi_values, cdr_number):
        credentials = self._l10n_pe_edi_get_factory_hka_credentials(company)
        if credentials.get('error'):
            return credentials
        return self._l10n_pe_edi_cancel_invoices_step_2_sunat_digiflow_common(
            company, edi_values, cdr_number, credentials)
