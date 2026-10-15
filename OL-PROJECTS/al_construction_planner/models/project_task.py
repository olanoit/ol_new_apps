# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .common import (
    DRIVER_TYPES, LEVELS, ML_GROUPS, MODULE_TYPES, UNIT_STATE_RANK, UNIT_STATES, UNIT_TYPES,
)

# Estados del módulo que pone el avance validado (y que su reversión quita).
PROGRESS_UNIT_STATES = ('produced', 'installed')
# Nivel inmediatamente superior de cada nivel en una obra sin plantilla de
# niveles (la obra es el proyecto). Con plantilla manda su orden.
PARENT_LEVEL = {'apartment': ('floor',), 'space': ('apartment',), 'furniture': ('space',),
                'module': ('space', 'furniture')}


class ProjectTask(models.Model):
    _inherit = 'project.task'

    construction_level = fields.Selection(
        LEVELS, string='Nivel de obra', index=True,
        help='Función del nivel en el árbol del plan: agrupador, piso, unidad, ambiente, '
             'mueble o módulo. Con plantilla de niveles sale del nivel de la plantilla.')
    construction_level_line_id = fields.Many2one(
        'construction.level.template.line', string='Nivel', index=True,
        help='Nivel de la plantilla de la obra (Torre, Piso, Departamento…): da el nombre que '
             'se ve en el árbol y fija la función del nivel.')
    construction_level_name = fields.Char(
        string='Nombre del nivel', compute='_compute_construction_level_name')
    # Ruta de ids de los niveles desde el primero (v1.7, M17-01): «12/34/56/».
    # Base de la acumulación por cualquier nivel de la plantilla sin recorrer
    # el árbol (=like ruta%).
    construction_path = fields.Char(
        string='Ruta en la obra', compute='_compute_construction_path', store=True,
        recursive=True, index=True)
    construction_unit_type = fields.Selection(
        UNIT_TYPES, string='Tipo de unidad',
        help='Departamento, nivel de dúplex, ducto, estacionamiento, área común, depósito, '
             'local o piloto (solo en el nivel Unidad).')
    construction_furniture_ml = fields.Float(
        string='Metros lineales del mueble', digits=(16, 2),
        help='Los del mueble de la tipología; con módulos con ancho, el árbol suma sus anchos.')
    construction_override_ids = fields.One2many(
        'construction.unit.override', 'task_id', string='Variantes de la unidad',
        help='Otro color, un componente excluido o un metrado distinto que la tipología.')
    construction_furniture_task_id = fields.Many2one(
        'project.task', string='Mueble', compute='_compute_construction_ancestors', store=True,
        index=True, recursive=True)
    construction_floor_task_id = fields.Many2one(
        'project.task', string='Piso', compute='_compute_construction_ancestors', store=True,
        index=True, recursive=True)
    construction_apartment_task_id = fields.Many2one(
        'project.task', string='Departamento', compute='_compute_construction_ancestors',
        store=True, index=True, recursive=True)
    construction_space_task_id = fields.Many2one(
        'project.task', string='Ambiente', compute='_compute_construction_ancestors',
        store=True, index=True, recursive=True)
    construction_typology_id = fields.Many2one(
        'construction.typology', string='Tipología', index=True, check_company=True,
        domain="[('project_id', '=', project_id)]", help='Tipología del ambiente.')
    # Receta del nivel (v1.7, M17-04): la plantilla de ejecución y el metrado
    # planificado en su unidad (120 m² de muro drywall).
    construction_execution_template_id = fields.Many2one(
        'construction.execution.template', string='Receta', index=True, check_company=True,
        domain="['|', ('project_id', '=', False), ('project_id', '=', project_id)]",
        help='Plantilla de ejecución del nivel: «Generar plan desde la receta» multiplica sus '
             'recursos por el metrado.')
    construction_qty = fields.Float(
        string='Metrado planificado', digits='Product Unit',
        help='Cantidad del nivel en la unidad de su receta (m², und, ml, kg).')
    construction_qty_uom_id = fields.Many2one(
        related='construction_execution_template_id.uom_id', string='Unidad del metrado')
    construction_module_code = fields.Char(string='Código del módulo')
    construction_module_type = fields.Selection(MODULE_TYPES, string='Tipo de módulo')
    construction_width_mm = fields.Integer(string='Ancho (mm)')
    construction_ml_group = fields.Selection(ML_GROUPS, string='Grupo ML')
    construction_unit_state = fields.Selection(
        UNIT_STATES, string='Estado del módulo', tracking=True,
        help='Avance físico del módulo: planificado, en producción, producido, en obra, '
             'instalado y entregado.')
    construction_unit_state_base = fields.Selection(
        UNIT_STATES, string='Estado del módulo antes del avance', readonly=True, copy=False,
        help='El que tenía el módulo cuando el avance validado lo subió por primera vez: a él '
             'vuelve si se revierten esos avances.')
    construction_plan_line_ids = fields.One2many(
        'construction.resource.plan.line', 'task_id', string='Recursos del nivel')
    construction_plan_amount = fields.Monetary(
        string='Monto planificado', compute='_compute_construction_plan_amount',
        currency_field='construction_currency_id',
        help='Suma de las líneas del plan vigente de este nivel y de todo lo que tiene debajo.')
    construction_currency_id = fields.Many2one(
        related='company_id.currency_id', string='Moneda de la obra')
    # Pestaña «Recursos y avance» (P-09).
    construction_current_line_ids = fields.Many2many(
        'construction.resource.plan.line', string='Recursos del plan vigente',
        compute='_compute_construction_current_line_ids',
        help='Líneas del plan vigente de este nivel y de todo lo que tiene debajo.')
    construction_progress_ids = fields.One2many(
        'construction.task.progress', 'task_id', string='Avances reportados')
    construction_progress_pct = fields.Float(
        string='Avance valorizado', compute='_compute_construction_progress_pct',
        help='Σ ejecutado × costo unitario entre Σ monto planificado de las líneas de contrata '
             'y personal propio del nivel y sus descendientes.')

    @api.depends('parent_id', 'construction_level',
                 'parent_id.construction_floor_task_id',
                 'parent_id.construction_apartment_task_id',
                 'parent_id.construction_space_task_id',
                 'parent_id.construction_furniture_task_id')
    def _compute_construction_ancestors(self):
        for task in self:
            ancestors = {'floor': False, 'apartment': False, 'space': False, 'furniture': False}
            node = task
            # Hasta seis niveles bajo la obra y los agrupadores de la plantilla.
            for _depth in range(10):
                if not node:
                    break
                level = node.construction_level
                if level in ancestors and not ancestors[level]:
                    ancestors[level] = node
                node = node.parent_id
            task.construction_floor_task_id = ancestors['floor']
            task.construction_apartment_task_id = ancestors['apartment']
            task.construction_space_task_id = ancestors['space']
            task.construction_furniture_task_id = ancestors['furniture']

    def _construction_path_name(self):
        """Nombres de los niveles de la tarea, de arriba abajo: «Torre A › Piso 01
        › Dpto 101 › Cocina», «ARQ › ARQ-03 › Muro drywall RF»."""
        self.ensure_one()
        ids = [int(i) for i in (self.construction_path or '').split('/') if i]
        # sudo: solo los nombres de los niveles superiores de una tarea que el
        # usuario ya ve (el portal no lee las tareas de la obra).
        tasks_sudo = self.sudo().browse(ids)
        return ' › '.join(tasks_sudo.mapped('name')) or self.name

    @api.depends('parent_id.construction_path', 'construction_level')
    def _compute_construction_path(self):
        for task in self:
            if not task.construction_level or not isinstance(task.id, int):
                task.construction_path = False
                continue
            parent = task.parent_id.construction_path if task.parent_id.construction_level else ''
            task.construction_path = '%s%s/' % (parent or '', task.id)

    @api.depends('construction_level', 'construction_level_line_id.name')
    def _compute_construction_level_name(self):
        labels = dict(LEVELS)
        for task in self:
            task.construction_level_name = task.construction_level_line_id.name \
                or labels.get(task.construction_level, '')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._construction_level_from_line(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._construction_level_from_line(vals)
        if vals.get('stage_id'):
            self._construction_check_evidence_photo(self.env['project.task.type'].browse(vals['stage_id']))
        return super().write(vals)

    def _construction_check_evidence_photo(self, stage):
        """Las etapas que exigen foto de evidencia no aceptan tareas sin
        adjuntos (la foto del mueble con su etiqueta)."""
        if not stage.construction_requires_photo:
            return
        missing = self.filtered(lambda t: t.stage_id != stage and not t.message_attachment_count)
        if missing:
            raise UserError(_(
                'No se puede pasar «%(task)s» a «%(stage)s» sin adjuntar la foto de evidencia '
                '(el mueble con su etiqueta).', task=missing[0].display_name, stage=stage.name))

    @api.model
    def _construction_level_from_line(self, vals):
        """El nivel de la plantilla fija la función del nivel."""
        if vals.get('construction_level_line_id'):
            line = self.env['construction.level.template.line'].browse(
                vals['construction_level_line_id'])
            vals['construction_level'] = line.level

    @api.constrains('construction_level', 'parent_id', 'construction_level_line_id')
    def _check_construction_level(self):
        """Un nivel cuelga del nivel inmediatamente superior (o de la obra si
        es el primero). Con plantilla de niveles, del nivel anterior de la
        plantilla; sin ella, piso › departamento › ambiente › módulo. Las
        subtareas sin nivel no se validan."""
        for task in self:
            line = task.construction_level_line_id
            if line:
                previous = line._previous()
                if task.parent_id.construction_level_line_id != previous \
                        or (not previous and task.parent_id):
                    raise ValidationError(self.env._(
                        'La tarea %(task)s es de nivel %(level)s: debe colgar de %(parent)s.',
                        task=task.display_name, level=line.name,
                        parent=previous.name.lower() if previous else self.env._('la obra')))
                continue
            expected = PARENT_LEVEL.get(task.construction_level)
            if not expected:
                continue
            if task.parent_id.construction_level not in expected:
                raise ValidationError(self.env._(
                    'La tarea %(task)s es de nivel %(level)s: debe colgar de un %(parent)s.',
                    task=task.display_name,
                    level=dict(LEVELS)[task.construction_level],
                    parent=' o '.join(dict(LEVELS)[level].lower() for level in expected)))

    def _construction_group_names(self):
        """Nombres de los agrupadores (torre, etapa) por encima de la tarea,
        de arriba abajo: la ruta del importador."""
        self.ensure_one()
        names, node = [], self.parent_id
        while node and node.construction_level == 'group':
            names.insert(0, node.name)
            node = node.parent_id
        return tuple(names)

    def _construction_furniture_for(self, ml_group, module_type=False):
        """Mueble del ambiente donde va un módulo sin mueble en su plantilla:
        el de su grupo ML o, sin grupo, el de su tipo (mueble bajo o alto; los
        demás en «Otros muebles»)."""
        self.ensure_one()
        names = {'low': self.env._('Mueble bajo'), 'high': self.env._('Mueble alto')}
        key = ml_group if ml_group in names else module_type
        return self._construction_furniture_named(names.get(key, self.env._('Otros muebles')))

    def _construction_furniture_named(self, name, ml=0.0):
        """Mueble ``name`` del ambiente; se crea con el nivel Mueble de la
        plantilla de la obra si aún no existe."""
        self.ensure_one()
        furniture = self.search([('parent_id', '=', self.id),
                                 ('construction_level', '=', 'furniture'), ('name', '=', name)],
                                limit=1)
        if not furniture:
            furniture = self.with_context(mail_create_nolog=True, tracking_disable=True).create(dict(
                self.project_id._construction_level_vals('furniture'), name=name,
                project_id=self.project_id.id, parent_id=self.id, user_ids=False,
                construction_furniture_ml=ml))
        elif ml and not furniture.construction_furniture_ml:
            furniture.construction_furniture_ml = ml
        return furniture

    def _construction_overrides(self):
        """Variantes que aplican a un ambiente: las suyas y las de su unidad."""
        self.ensure_one()
        return self.construction_override_ids | self.construction_apartment_task_id.construction_override_ids

    def _construction_plan_domain(self):
        """Líneas del plan vigente (o del borrador si no hay vigente) del nodo
        y de sus descendientes, por el ancestro almacenado de su nivel."""
        self.ensure_one()
        field = {
            'floor': 'floor_task_id', 'apartment': 'apartment_task_id',
            'space': 'space_task_id', 'furniture': 'furniture_task_id',
            'module': 'module_task_id',
        }.get(self.construction_level)
        plan = self.project_id._construction_current_plan()
        if self.construction_level == 'group':
            # Agrupador (torre, etapa): lo de los pisos que tiene debajo.
            floors = self.search([('id', 'child_of', self.id), ('construction_level', '=', 'floor')])
            return [('floor_task_id', 'in', floors.ids), ('plan_id', '=', plan.id)]
        if not field:
            return [('task_id', '=', self.id)]
        return [(field, '=', self.id), ('plan_id', '=', plan.id)]

    def _compute_construction_plan_amount(self):
        Line = self.env['construction.resource.plan.line']
        for task in self:
            if not task.id or not task.construction_level:
                task.construction_plan_amount = 0.0
                continue
            result = Line._read_group(task._construction_plan_domain(), [], ['amount_planned:sum'])
            task.construction_plan_amount = result[0][0] if result else 0.0

    def _compute_construction_current_line_ids(self):
        Line = self.env['construction.resource.plan.line']
        for task in self:
            if not task.id or not task.construction_level:
                task.construction_current_line_ids = Line
                continue
            task.construction_current_line_ids = Line.search(task._construction_plan_domain())

    def _compute_construction_progress_pct(self):
        Plan = self.env['construction.resource.plan']
        for task in self:
            if not task.id or not task.construction_level:
                task.construction_progress_pct = 0.0
                continue
            executed, planned = Plan._progress_amounts(task._construction_plan_domain()).get(
                False, (0.0, 0.0))
            task.construction_progress_pct = executed / planned if planned else 0.0

    def _construction_update_unit_state(self, revert=False):
        """Estado del módulo por el avance validado (especificación, «Avance
        por driver»): con todo el armado del módulo hecho pasa a Producido;
        con todas sus actividades de instalación (del módulo o, si cuelgan
        del ambiente, de su ambiente), a Instalado. Validar solo lo hace
        subir. Al revertir (``revert``), un módulo que el avance había dejado
        en Producido o Instalado baja a lo que justifica el avance que queda
        o, si es mayor, al estado que tenía antes del avance."""
        modules = self.filtered(lambda t: t.construction_level == 'module')
        spaces = self.filtered(lambda t: t.construction_level == 'space')
        if spaces:
            modules |= self.search([('construction_space_task_id', 'in', spaces.ids),
                                    ('construction_level', '=', 'module')])
        Line = self.env['construction.resource.plan.line']
        for module in modules:
            plan = module.project_id._construction_current_plan()
            space = module.construction_space_task_id
            lines = Line.search([
                ('plan_id', '=', plan.id), ('resource_type', 'in', DRIVER_TYPES),
                '|', ('task_id', '=', module.id), ('task_id', '=', space.id)])
            assembly = lines.filtered(lambda l: l.stage == 'assembly' and l.task_id == module)
            installation = lines.filtered(lambda l: l.stage == 'installation')

            def complete(group):
                return bool(group) and all(
                    l.product_uom_id.compare(l.qty_executed, l.qty_planned) >= 0 for l in group)

            target = 'installed' if complete(installation) else \
                'produced' if complete(assembly) else False
            current = module.construction_unit_state or 'planned'
            # sudo: el estado lo mueve el sistema con el avance validado o
            # revertido; el supervisor puede no poder editar la tarea.
            module_sudo = module.sudo()
            if target and UNIT_STATE_RANK[target] > UNIT_STATE_RANK[current]:
                vals = {'construction_unit_state': target}
                if current not in PROGRESS_UNIT_STATES:
                    vals['construction_unit_state_base'] = current
                module_sudo.write(vals)
            elif revert and current in PROGRESS_UNIT_STATES and (
                    not target or UNIT_STATE_RANK[target] < UNIT_STATE_RANK[current]):
                base = module.construction_unit_state_base or 'planned'
                lower = max(target or 'planned', base, key=UNIT_STATE_RANK.get)
                if UNIT_STATE_RANK[lower] < UNIT_STATE_RANK[current]:
                    module_sudo.construction_unit_state = lower

    def action_construction_register_progress(self):
        """Registrar avance (W-07) de este nivel."""
        self.ensure_one()
        plan = self.project_id._construction_current_plan()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'al_construction_planner.action_plan_progress_wizard')
        action['context'] = {
            'default_plan_id': plan.id,
            'construction_selection_task_ids': self.ids,
        }
        return action


class ProjectTaskType(models.Model):
    _inherit = 'project.task.type'

    construction_requires_photo = fields.Boolean(
        string='Exige foto de evidencia',
        help='Una tarea solo pasa a esta etapa con al menos un adjunto (la foto del mueble '
             'con su etiqueta).')
