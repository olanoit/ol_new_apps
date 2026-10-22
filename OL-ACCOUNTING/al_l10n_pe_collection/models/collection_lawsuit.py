from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

#: Vías del Código Procesal Civil para cobrar una suma de dinero. La elige el
#: abogado: el título ejecutivo (letra, pagaré, factura negociable conformada)
#: abre el proceso único de ejecución; sin título, la cuantía fija la vía.
PROCESS_TYPES = [
    ('execution', 'Proceso único de ejecución (título ejecutivo)'),
    ('guarantee', 'Ejecución de garantías'),
    ('summary', 'Sumarísimo (hasta 100 URP)'),
    ('abbreviated', 'Abreviado (más de 100 y hasta 1000 URP)'),
    ('ordinary', 'Conocimiento (más de 1000 URP)'),
    ('other', 'Otro'),
]
LAWSUIT_STATES = [
    ('draft', 'Preparación'),
    ('conciliation', 'Conciliación'),
    ('filed', 'Demanda presentada'),
    ('admitted', 'Admitida'),
    ('judgment', 'Sentencia'),
    ('enforcement', 'Ejecución forzada'),
    ('closed', 'Concluido'),
]
#: Estados en que la deuda está en cobranza judicial.
ACTIVE_STATES = ('filed', 'admitted', 'judgment', 'enforcement')
RESULTS = [
    ('paid', 'Cobrado'),
    ('settled', 'Transacción o acuerdo'),
    ('uncollectible', 'Incobrable: acciones agotadas'),
    ('lost', 'Desfavorable'),
    ('withdrawn', 'Desistimiento'),
]
EVENT_TYPES = [
    ('filing', 'Escrito'),
    ('resolution', 'Resolución'),
    ('notification', 'Notificación'),
    ('hearing', 'Audiencia'),
    ('seizure', 'Embargo o medida cautelar'),
    ('other', 'Otro'),
]


