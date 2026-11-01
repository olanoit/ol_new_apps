# -*- coding: utf-8 -*-
"""Etapa actual y plazo de cada ambiente (paquete 1.15, M115-04, con
M116-01 y M116-02 del paquete 1.16).

El ambiente es la tarea que tiene etapas (``construction.space.stage``). Su
etapa actual se guarda para el informe «Etapa de los ambientes» (M115-05) y
los filtros del Cronograma. Se recalcula con un método explícito: el avance
de cada etapa es un cálculo sobre las líneas del plan y los avances validados
que el ORM no puede seguir solo. Lo llaman el control de las líneas del plan
(avances, cambios de plan, acción programada), el cambio de fechas de una
etapa, la marca «Ambiente medido» y el estado de los módulos.

Árbol 1 · etapa actual. Pendiente, Medido y Entregado solo existen si el
perfil de la obra mide sus ambientes (``_construction_space_state_labels``):

1. todas las etapas al 100 % y todos los módulos entregados: Entregado; sin
   esos estados, la última etapa al 100 %;
2. si no, la primera etapa (por secuencia) con avance menor a 100 %; si es la
   primera de todas y su avance es 0: Medido o Pendiente; si no, esa etapa.

Árbol 2 · plazo de la etapa actual (depende de hoy: no se guarda):
terminado, sin fechas, atrasada (fin vencido), en riesgo (debía iniciar, o el
avance esperado por días hábiles supera al real en más del margen de
Ajustes) o a tiempo."""
from odoo import api, fields, models
from odoo.fields import Domain

from .common import UNIT_STATE_RANK

# Estados del ambiente que no son etapas del catálogo, con su color fijo
# (gris, azul y verde).
SPACE_STATE_CODES = ('pending', 'measured', 'delivered')
SPACE_STATE_COLORS = {'pending': '#9e9e9e', 'measured': '#3d85c6', 'delivered': '#2e7d32'}
SCHEDULE_STATES = [
    ('on_time', 'A tiempo'),
    ('risk', 'En riesgo'),
    ('late', 'Atrasada'),
    ('done', 'Terminado'),
    ('no_dates', 'Sin fechas'),
]
#: Orden de gravedad del plazo (el peor de los ambientes de un piso).
SCHEDULE_RANK = {'late': 4, 'risk': 3, 'on_time': 2, 'no_dates': 1, 'done': 0}
COMPLETE = 0.9999


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_stage_risk_margin = fields.Integer(
        string='Margen de «en riesgo»', default=20,
        help='Puntos de avance: la etapa actual de un ambiente está en riesgo si el avance '
             'esperado por los días hábiles transcurridos supera al real en más de este margen.')

    # Carga semanal, plan frente a ejecutado (paquete 1.15, M115-06).
    construction_load_green_pct = fields.Integer(
        string='Carga semanal: verde desde', default=95,
        help='Porcentaje de lo ejecutado frente a lo planificado desde el que la semana sale '
             'en verde.')
    construction_load_amber_pct = fields.Integer(
        string='Carga semanal: ámbar desde', default=70,
        help='Desde este porcentaje la semana sale en ámbar; debajo, en rojo.')

    def _construction_space_state_names(self):
        """{'pending', 'measured', 'delivered': nombre} para la lista de
        estados del ambiente; el puente de mobiliario da los de Ajustes."""
        return {'pending': self.env._('Pendiente'), 'measured': self.env._('Medido'),
                'delivered': self.env._('Entregado')}


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_stage_risk_margin = fields.Integer(
        related='company_id.construction_stage_risk_margin', readonly=False)
    construction_load_green_pct = fields.Integer(
        related='company_id.construction_load_green_pct', readonly=False)
    construction_load_amber_pct = fields.Integer(
        related='company_id.construction_load_amber_pct', readonly=False)


class ProjectProject(models.Model):
    _inherit = 'project.project'

    def _construction_space_state_labels(self):
        """Estados del ambiente que no son etapas (M116-02): ninguno en el
        núcleo; el puente de mobiliario los da si el perfil mide ambientes."""
        self.ensure_one()
        return {}


