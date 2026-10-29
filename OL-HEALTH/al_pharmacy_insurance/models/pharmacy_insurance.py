# -*- coding: utf-8 -*-
"""Convenios con aseguradoras (EPS) y empresas: cobertura, copago, topes y
afiliados. La caja cobra la parte del convenio con su método de pago y la
liquidación mensual la factura a la aseguradora (Informe SUNAT 029-2013)."""
from datetime import datetime, time

import pytz
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain


def local_day_start(env, day):
    """Inicio del día ``day`` en la hora local (usuario, compañía o Lima),
    como fecha y hora UTC sin zona: así se guarda ``date_order``."""
    tz = pytz.timezone(env.user.tz or env.company.partner_id.tz or 'America/Lima')
    start = tz.localize(datetime.combine(day, time.min))
    return start.astimezone(pytz.UTC).replace(tzinfo=None)


class PharmacyInsuranceAgreement(models.Model):
    _name = 'pharmacy.insurance.agreement'
    _description = 'Convenio con aseguradora o empresa'
    _inherit = ['mail.thread']
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(string='Convenio', required=True, tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string='Aseguradora o empresa', required=True, check_company=True,
        tracking=True, help='A quien se liquida la parte cubierta.')
    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    active = fields.Boolean(default=True)
    date_start = fields.Date(string='Vigente desde', required=True, default=fields.Date.today,
                             tracking=True)
    date_end = fields.Date(string='Vigente hasta', tracking=True)
    coverage_percent = fields.Float(
        string='Cobertura (%)', default=80.0, tracking=True,
        help='Porcentaje del precio que paga el convenio, salvo que una línea de cobertura '
             'indique otro para el producto o su categoría.')
    line_ids = fields.One2many('pharmacy.insurance.agreement.line', 'agreement_id',
                               string='Cobertura por producto o categoría')
    copay_amount = fields.Monetary(
        string='Copago por venta', currency_field='currency_id', tracking=True,
        help='Monto fijo que paga el paciente en cada venta, además de la parte no cubierta.')
    max_per_sale = fields.Monetary(
        string='Tope por venta', currency_field='currency_id', tracking=True,
        help='Lo máximo que cubre el convenio en una venta (0 = sin tope).')
    max_per_month = fields.Monetary(
        string='Tope mensual por afiliado', currency_field='currency_id', tracking=True,
        help='Lo máximo que cubre el convenio a un afiliado en el mes (0 = sin tope).')
    billing_mode = fields.Selection([
        ('direct', 'Convenio: factura a la aseguradora'),
        ('reimbursement', 'Reembolso: el paciente paga el total'),
    ], string='Modalidad', required=True, default='direct', tracking=True,
        help='Convenio: el paciente recibe su comprobante solo por su parte y la parte cubierta '
             'se factura a la aseguradora (Informe SUNAT 029-2013). Reembolso: el paciente paga '
             'el total con su boleta y pide el reembolso a la aseguradora; la caja no aplica el '
             'convenio.')
    require_prescription = fields.Boolean(
        string='Exige receta', tracking=True,
        help='El convenio solo cubre ventas con la receta registrada en la caja.')
    payment_method_id = fields.Many2one(
        'pos.payment.method', string='Método de pago del TPV', check_company=True, copy=False,
        readonly=True, help='Cuenta de cliente con la que la caja cobra la parte del convenio.')
    journal_id = fields.Many2one(
        'account.journal', string='Diario de facturación', check_company=True,
        domain="[('type', '=', 'sale')]",
        default=lambda self: self.env['account.journal'].search([
            ('type', '=', 'sale'), ('company_id', '=', self.env.company.id)], limit=1),
        help='Diario de ventas (serie de facturas) de la factura a la aseguradora en la liquidación.')
    affiliate_ids = fields.One2many('pharmacy.insurance.affiliate', 'agreement_id',
                                    string='Afiliados')
    affiliate_count = fields.Integer(compute='_compute_counts')
    liquidation_count = fields.Integer(compute='_compute_counts')

    _payment_method_unique = models.Constraint(
        'UNIQUE(payment_method_id)', 'Cada convenio tiene su propio método de pago del TPV.')

    @api.depends('affiliate_ids')
    def _compute_counts(self):
        liquidations = dict(self.env['pharmacy.insurance.liquidation']._read_group(
            [('agreement_id', 'in', self.ids)], ['agreement_id'], ['__count']))
        for agreement in self:
            agreement.affiliate_count = len(agreement.affiliate_ids)
            agreement.liquidation_count = liquidations.get(agreement, 0)

    @api.constrains('coverage_percent', 'copay_amount', 'max_per_sale', 'max_per_month')
    def _check_amounts(self):
        for agreement in self:
            if not 0 <= agreement.coverage_percent <= 100:
                raise ValidationError(_('La cobertura debe estar entre 0 y 100 %.'))
            if min(agreement.copay_amount, agreement.max_per_sale, agreement.max_per_month) < 0:
                raise ValidationError(_('El copago y los topes no pueden ser negativos.'))

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for agreement in self:
            if agreement.date_end and agreement.date_end < agreement.date_start:
                raise ValidationError(_('La vigencia del convenio termina antes de empezar.'))

    # ------------------------------------------------------------------
    # Método de pago del TPV
    # ------------------------------------------------------------------
    def action_create_pos_payment_method(self):
        """Crea el método «cuenta de cliente» (sin diario) del convenio. Solo
        marca en la caja la parte cubierta: no queda como venta ni como cuenta
        por cobrar de la caja, porque se factura a la aseguradora en la
        liquidación (ver ``pos.session._accumulate_amounts``)."""
        for agreement in self.filtered(lambda a: not a.payment_method_id):
            if agreement.billing_mode == 'reimbursement':
                raise UserError(_('Un convenio por reembolso no se cobra en la caja.'))
            receivable = agreement.company_id.account_default_pos_receivable_account_id
            if not receivable:
                raise UserError(_('La compañía no tiene cuenta por cobrar del punto de venta.'))
            agreement.payment_method_id = self.env['pos.payment.method'].create({
                'name': agreement.name,
                'company_id': agreement.company_id.id,
                'journal_id': False,
                'split_transactions': False,
                'receivable_account_id': receivable.id,
            })
        return True

    # ------------------------------------------------------------------
    # Cobertura
    # ------------------------------------------------------------------
    def _is_valid_on(self, date):
        self.ensure_one()
        return self.active and self.date_start <= date and (not self.date_end or date <= self.date_end)

    def _get_affiliate(self, partner, date):
        self.ensure_one()
        return self.affiliate_ids.filtered(lambda a: a.partner_id == partner and a._is_valid_on(date))[:1]

    def _get_line_percent(self, product):
        """Cobertura del producto: la línea del producto, luego la de su
        categoría (la más cercana) y si no, la del convenio."""
        self.ensure_one()
        by_product = self.line_ids.filtered(lambda l: l.product_id == product)
        if by_product:
            return by_product[0].coverage_percent
        category = product.categ_id
        while category:
            by_category = self.line_ids.filtered(
                lambda l, category=category: not l.product_id and l.categ_id == category)
            if by_category:
                return by_category[0].coverage_percent
            category = category.parent_id
        return self.coverage_percent

    def _month_used(self, affiliate, date, exclude_order=None):
        self.ensure_one()
        month_start = date.replace(day=1)
        domain = Domain([
            ('pharmacy_insurance_affiliate_id', '=', affiliate.id),
            ('state', 'in', ('paid', 'done')),
            ('date_order', '>=', local_day_start(self.env, month_start)),
            ('date_order', '<', local_day_start(self.env, month_start + relativedelta(months=1))),
        ])
        if exclude_order:
            domain &= Domain('id', '!=', exclude_order.id)
        groups = self.env['pos.order']._read_group(domain, [], ['pharmacy_insurance_amount:sum'])
        return groups[0][0] or 0.0

    def _compute_coverage(self, partner, lines, date, has_prescription, exclude_order=None,
                          max_amount=None):
        """Parte que cubre el convenio en una venta, repartida por línea.

        La venta se factura en dos comprobantes: la parte del paciente (su
        boleta o factura) y la parte cubierta (la factura a la aseguradora en
        la liquidación). Cada línea se parte en base e impuestos cubiertos ya
        redondeados; el paciente lleva el resto. Los dos comprobantes usan
        esos montos tal cual (impuestos manuales del motor de impuestos), así
        el ingreso, el IGV y el total de los dos suman la venta.

        :param lines: lista de dicts ``product``, ``price_unit``, ``qty``,
            ``discount`` y ``taxes`` (impuestos ya con la posición fiscal).
        :param max_amount: tope adicional (lo cobrado con el convenio en la
            caja, al guardar la venta).
        :return: dict con ``amount`` (cubierto con impuestos), ``affiliate``,
            ``error`` (motivo si no cubre) y ``allocations``: por línea,
            ``base`` (cubierto sin impuestos), ``taxes`` (impuesto cubierto por
            id de impuesto) y ``amount`` (cubierto con impuestos)."""
        self.ensure_one()
        currency = self.currency_id
        result = {'amount': 0.0, 'affiliate': self.env['pharmacy.insurance.affiliate'],
                  'error': False,
                  'allocations': [{'base': 0.0, 'taxes': {}, 'amount': 0.0} for _line in lines]}
        if self.billing_mode == 'reimbursement':
            result['error'] = _(
                'El convenio %s es por reembolso: el paciente paga el total con su boleta y pide '
                'el reembolso a la aseguradora.', self.name)
            return result
        if not self._is_valid_on(date):
            result['error'] = _('El convenio %s no está vigente.', self.name)
            return result
        affiliate = self._get_affiliate(partner, date)
        if not affiliate:
            result['error'] = _('%(partner)s no es afiliado vigente del convenio %(agreement)s.',
                                partner=partner.display_name, agreement=self.name)
            return result
        result['affiliate'] = affiliate
        if self.require_prescription and not has_prescription:
            result['error'] = _('El convenio %s exige la receta: regístrela antes de cobrar.', self.name)
            return result

        # 1. Lo que cubre cada línea según su porcentaje.
        details = []
        for line in lines:
            full = self._line_amounts(line)
            target = full['total_included'] * self._get_line_percent(line['product']) / 100.0 \
                if full['total_included'] > 0 else 0.0
            details.append({'full': full, 'target': target})
        # 2. Copago y topes sobre el total; lo que queda se reparte en proporción.
        covered = sum(d['target'] for d in details)
        wanted = max(0.0, covered - self.copay_amount)
        if self.max_per_sale:
            wanted = min(wanted, self.max_per_sale)
        if self.max_per_month:
            remaining = self.max_per_month - self._month_used(affiliate, date, exclude_order)
            wanted = min(wanted, max(0.0, remaining))
        if max_amount is not None:
            wanted = min(wanted, max_amount)
        wanted = currency.round(wanted)
        if currency.is_zero(wanted) or not covered:
            result['error'] = _('El convenio %s no cubre esta venta (tope alcanzado o sin cobertura).',
                                self.name)
            return result
        # 3. Cada línea se parte en base e impuestos cubiertos, redondeados.
        allocations = result['allocations']
        for index, detail in enumerate(details):
            if detail['target']:
                ratio = detail['target'] * wanted / covered / detail['full']['total_included']
                allocations[index] = self._allocate_line(detail['full'], ratio)
        # 4. La diferencia de redondeo va a la base de la línea más grande.
        diff = currency.round(wanted - sum(a['amount'] for a in allocations))
        if not currency.is_zero(diff):
            index = max(range(len(details)), key=lambda i: allocations[i]['amount'])
            allocation = allocations[index]
            base = currency.round(min(max(allocation['base'] + diff, 0.0),
                                      details[index]['full']['total_excluded']))
            allocation['amount'] = currency.round(allocation['amount'] + base - allocation['base'])
            allocation['base'] = base
        result['amount'] = currency.round(sum(a['amount'] for a in allocations))
        return result

    def _line_amounts(self, line):
        """Base, impuestos y total de la línea, cada uno redondeado."""
        currency = self.currency_id
        price_total = line['price_unit'] * line['qty'] * (1 - (line['discount'] or 0.0) / 100.0)
        if not line['taxes']:
            amount = currency.round(price_total)
            return {'total_excluded': amount, 'total_included': amount, 'taxes': []}
        computed = line['taxes'].compute_all(price_total, currency, 1, product=line['product'])
        return {
            'total_excluded': computed['total_excluded'],
            'total_included': computed['total_included'],
            'taxes': [(tax['id'], currency.round(tax['amount'])) for tax in computed['taxes']],
        }

    def _allocate_line(self, full, ratio):
        """Base e impuestos cubiertos de una línea: la proporción ``ratio`` de
        cada uno, redondeada. El paciente lleva el resto, así los dos
        comprobantes suman exactamente la línea."""
        currency = self.currency_id
        base = currency.round(full['total_excluded'] * ratio)
        taxes = {str(tax_id): currency.round(amount * ratio) for tax_id, amount in full['taxes']}
        return {'base': base, 'taxes': taxes, 'amount': currency.round(base + sum(taxes.values()))}

    @api.model
    def _pos_lines_from_ui(self, lines):
        products = self.env['product.product'].browse([line['product_id'] for line in lines])
        return [{
            'product': product,
            'price_unit': line['price_unit'],
            'qty': line['qty'],
            'discount': line.get('discount') or 0.0,
            'taxes': self.env['account.tax'].browse(line.get('tax_ids') or []),
        } for product, line in zip(products, lines)]

    @api.model
    def get_pos_coverage(self, payment_method_id, partner_id, lines, has_prescription):
        """Lo que cubre el convenio del método de pago en la venta de la caja.

        :param lines: lista de ``{'product_id', 'price_unit', 'qty', 'discount',
            'tax_ids'}`` de las líneas del pedido.
        :return: ``{'amount': float}`` o ``{'error': str}``."""
        method = self.env['pos.payment.method'].browse(payment_method_id).exists()
        agreement = method.pharmacy_insurance_agreement_id
        if not agreement:
            return {'error': _('El método de pago no es de un convenio.')}
        if not partner_id:
            return {'error': _('Elija al paciente afiliado antes de cobrar con el convenio.')}
        partner = self.env['res.partner'].browse(partner_id)
        result = agreement._compute_coverage(
            partner, self._pos_lines_from_ui(lines), fields.Date.context_today(self), has_prescription)
        if result['error']:
            return {'error': result['error']}
        return {'amount': result['amount'], 'agreement': agreement.name,
                'affiliate': result['affiliate'].number}

    def action_open_affiliates(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Afiliados'),
            'res_model': 'pharmacy.insurance.affiliate', 'view_mode': 'list,form',
            'domain': [('agreement_id', '=', self.id)],
            'context': {'default_agreement_id': self.id},
        }

    def action_open_liquidations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Liquidaciones'),
            'res_model': 'pharmacy.insurance.liquidation', 'view_mode': 'list,form',
            'domain': [('agreement_id', '=', self.id)],
            'context': {'default_agreement_id': self.id},
        }