class L10nPeCollectionLawsuit(models.Model):
    """Proceso judicial de cobranza contra un deudor.

    Desde que se presenta la demanda, sus documentos salen del seguimiento
    automático (la comunicación pasa por el estudio) y acreditan la morosidad
    para la provisión de cobranza dudosa sin esperar 12 meses (art. 21 f del
    Reglamento de la LIR). Si concluye como incobrable, sus documentos quedan
    con las acciones judiciales agotadas que exige el castigo de deudas de más
    de 3 UIT (art. 21 g).
    """
    _name = 'l10n_pe.collection.lawsuit'
    _description = 'Proceso judicial de cobranza'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', readonly=True, copy=False, default='/')
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    partner_id = fields.Many2one(
        'res.partner', string='Demandado', required=True, tracking=True, check_company=True, index=True,
        domain="['|', ('parent_id', '=', False), ('is_company', '=', True)]")
    user_id = fields.Many2one('res.users', string='Responsable', required=True, tracking=True,
                              default=lambda self: self.env.user)
    agency_id = fields.Many2one('l10n_pe.collection.agency', string='Estudio', tracking=True, check_company=True,
                                help='Estudio o agencia externa que lleva el proceso; sus usuarios lo ven y '
                                     'registran las actuaciones.')
    lawyer = fields.Char(string='Abogado')
    process_type = fields.Selection(
        PROCESS_TYPES, string='Vía', required=True, default='execution', tracking=True,
        help='Con título ejecutivo (letra, pagaré, factura negociable conformada): proceso único de ejecución. '
             'Sin título, la cuantía del petitorio fija la vía (Código Procesal Civil, arts. 475, 486 y 546).')
    court = fields.Char(string='Juzgado', tracking=True)
    file_number = fields.Char(string='N.° de expediente', tracking=True)
    line_ids = fields.Many2many(
        'account.move.line', string='Documentos', check_company=True, required=True,
        relation='account_move_line_l10n_pe_collection_lawsuit_rel', column1='l10n_pe_collection_lawsuit_id',
        column2='account_move_line_id',
        domain="[('partner_id', 'child_of', partner_id), ('parent_state', '=', 'posted'),"
               " ('account_id.account_type', '=', 'asset_receivable'), ('balance', '>', 0)]")
    state = fields.Selection(LAWSUIT_STATES, string='Etapa', default='draft', required=True, readonly=True,
                             tracking=True, copy=False)
    result = fields.Selection(RESULTS, string='Resultado', readonly=True, tracking=True, copy=False)
    date_conciliation = fields.Date(string='Conciliación', copy=False,
                                    help='Audiencia de conciliación extrajudicial previa, cuando corresponde.')
    date_filed = fields.Date(string='Demanda presentada el', readonly=True, copy=False, tracking=True)
    date_closed = fields.Date(string='Concluido el', readonly=True, copy=False, tracking=True)
    amount_claimed = fields.Monetary(string='Petitorio', readonly=True, copy=False,
                                     help='Saldo de los documentos al presentar la demanda.')
    amount_residual = fields.Monetary(string='Saldo actual', compute='_compute_amounts')
    amount_recovered = fields.Monetary(string='Recuperado', compute='_compute_amounts')
    amount_costs = fields.Monetary(string='Gastos y costas', compute='_compute_amounts')
    event_ids = fields.One2many('l10n_pe.collection.lawsuit.event', 'lawsuit_id', string='Actuaciones')
    cost_ids = fields.One2many('l10n_pe.collection.lawsuit.cost', 'lawsuit_id', string='Gastos')
    next_deadline = fields.Date(string='Próximo plazo', compute='_compute_next_deadline', store=True)
    note = fields.Text(string='Notas')

    @api.depends('line_ids.amount_residual', 'amount_claimed', 'cost_ids.amount')
    def _compute_amounts(self):
        for lawsuit in self:
            lawsuit.amount_residual = sum(lawsuit.line_ids.mapped('amount_residual'))
            lawsuit.amount_recovered = max(lawsuit.amount_claimed - lawsuit.amount_residual, 0.0) \
                if lawsuit.amount_claimed else 0.0
            lawsuit.amount_costs = sum(lawsuit.cost_ids.mapped('amount'))

    @api.depends('event_ids.date_deadline', 'event_ids.done')
    def _compute_next_deadline(self):
        for lawsuit in self:
            pending = lawsuit.event_ids.filtered(lambda e: e.date_deadline and not e.done)
            lawsuit.next_deadline = min(pending.mapped('date_deadline')) if pending else False

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        partner = self.partner_id.commercial_partner_id
        if partner.l10n_pe_collection_agency_id and not self.agency_id:
            self.agency_id = partner.l10n_pe_collection_agency_id

    @api.depends('name', 'partner_id')
    def _compute_display_name(self):
        for lawsuit in self:
            lawsuit.display_name = '%s · %s' % (lawsuit.name, lawsuit.partner_id.name or '')

    @api.constrains('line_ids', 'partner_id')
    def _check_lines(self):
        for lawsuit in self:
            if lawsuit.line_ids.partner_id.commercial_partner_id - lawsuit.partner_id.commercial_partner_id:
                raise ValidationError(_('Los documentos del proceso deben ser del demandado.'))

    @api.constrains('agency_id', 'partner_id')
    def _check_agency(self):
        """El estudio solo ve los documentos de los clientes que tiene asignados."""
        for lawsuit in self.filtered(lambda l: l.agency_id and l.state != 'closed'):
            if lawsuit.partner_id.l10n_pe_collection_agency_id != lawsuit.agency_id:
                raise ValidationError(_(
                    'Asigne primero %(partner)s a %(agency)s (Cobranza ‣ Cartera ‣ Agencias externas): el estudio '
                    'solo ve los documentos de los clientes que tiene asignados.',
                    partner=lawsuit.partner_id.name, agency=lawsuit.agency_id.name))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].with_company(
                    vals.get('company_id') or self.env.company.id).next_by_code('l10n_pe.collection.lawsuit') or '/'
            if vals.get('partner_id'):
                vals['partner_id'] = self.env['res.partner'].browse(vals['partner_id']).commercial_partner_id.id
        return super().create(vals_list)

    def write(self, vals):
        old_lines = self.line_ids
        res = super().write(vals)
        if 'line_ids' in vals or 'state' in vals:
            # sudo: el estudio externo no ve los reclamos, que también deciden si el
            # documento sale del seguimiento; solo se toca la marca no_followup.
            lines_sudo = (old_lines | self.line_ids).sudo()
            lines_sudo._l10n_pe_collection_sync_dispute()
        return res

    def unlink(self):
        if self.filtered(lambda l: l.state not in ('draft', 'conciliation')):
            raise UserError(_('Un proceso con demanda presentada no se elimina: concluya el proceso.'))
        return super().unlink()

    # ------------------------------------------------------------------
    # Etapas
    # ------------------------------------------------------------------

    def _set_stage(self, state, allowed):
        for lawsuit in self:
            if lawsuit.state not in allowed:
                raise UserError(_('El proceso %(name)s está en «%(state)s».', name=lawsuit.name,
                                  state=dict(LAWSUIT_STATES)[lawsuit.state]))
        self.state = state
        return True

    def action_conciliation(self):
        self._set_stage('conciliation', ('draft',))
        self.filtered(lambda l: not l.date_conciliation).date_conciliation = fields.Date.context_today(self)
        return True

    def action_file(self):
        """Demanda presentada: congela el petitorio y saca los documentos del seguimiento."""
        for lawsuit in self:
            if lawsuit.state not in ('draft', 'conciliation'):
                raise UserError(_('La demanda de %s ya se presentó.', lawsuit.name))
            if not lawsuit.court:
                raise UserError(_('Indique el juzgado de %s.', lawsuit.name))
            lawsuit.write({
                'state': 'filed',
                'date_filed': fields.Date.context_today(self),
                'amount_claimed': sum(lawsuit.line_ids.mapped('amount_residual')),
            })
            lawsuit.partner_id._l10n_pe_collection_log(_(
                'Demanda presentada (%(name)s) por %(amount)s: sus documentos salen del seguimiento automático.',
                name=lawsuit._get_html_link(), amount=lawsuit.currency_id.format(lawsuit.amount_claimed)))
        return True

    def action_admit(self):
        return self._set_stage('admitted', ('filed',))

    def action_judgment(self):
        return self._set_stage('judgment', ('filed', 'admitted'))

    def action_enforce(self):
        return self._set_stage('enforcement', ('admitted', 'judgment'))

    def action_close(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Concluir proceso'),
            'res_model': 'l10n_pe.collection.lawsuit.close', 'view_mode': 'form', 'target': 'new',
            'context': {'default_lawsuit_id': self.id},
        }

    def _l10n_pe_close(self, result, note=False):
        for lawsuit in self:
            if lawsuit.state == 'closed':
                raise UserError(_('El proceso %s ya concluyó.', lawsuit.name))
            lawsuit.write({'state': 'closed', 'result': result, 'date_closed': fields.Date.context_today(self)})
            body = _('Proceso %(name)s concluido: %(result)s.', name=lawsuit._get_html_link(),
                     result=dict(RESULTS)[result].lower())
            if note:
                lawsuit.message_post(body=note)
            lawsuit.partner_id._l10n_pe_collection_log(body)
        self._l10n_pe_sync_provisions()
        return True

    def action_reopen(self):
        if not self.env.user.has_group('al_l10n_pe_collection.group_collection_manager'):
            raise UserError(_('Solo el administrador de cobranza reabre un proceso judicial.'))
        for lawsuit in self.filtered(lambda l: l.state == 'closed'):
            lawsuit.write({'state': 'enforcement' if lawsuit.date_filed else 'draft', 'result': False,
                           'date_closed': False})
        self._l10n_pe_sync_provisions()
        return True

    def _l10n_pe_sync_provisions(self):
        """Marca en las provisiones contabilizadas el proceso judicial y, si
        concluyó incobrable, las acciones agotadas que exige el castigo."""
        # sudo: la provisión es solo del administrador, pero el estudio o el gestor
        # que concluye el proceso debe dejar el sustento al día.
        lines_sudo = self.env['l10n_pe.collection.provision.line'].sudo().search([
            ('move_line_id', 'in', self.line_ids.ids), ('provision_id.state', '=', 'posted'),
            ('write_off_move_id', '=', False)])
        for line_sudo in lines_sudo:
            lawsuits = line_sudo.move_line_id.l10n_pe_collection_lawsuit_ids
            line_sudo.write({
                'judicial': bool(lawsuits.filtered('date_filed')),
                'judicial_exhausted': bool(lawsuits.filtered(lambda l: l.result == 'uncollectible')),
            })

    def action_print_file(self):
        """Expediente de cobranza del demandado, con el proceso judicial."""
        self.ensure_one()
        return self.partner_id.action_l10n_pe_collection_file()


