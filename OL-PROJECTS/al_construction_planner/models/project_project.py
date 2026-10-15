# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .common import PURCHASE_DESTINATIONS, WEEKDAYS
from .construction_resource_plan import DRAFT_STATES, OPEN_STATES


class ProjectProject(models.Model):
    _inherit = 'project.project'

    # También lo define al_construction_material_request (con la ubicación de
    # la obra); el núcleo lo necesita sin depender de él.
    is_construction_site = fields.Boolean(
        string='Es obra', help='Habilita el planificador y, con compras, los requerimientos de '
                               'materiales y la ubicación de obra.')
    construction_profile_id = fields.Many2one(
        'construction.vertical.profile', string='Perfil de vertical',
        help='El rubro de la obra (v1.7, M17-05). Por defecto, el de la compañía; una obra de '
             'otro perfil toma al crearla la plantilla de niveles de ese perfil.')
    construction_level_template_id = fields.Many2one(
        'construction.level.template', string='Plantilla de niveles',
        compute='_compute_construction_level_template_id', store=True, readonly=False,
        help='Niveles del árbol de la obra y su nombre (Torre › Piso › Departamento › '
             'Ambiente › Mueble › Módulo). Vacía: Piso › Departamento › Ambiente › Módulo. '
             'No se cambia con un plan aprobado.')
    construction_purchase_destination = fields.Selection(
        PURCHASE_DESTINATIONS, string='Destino de la compra masiva',
        compute='_compute_construction_purchase_destination', store=True, readonly=False,
        help='El de la plantilla de niveles; se puede cambiar en cada obra (v1.7, M17-14).')
    construction_plan_ids = fields.One2many(
        'construction.resource.plan', 'project_id', string='Planes de recursos')
    construction_plan_count = fields.Integer(
        string='Nº de planes de recursos', compute='_compute_construction_plan_count')
    construction_typology_ids = fields.One2many(
        'construction.typology', 'project_id', string='Tipologías')
    construction_typology_count = fields.Integer(
        string='Nº de tipologías', compute='_compute_construction_plan_count')

    @api.model_create_multi
    def create(self, vals_list):
        # Por defecto, el perfil de la compañía (no como default del campo: la
        # columna de la compañía aún no existe al instalar).
        for vals in vals_list:
            if 'construction_profile_id' not in vals:
                company = self.env['res.company'].browse(vals.get('company_id')) \
                    if vals.get('company_id') else self.env.company
                vals['construction_profile_id'] = company.construction_profile_id.id
        return super().create(vals_list)

    @api.depends('construction_profile_id')
    def _compute_construction_level_template_id(self):
        # La de la compañía (aplicar un perfil la deja con la suya); una obra
        # de otro perfil, la de ese perfil. Una compañía que recibió su perfil
        # al actualizar a la v1.7 sin plantilla sigue con el árbol clásico.
        for project in self:
            if not project.construction_level_template_id:
                company = project.company_id or self.env.company
                profile = project.construction_profile_id
                if profile and profile != company.construction_profile_id:
                    template = profile.level_template_id
                else:
                    template = company.construction_level_template_id
                project.construction_level_template_id = template

    @api.depends('construction_level_template_id.purchase_destination')
    def _compute_construction_purchase_destination(self):
        for project in self:
            project.construction_purchase_destination = \
                project.construction_level_template_id.purchase_destination or \
                project.construction_purchase_destination or 'general'

    # Semana de la obra (especificación: jueves a miércoles, liquidación el
    # jueves y pago el sábado; configurable por obra con valor por defecto de
    # la compañía).
    construction_week_start_day = fields.Selection(
        WEEKDAYS, string='Inicio de semana', compute='_compute_construction_week_days',
        store=True, readonly=False,
        help='Primer día de las semanas de liquidación de la obra; el cierre es el día '
             'anterior.')
    construction_settlement_day = fields.Selection(
        WEEKDAYS, string='Día de liquidación', compute='_compute_construction_week_days',
        store=True, readonly=False,
        help='Primer día con este nombre después del cierre de la semana. Si es feriado, se '
             'corre al día hábil anterior.')
    construction_payment_day = fields.Selection(
        WEEKDAYS, string='Día de pago', compute='_compute_construction_week_days',
        store=True, readonly=False,
        help='Primer día con este nombre desde la liquidación: es el vencimiento de la '
             'factura de la contrata. Si es feriado, se corre al día hábil anterior.')
    construction_current_plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan vigente',
        compute='_compute_construction_current_plan_id')
    construction_supervisor_ids = fields.Many2many(
        'res.users', 'project_construction_supervisor_rel', 'project_id', 'user_id',
        string='Supervisores de obra', domain=[('share', '=', False)],
        help='Con el responsable del proyecto, son «sus obras» en el inicio de la '
             'aplicación: el supervisor ve ahí solo los avances por validar de ellas.')

    @api.depends('company_id')
    def _compute_construction_week_days(self):
        for project in self:
            company = project.company_id or self.env.company
            project.construction_week_start_day = (
                project.construction_week_start_day or company.construction_week_start_day or '3')
            project.construction_settlement_day = (
                project.construction_settlement_day or company.construction_settlement_day or '3')
            project.construction_payment_day = (
                project.construction_payment_day or company.construction_payment_day or '5')

    def _construction_period(self, day):
        """Semana de liquidación que contiene ``day``: (inicio, fin)."""
        self.ensure_one()
        start_day = int(self.construction_week_start_day or '3')
        start = day - timedelta(days=(day.weekday() - start_day) % 7)
        return start, start + timedelta(days=6)

    def _construction_settlement_dates(self, period_start):
        """Fechas de liquidación y de pago de la semana que empieza en
        ``period_start``: el primer día de liquidación después del cierre y el
        primer día de pago desde ese día, corridos al día hábil anterior si
        caen en feriado del calendario de la compañía."""
        self.ensure_one()
        company = self.company_id or self.env.company
        after_close = period_start + timedelta(days=7)
        settlement_day = int(self.construction_settlement_day or '3')
        payment_day = int(self.construction_payment_day or '5')
        settlement = after_close + timedelta(days=(settlement_day - after_close.weekday()) % 7)
        payment = settlement + timedelta(days=(payment_day - settlement.weekday()) % 7)
        return (company._construction_previous_working_day(settlement),
                company._construction_previous_working_day(payment))

    def _compute_construction_plan_count(self):
        plans = dict(self.env['construction.resource.plan']._read_group(
            [('project_id', 'in', self.ids)], ['project_id'], ['__count']))
        typologies = dict(self.env['construction.typology']._read_group(
            [('project_id', 'in', self.ids)], ['project_id'], ['__count']))
        for project in self:
            project.construction_plan_count = plans.get(project, 0)
            project.construction_typology_count = typologies.get(project, 0)

    @api.constrains('construction_level_template_id')
    def _check_construction_level_template(self):
        """La plantilla de niveles no cambia con un plan aprobado: el árbol ya
        está costeado con esos niveles."""
        for project in self:
            approved = project.construction_plan_ids.filtered(
                lambda p: p.state in ('approved', 'in_progress', 'closed'))
            levels = self.env['project.task'].search_count([
                ('project_id', '=', project.id), ('construction_level_line_id', '!=', False),
                ('construction_level_line_id.template_id', '!=', project.construction_level_template_id.id)])
            if approved and levels:
                raise ValidationError(self.env._(
                    'La obra %s ya tiene un plan aprobado: no se le cambia la plantilla de niveles.',
                    project.display_name))

    def _construction_distance_m(self, latitude, longitude):
        """Distancia en metros de un punto a la sede de la obra (fase 17); 0
        si la obra no tiene sede con ubicación."""
        self.ensure_one()
        site = self._construction_site() if hasattr(self, '_construction_site') else False
        if not site or not (site.latitude or site.longitude):
            return 0.0
        return site._distance_to(latitude, longitude)

    def _construction_level_lines(self):
        """Niveles de la plantilla de la obra por función del planificador:
        ``{'group': [líneas de arriba abajo], 'floor': línea, 'apartment': …,
        'space': …, 'furniture': …, 'module': …}``. Vacío sin plantilla."""
        self.ensure_one()
        template = self.construction_level_template_id
        if not template:
            return {}
        result = {'group': []}
        for line in template.line_ids.sorted(lambda l: (l.sequence, l.id)):
            if line.level == 'group':
                result['group'].append(line)
            else:
                result[line.level] = line
        return result

    def _construction_level_vals(self, level, depth=0):
        """Valores del nivel para crear una tarea de la obra: la línea de la
        plantilla (``depth``: posición entre los agrupadores superiores)."""
        self.ensure_one()
        lines = self._construction_level_lines()
        line = lines.get('group', [])[depth] if level == 'group' and \
            depth < len(lines.get('group', [])) else lines.get(level) if level != 'group' else False
        vals = {'construction_level': level}
        if line:
            vals['construction_level_line_id'] = line.id
        return vals

    def _construction_current_plan(self):
        """Plan vigente de la obra o, si aún no se aprobó ninguno, el que está
        en preparación."""
        self.ensure_one()
        Plan = self.env['construction.resource.plan']
        return (Plan.search([('project_id', '=', self.id), ('state', 'in', OPEN_STATES)], limit=1)
                or Plan.search([('project_id', '=', self.id), ('state', 'in', DRAFT_STATES)],
                               limit=1))

    def _construction_supervised_domain(self, user=None):
        """Obras del supervisor: las que tiene como responsable o como
        supervisor de obra."""
        user = user or self.env.user
        return ['|', ('user_id', '=', user.id), ('construction_supervisor_ids', 'in', user.ids)]

    def action_view_construction_plans(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Planes de recursos'),
            'res_model': 'construction.resource.plan',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_construction_typologies(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Tipologías'),
            'res_model': 'construction.typology',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def _compute_construction_current_plan_id(self):
        Plan = self.env['construction.resource.plan']
        for project in self:
            project.construction_current_plan_id = project._construction_current_plan() \
                if project.is_construction_site and project.id else Plan

    def _construction_plan_or_raise(self):
        self.ensure_one()
        plan = self._construction_current_plan()
        if not plan:
            raise UserError(self.env._('La obra %s aún no tiene plan de recursos.',
                                       self.display_name))
        return plan

    def action_construction_open_tree(self):
        return self._construction_plan_or_raise().action_open_tree()

    def action_construction_open_schedule(self):
        return self._construction_plan_or_raise().action_open_schedule()
