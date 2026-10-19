# -*- coding: utf-8 -*-
"""Liquidación de un convenio: la factura a la aseguradora.

Informe SUNAT 029-2013: lo que la aseguradora paga por su asegurado se
factura a nombre de la aseguradora, que es la usuaria; el paciente recibe su
comprobante solo por su parte (copago y lo no cubierto).

Asientos:

* Caja: la venta (boleta o factura del paciente, o el cierre de caja si no
  pidió comprobante) va solo por la parte del paciente, con su IGV, y se
  cobra con sus medios de pago. El método «Convenio» (cuenta de cliente) no
  deja cuenta por cobrar en la caja (``pos.session._accumulate_amounts``):
  la parte cubierta no está en la contabilidad de la caja.
* Liquidación: la factura de cliente a la aseguradora, una línea por
  producto vendido con su parte cubierta e impuestos. Es el ingreso y la
  cuenta por cobrar de la parte cubierta.

Resultado por venta: ingreso del paciente + ingreso de la aseguradora =
ingreso de la venta; IGV del paciente + IGV de la aseguradora = IGV de la
venta (cada línea se reparte en montos que cuadran con sus impuestos); la
cuenta por cobrar del paciente queda en cero (pagó su parte) y la de la
aseguradora es lo cubierto. Una venta se liquida una sola vez."""
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain

from .pharmacy_insurance import local_day_start


