# -*- coding: utf-8 -*-
"""Comprobante de Retención Electrónico (CRE, tipo 20) desde el pago.

La interfaz sigue al módulo oficial de Odoo ``l10n_pe_edi_withholding``
(Enterprise 19.4/20) para que al migrar se pueda cambiar a él: mismos campos
(``l10n_pe_edi_status``, ``l10n_pe_edi_warnings``,
``l10n_pe_edi_attachment_file``, ``l10n_pe_edi_retention_number``,
``l10n_pe_edi_is_required``) y mismos métodos (reparto por comprobante,
XML, nombre del archivo, envío y servicio de SUNAT). La implementación es
propia y se apoya en los servicios de firma y envío de ``l10n_pe_edi`` 19.0.

Diferencia deliberada con el oficial: la retención es el 3 % del importe
pagado **con IGV** (R.S. 037-2002/SUNAT); en los XML de prueba oficiales sale
el 3 % de la base sin IGV.
"""
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

# R.S. 274-2015/SUNAT: el CRE se envía a SUNAT u OSE dentro de los 7 días
# calendario siguientes a su emisión; fuera de plazo no vale como CRE.
SEND_DEADLINE_DAYS = 7
# Estados del CRE (los comparte el CRE sin pago de Odoo).
CRE_STATES = [('to_send', 'Por enviar'), ('sent', 'Enviado'),
              ('reversing', 'Reversión en proceso'), ('cancelled', 'Anulado')]


