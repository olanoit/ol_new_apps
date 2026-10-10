# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .common import DRIVER_TYPES, LEVELS, ML_GROUPS, MODULE_TYPES, UNIT_STATE_RANK, UNIT_STATES

# Estados del módulo que pone el avance validado (y que su reversión quita).
PROGRESS_UNIT_STATES = ('produced', 'installed')
# Nivel inmediatamente superior de cada nivel (la obra es el proyecto).
PARENT_LEVEL = {'apartment': 'floor', 'space': 'apartment', 'module': 'space'}


class ProjectTask(models.Model):
    _inherit = 'project.task'

    construction_level = fields.Selection(
        LEVELS, string='Nivel de obra', index=True,
        help='Define la jerarquía del árbol del plan: piso › departamento › ambiente › módulo.')
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
                 'parent_id.construction_space_task_id')
    def _compute_construction_ancestors(self):
        for task in self:
            ancestors = {'floor': False, 'apartment': False, 'space': False}
            node = task
            # La obra tiene cinco niveles: como mucho cuatro saltos hacia arriba.
            for _depth in range(6):
                if not node:
                    break
                level = node.construction_level
                if level in ancestors and not ancestors[level]:
                    ancestors[level] = node
                node = node.parent_id
            task.construction_floor_task_id = ancestors['floor']
            task.construction_apartment_task_id = ancestors['apartment']
            task.construction_space_task_id = ancestors['space']

    @api.constrains('construction_level', 'parent_id')
    def _check_construction_level(self):
        """Un nivel cuelga del nivel inmediatamente superior (o de la obra si
        es piso). Las subtareas sin nivel no se validan."""
        for task in self:
            expected = PARENT_LEVEL.get(task.construction_level)
            if not expected:
                continue
            if task.parent_id.construction_level != expected:
                raise ValidationError(self.env._(
                    'La tarea %(task)s es de nivel %(level)s: debe colgar de un %(parent)s.',
                    task=task.display_name,
                    level=dict(LEVELS)[task.construction_level],
                    parent=dict(LEVELS)[expected].lower()))

    def _construction_plan_domain(self):
        """Líneas del plan vigente (o del borrador si no hay vigente) del nodo
        y de sus descendientes, por el ancestro almacenado de su nivel."""
        self.ensure_one()
        field = {
            'floor': 'floor_task_id', 'apartment': 'apartment_task_id',
            'space': 'space_task_id', 'module': 'module_task_id',
        }.get(self.construction_level)
        if not field:
            return [('task_id', '=', self.id)]
        plan = self.project_id._construction_current_plan()
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
            modules |= self.search([('parent_id', 'in', spaces.ids),
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
