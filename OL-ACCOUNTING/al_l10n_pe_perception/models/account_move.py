# -*- coding: utf-8 -*-
"""Percepción del IGV en la factura de venta (agente de percepción) y acceso
al registro de la percepción que nos cobra un proveedor.

La percepción se efectúa al cobrar (art. 4 de la R.S. 058-2006/SUNAT) y se
acredita con el comprobante de percepción (``l10n_pe.perception``); la
factura la anticipa: decide si la operación está sujeta, con qué tasa y por
cuánto, para informarla en el XML (operación 2001 y cargo del catálogo 53) y
en el PDF («Operación sujeta a percepción del IGV», art. 11.1).
"""
from odoo import api, fields, models
from odoo.exceptions import UserError

# Tasas (porcentaje) y códigos: catálogo 53 de la factura y catálogo 22 del
# comprobante de percepción. Tabla oficial «Porcentajes de percepción del IGV».
PERCEPTION_REGIMES = {
    '51': {'rate': 2.0, 'cpe_code': '01', 'name': 'Percepción venta interna (2 %)'},
    '52': {'rate': 1.0, 'cpe_code': '02', 'name': 'Percepción a la adquisición de combustible (1 %)'},
    '53': {'rate': 0.5, 'cpe_code': '03',
           'name': 'Percepción al agente de percepción con tasa especial (0,5 %)'},
}
PERCEPTION_CODES = [(code, values['name']) for code, values in PERCEPTION_REGIMES.items()]
# Comprobantes que permiten ejercer el crédito fiscal: factura y nota de débito.
CREDIT_DOCUMENTS = ('01', '08')
# Consumidor final (art. 7): persona natural que compra hasta S/ 1 500 por
# comprobante (desde el 1/1/2014); S/ 100 en los numerales 1, 2 y 3.
FINAL_CONSUMER_LIMIT = 1500.0
FINAL_CONSUMER_LIMIT_LOW = 100.0
INTERNAL_TYPES = ('internal', 'internal_low', 'glp')


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_perception_code = fields.Selection(
        PERCEPTION_CODES, string='Percepción del IGV', compute='_compute_l10n_pe_perception',
        store=True, help='Régimen de percepción de la operación (catálogo 53). Vacío: no '
                         'sujeta o excluida.')
    l10n_pe_perception_rate = fields.Float(
        string='Tasa de percepción (%)', digits=(5, 2), compute='_compute_l10n_pe_perception',
        store=True)
    l10n_pe_perception_base = fields.Monetary(
        string='Base sujeta a percepción', currency_field='currency_id',
        compute='_compute_l10n_pe_perception', store=True,
        help='Precio de venta (con IGV) de los bienes sujetos, en la moneda de la factura.')
    l10n_pe_perception_base_pen = fields.Monetary(
        string='Base sujeta (S/)', currency_field='company_currency_id',
        compute='_compute_l10n_pe_perception', store=True)
    l10n_pe_perception_amount = fields.Monetary(
        string='Percepción estimada (S/)', currency_field='company_currency_id',
        compute='_compute_l10n_pe_perception', store=True,
        help='Percepción si la factura se cobra entera al tipo de cambio de su fecha. Se '
             'efectúa y se acredita al cobrar, con el comprobante de percepción.')
    l10n_pe_perception_note = fields.Char(
        string='Motivo', compute='_compute_l10n_pe_perception', store=True,
        help='Por qué la operación no está sujeta, aunque tenga bienes del régimen.')
    l10n_pe_perception_line_ids = fields.One2many(
        'l10n_pe.perception.line', 'invoice_id', string='Comprobantes de percepción',
        readonly=True)
    l10n_pe_perception_collected = fields.Monetary(
        string='Percibido (S/)', currency_field='company_currency_id',
        compute='_compute_l10n_pe_perception_collected',
        help='Percepción acreditada con comprobantes de percepción emitidos.')
    l10n_pe_perception_received_line_ids = fields.One2many(
        'l10n_pe.perception.received.line', 'bill_id', string='Percepciones que nos cobraron',
        readonly=True)

    # ------------------------------------------------------------------
    # Régimen de la factura de venta
    # ------------------------------------------------------------------
    @api.depends('move_type', 'state', 'partner_id', 'currency_id', 'invoice_date', 'date',
                 'company_id.l10n_pe_perception_agent', 'company_id.l10n_pe_perception_fuel_agent',
                 'l10n_latam_document_type_id',
                 'invoice_line_ids.price_total', 'invoice_line_ids.product_id',
                 'commercial_partner_id.is_retention_agent',
                 'commercial_partner_id.l10n_pe_is_perception_agent',
                 'commercial_partner_id.l10n_pe_perception_excluded')
    def _compute_l10n_pe_perception(self):
        for move in self:
            values = move._l10n_pe_perception_values()
            move.l10n_pe_perception_code = values['code']
            move.l10n_pe_perception_rate = values['rate']
            move.l10n_pe_perception_base = values['base']
            move.l10n_pe_perception_base_pen = values['base_pen']
            move.l10n_pe_perception_amount = values['amount']
            move.l10n_pe_perception_note = values['note']

    def _l10n_pe_perception_values(self):
        """Régimen, tasa, base y monto estimado de la percepción de la factura
        (R.S. 058-2006/SUNAT arts. 5 a 7; combustibles, R.S. 128-2002/SUNAT)."""
        self.ensure_one()
        empty = {'code': False, 'rate': 0.0, 'base': 0.0, 'base_pen': 0.0, 'amount': 0.0,
                 'note': False}
        company = self.company_id
        if self.move_type != 'out_invoice' or self.country_code != 'PE' \
                or not (company.l10n_pe_perception_agent or company.l10n_pe_perception_fuel_agent):
            return empty
        lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product' and l.product_id.l10n_pe_perception_type)
        fuel = lines.filtered(lambda l: l.product_id.l10n_pe_perception_type == 'fuel')
        internal = lines - fuel
        # Un comprobante de percepción por tasa (art. 10.4): la factura se
        # percibe por un solo régimen; con combustibles, el de combustibles.
        if fuel and company.l10n_pe_perception_fuel_agent:
            regime, subject = 'fuel', fuel
        elif internal and company.l10n_pe_perception_agent:
            regime, subject = 'internal', internal
        else:
            return empty
        base = self.currency_id.round(sum(subject.mapped('price_total')))
        if self.currency_id.is_zero(base):
            return empty
        day = self.invoice_date or self.date or fields.Date.context_today(self)
        base_pen = self.currency_id._convert(base, company.currency_id, company, day)
        partner = self.commercial_partner_id
        doc_code = self.l10n_latam_document_type_id.code or '01'
        credit_doc = doc_code in CREDIT_DOCUMENTS
        values = dict(empty, base=base, base_pen=base_pen)

        def excluded(note):
            return dict(values, note=note)

        if 'l10n_pe_detraction_applies' in self._fields and self.l10n_pe_detraction_applies:
            return excluded(self.env._('Operación con detracción (SPOT): excluida.'))
        if regime == 'fuel':
            if partner.l10n_pe_is_perception_agent:
                return excluded(self.env._('El cliente es agente de percepción.'))
            if partner.l10n_pe_perception_excluded:
                return excluded(self.env._('Consumidor directo exceptuado.'))
            if not credit_doc:
                return excluded(self.env._('Consumidor final (comprobante sin crédito fiscal).'))
            code = '52'
        else:
            if credit_doc and (partner.is_retention_agent or partner.l10n_pe_perception_excluded):
                return excluded(self.env._(
                    'El cliente es agente de retención o entidad exceptuada (art. 6).'))
            if not credit_doc and partner._l10n_pe_perception_is_natural_person():
                low = all(l.product_id.l10n_pe_perception_type == 'internal_low' for l in subject)
                limit = FINAL_CONSUMER_LIMIT_LOW if low else FINAL_CONSUMER_LIMIT
                if company.currency_id.compare_amounts(base_pen, limit) <= 0:
                    return excluded(self.env._(
                        'Consumidor final: persona natural hasta S/ %s por comprobante (art. 7).',
                        '%.2f' % limit))
            code = '53' if credit_doc and partner.l10n_pe_is_perception_agent else '51'
        rate = PERCEPTION_REGIMES[code]['rate']
        return dict(values, code=code, rate=rate,
                    amount=company.currency_id.round(base_pen * rate / 100.0))

    def _l10n_pe_perception_total_pen(self):
        """Monto total cobrado en soles incluida la percepción (lo que informa
        la factura en ``cac:PaymentTerms`` «Percepcion»)."""
        self.ensure_one()
        company = self.company_id
        day = self.invoice_date or self.date or fields.Date.context_today(self)
        total_pen = self.currency_id._convert(self.amount_total, company.currency_id, company, day)
        return company.currency_id.round(total_pen + self.l10n_pe_perception_amount)

    @api.depends('l10n_pe_perception_line_ids.perception_pen',
                 'l10n_pe_perception_line_ids.perception_id.state')
    def _compute_l10n_pe_perception_collected(self):
        for move in self:
            move.l10n_pe_perception_collected = sum(
                move.l10n_pe_perception_line_ids.filtered(
                    lambda l: l.perception_id.state == 'posted').mapped('perception_pen'))

    def _post(self, soft=True):
        """Operación 2001 «sujeta a percepción» (catálogo 51) en la factura que
        la tiene, salvo que el usuario haya elegido otro tipo de operación."""
        for move in self.filtered('l10n_pe_perception_code'):
            if 'l10n_pe_edi_operation_type' in move._fields \
                    and move.l10n_pe_edi_operation_type in (False, '0101'):
                move.l10n_pe_edi_operation_type = '2001'
        return super()._post(soft=soft)

    # ------------------------------------------------------------------
    # Percepción que nos cobra un proveedor
    # ------------------------------------------------------------------
    def action_l10n_pe_register_perception(self):
        """«Registrar percepción» desde una factura de proveedor: borrador con
        la percepción consignada en el comprobante (numeral 10.6) al 2 %."""
        self.ensure_one()
        if self.move_type != 'in_invoice' or self.state != 'posted':
            raise UserError(self.env._('Registre la percepción desde una factura de proveedor '
                                       'publicada.'))
        company = self.company_id
        day = self.invoice_date or self.date
        total_pen = self.currency_id._convert(self.amount_total, company.currency_id, company, day)
        series, _sep, number = (self.l10n_latam_document_number or self.ref or '').partition('-')
        received = self.env['l10n_pe.perception.received'].create({
            'company_id': company.id,
            'partner_id': self.commercial_partner_id.id,
            'kind': 'internal',
            'document_kind': 'invoice',
            'l10n_pe_series': series.strip()[:4] or False,
            'l10n_pe_number': number.strip()[:8] or False,
            'date': day,
            'line_ids': [(0, 0, {
                'bill_id': self.id,
                'base_amount': total_pen,
                'amount': company.currency_id.round(total_pen * 0.02),
            })],
        })
        return {
            'type': 'ir.actions.act_window', 'res_model': 'l10n_pe.perception.received',
            'res_id': received.id, 'view_mode': 'form', 'target': 'current',
        }

