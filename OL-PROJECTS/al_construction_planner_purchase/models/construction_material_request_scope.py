# -*- coding: utf-8 -*-
"""Alcance del requerimiento de obra (RQ-01 a RQ-07, «Requerimiento de obra —
selección de nivel y etapa»).

Quien pide indica en el mismo requerimiento para qué niveles (piso,
departamento, ambiente, mueble o los de la plantilla de la obra), etapas y
tareas del Gantt es el material, y «Traer materiales del plan» llena el
requerimiento abierto con el saldo por pedir del plan vigente: una línea por
material, nivel y etapa, enlazada a sus líneas del plan.

El material de la etapa de fabricación (Producción) va a la preproducción de
la planta que elige quien pide; lo demás, a la ubicación de la obra.
"""
from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_construction_planner.models.common import LEVELS, stage_selection

# Selectores de nivel del formulario: uno por nivel de la plantilla, sin el
# nivel de detalle (módulo, actividad), hasta seis como los niveles del plan.
SCOPE_DEPTH = 6


def _scope_fields(namespace):
    """Campos de cada selector: lo elegido, su etiqueta (vacía: la obra no
    tiene ese nivel) y lo que se puede elegir según lo elegido arriba."""
    for depth in range(1, SCOPE_DEPTH + 1):
        namespace['construction_scope_%s_ids' % depth] = fields.Many2many(
            'project.task', 'construction_mat_request_scope_%s_rel' % depth,
            'request_id', 'task_id', string='Nivel %s elegido' % depth, copy=False,
            check_company=True,
            help='Vacío: todos los de este nivel bajo lo elegido arriba.')
        namespace['construction_scope_%s_label' % depth] = fields.Char(
            string='Nombre del nivel %s' % depth, compute='_compute_construction_scope')
        namespace['construction_scope_%s_allowed_ids' % depth] = fields.Many2many(
            'project.task', string='Nivel %s permitido' % depth,
            compute='_compute_construction_scope')


SCOPE_FIELDS = ['construction_scope_%s_ids' % depth for depth in range(1, SCOPE_DEPTH + 1)]


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_request_production_stage = fields.Boolean(
        string='Etapa Producción en el requerimiento de obra', default=True,
        help='Mientras la orden de fabricación del planificador no esté en uso, el jefe de '
             'producción pide su material por el requerimiento de obra eligiendo la etapa '
             'Producción; se despacha a la preproducción de la planta.')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_request_production_stage = fields.Boolean(
        related='company_id.construction_request_production_stage', readonly=False)


class StockLocation(models.Model):
    _inherit = 'stock.location'

    construction_preproduction = fields.Boolean(
        string='Preproducción de planta',
        help='Destino del material de la etapa Producción pedido por el requerimiento de obra '
             '(BRE/Preproducción, PPD/Preproducción).')


class ConstructionStage(models.Model):
    _inherit = 'construction.stage'

    @api.model
    def _construction_production_codes(self):
        """Códigos de las etapas de fabricación (taller): su material va a la
        preproducción de la planta."""
        return set(self.with_context(active_test=False).search(
            [('kind', '=', 'production')]).mapped('code'))

    @api.model
    def _construction_request_stages(self, company):
        """Etapas que se pueden elegir en el requerimiento: las que llevan
        recursos, sin las de fabricación si el ajuste de la compañía lo apaga."""
        stages = self.search([])
        if 'is_group' in self._fields:
            stages = stages.filtered(lambda stage: not stage.is_group)
        if not company.construction_request_production_stage:
            stages = stages.filtered(lambda stage: stage.kind != 'production')
        return stages


