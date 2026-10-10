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

from .construction_supply_board import SOON_DAYS

GROUP = 'al_construction_planner.group_planner_'
#: Días hacia adelante para las etapas sin contrata (P-01).
STAGE_HORIZON_DAYS = 14


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
        for project in plans.project_id.sorted('name'):
            plan = project._construction_current_plan()
            if not plan:
                continue
            approved = plan.state not in ('draft', 'to_approve')
            amounts = Plan._progress_amounts([('plan_id', '=', plan.id)])
            milestone = self._next_milestone(project, plan, today)
            works.append({
                'project_id': project.id,
                'project_name': project.display_name,
                'plan_id': plan.id,
                'plan_name': '%s · v%s' % (plan.name, plan.version),
                'period': '%s → %s' % (format_date(self.env, plan.date_start, date_format='dd/MM'),
                                       format_date(self.env, plan.date_end, date_format='dd/MM')),
                'amount_total': plan.amount_total if approved else False,
                'amount_remaining': plan.amount_remaining if approved else False,
                'progress': Plan._progress_ratio(amounts, False) if approved else False,
                'milestone': milestone['label'],
                'milestone_date': milestone['date'] and fields.Date.to_string(milestone['date']),
                'state': plan.state,
                'state_label': states[plan.state],
                'currency_symbol': plan.currency_id.symbol,
            })
        return works

    @api.model
    def _next_milestone(self, project, plan, today):
        """El hito más cercano desde hoy entre corte, presentación,
        confirmación, factura y cobro de las valorizaciones previstas (P-21)
        y fin de etapa (P-15). Un plan sin aprobar tiene como hito aprobarlo."""
        if plan.state == 'draft':
            return {'label': self.env._('Aprobar el plan'), 'date': False}
        if plan.state == 'to_approve':
            return {'label': self.env._('Aprobación del plan'), 'date': False}
        candidates = []
        labels = {
            'cutoff': self.env._('Valorización %s · corte'),
            'submit': self.env._('Valorización %s · presentación'),
            'confirm': self.env._('Valorización %s · confirmación'),
            'invoice': self.env._('Valorización %s · factura'),
            'collection': self.env._('Valorización %s · cobro'),
        }
        try:
            forecast = project._construction_get_valuation_forecast() \
                if project.construction_sale_order_id else {'rows': []}
        except UserError:
            forecast = {'rows': []}
        for row in forecast['rows']:
            for key, label in labels.items():
                if row.get(key) and row[key] >= today:
                    candidates.append((row[key], label % row['number']))
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
    def _pending_definitions(self, today):
        """Pendientes posibles: (clave, grupo, etiqueta, dónde, modelo,
        dominio, acción base). El dominio puede ser una función (se calcula
        solo para quien atiende el pendiente) y, en las alertas de
        abastecimiento, el tipo de alerta."""
        supervised = self._supervised_projects()
        mine = [('project_id', 'in', supervised.ids)] if supervised is not None else []
        soon = today + timedelta(days=STAGE_HORIZON_DAYS)
        return [
            ('progress_to_validate', 'planner', self.env._('Avances reportados por validar'),
             self.env._('Avance'), 'construction.task.progress',
             [('state', '=', 'draft')] + mine,
             'al_construction_planner.action_construction_progress_to_validate'),
            ('settlements_to_validate', 'planner', self.env._('Liquidaciones por validar'),
             self.env._('Contratas'), 'construction.contract.settlement',
             [('state', '=', 'submitted')] + mine,
             'al_construction_planner.action_construction_contract_settlement'),
            ('deliveries_to_confirm', 'manager', self.env._('Entregas semanales por confirmar'),
             self.env._('Ingresos'), 'construction.weekly.delivery',
             [('state', '=', 'draft')],
             'al_construction_planner.action_construction_weekly_delivery'),
            ('valuations_to_invoice', 'revenue',
             self.env._('Valorizaciones confirmadas por facturar'), self.env._('Ingresos'),
             'construction.valuation', [('state', '=', 'confirmed')],
             'al_construction_planner.action_construction_valuation'),
            ('supply_no_po', 'planner',
             self.env._('Necesidades sin OC en menos de %s días', SOON_DAYS),
             self.env._('Abastecimiento'), 'supply', 'no_po',
             'al_construction_planner.action_construction_supply_board'),
            ('supply_price', 'planner', self.env._('Último precio sobre el costo del plan'),
             self.env._('Abastecimiento'), 'supply', 'price',
             'al_construction_planner.action_construction_supply_board'),
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
    def _supply_alerts(self, today):
        plans = self.env['construction.resource.plan'].search(
            [('state', 'in', ('approved', 'in_progress'))])
        return self.env['construction.supply.board']._get_supply_alerts(
            plans.project_id, date_ref=today)

    @api.model
    def _get_pending(self, today):
        user = self.env.user
        alerts = None
        result = []
        for key, group, label, where, model, domain, action_ref in \
                self._pending_definitions(today):
            if not user.has_group(GROUP + group):
                continue
            if model == 'supply':
                if alerts is None:
                    alerts = self._supply_alerts(today)
                matching = [a for a in alerts if a['type'] == domain]
                count = len(matching)
                action = self.env['ir.actions.actions']._for_xml_id(action_ref)
                if matching:
                    action['context'] = {'construction_project_id': matching[0]['project_id']}
            else:
                Model = self.env[model]
                if not Model.has_access('read'):
                    continue
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
            result.append({'key': key, 'label': label, 'where': where, 'count': count,
                           'action': action})
        return result

    @api.model
    def _eval_context(self, action):
        context = action.get('context') or {}
        if isinstance(context, str):
            context = safe_eval(context, {'uid': self.env.uid, 'context': {}})
        return dict(context)

    @api.model
    def get_home_data(self):
        today = fields.Date.context_today(self)
        return {
            'today': fields.Date.to_string(today),
            'today_label': format_date(self.env, today, date_format='EEEE dd/MM/yyyy'),
            'works': self._get_works(today),
            'pending': self._get_pending(today),
            'can_plan': self.env.user.has_group(GROUP + 'planner'),
        }

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
