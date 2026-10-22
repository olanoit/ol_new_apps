from dateutil.relativedelta import relativedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError

COMMISSION_STATES = [
    ('draft', 'Borrador'),
    ('confirmed', 'Confirmada'),
    ('billed', 'Facturada'),
    ('cancel', 'Anulada'),
]


class L10nPeCollectionCommissionPlan(models.Model):
    """Plan de comisión: porcentaje de lo recuperado según los días de atraso
    que tenía el documento cuando se cobró. Lo cobrado antes de vencer no
    comisiona salvo que un tramo lo cubra."""
    _name = 'l10n_pe.collection.commission.plan'
    _description = 'Plan de comisión de cobranza'
    _order = 'name'

    name = fields.Char(string='Plan', required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company)
    line_ids = fields.One2many('l10n_pe.collection.commission.plan.line', 'plan_id', string='Escala', copy=True)
    note = fields.Text(string='Notas')

    def _rate_for_days(self, days):
        """Porcentaje del tramo que cubre ``days`` días de atraso (0 si ninguno)."""
        self.ensure_one()
        for line in self.line_ids.sorted('days_from', reverse=True):
            if days >= line.days_from and (not line.days_to or days <= line.days_to):
                return line.rate
        return 0.0


class L10nPeCollectionCommissionPlanLine(models.Model):
    _name = 'l10n_pe.collection.commission.plan.line'
    _description = 'Tramo del plan de comisión'
    _order = 'days_from'

    plan_id = fields.Many2one('l10n_pe.collection.commission.plan', string='Plan', required=True,
                              ondelete='cascade', index=True)
    days_from = fields.Integer(string='Desde (días de atraso)', required=True)
    days_to = fields.Integer(string='Hasta (días de atraso)', help='Vacío o cero en el último tramo: sin límite.')
    rate = fields.Float(string='Comisión (%)', required=True, digits=(5, 2))

    @api.constrains('days_from', 'days_to', 'rate')
    def _check_values(self):
        for line in self:
            if line.days_to and line.days_to < line.days_from:
                raise ValidationError(_('Un tramo de la escala termina antes de empezar.'))
            if not 0 <= line.rate <= 100:
                raise ValidationError(_('La comisión va de 0 a 100 %.'))
        for plan in self.plan_id:
            ranges = sorted((l.days_from, l.days_to or 10 ** 6) for l in plan.line_ids)
            for (_from_a, to_a), (from_b, _to_b) in zip(ranges, ranges[1:]):
                if from_b <= to_a:
                    raise ValidationError(_('Los tramos del plan %s se superponen.', plan.name))


