# -*- coding: utf-8 -*-
"""Caja: el convenio cobra con su método de pago «cuenta de cliente» y la
venta se parte en dos (Informe SUNAT 029-2013):

* la parte del paciente: su boleta o factura (o, sin comprobante, la venta
  del cierre de caja) lleva solo esa parte de cada línea, con su IGV;
* la parte cubierta: no se registra en la caja (ni como venta ni como cuenta
  por cobrar); se factura a la aseguradora en la liquidación.

Cada línea guarda su base e impuestos cubiertos, ya redondeados; la parte
del paciente es el resto. Los dos comprobantes usan esos montos tal cual, así
suman exactamente la venta."""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    pharmacy_insurance_agreement_ids = fields.One2many(
        'pharmacy.insurance.agreement', 'payment_method_id', string='Convenios')
    pharmacy_insurance_agreement_id = fields.Many2one(
        'pharmacy.insurance.agreement', string='Convenio',
        compute='_compute_pharmacy_insurance_agreement_id')
    pharmacy_is_insurance = fields.Boolean(
        string='Es de un convenio', compute='_compute_pharmacy_insurance_agreement_id')

    @api.depends('pharmacy_insurance_agreement_ids')
    def _compute_pharmacy_insurance_agreement_id(self):
        for method in self:
            method.pharmacy_insurance_agreement_id = method.pharmacy_insurance_agreement_ids[:1]
            method.pharmacy_is_insurance = bool(method.pharmacy_insurance_agreement_ids)

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + ['pharmacy_is_insurance']


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    pharmacy_insurance_base = fields.Monetary(
        string='Base cubierta', currency_field='currency_id', readonly=True, copy=False,
        help='Parte de la base imponible de la línea que se factura a la aseguradora.')
    pharmacy_insurance_taxes = fields.Json(
        string='Impuestos cubiertos', readonly=True, copy=False,
        help='Impuesto de la parte cubierta, por id de impuesto.')
    pharmacy_insurance_amount = fields.Monetary(
        string='Cubierto por el convenio', currency_field='currency_id', readonly=True, copy=False)

    def _pharmacy_insurance_line_values(self):
        self.ensure_one()
        return {
            'product': self.product_id,
            'price_unit': self.price_unit,
            'qty': self.qty,
            'discount': self.discount,
            'taxes': self.tax_ids_after_fiscal_position,
        }

    def _pharmacy_patient_amounts(self):
        """Base e impuestos de la parte del paciente: la línea menos lo
        cubierto. None si la línea no tiene convenio."""
        self.ensure_one()
        agreement = self.order_id.pharmacy_insurance_agreement_id
        if not agreement or not self.pharmacy_insurance_amount:
            return None
        currency = self.order_id.currency_id
        full = agreement._line_amounts(self._pharmacy_insurance_line_values())
        covered_taxes = self.pharmacy_insurance_taxes or {}
        return {
            'full': full,
            'base': currency.round(full['total_excluded'] - self.pharmacy_insurance_base),
            'taxes': {str(tax_id): currency.round(amount - covered_taxes.get(str(tax_id), 0.0))
                      for tax_id, amount in full['taxes']},
        }

    def _pharmacy_is_fully_covered(self):
        self.ensure_one()
        patient = self._pharmacy_patient_amounts()
        return bool(patient) and self.order_id.currency_id.is_zero(
            patient['base'] + sum(patient['taxes'].values()))

    def _prepare_base_line_for_taxes_computation(self):
        """En el comprobante del paciente y en la venta del cierre de caja, la
        línea va solo por la parte del paciente, con su base e impuestos
        exactos (montos manuales del motor de impuestos)."""
        base_line = super()._prepare_base_line_for_taxes_computation()
        context = self.env.context
        if not (context.get('invoicing') or context.get('linked_to_pos')):
            return base_line
        patient = self._pharmacy_patient_amounts()
        if not patient:
            return base_line
        full = patient['full']
        price_included = any(tax.price_include for tax in self.tax_ids_after_fiscal_position)
        if price_included:
            whole = full['total_included']
            part = patient['base'] + sum(patient['taxes'].values())
        else:
            whole, part = full['total_excluded'], patient['base']
        base_line['price_unit'] = self.price_unit * (part / whole) if whole else 0.0
        rate = base_line.get('rate') or 1.0
        company_currency = self.order_id.company_id.currency_id
        base_line['manual_total_excluded_currency'] = patient['base']
        base_line['manual_total_excluded'] = company_currency.round(patient['base'] / rate)
        base_line['manual_tax_amounts'] = {
            tax_id: {
                'base_amount_currency': patient['base'],
                'tax_amount_currency': amount,
                'base_amount': company_currency.round(patient['base'] / rate),
                'tax_amount': company_currency.round(amount / rate),
            } for tax_id, amount in patient['taxes'].items()
        }
        return base_line


