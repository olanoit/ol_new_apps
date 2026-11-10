# -*- coding: utf-8 -*-
"""Inicio de la aplicación (P-01, fase 11): las obras con su plan, saldo,
avance, próximo hito y estado, y «Pendientes de hoy» según los grupos del
usuario. Cada pendiente es un filtro sobre los documentos que las reglas dejan
pendientes y abre esa lista filtrada; solo se muestran los que el usuario
puede atender."""
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date
from odoo.tools.safe_eval import safe_eval

from .common import can_see_amounts

GROUP = 'al_construction_planner.group_planner_'
#: Días hacia adelante para las etapas sin contrata (P-01).
STAGE_HORIZON_DAYS = 14
#: Áreas de los pendientes (paquete 7 de CREVAL, CR-65), en orden.
PENDING_AREAS = [
    ('site', 'Obra'),
    ('planning', 'Planificación'),
    ('purchase', 'Compras'),
    ('contracts', 'Contratas'),
    ('revenue', 'Ingresos'),
    ('other', 'Otros'),
]


class ConstructionPlannerHome(models.AbstractModel):
    _name = 'construction.planner.home'
    _description = 'Inicio de la planificación de obra'

    # ------------------------------------------------------------------
    # Obras
    # ------------------------------------------------------------------
    @api.model
    def _get_works(self, today):
        Plan = self.env['construction.resource.plan']
        plans = Plan.search([('state', 'not in', ('cancel', 'replaced'))])
        states = dict(Plan._fields['state']._description_selection(self.env))
        works = []
        show_amounts = can_see_amounts(self.env)
        mine = self._my_project_ids()
        for project in plans.project_id.sorted('name'):
            # CR-59: una obra con el plan cerrado sigue en la cartera
            # (Postventa).
            plan = project._construction_portfolio_plan()
            if not plan:
                continue
            approved = plan.state not in ('draft', 'to_approve')
            amounts = Plan._progress_amounts([('plan_id', '=', plan.id)])
            milestone = self._next_milestone(project, plan, today)
            works.append({
                **self._work_portfolio_values(project, plan, mine),
                'project_id': project.id,
                'project_name': project.display_name,
                'plan_id': plan.id,
                'plan_name': '%s · v%s' % (plan.name, plan.version),
                'period': '%s → %s' % (format_date(self.env, plan.date_start, date_format='dd/MM'),
                                       format_date(self.env, plan.date_end, date_format='dd/MM')),
                'amount_total': plan.amount_total if approved and show_amounts else False,
                'amount_remaining': plan.amount_remaining if approved and show_amounts
                else False,
                'progress': Plan._progress_ratio(amounts, False) if approved else False,
                'milestone': milestone['label'],
                'milestone_date': milestone['date'] and fields.Date.to_string(milestone['date']),
                'state': plan.state,
                'state_label': states[plan.state],
                'currency_symbol': plan.currency_id.symbol,
            })
        return works

    @api.model
    def _my_project_ids(self):
        """Ids de «Mis obras» (CR-59): las que el usuario supervisa
        (``_construction_supervised_domain``)."""
        Project = self.env['project.project']
        return set(Project.search(Project._construction_supervised_domain(self.env.user)).ids)

    @api.model
    def _work_portfolio_values(self, project, plan, mine):
        """Datos de la obra en la cartera (paquete 7 de CREVAL, CR-59): etapa,
        favorita, cliente, fechas y los indicadores que aporte el puente de
        ventas (``_work_indicators``)."""
        start = project.date_start or (plan and plan.date_start)
        end = project.date or (plan and plan.date_end)
        return {
            'stage': project._construction_portfolio_stage(plan),
            'is_favorite': project.is_favorite,
            'mine': project.id in mine,
            'partner': project.partner_id.display_name or '',
            'date_start': fields.Date.to_string(start) if start else False,
            'date_end': fields.Date.to_string(end) if end else False,
            'dates': '%s → %s' % (format_date(self.env, start, date_format='dd/MM/yy'),
                                  format_date(self.env, end, date_format='dd/MM/yy'))
            if start and end else '',
            'indicators': self._work_indicators(project, plan),
        }

    @api.model
    def _work_indicators(self, project, plan):
        """Indicadores de la obra en la cartera; los aporta el puente de
        ventas. Sin él, ``False`` y el Inicio muestra la tabla de planes."""
        return False

    def _get_unplanned_works(self):
        """Paquete 1.17, M117-09: las obras todavía sin plan, la más antigua
        primero. Lo que aporta cada puente sale del gancho de la obra."""
        Plan = self.env['construction.resource.plan']
        planned = Plan.search([('state', 'not in', ('cancel', 'replaced'))]).project_id
        projects = self.env['project.project'].search([
            ('is_construction_site', '=', True), ('id', 'not in', planned.ids),
            ('is_template', '=', False)], order='create_date, id')
        mine = self._my_project_ids()
        return [dict(project._construction_home_extra(), project_id=project.id,
                     project_name=project.display_name, stage='planning',
                     is_favorite=project.is_favorite, mine=project.id in mine)
                for project in projects]

    @api.model
    def _next_milestone(self, project, plan, today):
        """El hito más cercano desde hoy entre corte, presentación,
        confirmación, factura y cobro de las valorizaciones previstas (P-21)
        y fin de etapa (P-15). Un plan sin aprobar tiene como hito aprobarlo."""
        if plan.state == 'draft':
            return {'label': self.env._('Aprobar el plan'), 'date': False}
        if plan.state == 'to_approve':
            return {'label': self.env._('Aprobación del plan'), 'date': False}
        candidates = self._next_milestone_candidates(project, today)
        stage = self.env['construction.space.stage'].search(
            [('project_id', '=', project.id), ('date_end', '>=', today)],
            order='date_end, sequence', limit=1)
        if stage:
            stage_label = dict(stage._fields['stage']._description_selection(self.env))
            candidates.append((stage.date_end, self.env._(
                'Fin de %(stage)s · %(space)s', stage=stage_label[stage.stage].lower(),
                space=stage.space_task_id.display_name)))
        if not candidates:
            return {'label': self.env._('Cerrar el plan') if plan.state == 'in_progress'
                    else '', 'date': False}
        day, label = min(candidates, key=lambda c: c[0])
        return {'label': '%s %s' % (label, format_date(self.env, day, date_format='dd/MM')),
                'date': day}

    @api.model
    def _next_milestone_candidates(self, project, today):
        """[(fecha, etiqueta)] de los hitos de la obra desde hoy: el puente de
        ventas agrega los de las valorizaciones previstas."""
        return []

    # ------------------------------------------------------------------
    # Pendientes de hoy
    # ------------------------------------------------------------------
    @api.model
    def _supervised_projects(self):
        """Obras del supervisor o ``None`` si no supervisa ninguna (ve todo).
        La Jefatura (Administrador) ve todas."""
        user = self.env.user
        if user.has_group(GROUP + 'manager'):
            return None
        Project = self.env['project.project']
        projects = Project.search(Project._construction_supervised_domain(user))
        return projects or None

    @api.model
    def _pending_mine(self):
        """Dominio de las obras del supervisor (vacío: todas)."""
        supervised = self._supervised_projects()
        return [('project_id', 'in', supervised.ids)] if supervised is not None else []

    @api.model
    def _pending_definitions(self, today):
        """Pendientes posibles: (clave, grupo, etiqueta, dónde, modelo,
        dominio, acción base). El dominio puede ser una función (se calcula
        solo para quien atiende el pendiente) y, en las alertas de
        abastecimiento, el tipo de alerta."""
        mine = self._pending_mine()
        soon = today + timedelta(days=STAGE_HORIZON_DAYS)
        return [
            ('progress_to_validate', 'planner', self.env._('Avances reportados por validar'),
             self.env._('Avance'), 'construction.task.progress',
             [('state', '=', 'draft')] + mine,
             'al_construction_planner.action_construction_progress_to_validate'),
            ('stages_without_contract', 'planner',
             self.env._('Etapas sin contrata que empiezan en 2 semanas'),
             self.env._('Cronograma'), 'construction.space.stage',
             lambda: [('id', 'in', self._stages_without_contract(today, soon))],
             'al_construction_planner.action_construction_space_stage'),
            ('lines_without_cost', 'planner', self.env._('Líneas sin costo en planes en borrador'),
             self.env._('Obras'), 'construction.resource.plan.line',
             [('plan_id.state', '=', 'draft'), ('price_unit_planned', '=', False)],
             'al_construction_planner.action_construction_resource_plan_line'),
        ]

    @api.model
    def _stages_without_contract(self, today, soon):
        """Ids de las etapas que empiezan entre hoy y ``soon`` con contratas o
        personal propio en el plan y sin contrata ni cuadrilla asignadas."""
        Stage = self.env['construction.space.stage']
        stages = Stage.search([('date_start', '>=', today), ('date_start', '<=', soon)])
        resources = Stage._resources_by_stage(stages)
        return [stage.id for stage in stages
                if resources.get((stage.space_task_id.id, stage.stage), {}).get('drivers')
                and not resources[(stage.space_task_id.id, stage.stage)].get('partner')
                and not resources[(stage.space_task_id.id, stage.stage)].get('role')]

    @api.model
    def _pending_areas(self):
        """Área de cada pendiente (CR-65), por su clave. Los puentes agregan
        las de sus pendientes; uno sin área cae en «Otros»."""
        return {
            'progress_to_validate': 'site',
            'stages_without_contract': 'planning',
            'lines_without_cost': 'planning',
        }

    @api.model
    def _get_pending(self, today):
        user = self.env.user
        cache = {}
        result = []
        areas = self._pending_areas()
        area_labels = dict(PENDING_AREAS)
        roles = {}
        for key, group, label, where, model, domain, action_ref in \
                self._pending_definitions(today):
            if not user.has_group(GROUP + group):
                continue
            entry = self._pending_entry(model, domain, label, action_ref, today, cache)
            if entry is None:
                continue
            count, action = entry
            if group not in roles:
                roles[group] = self.env.ref(GROUP + group, raise_if_not_found=False).name or ''
            area = areas.get(key, 'other')
            result.append({'key': key, 'label': label, 'where': where, 'count': count,
                           'action': action, 'area': area,
                           'area_label': area_labels.get(area, area_labels['other']),
                           'role': roles[group]})
        return result

    @api.model
    def _pending_entry(self, model, domain, label, action_ref, today, cache):
        """(cantidad, acción) de un pendiente sobre ``model``, o ``None`` si el
        usuario no lo ve. Los puentes resuelven sus pendientes especiales (las
        alertas de abastecimiento)."""
        Model = self.env.get(model)
        if Model is None or not Model.has_access('read'):
            return None
        if callable(domain):
            # Solo se calcula si el usuario atiende ese pendiente.
            domain = domain()
        count = Model.search_count(domain)
        action = self.env['ir.actions.actions']._for_xml_id(action_ref)
        action.update({'domain': domain, 'name': label})
        # Sin los filtros por defecto de la acción: la lista muestra
        # exactamente lo pendiente.
        context = {k: v for k, v in self._eval_context(action).items()
                   if not k.startswith('search_default_')}
        action['context'] = context
        return count, action

    @api.model
    def _eval_context(self, action):
        context = action.get('context') or {}
        if isinstance(context, str):
            context = safe_eval(context, {'uid': self.env.uid, 'context': {}})
        return dict(context)

    @api.model
    def get_home_data(self, month=False):
        today = fields.Date.context_today(self)
        home = self.with_context(construction_portfolio_month=month or False)
        return {
            'areas': [list(area) for area in PENDING_AREAS],
            'month': (fields.Date.to_date(month) if month else today.replace(day=1)).isoformat(),
            'today': fields.Date.to_string(today),
            'today_label': format_date(self.env, today, date_format='EEEE dd/MM/yyyy'),
            'works': home._get_works(today),
            'unplanned': self._get_unplanned_works(),
            'pending': self._get_pending(today),
            'can_plan': self.env.user.has_group(GROUP + 'planner'),
            # El cronograma valorizado es del puente de ventas.
            'has_schedule_report': 'construction.schedule.report' in self.env,
            'show_amounts': can_see_amounts(self.env),
        }

    @api.model
    def toggle_favorite(self, project_id):
        """CR-59: la estrella es el favorito nativo del proyecto, por usuario."""
        project = self.env['project.project'].browse(project_id).exists()
        if not project:
            raise UserError(self.env._('La obra ya no existe.'))
        project.check_access('read')
        # El método nativo escribe con sudo: quien lee la obra la marca.
        project._set_favorite_user_ids(not project.is_favorite)
        project.invalidate_recordset(['is_favorite'])
        return project.is_favorite

    @api.model
    def action_open_plan(self, plan_id):
        plan = self.env['construction.resource.plan'].browse(plan_id).exists()
        if not plan:
            raise UserError(self.env._('El plan ya no existe.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'construction.resource.plan',
            'res_id': plan.id,
            'views': [[False, 'form']],
            'target': 'current',
        }