class L10nPeCollectionCommission(models.Model):
    """Liquidación de comisiones de un gestor o de una agencia por un periodo.

    Base: lo recuperado, es decir, cada conciliación de un documento por cobrar
    con un cobro de banco o caja cuya fecha cae en el periodo. Al gestor se le
    atribuye lo cobrado de sus clientes que no estaban en una agencia ese día; a
    la agencia, lo cobrado de los clientes que tenía asignados ese día. Un cobro
    comisiona una sola vez, y si se desconcilia después de liquidado (cheque
    rebotado, pago revertido) la siguiente liquidación lo descuenta.
    """
    _name = 'l10n_pe.collection.commission'
    _description = 'Liquidación de comisiones de cobranza'
    _inherit = ['mail.thread']
    _order = 'date_from desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', readonly=True, copy=False, default='/')
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    beneficiary = fields.Selection([('user', 'Gestor'), ('agency', 'Agencia externa')], string='Para',
                                   required=True, default='user', tracking=True)
    user_id = fields.Many2one('res.users', string='Gestor', tracking=True)
    agency_id = fields.Many2one('l10n_pe.collection.agency', string='Agencia', tracking=True, check_company=True)
    plan_id = fields.Many2one('l10n_pe.collection.commission.plan', string='Plan de comisión', required=True,
                              compute='_compute_plan_id', store=True, readonly=False, precompute=True,
                              check_company=True)
    date_from = fields.Date(string='Desde', required=True,
                            default=lambda self: fields.Date.context_today(self).replace(day=1)
                            - relativedelta(months=1))
    date_to = fields.Date(string='Hasta', required=True,
                          default=lambda self: fields.Date.context_today(self).replace(day=1)
                          - relativedelta(days=1))
    state = fields.Selection(COMMISSION_STATES, string='Estado', default='draft', required=True, readonly=True,
                             tracking=True, copy=False)
    line_ids = fields.One2many('l10n_pe.collection.commission.line', 'commission_id', string='Cobros', copy=False)
    amount_recovered = fields.Monetary(string='Recuperado', compute='_compute_amounts', store=True)
    amount_commission = fields.Monetary(string='Comisión', compute='_compute_amounts', store=True, tracking=True)
    invoice_id = fields.Many2one('account.move', string='Factura de la agencia', readonly=True, copy=False)
    note = fields.Text(string='Notas')

    @api.constrains('date_from', 'date_to', 'beneficiary', 'user_id', 'agency_id')
    def _check_values(self):
        for commission in self:
            if commission.date_to < commission.date_from:
                raise ValidationError(_('La liquidación termina antes de empezar.'))
            if commission.beneficiary == 'user' and not commission.user_id:
                raise ValidationError(_('Indique el gestor.'))
            if commission.beneficiary == 'agency' and not commission.agency_id:
                raise ValidationError(_('Indique la agencia.'))

    @api.depends('beneficiary', 'agency_id', 'company_id')
    def _compute_plan_id(self):
        for commission in self:
            if commission.beneficiary == 'agency' and commission.agency_id.plan_id:
                commission.plan_id = commission.agency_id.plan_id
            elif not commission.plan_id:
                commission.plan_id = commission.company_id.root_id.l10n_pe_collection_commission_plan_id \
                    or self.env.ref('al_l10n_pe_collection.commission_plan_default', raise_if_not_found=False)

    @api.depends('line_ids.amount', 'line_ids.commission_amount')
    def _compute_amounts(self):
        for commission in self:
            commission.amount_recovered = sum(commission.line_ids.mapped('amount'))
            commission.amount_commission = sum(commission.line_ids.mapped('commission_amount'))

    @api.depends('name', 'user_id', 'agency_id', 'beneficiary')
    def _compute_display_name(self):
        for commission in self:
            who = commission.agency_id.name if commission.beneficiary == 'agency' else commission.user_id.name
            commission.display_name = '%s · %s' % (commission.name or '/', who or '')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('l10n_pe.collection.commission') or '/'
        return super().create(vals_list)

    def unlink(self):
        if self.filtered(lambda c: c.state not in ('draft', 'cancel')):
            raise UserError(_('Solo se eliminan liquidaciones en borrador o anuladas.'))
        return super().unlink()

    # ------------------------------------------------------------------
    # Cálculo
    # ------------------------------------------------------------------

    def _used_partial_ids(self):
        """Cobros que ya comisionaron en otra liquidación vigente."""
        lines = self.env['l10n_pe.collection.commission.line'].search([
            ('commission_id', '!=', self.id), ('commission_id.state', '!=', 'cancel'),
            ('partial_id', '!=', False), ('company_id', 'child_of', self.company_id.root_id.id)])
        return set(lines.partial_id.ids)

    def _candidate_partials(self):
        """Conciliaciones de documentos por cobrar con cobros de banco o caja en el periodo."""
        company = self.company_id
        return self.env['account.partial.reconcile'].search([
            ('company_id', 'child_of', company.root_id.id),
            ('max_date', '>=', self.date_from), ('max_date', '<=', self.date_to),
            ('debit_move_id.parent_state', '=', 'posted'),
            ('debit_move_id.account_id.account_type', '=', 'asset_receivable'),
            ('debit_move_id.account_id', 'not in', company._l10n_pe_collection_excluded_accounts().ids),
            ('debit_move_id.journal_id.type', 'not in', ('bank', 'cash')),
            ('debit_move_id.partner_id', '!=', False),
            ('credit_move_id.parent_state', '=', 'posted'),
            ('credit_move_id.journal_id.type', 'in', ('bank', 'cash')),
        ], order='max_date, id')

    def _belongs(self, partial, assignments):
        """¿El cobro es de este gestor o de esta agencia?"""
        line = partial.debit_move_id
        partner = line.partner_id.commercial_partner_id
        day = partial.max_date
        covering = assignments.filtered(lambda a: a.partner_id == partner and a._covers(day))
        if self.beneficiary == 'agency':
            return bool(covering.filtered(lambda a: a.agency_id == self.agency_id))
        if covering:
            return False
        responsible = partner.with_company(line.company_id).followup_responsible_id \
            or partner.with_company(line.company_id.root_id).followup_responsible_id
        return responsible == self.user_id

    def action_compute(self):
        for commission in self:
            if commission.state != 'draft':
                raise UserError(_('Solo se recalcula una liquidación en borrador.'))
            used = commission._used_partial_ids()
            partials = commission._candidate_partials().filtered(lambda p: p.id not in used)
            assignments = self.env['l10n_pe.collection.agency.assignment'].search([
                ('partner_id', 'in', partials.debit_move_id.partner_id.commercial_partner_id.ids),
                ('date_from', '<=', commission.date_to),
                '|', ('date_to', '=', False), ('date_to', '>=', commission.date_from)])
            commands = [Command.clear()]
            for partial in partials.filtered(lambda p: commission._belongs(p, assignments)):
                line = partial.debit_move_id
                days = (partial.max_date - (line.date_maturity or line.date)).days
                commands.append(Command.create({
                    'line_type': 'recovery',
                    'partial_id': partial.id,
                    'move_id': line.move_id.id,
                    'payment_move_id': partial.credit_move_id.move_id.id,
                    'partner_id': line.partner_id.commercial_partner_id.id,
                    'date': partial.max_date,
                    'date_maturity': line.date_maturity or line.date,
                    'days_overdue': days,
                    'amount': partial.amount,
                    'rate': commission.plan_id._rate_for_days(days),
                }))
            for reversed_line in commission._reversed_lines():
                commands.append(Command.create({
                    'line_type': 'clawback',
                    'origin_line_id': reversed_line.id,
                    'move_id': reversed_line.move_id.id,
                    'payment_move_id': reversed_line.payment_move_id.id,
                    'partner_id': reversed_line.partner_id.id,
                    'date': reversed_line.date,
                    'date_maturity': reversed_line.date_maturity,
                    'days_overdue': reversed_line.days_overdue,
                    'amount': -reversed_line.amount,
                    'rate': reversed_line.rate,
                }))
            commission.line_ids = commands
        return True

    def _reversed_lines(self):
        """Cobros ya liquidados a este beneficiario que se desconciliaron después
        y que ninguna liquidación vigente ha descontado."""
        domain = [
            ('commission_id', '!=', self.id), ('commission_id.state', 'in', ('confirmed', 'billed')),
            ('line_type', '=', 'recovery'), ('partial_id', '=', False),
            ('company_id', 'child_of', self.company_id.root_id.id),
        ]
        if self.beneficiary == 'agency':
            domain.append(('commission_id.agency_id', '=', self.agency_id.id))
        else:
            domain += [('commission_id.beneficiary', '=', 'user'), ('commission_id.user_id', '=', self.user_id.id)]
        lines = self.env['l10n_pe.collection.commission.line'].search(domain)
        clawed = self.env['l10n_pe.collection.commission.line'].search([
            ('origin_line_id', 'in', lines.ids), ('commission_id', '!=', self.id),
            ('commission_id.state', '!=', 'cancel')])
        return lines - clawed.origin_line_id

    # ------------------------------------------------------------------
    # Estados
    # ------------------------------------------------------------------

    def action_confirm(self):
        for commission in self:
            if commission.state != 'draft':
                continue
            if not commission.line_ids:
                raise UserError(_('La liquidación %s no tiene cobros: pulse «Calcular».', commission.name))
            used = commission._used_partial_ids()
            repeated = commission.line_ids.filtered(lambda l: l.partial_id.id in used)
            if repeated:
                raise UserError(_('Estos cobros ya están en otra liquidación: %s. Recalcule.',
                                  ', '.join(repeated.move_id.mapped('name'))))
            commission.state = 'confirmed'
        return True

    def action_create_bill(self):
        """Factura de proveedor en borrador por la comisión de la agencia; se
        completa con la serie y el número del comprobante que emita la agencia."""
        self.ensure_one()
        if self.beneficiary != 'agency' or self.state != 'confirmed':
            raise UserError(_('Solo se factura la liquidación confirmada de una agencia.'))
        if self.currency_id.compare_amounts(self.amount_commission, 0) <= 0:
            raise UserError(_('La comisión no es positiva: no hay nada que facturar.'))
        product = self.company_id.root_id.l10n_pe_collection_commission_product_id
        if not product:
            raise UserError(_('Configure en Ajustes el servicio con el que se facturan las comisiones de cobranza.'))
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.agency_id.partner_id.id,
            'company_id': self.company_id.id,
            'ref': self.name,
            'invoice_line_ids': [Command.create({
                'product_id': product.id,
                'name': _('Comisión de cobranza del %(from)s al %(to)s (%(name)s)',
                          **{'from': self.date_from.strftime('%d/%m/%Y'), 'to': self.date_to.strftime('%d/%m/%Y'),
                             'name': self.name}),
                'quantity': 1,
                'price_unit': self.amount_commission,
            })],
        })
        self.write({'invoice_id': bill.id, 'state': 'billed'})
        return self.action_open_bill()

    def action_open_bill(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'account.move', 'res_id': self.invoice_id.id,
                'view_mode': 'form', 'name': self.invoice_id.display_name}

    def action_cancel(self):
        for commission in self:
            if commission.invoice_id and commission.invoice_id.state != 'cancel':
                raise UserError(_('Anule primero la factura de la agencia %s.', commission.invoice_id.display_name))
            commission.state = 'cancel'
        return True

    def action_draft(self):
        self.filtered(lambda c: c.state in ('confirmed', 'cancel')).write({'state': 'draft', 'invoice_id': False})
        return True