class PosOrder(models.Model):
    _inherit = 'pos.order'

    pharmacy_insurance_agreement_id = fields.Many2one(
        'pharmacy.insurance.agreement', string='Convenio', readonly=True, copy=False,
        index='btree_not_null', check_company=True)
    pharmacy_insurance_affiliate_id = fields.Many2one(
        'pharmacy.insurance.affiliate', string='Afiliado', readonly=True, copy=False,
        index='btree_not_null')
    pharmacy_insurance_amount = fields.Monetary(
        string='Cubierto por el convenio', currency_field='currency_id', readonly=True, copy=False)
    pharmacy_insurance_liquidation_id = fields.Many2one(
        'pharmacy.insurance.liquidation', string='Liquidación', readonly=True, copy=False,
        index='btree_not_null')

    def _process_saved_order(self, draft):
        # Antes que el comprobante del paciente: este se arma con lo cubierto.
        if not draft:
            self._pharmacy_insurance_register()
        return super()._process_saved_order(draft)

    def _pharmacy_insurance_lines(self):
        self.ensure_one()
        return [line._pharmacy_insurance_line_values() for line in self.lines]

    def _pharmacy_insurance_register(self):
        """Reparte lo cobrado con el convenio entre las líneas y lo guarda.
        Falla si supera la cobertura (la caja la calcula igual, así que solo
        pasa si se alteró el monto)."""
        for order in self:
            payments = order.payment_ids.filtered(
                lambda p: p.payment_method_id.pharmacy_insurance_agreement_id)
            if not payments:
                continue
            agreements = payments.payment_method_id.pharmacy_insurance_agreement_id
            if len(agreements) > 1:
                raise ValidationError(_('Una venta solo se cobra con un convenio.'))
            if order.is_refund or order.amount_total < 0:
                raise ValidationError(_('Las devoluciones de ventas con convenio se hacen con una nota '
                                        'de crédito a la aseguradora, no en la caja.'))
            amount = sum(payments.mapped('amount'))
            args = (order.partner_id, order._pharmacy_insurance_lines(),
                    fields.Date.context_today(self, order.date_order),
                    bool(order._pharmacy_insurance_has_prescription()))
            coverage = agreements._compute_coverage(*args, exclude_order=order)
            if coverage['error']:
                raise ValidationError(coverage['error'])
            if order.currency_id.compare_amounts(amount, coverage['amount']) < 0:
                # El cajero cobró menos con el convenio: se reparte lo cobrado.
                coverage = agreements._compute_coverage(*args, exclude_order=order, max_amount=amount)
            if order.currency_id.compare_amounts(amount, coverage['amount']) != 0:
                raise ValidationError(_(
                    'La venta %(order)s cobra %(amount)s con el convenio %(agreement)s, que '
                    'cubre %(covered)s.', order=order.name, amount=amount,
                    agreement=agreements.name, covered=coverage['amount']))
            for line, allocation in zip(order.lines, coverage['allocations']):
                line.write({'pharmacy_insurance_base': allocation['base'],
                            'pharmacy_insurance_taxes': allocation['taxes'],
                            'pharmacy_insurance_amount': allocation['amount']})
            order.write({
                'pharmacy_insurance_agreement_id': agreements.id,
                'pharmacy_insurance_affiliate_id': coverage['affiliate'].id,
                'pharmacy_insurance_amount': amount,
            })

    def _pharmacy_insurance_has_prescription(self):
        self.ensure_one()
        return self.pharmacy_prescription_number or self.pharmacy_prescription_id

    @api.model
    def _get_invoice_lines_values(self, line_values, pos_line, move_type):
        """Los montos manuales del paciente siguen valiendo si otro módulo
        cambia el precio y la cantidad de la línea (presentaciones)."""
        values = super()._get_invoice_lines_values(line_values, pos_line, move_type)
        extra = values.get('extra_tax_data')
        if extra and extra.get('manual_tax_amounts') and 'price_unit' in values:
            extra.update({'price_unit': values['price_unit'], 'quantity': values['quantity'],
                          'discount': values.get('discount', 0.0)})
        return values

    def _prepare_invoice_lines(self, move_type):
        """El comprobante del paciente no lleva las líneas que el convenio
        cubre por completo (irían a precio cero, como si fueran gratuitas)."""
        lines = super()._prepare_invoice_lines(move_type)
        covered_products = {line.product_id.id for line in self.lines
                            if line._pharmacy_is_fully_covered()}
        if not covered_products:
            return lines
        return [command for command in lines
                if not (command[2].get('product_id') in covered_products
                        and not command[2].get('price_unit'))]


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _accumulate_amounts(self, data):
        """La parte cubierta no es cuenta por cobrar de la caja: su venta y su
        cobro van en la factura a la aseguradora. Como la venta del cierre ya
        va solo por la parte del paciente, el asiento cuadra."""
        data = super()._accumulate_amounts(data)
        for key in ('combine_receivables_pay_later', 'split_receivables_pay_later'):
            receivables = data.get(key)
            if not receivables:
                continue
            for record in list(receivables):
                method = record if record._name == 'pos.payment.method' else record.payment_method_id
                if method.pharmacy_insurance_agreement_id:
                    del receivables[record]
        return data