class L10nPeCollectionLawsuitEvent(models.Model):
    """Actuación del proceso: escrito, resolución, audiencia, embargo… con su
    plazo, que se agenda como actividad al responsable."""
    _name = 'l10n_pe.collection.lawsuit.event'
    _description = 'Actuación judicial'
    _order = 'date desc, id desc'

    lawsuit_id = fields.Many2one('l10n_pe.collection.lawsuit', string='Proceso', required=True,
                                 ondelete='cascade', index=True)
    company_id = fields.Many2one(related='lawsuit_id.company_id', store=True, string='Compañía')
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    event_type = fields.Selection(EVENT_TYPES, string='Tipo', required=True, default='filing')
    name = fields.Char(string='Actuación', required=True)
    date_deadline = fields.Date(string='Plazo', help='Se agenda una actividad al responsable del proceso.')
    done = fields.Boolean(string='Atendido')
    activity_id = fields.Many2one('mail.activity', string='Actividad', readonly=True, copy=False,
                                  ondelete='set null')

    @api.model_create_multi
    def create(self, vals_list):
        events = super().create(vals_list)
        events._l10n_pe_schedule()
        return events

    def write(self, vals):
        res = super().write(vals)
        if {'date_deadline', 'done', 'name'} & set(vals):
            self._l10n_pe_schedule()
        return res

    def _l10n_pe_schedule(self):
        for event in self:
            if event.activity_id and (event.done or not event.date_deadline):
                event.activity_id.action_feedback(feedback=_('Atendido'))
                continue
            if event.done or not event.date_deadline:
                continue
            values = {'date_deadline': event.date_deadline, 'summary': event.name}
            if event.activity_id:
                event.activity_id.write(values)
            else:
                event.activity_id = event.lawsuit_id.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=event.lawsuit_id.user_id.id, **values)