class ConstructionMaterialRequest(models.Model):
    _inherit = 'construction.material.request'

    _scope_fields(locals())

    construction_stage_ids = fields.Many2many(
        'construction.stage', 'construction_mat_request_stage_rel', 'request_id', 'stage_id',
        string='Etapas', copy=False,
        domain="[('id', 'in', construction_allowed_stage_ids)]",
        help='Vacío: todas. Cada línea guarda su etapa.')
    construction_allowed_stage_ids = fields.Many2many(
        'construction.stage', string='Etapas permitidas',
        compute='_compute_construction_allowed_stage_ids')
    construction_gantt_task_ids = fields.Many2many(
        'project.task', 'construction_mat_request_gantt_task_rel', 'request_id', 'task_id',
        string='Tareas del Gantt', copy=False, check_company=True,
        domain="[('project_id', '=', project_id), ('construction_level', '=', False)]",
        help='Tareas de la obra que no son niveles del planificador: no tienen líneas en el '
             'plan, el material se agrega a mano y cada línea queda con su tarea.')
    construction_production_location_id = fields.Many2one(
        'stock.location', string='Planta', check_company=True, tracking=True,
        domain="[('construction_preproduction', '=', True), ('usage', '=', 'internal')]",
        help='Preproducción de la planta que recibe el material de la etapa Producción. El '
             'costo sigue yendo a la obra por la analítica de la línea.')
    construction_needs_plant = fields.Boolean(
        string='Lleva material de producción', compute='_compute_construction_needs_plant')
    construction_has_levels = fields.Boolean(
        string='Obra con niveles', compute='_compute_construction_scope')
    # Valores por defecto de las líneas agregadas a mano.
    construction_default_stage = fields.Char(
        string='Etapa por defecto', compute='_compute_construction_line_defaults')
    construction_default_task_id = fields.Many2one(
        'project.task', string='Tarea por defecto', compute='_compute_construction_line_defaults')

    # ------------------------------------------------------------------
    # Selectores de nivel en cascada (RQ-01)
    # ------------------------------------------------------------------
    def _construction_scope_slots(self):
        """[(nombre, dominio)] de los niveles elegibles de la obra, de arriba
        abajo. Los nombres salen de la plantilla de niveles; sin plantilla, de
        los niveles del planificador. Un nivel sin tareas en la obra no sale
        (la obra de mobiliario sin muebles: los módulos cuelgan del ambiente)."""
        self.ensure_one()
        if not self.project_id:
            return []
        Task = self.env['project.task']
        template = self.project_id.construction_level_template_id
        if template:
            levels = template.line_ids.sorted(lambda l: (l.sequence, l.id)).filtered(
                lambda l: l.role != 'module')
            slots = [(line.name, [
                '|', ('construction_level_line_id', '=', line.id),
                '&', ('construction_level_line_id', '=', False),
                ('construction_level', '=', line.level)]) for line in levels]
        else:
            slots = [(label, [('construction_level', '=', level)])
                     for level, label in LEVELS if level != 'module']
        base = [('project_id', '=', self.project_id.id)]
        return [(name, base + domain) for name, domain in slots
                if Task.search_count(base + domain, limit=1)][:SCOPE_DEPTH]

    def _construction_scope_allowed(self, slots, depth):
        """Tareas que se pueden elegir en el nivel ``depth``: las de ese nivel
        que cuelgan de lo elegido en el nivel más bajo de arriba."""
        self.ensure_one()
        Task = self.env['project.task']
        if depth > len(slots):
            return Task
        domain = list(slots[depth - 1][1])
        for upper in range(depth - 1, 0, -1):
            chosen = self['construction_scope_%s_ids' % upper]
            if chosen:
                # En el onchange las tareas llegan como registros nuevos.
                domain.append(('id', 'child_of', chosen._origin.ids))
                break
        return Task.search(domain)

    @api.depends('project_id', *SCOPE_FIELDS)
    def _compute_construction_scope(self):
        for request in self:
            slots = request._construction_scope_slots()
            request.construction_has_levels = bool(slots)
            for depth in range(1, SCOPE_DEPTH + 1):
                request['construction_scope_%s_label' % depth] = \
                    slots[depth - 1][0] if depth <= len(slots) else False
                request['construction_scope_%s_allowed_ids' % depth] = \
                    request._construction_scope_allowed(slots, depth)

    @api.onchange('project_id')
    def _onchange_construction_scope_project(self):
        for name in SCOPE_FIELDS + ['construction_gantt_task_ids']:
            self[name] = self.env['project.task']

    @api.onchange(*SCOPE_FIELDS)
    def _onchange_construction_scope(self):
        """Lo elegido abajo que ya no cuelga de lo elegido arriba sale."""
        slots = self._construction_scope_slots()
        for depth in range(2, SCOPE_DEPTH + 1):
            name = 'construction_scope_%s_ids' % depth
            if self[name]:
                allowed = set(self._construction_scope_allowed(slots, depth).ids)
                self[name] = self[name].filtered(lambda task: task._origin.id in allowed)

    def _construction_scope_tasks(self):
        """Lo elegido en el nivel más bajo; ``None`` si no se eligió nada (toda
        la obra)."""
        self.ensure_one()
        for depth in range(SCOPE_DEPTH, 0, -1):
            chosen = self['construction_scope_%s_ids' % depth]
            if chosen:
                return chosen
        return None

    # ------------------------------------------------------------------
    # Etapas (RQ-02) y tareas del Gantt (RQ-03)
    # ------------------------------------------------------------------
    @api.depends('company_id')
    def _compute_construction_allowed_stage_ids(self):
        Stage = self.env['construction.stage']
        for request in self:
            request.construction_allowed_stage_ids = Stage._construction_request_stages(
                request.company_id)

    def _construction_scope_stage_codes(self):
        """Códigos de las etapas elegidas (vacío: las permitidas)."""
        self.ensure_one()
        stages = self.construction_stage_ids & self.construction_allowed_stage_ids \
            or self.construction_allowed_stage_ids
        return stages.mapped('code')

    @api.depends('construction_stage_ids', 'construction_gantt_task_ids')
    def _compute_construction_line_defaults(self):
        for request in self:
            stages = request.construction_stage_ids
            request.construction_default_stage = stages.code if len(stages) == 1 else False
            tasks = request.construction_gantt_task_ids
            request.construction_default_task_id = tasks if len(tasks) == 1 else False

    @api.depends('construction_stage_ids', 'line_ids.construction_stage')
    def _compute_construction_needs_plant(self):
        codes = self.env['construction.stage']._construction_production_codes()
        for request in self:
            request.construction_needs_plant = bool(
                codes & set(request.construction_stage_ids.mapped('code'))
                or request.line_ids.filtered(
                    lambda l: not l.cancelled and l.construction_stage in codes))

    # ------------------------------------------------------------------
    # Traer materiales del plan (RQ-04)
    # ------------------------------------------------------------------
    def _construction_line_analytic(self, plan_lines):
        """La analítica de las líneas del plan pasa a la línea si todas
        coinciden (como el asistente «Requerimiento de obra desde el plan»)."""
        distributions = {tuple(sorted((line.analytic_distribution or {}).items()))
                         for line in plan_lines}
        if len(distributions) == 1 and next(iter(distributions)):
            return {'analytic_distribution': dict(next(iter(distributions)))}
        return {}

    def _construction_fetch_groups(self):
        """{(nivel, producto, etapa): líneas del plan} del alcance elegido: el
        nivel es lo elegido en el nivel más bajo (la obra si no se eligió
        nada)."""
        self.ensure_one()
        # sudo: quien pide (residente, supervisor) no ve el plan; solo se leen
        # las líneas del plan vigente de su obra para traer su saldo.
        plan_sudo = self.construction_plan_id.sudo()
        domain = [('plan_id', '=', plan_sudo.id), ('resource_type', '=', 'material'),
                  ('product_id', '!=', False),
                  ('stage', 'in', self._construction_scope_stage_codes())]
        tasks = self._construction_scope_tasks()
        if tasks is not None:
            domain.append(('task_id', 'child_of', tasks.ids))
        Task = self.env['project.task']
        chosen = set(tasks.ids) if tasks is not None else set()
        groups = defaultdict(lambda: self.env['construction.resource.plan.line'].sudo())
        for line in self.env['construction.resource.plan.line'].sudo().search(domain):
            if line.product_id.type != 'consu':
                continue
            level = Task
            if chosen:
                path = [int(i) for i in (line.task_path or '').split('/') if i]
                level = Task.browse(next((i for i in path if i in chosen), line.task_id.id))
            groups[(level, line.product_id, line.stage)] |= line
        return groups

    def action_construction_fetch_plan(self):
        """«Traer materiales del plan»: una línea por material, nivel y etapa
        con el saldo por pedir, enlazada a sus líneas del plan. Lo ya traído no
        se repite."""
        self.ensure_one()
        self._check_state(('draft',))
        if not self.construction_plan_id:
            raise UserError(self.env._(
                'La obra %s no tiene un plan de recursos vigente: agregue los materiales a mano.',
                self.project_id.display_name))
        existing = {(line.task_id, line.product_id, line.construction_stage)
                    for line in self.line_ids.filtered(lambda l: not l.cancelled)}
        values, shares_by_key = [], []
        for (level, product, stage), plan_lines in sorted(
                self._construction_fetch_groups().items(),
                key=lambda kv: (kv[0][0]._construction_path_name() if kv[0][0] else '',
                                kv[0][2] or '', kv[0][1].display_name)):
            if (level, product, stage) in existing:
                continue
            remaining = sum(line._qty_to_product_uom(line.qty_planned - line.qty_requested)
                            for line in plan_lines)
            if product.uom_id.compare(remaining, 0.0) <= 0:
                continue
            values.append(dict({
                'request_id': self.id,
                'product_id': product.id,
                'product_qty': remaining,
                'product_uom_id': product.uom_id.id,
                'task_id': level.id,
                'construction_stage': stage,
            }, **self._construction_line_analytic(plan_lines)))
            shares_by_key.append(plan_lines._supply_split(remaining))
        if not values:
            raise UserError(self.env._(
                'No queda saldo por pedir en el plan para esta selección de niveles y etapas.'))
        new_lines = self.env['construction.material.request.line'].create(values)
        # sudo: las asignaciones al plan son del planificador; quien pide solo
        # enlaza las líneas de su propio requerimiento (como al solicitar la
        # aprobación, _construction_sync_allocations).
        self.env['construction.resource.plan.allocation'].sudo().create([{
            'plan_line_id': plan_line.id,
            'kind': 'material_request',
            'material_request_line_id': request_line.id,
            'qty_allocated': share,
        } for request_line, shares in zip(new_lines, shares_by_key)
            for plan_line, share in shares.items() if not plan_line.product_uom_id.is_zero(share)])
        if not self.date_required:
            dates = [line.date_needed for shares in shares_by_key for line in shares
                     if line.date_needed]
            if dates:
                self.date_required = min(dates)
        self.construction_plan_id.sudo()._mark_in_progress()
        self.message_post(body=self.env._(
            '%(count)s materiales traídos del plan %(plan)s.',
            count=len(new_lines), plan=self.construction_plan_id.sudo().display_name))
        return True

    # ------------------------------------------------------------------
    # Material de producción (RQ-07)
    # ------------------------------------------------------------------
    def _check_ready_to_submit(self):
        super()._check_ready_to_submit()
        codes = self.env['construction.stage']._construction_production_codes()
        for request in self:
            production = request.line_ids.filtered(
                lambda l: not l.cancelled and l.construction_stage in codes)
            if not production:
                continue
            if not request.company_id.construction_request_production_stage:
                raise UserError(self.env._(
                    'El material de producción se pide con la orden de fabricación: quite la '
                    'etapa Producción de las líneas de %s.', request.name))
            if not request.construction_production_location_id:
                raise UserError(self.env._(
                    'Elija la planta que recibe el material de producción de %s.',
                    request.name))