class PharmacyInsuranceAgreementLine(models.Model):
    _name = 'pharmacy.insurance.agreement.line'
    _description = 'Cobertura del convenio por producto o categoría'
    _order = 'sequence, id'

    agreement_id = fields.Many2one('pharmacy.insurance.agreement', required=True, ondelete='cascade',
                                   index=True)
    company_id = fields.Many2one(related='agreement_id.company_id', store=True)
    sequence = fields.Integer(default=10)
    categ_id = fields.Many2one('product.category', string='Categoría')
    product_id = fields.Many2one('product.product', string='Producto', check_company=True)
    coverage_percent = fields.Float(string='Cobertura (%)', required=True)

    @api.constrains('categ_id', 'product_id', 'coverage_percent')
    def _check_line(self):
        for line in self:
            if not (line.categ_id or line.product_id):
                raise ValidationError(_('Indique la categoría o el producto de la cobertura.'))
            if not 0 <= line.coverage_percent <= 100:
                raise ValidationError(_('La cobertura debe estar entre 0 y 100 %.'))


class PharmacyInsuranceAffiliate(models.Model):
    _name = 'pharmacy.insurance.affiliate'
    _description = 'Afiliado a un convenio'
    _order = 'partner_id, agreement_id'
    _rec_names_search = ('number', 'partner_id')
    _check_company_auto = True

    agreement_id = fields.Many2one('pharmacy.insurance.agreement', string='Convenio', required=True,
                                   ondelete='cascade', index=True, check_company=True)
    company_id = fields.Many2one(related='agreement_id.company_id', store=True)
    partner_id = fields.Many2one('res.partner', string='Paciente', required=True, index=True,
                                 check_company=True)
    number = fields.Char(string='N.º de afiliado', required=True)
    date_start = fields.Date(string='Afiliado desde', required=True, default=fields.Date.today)
    date_end = fields.Date(string='Afiliado hasta')
    active = fields.Boolean(default=True)

    _number_unique = models.Constraint(
        'UNIQUE(agreement_id, number)', 'El número de afiliado ya existe en el convenio.')

    @api.depends('number', 'partner_id', 'agreement_id')
    def _compute_display_name(self):
        for affiliate in self:
            affiliate.display_name = f'{affiliate.partner_id.name} · {affiliate.agreement_id.name} ({affiliate.number})'

    def _is_valid_on(self, date):
        self.ensure_one()
        return self.active and self.date_start <= date and (not self.date_end or date <= self.date_end)