class L10nPeCollectionCommissionLine(models.Model):
    _name = 'l10n_pe.collection.commission.line'
    _description = 'Cobro de la liquidación de comisiones'
    _order = 'date, id'

    commission_id = fields.Many2one('l10n_pe.collection.commission', string='Liquidación', required=True,
                                    ondelete='cascade', index=True)
    company_id = fields.Many2one(related='commission_id.company_id', store=True, string='Compañía')
    currency_id = fields.Many2one(related='commission_id.currency_id', string='Moneda')
    line_type = fields.Selection([('recovery', 'Cobro'), ('clawback', 'Descuento')], string='Tipo',
                                 required=True, default='recovery')
    # Si el cobro se desconcilia, la conciliación desaparece: la línea queda
    # sin ella y la siguiente liquidación la descuenta.
    partial_id = fields.Many2one('account.partial.reconcile', string='Conciliación', ondelete='set null', index=True)
    origin_line_id = fields.Many2one('l10n_pe.collection.commission.line', string='Cobro descontado',
                                     ondelete='restrict', index=True)
    move_id = fields.Many2one('account.move', string='Documento')
    payment_move_id = fields.Many2one('account.move', string='Cobro')
    partner_id = fields.Many2one('res.partner', string='Cliente')
    date = fields.Date(string='Fecha de cobro')
    date_maturity = fields.Date(string='Vencimiento')
    days_overdue = fields.Integer(string='Días de atraso')
    amount = fields.Monetary(string='Recuperado')
    rate = fields.Float(string='Comisión (%)', digits=(5, 2))
    commission_amount = fields.Monetary(string='Comisión', compute='_compute_commission_amount', store=True)
    reversed = fields.Boolean(string='Desconciliado', compute='_compute_reversed',
                              help='El cobro se desconcilió después de calcular la liquidación.')

    @api.depends('amount', 'rate')
    def _compute_commission_amount(self):
        for line in self:
            line.commission_amount = line.currency_id.round(line.amount * line.rate / 100.0)

    @api.depends('partial_id', 'line_type')
    def _compute_reversed(self):
        for line in self:
            line.reversed = line.line_type == 'recovery' and not line.partial_id