class ConstructionMaterialRequestLine(models.Model):
    _inherit = 'construction.material.request.line'

    construction_stage = fields.Selection(
        stage_selection, string='Etapa',
        help='Etapa del plan para la que es el material. La de fabricación va a la '
             'preproducción de la planta.')
    construction_level_label = fields.Char(
        string='Nivel', compute='_compute_construction_level_label',
        help='El nivel de la línea y el de arriba, por ejemplo «Dpto 102 / Cocina».')

    @api.depends('task_id.name', 'task_id.parent_id.name', 'task_id.construction_level')
    def _compute_construction_level_label(self):
        for line in self:
            task = line.task_id
            parent = task.parent_id
            if task.construction_level and parent.construction_level:
                line.construction_level_label = '%s / %s' % (parent.name, task.name)
            else:
                line.construction_level_label = task.name or False

    def _construction_candidate_plan_lines(self, plan):
        """Una línea con etapa solo se compara con las líneas del plan de esa
        etapa (las ya enlazadas mandan)."""
        lines = super()._construction_candidate_plan_lines(plan)
        assigned = self.construction_allocation_ids.plan_line_id.filtered(
            lambda l: l.plan_id == plan)
        if self.construction_stage and not assigned:
            lines = lines.filtered(lambda l: l.stage == self.construction_stage)
        return lines

    @api.depends('construction_stage')
    def _compute_construction_plan_control(self):
        return super()._compute_construction_plan_control()

    @api.depends('construction_stage', 'request_id.construction_production_location_id')
    def _compute_location_dest_id(self):
        return super()._compute_location_dest_id()

    def _get_default_location_dest(self):
        plant = self.request_id.construction_production_location_id
        if plant and self.construction_stage and self.construction_stage in \
                self.env['construction.stage']._construction_production_codes():
            return plant
        return super()._get_default_location_dest()