class L10nPeCollectionLawsuitCost(models.Model):
    _name = 'l10n_pe.collection.lawsuit.cost'
    _description = 'Gasto judicial'
    _order = 'date desc, id desc'

    lawsuit_id = fields.Many2one('l10n_pe.collection.lawsuit', string='Proceso', required=True,
                                 ondelete='cascade', index=True)
    company_id = fields.Many2one(related='lawsuit_id.company_id', store=True, string='Compañía')
    currency_id = fields.Many2one(related='lawsuit_id.currency_id', string='Moneda')
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    name = fields.Char(string='Concepto', required=True,
                       help='Tasas judiciales, cédulas de notificación, honorarios, peritos, martillero…')
    amount = fields.Monetary(string='Importe', required=True)
    move_id = fields.Many2one('account.move', string='Comprobante',
                              domain="[('move_type', 'in', ('in_invoice', 'in_receipt', 'entry'))]")


class L10nPeCollectionLawsuitClose(models.TransientModel):
    _name = 'l10n_pe.collection.lawsuit.close'
    _description = 'Concluir proceso judicial'

    lawsuit_id = fields.Many2one('l10n_pe.collection.lawsuit', required=True)
    result = fields.Selection(RESULTS, string='Resultado', required=True)
    note = fields.Text(string='Sustento',
                       help='Resolución, acta de transacción o constancia de que no hay bienes que embargar.')

    def action_close(self):
        self.ensure_one()
        if self.result == 'uncollectible' and not self.note:
            raise UserError(_('Describa el sustento de la incobrabilidad: es lo que pide SUNAT para el castigo.'))
        return self.lawsuit_id._l10n_pe_close(self.result, self.note)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    l10n_pe_collection_lawsuit_ids = fields.Many2many(
        'l10n_pe.collection.lawsuit', string='Procesos judiciales', copy=False,
        relation='account_move_line_l10n_pe_collection_lawsuit_rel', column1='account_move_line_id',
        column2='l10n_pe_collection_lawsuit_id')
    l10n_pe_collection_in_lawsuit = fields.Boolean(
        string='En cobranza judicial', compute='_compute_l10n_pe_collection_in_lawsuit', store=True)

    @api.depends('l10n_pe_collection_lawsuit_ids.state')
    def _compute_l10n_pe_collection_in_lawsuit(self):
        for line in self:
            line.l10n_pe_collection_in_lawsuit = any(
                l.state in ACTIVE_STATES for l in line.l10n_pe_collection_lawsuit_ids)
