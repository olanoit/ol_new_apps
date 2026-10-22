from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class L10nPeCollectionAgency(models.Model):
    """Agencia externa de cobranza (estudio o call center).

    Sus usuarios entran con el grupo «Agencia externa», que solo deja ver los
    clientes que tiene asignados y sus documentos. Cobra una comisión sobre lo
    recuperado de esos clientes mientras dura la asignación.
    """
    _name = 'l10n_pe.collection.agency'
    _description = 'Agencia de cobranza'
    _inherit = ['mail.thread']
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(string='Agencia', required=True, tracking=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    partner_id = fields.Many2one('res.partner', string='Proveedor', required=True, check_company=True,
                                 tracking=True, help='A quien se le factura la comisión.')
    user_ids = fields.Many2many(
        'res.users', 'l10n_pe_collection_agency_user_rel', 'agency_id', 'user_id', string='Usuarios',
        domain="[('share', '=', False)]",
        help='Personal de la agencia que entra a Odoo: recibe el grupo «Agencia externa» y solo ve la '
             'cartera asignada.')
    plan_id = fields.Many2one('l10n_pe.collection.commission.plan', string='Plan de comisión', tracking=True,
                              check_company=True)
    assignment_ids = fields.One2many('l10n_pe.collection.agency.assignment', 'agency_id', string='Asignaciones')
    partner_count = fields.Integer(string='Clientes asignados', compute='_compute_portfolio')
    portfolio_amount = fields.Monetary(string='Cartera asignada', compute='_compute_portfolio',
                                       help='Saldo por cobrar hoy de los clientes asignados.')
    commission_count = fields.Integer(string='Liquidaciones', compute='_compute_commission_count')
    note = fields.Text(string='Condiciones')

    @api.depends('assignment_ids.state')
    def _compute_portfolio(self):
        Portfolio = self.env['l10n_pe.collection.portfolio']
        for agency in self:
            partners = agency.assignment_ids.filtered(lambda a: a.state == 'active').partner_id
            agency.partner_count = len(partners)
            agency.portfolio_amount = sum(Portfolio.search([
                ('partner_id', 'in', partners.ids), ('in_collection', '=', True),
                ('company_id', 'child_of', agency.company_id.root_id.id)]).mapped('amount_residual')) \
                if partners else 0.0

    def _compute_commission_count(self):
        counts = dict(self.env['l10n_pe.collection.commission']._read_group(
            [('agency_id', 'in', self.ids)], ['agency_id'], ['__count']))
        for agency in self:
            agency.commission_count = counts.get(agency, 0)

    @api.model_create_multi
    def create(self, vals_list):
        agencies = super().create(vals_list)
        agencies._sync_agency_group()
        return agencies

    def write(self, vals):
        old_users = self.user_ids
        res = super().write(vals)
        if 'user_ids' in vals:
            (self | self.search([('user_ids', 'in', old_users.ids)]))._sync_agency_group(old_users)
        return res

    def _sync_agency_group(self, old_users=None):
        """Da el grupo «Agencia externa» a los usuarios de las agencias y se lo
        quita a quien ya no pertenece a ninguna."""
        group = self.env.ref('al_l10n_pe_collection.group_collection_agency')
        users = self.user_ids
        # sudo: el administrador de cobranza no administra usuarios; solo se toca este grupo.
        group_sudo = group.sudo()
        group_sudo.write({'user_ids': [(4, user.id) for user in users]})
        if old_users:
            gone = old_users - self.sudo().search([]).user_ids
            if gone:
                group_sudo.write({'user_ids': [(3, user.id) for user in gone]})

    def action_open_assignments(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'al_l10n_pe_collection.action_collection_agency_assignment')
        action['domain'] = [('agency_id', '=', self.id)]
        action['context'] = {'default_agency_id': self.id, 'search_default_active': 1}
        return action

    def action_open_commissions(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('al_l10n_pe_collection.action_collection_commission')
        action['domain'] = [('agency_id', '=', self.id)]
        action['context'] = {'default_beneficiary': 'agency', 'default_agency_id': self.id}
        return action

    def action_recall_all(self):
        self.ensure_one()
        self.assignment_ids.filtered(lambda a: a.state == 'active').action_recall()
        return True


class L10nPeCollectionAgencyAssignment(models.Model):
    """Cliente entregado a una agencia desde una fecha hasta su retiro o el fin
    pactado. Da a la agencia acceso al cliente y es la base de su comisión: solo
    cuenta lo cobrado mientras la asignación estuvo vigente."""
    _name = 'l10n_pe.collection.agency.assignment'
    _description = 'Asignación a agencia de cobranza'
    _inherit = ['mail.thread']
    _order = 'date_from desc, id desc'
    _check_company_auto = True

    agency_id = fields.Many2one('l10n_pe.collection.agency', string='Agencia', required=True, index=True,
                                check_company=True, tracking=True)
    company_id = fields.Many2one(related='agency_id.company_id', store=True, string='Compañía')
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    partner_id = fields.Many2one(
        'res.partner', string='Cliente', required=True, index=True, tracking=True,
        domain="['|', ('parent_id', '=', False), ('is_company', '=', True)]")
    date_from = fields.Date(string='Desde', required=True, default=fields.Date.context_today, tracking=True)
    date_to = fields.Date(string='Hasta', tracking=True,
                          help='Fin pactado; al pasar, la asignación termina sola. Al retirar al cliente se '
                               'pone la fecha de retiro.')
    state = fields.Selection([('active', 'Vigente'), ('ended', 'Terminada')], string='Estado', default='active',
                             required=True, readonly=True, tracking=True, copy=False)
    amount_assigned = fields.Monetary(string='Deuda entregada', readonly=True, copy=False,
                                      help='Saldo vencido del cliente al asignarlo.')
    amount_residual = fields.Monetary(string='Saldo actual', compute='_compute_amounts')
    amount_recovered = fields.Monetary(string='Recuperado', compute='_compute_amounts',
                                       help='Cobrado por bancos y cajas mientras la asignación estuvo vigente.')
    note = fields.Char(string='Notas')

    _partner_active_uniq = models.UniqueIndex(
        "(partner_id) WHERE state = 'active'", 'El cliente ya está asignado a una agencia.')

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for assignment in self:
            if assignment.date_to and assignment.date_to < assignment.date_from:
                raise ValidationError(_('La asignación termina antes de empezar.'))

    @api.depends('partner_id', 'date_from', 'date_to', 'state')
    def _compute_amounts(self):
        Portfolio = self.env['l10n_pe.collection.portfolio']
        tools = self.env['l10n_pe.collection.tools']
        today = fields.Date.context_today(self)
        for assignment in self:
            if not assignment.partner_id or not assignment.date_from:
                assignment.amount_residual = assignment.amount_recovered = 0.0
                continue
            company = assignment.company_id or self.env.company
            assignment.amount_residual = sum(Portfolio.search([
                ('partner_id', '=', assignment.partner_id.id), ('in_collection', '=', True),
                ('company_id', 'child_of', company.root_id.id)]).mapped('amount_residual'))
            end = min(assignment.date_to or today, today)
            assignment.amount_recovered = tools._collected(company, assignment.date_from, end, assignment.partner_id)

    @api.depends('agency_id', 'partner_id')
    def _compute_display_name(self):
        for assignment in self:
            assignment.display_name = '%s · %s' % (assignment.partner_id.name or '', assignment.agency_id.name or '')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('partner_id'):
                vals['partner_id'] = self.env['res.partner'].browse(vals['partner_id']).commercial_partner_id.id
        assignments = super().create(vals_list)
        Portfolio = self.env['l10n_pe.collection.portfolio']
        for assignment in assignments:
            assignment.amount_assigned = sum(Portfolio.search([
                ('partner_id', '=', assignment.partner_id.id), ('in_collection', '=', True),
                ('is_overdue', '=', True),
                ('company_id', 'child_of', assignment.company_id.root_id.id)]).mapped('amount_residual'))
            assignment.partner_id._l10n_pe_collection_log(_(
                'Cartera entregada a la agencia de cobranza %s.', assignment.agency_id.name))
        assignments._sync_partner_agency()
        return assignments

    def write(self, vals):
        res = super().write(vals)
        if {'state', 'agency_id', 'partner_id'} & set(vals):
            self._sync_partner_agency()
        return res

    def unlink(self):
        if self.filtered(lambda a: a.state == 'active'):
            raise UserError(_('Retire primero al cliente de la agencia.'))
        return super().unlink()

    def _sync_partner_agency(self):
        """Copia la agencia vigente al cliente: es lo que miran las reglas de
        acceso del grupo «Agencia externa»."""
        for partner in self.partner_id:
            active = self.search([('partner_id', '=', partner.id), ('state', '=', 'active')], limit=1)
            if partner.l10n_pe_collection_agency_id != active.agency_id:
                # sudo: el administrador de cobranza no edita contactos; es un campo técnico de acceso.
                partner_sudo = partner.sudo()
                partner_sudo.l10n_pe_collection_agency_id = active.agency_id

    def action_recall(self):
        today = fields.Date.context_today(self)
        for assignment in self.filtered(lambda a: a.state == 'active'):
            assignment.write({'state': 'ended',
                              'date_to': min(assignment.date_to, today) if assignment.date_to else today})
            assignment.partner_id._l10n_pe_collection_log(_(
                'Cartera retirada de la agencia de cobranza %s.', assignment.agency_id.name))
        return True

    @api.model
    def _cron_end_assignments(self):
        """Termina las asignaciones cuyo plazo pactado ya pasó."""
        today = fields.Date.context_today(self)
        self.search([('state', '=', 'active'), ('date_to', '<', today)]).action_recall()

    def _covers(self, day):
        self.ensure_one()
        return self.date_from <= day and (not self.date_to or day <= self.date_to)


class L10nPeCollectionAgencyAssign(models.TransientModel):
    """Entrega varios clientes a una agencia desde la lista de clientes."""
    _name = 'l10n_pe.collection.agency.assign'
    _description = 'Asignar clientes a una agencia'

    agency_id = fields.Many2one('l10n_pe.collection.agency', string='Agencia', required=True)
    partner_ids = fields.Many2many('res.partner', string='Clientes', required=True,
                                   default=lambda self: self._default_partner_ids())
    date_from = fields.Date(string='Desde', required=True, default=fields.Date.context_today)
    date_to = fields.Date(string='Hasta', help='Fin pactado de la gestión de la agencia; vacío: hasta retirarlos.')
    replace = fields.Boolean(string='Retirar de otra agencia',
                             help='Si un cliente ya está en otra agencia, se retira de ella y pasa a esta.')

    @api.model
    def _default_partner_ids(self):
        if self.env.context.get('active_model') == 'res.partner':
            return self.env.context.get('active_ids')
        return False

    def action_assign(self):
        self.ensure_one()
        Assignment = self.env['l10n_pe.collection.agency.assignment']
        partners = self.partner_ids.commercial_partner_id
        current = Assignment.search([('partner_id', 'in', partners.ids), ('state', '=', 'active')])
        same = current.filtered(lambda a: a.agency_id == self.agency_id)
        other = current - same
        if other and not self.replace:
            raise UserError(_('Ya están en otra agencia: %s. Marque «Retirar de otra agencia» para moverlos.',
                              ', '.join(other.partner_id.mapped('name'))))
        other.action_recall()
        new = Assignment.create([{
            'agency_id': self.agency_id.id, 'partner_id': partner.id,
            'date_from': self.date_from, 'date_to': self.date_to,
        } for partner in partners - same.partner_id])
        return self.agency_id.action_open_assignments() if new else True