class PharmacyInsuranceLiquidation(models.Model):
    _name = 'pharmacy.insurance.liquidation'
    _description = 'Liquidación de convenio'
    _inherit = ['mail.thread']
    _order = 'date_to desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', readonly=True, copy=False, default='/')
    agreement_id = fields.Many2one('pharmacy.insurance.agreement', string='Convenio', required=True,
                                   check_company=True, tracking=True)
    partner_id = fields.Many2one(related='agreement_id.partner_id', string='Aseguradora o empresa')
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    date_from = fields.Date(string='Desde', required=True)
    date_to = fields.Date(string='Hasta', required=True)
    order_ids = fields.One2many('pos.order', 'pharmacy_insurance_liquidation_id',
                                string='Ventas cubiertas')
    order_count = fields.Integer(compute='_compute_amount')
    amount_total = fields.Monetary(string='Total a cobrar', currency_field='currency_id',
                                   compute='_compute_amount', store=True)
    invoice_id = fields.Many2one('account.move', string='Factura', readonly=True, copy=False,
                                 check_company=True)
    invoice_state = fields.Selection(related='invoice_id.state', string='Estado de la factura')
    refund_invoice_ids = fields.Many2many(
        'account.move', 'pharmacy_insurance_liquidation_refund_rel', 'liquidation_id', 'move_id',
        string='Notas de crédito', readonly=True, copy=False, check_company=True,
        help='Devoluciones de ventas que ya se facturaron a la aseguradora en una liquidación '
             'anterior: una nota de crédito por factura de origen.')
    state = fields.Selection([('draft', 'Borrador'), ('invoiced', 'Facturada'),
                              ('cancel', 'Anulada')], string='Estado', default='draft',
                             required=True, tracking=True, copy=False)

    @api.depends('order_ids.pharmacy_insurance_amount')
    def _compute_amount(self):
        for liquidation in self:
            liquidation.order_count = len(liquidation.order_ids)
            liquidation.amount_total = sum(liquidation.order_ids.mapped('pharmacy_insurance_amount'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('pharmacy.insurance.liquidation') or '/'
        return super().create(vals_list)

    def _eligible_orders_domain(self):
        self.ensure_one()
        return Domain([
            ('pharmacy_insurance_agreement_id', '=', self.agreement_id.id),
            ('pharmacy_insurance_liquidation_id', '=', False),
            ('pharmacy_insurance_amount', '!=', 0),
            ('state', 'in', ('paid', 'done')),
            ('date_order', '>=', local_day_start(self.env, self.date_from)),
            ('date_order', '<', local_day_start(self.env, self.date_to + timedelta(days=1))),
            ('company_id', '=', self.company_id.id),
        ])

    def action_load_orders(self):
        for liquidation in self:
            if liquidation.state != 'draft':
                raise UserError(_('Solo se cargan ventas en una liquidación en borrador.'))
            liquidation.order_ids.write({'pharmacy_insurance_liquidation_id': False})
            self.env['pos.order'].search(liquidation._eligible_orders_domain()).write(
                {'pharmacy_insurance_liquidation_id': liquidation.id})
        return True

    def _invoice_line_name(self, line):
        order = line.order_id
        patient = order.partner_id
        parts = [line.product_id.display_name, order.pos_reference or order.name]
        if order.account_move:
            parts.append(_('Comprobante %s', order.account_move.name))
        if patient.vat:
            parts.append(_('DNI %s', patient.vat))
        parts.append(_('Paciente %s', patient.name))
        parts.append(_('Afiliado %s', order.pharmacy_insurance_affiliate_id.number))
        if order.pharmacy_prescription_number:
            parts.append(_('Receta %s', order.pharmacy_prescription_number))
        return ' · '.join(parts)

    def _prepare_invoice_line(self, line, base, tax_amounts, quantity):
        """Línea de la factura (o nota de crédito) a la aseguradora por la
        parte cubierta de una línea vendida, con su base e impuestos exactos
        (montos manuales del motor de impuestos, como en el comprobante del
        paciente)."""
        currency = self.currency_id
        taxes = line.tax_ids_after_fiscal_position
        price_included = any(tax.price_include for tax in taxes)
        total = base + sum(tax_amounts.values())
        price_unit = (total if price_included else base) / quantity
        AccountTax = self.env['account.tax']
        base_line = AccountTax._prepare_base_line_for_taxes_computation(
            None,
            product_id=line.product_id,
            tax_ids=taxes,
            price_unit=price_unit,
            quantity=quantity,
            discount=0.0,
            currency_id=currency,
            rate=1.0,
            manual_total_excluded_currency=base,
            manual_total_excluded=base,
            manual_tax_amounts={
                tax_id: {'base_amount_currency': base, 'tax_amount_currency': amount,
                         'base_amount': base, 'tax_amount': amount}
                for tax_id, amount in tax_amounts.items()
            } if taxes else None,
        )
        return {
            'product_id': line.product_id.id,
            'name': self._invoice_line_name(line),
            'quantity': quantity,
            'product_uom_id': line.product_uom_id.id,
            'price_unit': price_unit,
            'discount': 0.0,
            'tax_ids': [fields.Command.set(taxes.ids)],
            'extra_tax_data': AccountTax._export_base_line_extra_tax_data(base_line),
        }

    def _covered_parts(self):
        """Partes cubiertas a facturar y a abonar a la aseguradora.

        Una devolución cuya venta está en esta misma liquidación se descuenta
        de esa línea (el producto devuelto entero desaparece de la factura).
        Si la venta ya se facturó en una liquidación anterior, la devolución
        va a una nota de crédito de esa factura.

        :return: ``(to_invoice, to_refund)``: lista de ``(línea, base,
            impuestos, cantidad)`` en positivo, y dict factura de origen →
            lista con el mismo formato."""
        self.ensure_one()
        currency = self.currency_id
        lines = self.order_ids.sorted('date_order').lines.filtered('pharmacy_insurance_amount')
        sales = {}
        for line in lines.filtered(lambda l: l.pharmacy_insurance_amount > 0):
            sales[line] = [line.pharmacy_insurance_base,
                           dict(line.pharmacy_insurance_taxes or {}), line.qty]
        to_refund = {}
        for line in lines.filtered(lambda l: l.pharmacy_insurance_amount < 0):
            origin = line.refunded_orderline_id
            taxes = line.pharmacy_insurance_taxes or {}
            if origin in sales:
                part = sales[origin]
                part[0] += line.pharmacy_insurance_base
                for tax_id, amount in taxes.items():
                    part[1][tax_id] = part[1].get(tax_id, 0.0) + amount
                part[2] += line.qty
                continue
            origin_invoice = origin.order_id.pharmacy_insurance_liquidation_id.invoice_id
            if not origin_invoice or origin_invoice.state == 'cancel':
                raise UserError(_(
                    'La devolución %(refund)s es de la venta %(order)s, que aún no se factura a la '
                    'aseguradora: liquide primero el periodo de esa venta o inclúyalo en esta '
                    'liquidación.', refund=line.order_id.name, order=origin.order_id.name))
            to_refund.setdefault(origin_invoice, []).append((
                line, -line.pharmacy_insurance_base,
                {tax_id: -amount for tax_id, amount in taxes.items()}, -line.qty))
        to_invoice = [
            (line, currency.round(base), {k: currency.round(v) for k, v in taxes.items()}, qty)
            for line, (base, taxes, qty) in sales.items()
            if qty > 0 and not currency.is_zero(base + sum(taxes.values()))
        ]
        return to_invoice, to_refund

    def _prepare_invoice_lines(self):
        """Una línea por producto vendido con su parte cubierta (menos lo
        devuelto), con los mismos impuestos de la venta."""
        self.ensure_one()
        return [fields.Command.create(self._prepare_invoice_line(*part))
                for part in self._covered_parts()[0]]

    def action_create_invoice(self):
        for liquidation in self:
            if liquidation.state != 'draft':
                continue
            agreement = liquidation.agreement_id
            if not liquidation.order_ids:
                raise UserError(_('La liquidación no tiene ventas: pulse «Cargar ventas».'))
            if not agreement.journal_id:
                raise UserError(_('Indique el diario de facturación del convenio %s.', agreement.name))
            to_invoice, to_refund = liquidation._covered_parts()
            Move = self.env['account.move'].with_company(liquidation.company_id)
            common = {
                'partner_id': agreement.partner_id.id,
                'journal_id': agreement.journal_id.id,
                'invoice_date': liquidation.date_to,
                'invoice_origin': liquidation.name,
            }
            invoice = Move
            if to_invoice:
                invoice = Move.create({
                    **common,
                    'move_type': 'out_invoice',
                    'ref': _('Liquidación %(name)s · %(agreement)s', name=liquidation.name,
                             agreement=agreement.name),
                    'invoice_line_ids': [fields.Command.create(liquidation._prepare_invoice_line(*part))
                                         for part in to_invoice],
                })
            refunds = Move
            for origin_invoice, parts in to_refund.items():
                refunds |= Move.create({
                    **common,
                    'move_type': 'out_refund',
                    'reversed_entry_id': origin_invoice.id,
                    'ref': _('Devoluciones de %(invoice)s · liquidación %(name)s',
                             invoice=origin_invoice.name, name=liquidation.name),
                    'invoice_line_ids': [fields.Command.create(liquidation._prepare_invoice_line(*part))
                                         for part in parts],
                })
            liquidation.write({'invoice_id': invoice.id, 'refund_invoice_ids': [fields.Command.set(refunds.ids)],
                               'state': 'invoiced'})
        return self.action_open_invoice() if len(self) == 1 and self.invoice_id else True

    def action_cancel(self):
        for liquidation in self:
            moves = liquidation.invoice_id | liquidation.refund_invoice_ids
            posted = moves.filtered(lambda move: move.state == 'posted')
            if posted:
                raise UserError(_(
                    'El comprobante %s ya está validado: anúlelo con una nota de crédito (o una de '
                    'débito, si es una nota de crédito) y luego anule la liquidación.', posted[0].name))
            moves.filtered(lambda move: move.state == 'draft').button_cancel()
            liquidation.order_ids.write({'pharmacy_insurance_liquidation_id': False})
            liquidation.state = 'cancel'
        return True

    def action_open_refunds(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'account.move', 'name': _('Notas de crédito'),
            'domain': [('id', 'in', self.refund_invoice_ids.ids)], 'view_mode': 'list,form',
        }

    def action_open_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'account.move',
            'res_id': self.invoice_id.id, 'view_mode': 'form',
        }