class ProjectTask(models.Model):
    _inherit = 'project.task'

    construction_current_stage = fields.Selection(
        selection='_selection_construction_current_stage', string='Etapa actual',
        readonly=True, copy=False, index=True,
        help='Etapa en la que está el ambiente: la primera sin terminar, o Pendiente, Medido o '
             'Entregado si la obra mide sus ambientes.')
    construction_current_stage_progress = fields.Float(
        string='Avance de la etapa actual', readonly=True, copy=False, aggregator='avg')
    construction_current_stage_start = fields.Date(
        string='Inicio de la etapa actual', readonly=True, copy=False)
    construction_current_stage_end = fields.Date(
        string='Fin de la etapa actual', readonly=True, copy=False)
    construction_current_partner_id = fields.Many2one(
        'res.partner', string='Contrata de la etapa actual', readonly=True, copy=False,
        index='btree_not_null')
    construction_stage_schedule = fields.Selection(
        SCHEDULE_STATES, string='Plazo', compute='_compute_construction_stage_schedule',
        search='_search_construction_stage_schedule')
    construction_stage_schedule_label = fields.Char(
        string='Plazo (detalle)', compute='_compute_construction_stage_schedule')
    # Dos primeros niveles de la plantilla de la obra (M115-05): piso y
    # departamento en mobiliario; especialidad y sub-especialidad en
    # construcción por partidas.
    construction_level1_task_id = fields.Many2one(
        'project.task', string='Nivel 1', compute='_compute_construction_top_levels',
        store=True, recursive=True, index='btree_not_null')
    construction_level2_task_id = fields.Many2one(
        'project.task', string='Nivel 2', compute='_compute_construction_top_levels',
        store=True, recursive=True, index='btree_not_null')

    @api.model
    def _selection_construction_current_stage(self):
        names = self.env.company._construction_space_state_names()
        stages = self.env['construction.stage'].with_context(active_test=False)._leaf_stages()
        return ([('pending', names['pending']), ('measured', names['measured'])]
                + [(stage.code, stage._label()) for stage in stages]
                + [('delivered', names['delivered'])])

    @api.depends('construction_level', 'parent_id.construction_level',
                 'parent_id.construction_level1_task_id', 'parent_id.construction_level2_task_id')
    def _compute_construction_top_levels(self):
        for task in self:
            parent = task.parent_id if task.parent_id.construction_level else self.browse()
            if not task.construction_level:
                task.construction_level1_task_id = task.construction_level2_task_id = False
            elif not parent:
                task.construction_level1_task_id = task
                task.construction_level2_task_id = False
            else:
                task.construction_level1_task_id = parent.construction_level1_task_id or parent
                task.construction_level2_task_id = parent.construction_level2_task_id or task

    # ------------------------------------------------------------------
    # Etapa actual (árbol 1)
    # ------------------------------------------------------------------
    def _construction_space_measured(self):
        """¿El ambiente está medido? El núcleo no mide ambientes; lo dice el
        puente de mobiliario («Ambiente medido»)."""
        self.ensure_one()
        return False

    @api.model
    def _construction_current_stage_trigger_fields(self):
        """Campos de la tarea que cambian la etapa actual de su ambiente."""
        return {'construction_unit_state'}

    def _construction_refresh_current_stage(self):
        """Recalcula y guarda la etapa actual de los ambientes de ``self``
        (las tareas sin etapas quedan vacías)."""
        spaces = self.exists().filtered(lambda t: t.construction_level)
        if not spaces:
            return
        SpaceStage = self.env['construction.space.stage'].sudo()
        Plan = self.env['construction.resource.plan']
        catalog = {stage.code: stage for stage in self.env['construction.stage'].with_context(
            active_test=False).search([])}
        updates = {}
        for project in spaces.project_id:
            group = spaces.filtered(lambda s, project=project: s.project_id == project)
            records = SpaceStage.search([('space_task_id', 'in', group.ids)])
            plan = project._construction_current_plan()
            # {(ambiente, etapa): (ejecutado, planificado)} de contratas y
            # personal propio, una consulta por etapa (no por ambiente).
            amounts = {}
            if plan:
                for code in set(records.mapped('stage')):
                    stage_spaces = records.filtered(lambda r, code=code: r.stage == code).space_task_id
                    for space_id, values in Plan._progress_amounts(
                            [('plan_id', '=', plan.id), ('stage', '=', code),
                             ('space_task_id', 'in', stage_spaces.ids)],
                            'space_task_id').items():
                        amounts[(space_id, code)] = values
            resources = SpaceStage._resources_by_stage(records)
            labels = project._construction_space_state_labels()
            by_space = {}
            for record in records:
                by_space.setdefault(record.space_task_id.id, []).append(record)
            for space in group:
                stages = sorted(by_space.get(space.id, []), key=lambda r: (
                    catalog[r.stage]._tree_key() if r.stage in catalog else (9999,), r.id))
                progress = space._construction_stage_ratios(stages, amounts, catalog)
                updates[space] = space._construction_current_stage_values(
                    stages, progress, resources, labels)
        for space, vals in updates.items():
            if any(space[key] != value for key, value in vals.items()):
                # sudo: la etapa actual la mueve el sistema con el avance, las
                # fechas o la medida; quien los registra puede no editar la tarea.
                space.sudo().with_context(construction_current_stage_refresh=True).write(vals)

    def _construction_stage_ratios(self, stages, amounts, catalog):
        """{(ambiente, etapa): avance} de las etapas del ambiente, en orden.

        Una etapa con contratas o personal propio tiene el avance de sus
        líneas. Una sin ellas (la producción en taller de mobiliario) no se
        mide: una etapa de fabricación está terminada si todos los módulos
        del ambiente ya salieron de producción; cualquier etapa sin líneas
        está terminada si alguna etapa siguiente ya tiene avance."""
        self.ensure_one()
        ratios, unmeasured = {}, []
        modules = self.search([('construction_space_task_id', '=', self.id),
                               ('construction_level', '=', 'module')])
        produced = bool(modules) and all(
            UNIT_STATE_RANK.get(module.construction_unit_state or 'planned', 0)
            >= UNIT_STATE_RANK['produced'] for module in modules)
        for record in stages:
            executed, planned = amounts.get((self.id, record.stage), (0.0, 0.0))
            key = (self.id, record.stage)
            if planned:
                ratios[key] = round(executed / planned, 4)
                if ratios[key] > 0:
                    for previous in unmeasured:
                        ratios[previous] = 1.0
                    unmeasured = []
                continue
            stage = catalog.get(record.stage)
            if stage and stage.kind == 'production' and produced:
                ratios[key] = 1.0
            else:
                ratios[key] = 0.0
                unmeasured.append(key)
        return ratios

    def _construction_current_stage_values(self, stages, progress, resources, labels):
        """Valores guardados de la etapa actual (árbol 1)."""
        self.ensure_one()
        empty = {'construction_current_stage': False, 'construction_current_stage_progress': 0.0,
                 'construction_current_stage_start': False, 'construction_current_stage_end': False,
                 'construction_current_partner_id': False}
        if not stages:
            return empty

        def ratio(record):
            return progress.get((self.id, record.stage), 0.0)

        current = next((record for record in stages if ratio(record) < COMPLETE), None)
        if current is None:
            last = stages[-1]
            vals = dict(empty, construction_current_stage_progress=100.0,
                        construction_current_stage_start=last.date_start,
                        construction_current_stage_end=last.date_end)
            if labels and self._construction_modules_delivered():
                vals['construction_current_stage'] = 'delivered'
            else:
                vals['construction_current_stage'] = last.stage
            return vals
        pct = round(ratio(current) * 100, 1)
        code = current.stage
        if labels and current == stages[0] and not pct:
            code = 'measured' if self._construction_space_measured() else 'pending'
        partner = resources.get((self.id, current.stage), {}).get('partner')
        return {
            'construction_current_stage': code,
            'construction_current_stage_progress': pct,
            'construction_current_stage_start': current.date_start,
            'construction_current_stage_end': current.date_end,
            'construction_current_partner_id': partner.id if partner else False,
        }

    def _construction_modules_delivered(self):
        """Todos los módulos del ambiente entregados (sin módulos: sí)."""
        self.ensure_one()
        modules = self.search([('construction_space_task_id', '=', self.id),
                               ('construction_level', '=', 'module')])
        return all(module.construction_unit_state == 'delivered' for module in modules)

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('construction_current_stage_refresh') \
                and self._construction_current_stage_trigger_fields() & set(vals):
            spaces = self.mapped('construction_space_task_id') | self.filtered(
                lambda t: t.construction_stage_ids)
            spaces._construction_refresh_current_stage()
        return res

    # ------------------------------------------------------------------
    # Plazo (árbol 2)
    # ------------------------------------------------------------------
    @api.depends('construction_current_stage', 'construction_current_stage_progress',
                 'construction_current_stage_start', 'construction_current_stage_end')
    @api.depends_context('construction_today')
    def _compute_construction_stage_schedule(self):
        today = self._construction_today()
        for task in self:
            state, label = task._construction_schedule(today)
            task.construction_stage_schedule = state
            task.construction_stage_schedule_label = label

    def _construction_today(self):
        today = self.env.context.get('construction_today')
        return fields.Date.to_date(today) if today else fields.Date.context_today(self)

    def _construction_schedule(self, today):
        """(estado, texto) del plazo de la etapa actual."""
        self.ensure_one()
        code = self.construction_current_stage
        if not code:
            return False, ''
        pct = self.construction_current_stage_progress
        if code == 'delivered' or pct >= 100:
            return 'done', self.env._('terminado')
        start, end = self.construction_current_stage_start, self.construction_current_stage_end
        if not start or not end:
            return 'no_dates', self.env._('sin fechas')
        if today > end:
            return 'late', self.env._('atrasada %s d', (today - end).days)
        if today < start:
            return 'on_time', self.env._('inicia %s', start.strftime('%d/%m'))
        if not pct:
            return 'risk', self.env._('debía iniciar %s', start.strftime('%d/%m'))
        company = self.company_id or self.env.company
        total = company._construction_count_site_days(start, end) or 1
        elapsed = company._construction_count_site_days(start, today)
        expected = min(100.0, 100.0 * elapsed / total)
        if expected - pct > company.construction_stage_risk_margin:
            return 'risk', self.env._('en riesgo · esperado %s %%', round(expected))
        return 'on_time', self.env._('a tiempo')

    def _search_construction_stage_schedule(self, operator, value):
        if operator not in ('in', 'not in'):
            return NotImplemented
        values = set(value or [])
        candidates = self.search([('construction_current_stage', '!=', False)])
        today = self._construction_today()
        ids = [task.id for task in candidates if task._construction_schedule(today)[0] in values]
        return Domain('id', operator, ids)

    # ------------------------------------------------------------------
    # Datos del Cronograma
    # ------------------------------------------------------------------
    @api.model
    def _construction_space_states(self):
        """Estados del ambiente en orden, con su color, para el Cronograma:
        [{code, label, color}]. Sin estados de mobiliario, solo las etapas."""
        colors = {stage.code: stage.color for stage in self.env['construction.stage'].with_context(
            active_test=False).search([])}
        result = []
        for code, label in self._selection_construction_current_stage():
            result.append({'code': code, 'label': label,
                           'color': SPACE_STATE_COLORS.get(code) or colors.get(code) or '#3d85c6',
                           'is_state': code in SPACE_STATE_CODES})
        return result


class ConstructionSpaceStage(models.Model):
    _inherit = 'construction.space.stage'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.space_task_id._construction_refresh_current_stage()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {'date_start', 'date_end', 'stage', 'space_task_id'} & set(vals):
            self.space_task_id._construction_refresh_current_stage()
        return res

    def unlink(self):
        spaces = self.space_task_id
        res = super().unlink()
        spaces._construction_refresh_current_stage()
        return res


class ConstructionResourcePlanLine(models.Model):
    _inherit = 'construction.resource.plan.line'

    def _refresh_control(self):
        res = super()._refresh_control()
        # El avance de las etapas cambia con el control de las líneas
        # (avances validados o revertidos, nuevas versiones del plan).
        lines = self.sudo().exists().filtered(
            lambda l: l.resource_type in ('contract', 'labor') and l.space_task_id)
        lines.space_task_id._construction_refresh_current_stage()
        return res
