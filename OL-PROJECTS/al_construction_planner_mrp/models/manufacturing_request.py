# -*- coding: utf-8 -*-
"""Requerimiento de fabricación (paquete 1.25, M125-01 a M125-04).

El asistente del árbol de recursos («Requerimiento de fabricación») guarda el
pedido a producción como documento con número propio (RQF/AAAA/NNNNN): qué
ambientes se pidieron, quién los pidió y qué órdenes salieron. Cada orden
lleva su requerimiento; las órdenes hijas de corte, también, pero no cuentan
en su estado. El número viaja a la orden de corte y a las transferencias con
una referencia nativa (``stock.reference``), igual que la referencia propia
de cada orden.

Sirve a las dos verticales: el asistente es común (tipologías en mobiliario,
líneas de producción del plan en construcción por partidas)."""
from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError

REQUEST_REVIEW_ACTIVITY = 'al_construction_planner_mrp.mail_activity_manufacturing_request_review'
SEQUENCE_CODE = 'construction.manufacturing.request'

REQUEST_STATES = [
    ('draft', 'Borrador'),
    ('partial', 'Confirmado parcial'),
    ('confirmed', 'Confirmado'),
    ('done', 'Producido'),
    ('cancel', 'Cancelado'),
]


class ConstructionManufacturingRequest(models.Model):
    _name = 'construction.manufacturing.request'
    _description = 'Requerimiento de fabricación'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True
    # El jefe de producción solo lee el requerimiento: su actividad y el
    # historial de la cancelación (M125-03 y M125-04) se escriben con lectura.
    _mail_post_access = 'read'

    name = fields.Char(string='Número', required=True, readonly=True, copy=False, default='/',
                       index='trigram')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, readonly=True,
        default=lambda self: self.env.company)
    project_id = fields.Many2one(
        'project.project', string='Obra', required=True, readonly=True, index=True,
        check_company=True)
    plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan de recursos', required=True, readonly=True,
        index=True, check_company=True)
    date = fields.Datetime(string='Fecha', required=True, readonly=True,
                           default=fields.Datetime.now)
    user_id = fields.Many2one(
        'res.users', string='Solicitado por', required=True, readonly=True,
        default=lambda self: self.env.user)
    production_head_ids = fields.Many2many(
        'res.users', 'construction_mrp_request_head_rel', 'request_id', 'user_id',
        string='Jefe de producción', readonly=True,
        help='El de la compañía o, sin él, los responsables de Fabricación.')
    group_by = fields.Selection(
        [('floor', 'Piso'), ('selection', 'Selección')], string='Una OF por', readonly=True)
    picking_type_id = fields.Many2one(
        'stock.picking.type', string='Planta forzada', readonly=True, check_company=True)
    space_task_ids = fields.Many2many(
        'project.task', 'construction_mrp_request_space_rel', 'request_id', 'task_id',
        string='Ambientes', readonly=True,
        help='Los ambientes de las órdenes creadas: la selección real del asistente.')
    space_labels = fields.Html(
        string='Ambientes pedidos', compute='_compute_space_labels', sanitize=False)
    note = fields.Text(string='Notas')
    reference_id = fields.Many2one(
        'stock.reference', string='Referencia', readonly=True, copy=False,
        help='Referencia nativa con el número del requerimiento: viaja a la orden de corte y '
             'a las transferencias.')
    production_ids = fields.One2many(
        'mrp.production', 'construction_mrp_request_id', string='Órdenes de fabricación',
        domain=[('construction_parent_id', '=', False)])
    cut_production_ids = fields.One2many(
        'mrp.production', 'construction_mrp_request_id', string='Órdenes de corte',
        domain=[('construction_parent_id', '!=', False)])
    production_count = fields.Integer(compute='_compute_counts', string='N.º de órdenes')
    cut_production_count = fields.Integer(compute='_compute_counts', string='N.º de órdenes de corte')
    picking_count = fields.Integer(compute='_compute_counts', string='N.º de entregas')
    state = fields.Selection(
        REQUEST_STATES, string='Estado', compute='_compute_state', store=True, index=True,
        tracking=True)

    @api.model
    def _construction_protected_fields(self):
        """Cabecera del requerimiento: la escribe el asistente al crearlo y
        no cambia después; las personas solo escriben las notas."""
        return {'name', 'company_id', 'project_id', 'plan_id', 'date', 'user_id',
                'production_head_ids', 'group_by', 'picking_type_id', 'space_task_ids',
                'reference_id'}

    @api.depends('production_ids.state')
    def _compute_state(self):
        for request in self:
            productions = request.production_ids
            active = productions.filtered(lambda p: p.state != 'cancel')
            if not productions:
                request.state = 'draft'
            elif not active:
                request.state = 'cancel'
            elif all(p.state == 'draft' for p in active):
                request.state = 'draft'
            elif any(p.state == 'draft' for p in active):
                request.state = 'partial'
            elif all(p.state == 'done' for p in active):
                request.state = 'done'
            else:
                request.state = 'confirmed'

    def _compute_counts(self):
        for request in self:
            request.production_count = len(request.production_ids)
            request.cut_production_count = len(request.cut_production_ids)
            request.picking_count = len(request._construction_pickings())

    @api.depends('space_task_ids')
    def _compute_space_labels(self):
        for request in self:
            labels = [self._construction_space_label(space)
                      for space in request.space_task_ids.sorted(
                          lambda t: (t.construction_floor_task_id.name or '',
                                     t.construction_apartment_task_id.name or '', t.name or ''))]
            request.space_labels = Markup('').join(
                Markup('<span class="badge rounded-pill text-bg-light border me-1 mb-1">%s</span>')
                % label for label in labels) or False

    @api.model
    def _construction_space_label(self, space):
        """«Piso / Departamento / Ambiente · Tipología» (M125-01): la etiqueta
        de los avisos del asistente, ampliada con el piso y la tipología. En
        construcción por partidas el nivel con etapas no tiene piso ni
        tipología y queda solo su nombre."""
        path = ' / '.join(filter(None, [
            space.construction_floor_task_id.name, space.construction_apartment_task_id.name,
            space.name]))
        typology = space.construction_typology_id
        return '%s · %s' % (path, typology.code or typology.name) if typology else path

    @api.depends('name', 'project_id')
    @api.depends_context('construction_request_long_name')
    def _compute_display_name(self):
        """El número; con ``construction_request_long_name`` (los grupos de
        la lista de órdenes del planificador), «número · obra · agrupador»."""
        long_name = self.env.context.get('construction_request_long_name')
        for request in self:
            if not long_name:
                request.display_name = request.name
                continue
            floors = request.space_task_ids.construction_floor_task_id
            # Solo el nombre de la obra: el jefe de producción puede no leer
            # la ficha de la obra.
            project_sudo = request.project_id.sudo()
            request.display_name = ' · '.join(filter(None, [
                request.name, project_sudo.display_name,
                ', '.join(floors.sorted('name').mapped('name'))]))

    # ------------------------------------------------------------------
    # Creación
    # ------------------------------------------------------------------
    @api.model
    def _construction_next_number(self, company):
        """Número de la secuencia RQF de la compañía (M125-01, criterio 2:
        cada compañía numera desde 00001). La primera vez se crea la
        secuencia de la compañía con el prefijo de la que trae el módulo."""
        # Las secuencias son configuración técnica: quien pide a producción
        # no administra secuencias.
        Sequence_sudo = self.env['ir.sequence'].sudo()
        if not Sequence_sudo.search_count([('code', '=', SEQUENCE_CODE),
                                           ('company_id', '=', company.id)]):
            template = self.env.ref(
                'al_construction_planner_mrp.seq_construction_manufacturing_request',
                raise_if_not_found=False)
            Sequence_sudo.create({
                'name': self.env._('Requerimiento de fabricación (%s)', company.name),
                'code': SEQUENCE_CODE, 'company_id': company.id,
                'prefix': template.sudo().prefix if template else 'RQF/%(year)s/',
                'padding': template.sudo().padding if template else 5,
            })
        return Sequence_sudo.with_company(company).next_by_code(SEQUENCE_CODE)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                company = self.env['res.company'].browse(
                    vals.get('company_id') or self.env.company.id)
                vals['name'] = self._construction_next_number(company)
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and self._construction_protected_fields() & set(vals):
            raise UserError(self.env._(
                'La cabecera del requerimiento de fabricación la escribe el asistente al '
                'crearlo: no se cambia a mano.'))
        return super().write(vals)

    def copy(self, default=None):
        raise UserError(self.env._(
            'Un requerimiento de fabricación nace del árbol de recursos: no se duplica.'))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_with_orders(self):
        if self.production_ids:
            raise UserError(self.env._(
                'El requerimiento tiene órdenes de fabricación: se cancela, no se elimina.'))

    # ------------------------------------------------------------------
    # Transferencias del requerimiento (M125-02)
    # ------------------------------------------------------------------
    def _construction_pickings(self):
        self.ensure_one()
        if not self.reference_id:
            return self.env['stock.picking']
        return self.env['stock.picking'].search([('reference_ids', 'in', self.reference_id.ids)])

    # ------------------------------------------------------------------
    # Actividad del jefe de producción (M125-03)
    # ------------------------------------------------------------------
    def _construction_schedule_review(self):
        """Una actividad «Revisar y confirmar las órdenes del requerimiento»
        por requerimiento, con la fecha del cronograma de cada orden."""
        for request in self:
            company = request.company_id
            if not company.construction_production_date_review:
                continue
            users = request.production_head_ids or request.user_id
            items = Markup('').join(
                Markup('<li>%s: %s</li>') % (production.name,
                                             production._construction_date_review_note())
                for production in request.production_ids)
            note = Markup('<p>%s</p><ul>%s</ul>') % (
                self.env._('Órdenes del requerimiento:'), items)
            for user in users:
                request.activity_schedule(
                    REQUEST_REVIEW_ACTIVITY, user_id=user.id, note=note,
                    date_deadline=fields.Date.context_today(request))

    def _construction_close_review(self):
        """Cierra la actividad cuando ninguna orden queda en «Borrador», con
        la fecha confirmada de cada una en el comentario."""
        for request in self:
            productions = request.production_ids
            if any(p.state == 'draft' for p in productions):
                continue
            if not request.activity_ids.filtered(
                    lambda a: a.activity_type_id.id == self.env.ref(REQUEST_REVIEW_ACTIVITY).id):
                continue
            lines = [
                '%s: %s' % (production.name, production.construction_date_confirmed
                            or dict(production._fields['state']._description_selection(
                                self.env))[production.state])
                for production in productions]
            request.activity_feedback(
                [REQUEST_REVIEW_ACTIVITY],
                feedback=self.env._('Órdenes del requerimiento:\n%s', '\n'.join(lines)))

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def _construction_action(self, name, model, domain, form_id=False, context=None):
        action = {
            'type': 'ir.actions.act_window', 'name': name, 'res_model': model,
            'domain': domain, 'context': dict(context or {}, create=False),
        }
        if form_id:
            action.update(view_mode='form', res_id=form_id)
        else:
            action.update(view_mode='list,form')
        return action

    def action_view_productions(self):
        self.ensure_one()
        productions = self.production_ids
        return self._construction_action(
            self.env._('Órdenes de fabricación'), 'mrp.production',
            [('id', 'in', productions.ids)], len(productions) == 1 and productions.id)

    def action_view_cut_productions(self):
        self.ensure_one()
        productions = self.cut_production_ids
        return self._construction_action(
            self.env._('Órdenes de corte'), 'mrp.production',
            [('id', 'in', productions.ids)], len(productions) == 1 and productions.id)

    def action_view_pickings(self):
        self.ensure_one()
        pickings = self._construction_pickings()
        return self._construction_action(
            self.env._('Entregas a producción'), 'stock.picking',
            [('id', 'in', pickings.ids)], len(pickings) == 1 and pickings.id)

    def action_cancel(self):
        """M125-04: abre la confirmación; el diálogo muestra lo que ya pasó a
        producción y cancela solo lo que sigue en borrador."""
        self.ensure_one()
        if self.state in ('cancel', 'done'):
            raise UserError(self.env._(
                'El requerimiento %s ya está cancelado o producido.', self.name))
        wizard = self.env['construction.manufacturing.request.cancel.wizard'].create({
            'request_id': self.id})
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Cancelar %s', self.name),
            'res_model': wizard._name, 'res_id': wizard.id,
            'view_mode': 'form', 'target': 'new',
        }

    def _construction_cancel_drafts(self):
        """Cancela con la cancelación nativa las órdenes que siguen en
        borrador y deja en el historial cuáles y quién."""
        self.ensure_one()
        drafts = self.production_ids.filtered(lambda p: p.state == 'draft')
        if not drafts:
            raise UserError(self.env._(
                'El requerimiento %s no tiene órdenes en borrador que cancelar.', self.name))
        drafts.action_cancel()
        self.message_post(body=Markup('%s<br/>%s') % (
            self.env._('%s canceló las órdenes en borrador:', self.env.user.name),
            escape(', '.join(drafts.mapped('name')))))
        self._construction_close_review()
        return drafts


class StockReference(models.Model):
    _inherit = 'stock.reference'

    construction_mrp_request_ids = fields.One2many(
        'construction.manufacturing.request', 'reference_id',
        string='Requerimientos de fabricación')


class ProjectProject(models.Model):
    _inherit = 'project.project'

    construction_mrp_request_count = fields.Integer(
        string='Requerimientos de fabricación', compute='_compute_construction_mrp_request_count',
        groups='al_construction_planner.group_planner_user')

    def _compute_construction_mrp_request_count(self):
        counts = dict(self.env['construction.manufacturing.request']._read_group(
            [('project_id', 'in', self.ids)], ['project_id'], ['__count']))
        for project in self:
            project.construction_mrp_request_count = counts.get(project, 0)

    def action_view_construction_mrp_requests(self):
        """M125-01, punto 11: los requerimientos de fabricación de la obra."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'al_construction_planner_mrp.action_construction_manufacturing_request')
        action['domain'] = [('project_id', '=', self.id)]
        action['context'] = {'default_project_id': self.id}
        return action