class AccountPayment(models.Model):
    _name = 'account.payment'
    _inherit = ['account.payment', 'l10n_pe.retention.edi.mixin']

    # Etiqueta en español del marco nativo
    withholding_line_ids = fields.One2many(string='Retenciones')

    l10n_pe_edi_retention_number = fields.Char(
        string='Nº comprobante de retención',
        compute='_compute_l10n_pe_edi_retention_number', store=True)
    l10n_pe_edi_status = fields.Selection(
        selection=CRE_STATES, string='Estado del CRE', copy=False, tracking=True)
    l10n_pe_edi_warnings = fields.Json(string='Avisos del CRE', readonly=True, copy=False)
    l10n_pe_edi_attachment_file = fields.Binary(
        string='CRE firmado y CDR', attachment=True, copy=False)
    l10n_pe_edi_is_required = fields.Boolean(
        string='CRE por enviar', compute='_compute_l10n_pe_edi_is_required')
    l10n_pe_edi_deadline = fields.Date(
        string='Enviar el CRE hasta', compute='_compute_l10n_pe_edi_deadline', store=True,
        help='Plazo de 7 días calendario desde la emisión del comprobante de retención '
             '(fecha del pago) para enviarlo a SUNAT u OSE.')
    l10n_pe_edi_overdue = fields.Boolean(
        string='CRE fuera de plazo', compute='_compute_l10n_pe_edi_overdue',
        search='_search_l10n_pe_edi_overdue')
    l10n_pe_edi_error_message = fields.Char(
        string='Error del CRE', compute='_compute_l10n_pe_edi_error_message')
    # Guardado para los totales de la lista y el análisis de retenciones.
    l10n_pe_retention_amount = fields.Monetary(
        string='Importe retenido', currency_field='currency_id',
        compute='_compute_l10n_pe_retention_amount', store=True,
        help='Suma de las líneas de retención del IGV del pago.')
    l10n_pe_retention_deduction_ids = fields.One2many(
        'l10n_pe.retention.credit.deduction', 'payment_id',
        string='Notas de crédito descontadas', readonly=True,
        help='Retención de notas de crédito del proveedor descontada en este CRE (art. 2 de '
             'la R.S. 037-2002/SUNAT).')

    def _l10n_pe_retention_lines(self):
        return self.withholding_line_ids.filtered(
            lambda l: l.tax_id == self.company_id.l10n_pe_retention_tax_id)

    @api.depends('withholding_line_ids.amount', 'withholding_line_ids.tax_id',
                 'company_id.l10n_pe_retention_tax_id')
    def _compute_l10n_pe_retention_amount(self):
        for payment in self:
            payment.l10n_pe_retention_amount = sum(
                payment._l10n_pe_retention_lines().mapped('amount'))

    @api.depends('withholding_line_ids.name')
    def _compute_l10n_pe_edi_retention_number(self):
        for payment in self:
            payment.l10n_pe_edi_retention_number = ', '.join(
                n for n in payment._l10n_pe_retention_lines().mapped('name') if n) or False

    @api.depends('state', 'l10n_pe_edi_retention_number', 'l10n_pe_edi_status', 'country_code')
    def _compute_l10n_pe_edi_is_required(self):
        for payment in self:
            payment.l10n_pe_edi_is_required = bool(
                payment.state in ('in_process', 'paid')
                and payment.l10n_pe_edi_retention_number
                and payment.country_code == 'PE'
                and payment.l10n_pe_edi_status not in ('sent', 'reversing', 'cancelled'))

    @api.depends('date', 'l10n_pe_edi_retention_number')
    def _compute_l10n_pe_edi_deadline(self):
        for payment in self:
            payment.l10n_pe_edi_deadline = (
                payment.date + timedelta(days=SEND_DEADLINE_DAYS)
                if payment.date and payment.l10n_pe_edi_retention_number else False)

    @api.depends('l10n_pe_edi_deadline', 'l10n_pe_edi_status')
    def _compute_l10n_pe_edi_overdue(self):
        today = fields.Date.context_today(self)
        for payment in self:
            payment.l10n_pe_edi_overdue = bool(
                payment.l10n_pe_edi_status == 'to_send'
                and payment.l10n_pe_edi_deadline and payment.l10n_pe_edi_deadline < today)

    def _search_l10n_pe_edi_overdue(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            return NotImplemented
        domain = [('l10n_pe_edi_status', '=', 'to_send'),
                  ('l10n_pe_edi_deadline', '<', fields.Date.context_today(self))]
        return domain if (operator == '=') == value else ['!', '&', *domain]

    @api.depends('l10n_pe_edi_warnings')
    def _compute_l10n_pe_edi_error_message(self):
        for payment in self:
            error = (payment.l10n_pe_edi_warnings or {}).get('edi_error') or {}
            payment.l10n_pe_edi_error_message = error.get('message') or False

    def action_post(self):
        """El comprobante de retención se numera al emitir el pago (el marco
        nativo lo haría recién al generar el asiento con el extracto, tarde
        para el flujo SUNAT) y queda por enviar."""
        res = super().action_post()
        for payment in self:
            lines = payment._l10n_pe_retention_lines()
            for line in lines.filtered(lambda l: not l.name and l.withholding_sequence_id):
                line.name = line.withholding_sequence_id.next_by_id()
            if lines and not payment.l10n_pe_edi_status:
                payment.l10n_pe_edi_status = 'to_send'
            if lines:
                payment._l10n_pe_retention_record_deductions()
        return res

    def _l10n_pe_retention_record_deductions(self):
        """Si se retuvo menos del 3 % de lo pagado (el asistente descuenta la
        retención pendiente de las notas de crédito del proveedor), la
        diferencia se imputa a esas notas, de la más antigua a la más
        reciente, y queda registrada con este CRE."""
        self.ensure_one()
        company = self.company_id
        currency = company.currency_id
        self.l10n_pe_retention_deduction_ids.unlink()
        if not company.l10n_pe_retention_deduct_credit_notes:
            return
        # Al confirmar, el pago aún no está conciliado con sus facturas: se
        # compara cada línea de retención con el 3 % de su base.
        lines = self._l10n_pe_retention_lines()

        def to_pen(amount):
            return self.currency_id._convert(amount, currency, company, self.date)

        expected = sum(currency.round(to_pen(line.base_amount) * company.l10n_pe_retention_rate
                                      / 100.0) for line in lines)
        retained = sum(to_pen(abs(line.amount)) for line in lines)
        # el redondeo de cada línea puede dejar céntimos sueltos
        shortfall = currency.round(expected - retained)
        if currency.compare_amounts(shortfall, 0.01 * len(lines)) <= 0:
            return
        for note, amount in self.env['account.move']._l10n_pe_retention_plan_deductions(
                company, self.partner_id, shortfall):
            self.env['l10n_pe.retention.credit.deduction'].create({
                'company_id': company.id, 'credit_note_id': note.id,
                'amount': amount, 'payment_id': self.id})

    # ------------------------------------------------------------------
    # Reparto por comprobante (misma salida que el oficial)
    # ------------------------------------------------------------------
    def _l10n_pe_edi_get_paid_per_bill(self):
        """``{bill.id: importe}`` en la moneda de cada factura, según la
        conciliación del pago. Vacío si el pago aún no tiene asiento (en 19.0
        nace al conciliar el extracto)."""
        self.ensure_one()
        result = {}
        if not self.move_id:
            return result
        payment_lines = self.move_id.line_ids
        for bill in self.reconciled_bill_ids:
            for partial in bill.line_ids.matched_debit_ids | bill.line_ids.matched_credit_ids:
                if partial.debit_move_id in payment_lines:
                    amount = partial.credit_amount_currency
                elif partial.credit_move_id in payment_lines:
                    amount = partial.debit_amount_currency
                else:
                    continue
                result[bill.id] = result.get(bill.id, 0.0) + amount
        return result

    def _l10n_pe_edi_get_retention_breakdown(self):
        """Reparto del pago y de la retención entre sus comprobantes, con las
        mismas claves que el oficial: ``bill``, ``bill_paid_currency`` (moneda
        de la factura), ``bill_paid_pen``, ``bill_retention_pen``,
        ``net_total_paid_pen`` y ``exchange_rate`` (moneda de la factura a
        soles, a la fecha del pago). Lo usan el XML, el PDF y el resumen 626.

        Sin conciliación, el pago se reparte en proporción al total de cada
        factura. La retención se reparte según lo pagado y el redondeo cae en
        la última.
        """
        self.ensure_one()
        company = self.company_id
        company_currency = company.currency_id
        bills = self.invoice_ids or self.reconciled_bill_ids
        if not bills:
            return []
        rates = {
            bill: (1.0 if bill.currency_id == company_currency
                   else self.env['res.currency']._get_conversion_rate(
                       bill.currency_id, company_currency, company, self.date))
            for bill in bills
        }
        paid_per_bill = self._l10n_pe_edi_get_paid_per_bill()
        if not any(paid_per_bill.values()):
            # importe bruto del pago (antes de retener) repartido por el total
            gross_pen = self.currency_id._convert(self.amount, company_currency, company, self.date)
            weights = {bill: abs(bill.amount_total_signed) for bill in bills}
            total_weight = sum(weights.values()) or 1.0
            paid_per_bill = {
                bill.id: bill.currency_id.round(gross_pen * weights[bill] / total_weight / rates[bill])
                for bill in bills}
        # Con notas de crédito descontadas, cada comprobante informa su 3 %
        # completo y las notas restan (ver _l10n_pe_retention_deduction_entries).
        deductions = self.l10n_pe_retention_deduction_ids
        retention_pen = company_currency.round(sum(
            self.currency_id._convert(abs(line.amount), company_currency, company, self.date)
            for line in self._l10n_pe_retention_lines()) + sum(deductions.mapped('amount')))

        paid_pen = {bill: company_currency.round(paid_per_bill.get(bill.id, 0.0) * rates[bill])
                    for bill in bills}
        total_paid_pen = sum(paid_pen.values()) or 1.0
        breakdown = []
        retained_left = retention_pen
        for index, bill in enumerate(bills):
            if index == len(bills) - 1:
                retained = retained_left
            else:
                retained = company_currency.round(retention_pen * paid_pen[bill] / total_paid_pen)
                retained_left -= retained
            breakdown.append({
                'bill': bill,
                'bill_paid_currency': paid_per_bill.get(bill.id, 0.0),
                'bill_paid_pen': paid_pen[bill],
                'bill_retention_pen': retained,
                'net_total_paid_pen': paid_pen[bill] - retained,
                'exchange_rate': rates[bill],
            })
        return breakdown + self._l10n_pe_retention_deduction_entries(deductions)

    # ------------------------------------------------------------------
    # Lo que el pago aporta al CRE (l10n_pe.retention.edi.mixin)
    # ------------------------------------------------------------------
    def _l10n_pe_retention_bills(self):
        self.ensure_one()
        return self.invoice_ids | self.reconciled_bill_ids

    def _l10n_pe_retention_note(self):
        self.ensure_one()
        return self.memo

    def _l10n_pe_retention_check_ready(self):
        self.ensure_one()
        if not self._l10n_pe_retention_lines():
            raise UserError(self.env._('El pago no tiene líneas de retención de IGV.'))

    # ------------------------------------------------------------------
    # Un CRE aceptado ata al pago hasta revertirlo en SUNAT
    # ------------------------------------------------------------------
    def _l10n_pe_retention_check_unlocked(self):
        locked = self.filtered(lambda p: p.l10n_pe_edi_status in ('sent', 'reversing'))
        if locked:
            raise UserError(self.env._(
                'Estos pagos tienen un comprobante de retención aceptado por SUNAT: %s. '
                'Reviértalo primero (botón «Revertir CRE») y, cuando SUNAT acepte la '
                'reversión, el pago se podrá restablecer o cancelar.',
                ', '.join(locked.mapped('display_name'))))

    def action_draft(self):
        self._l10n_pe_retention_check_unlocked()
        reversed_cre = self.filtered(lambda p: p.l10n_pe_edi_status == 'cancelled')
        res = super().action_draft()
        # al confirmar de nuevo se vuelven a imputar las notas de crédito
        self.l10n_pe_retention_deduction_ids.unlink()
        if reversed_cre:
            # El número revertido no se reutiliza: al confirmar de nuevo, la
            # retención toma un número nuevo y vuelve a quedar por enviar.
            reversed_cre._l10n_pe_retention_lines().write({'name': False})
            reversed_cre.write({
                'l10n_pe_edi_status': False, 'l10n_pe_edi_warnings': False,
                'l10n_pe_edi_reversal_filename': False, 'l10n_pe_edi_reversal_ticket': False,
                'l10n_pe_edi_reversal_message': False,
            })
        return res

    def action_cancel(self):
        self._l10n_pe_retention_check_unlocked()
        return super().action_cancel()
