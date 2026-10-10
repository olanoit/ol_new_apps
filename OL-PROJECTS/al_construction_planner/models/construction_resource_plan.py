# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import timedelta

from lxml import etree
from markupsafe import Markup

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import split_every
from odoo.tools.misc import formatLang

from .common import DRIVER_TYPES, RESOURCE_TYPES, STAGES

PLAN_STATES = [
    ('draft', 'Borrador'),
    ('to_approve', 'En aprobación'),
    ('approved', 'Aprobado'),
    ('in_progress', 'En ejecución'),
    ('closed', 'Cerrado'),
    ('replaced', 'Reemplazado'),
    ('cancel', 'Cancelado'),
]
# Estados en los que el plan es el vigente de la obra.
OPEN_STATES = ('approved', 'in_progress')
# Estados de una versión en preparación.
DRAFT_STATES = ('draft', 'to_approve')


class ConstructionResourcePlan(models.Model):
    """Plan de recursos de una obra (una versión). Sus líneas cuelgan de los
    niveles de la obra y se acumulan hacia arriba en el árbol."""
    _name = 'construction.resource.plan'
    _description = 'Plan de recursos de obra'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'tier.validation']
    _order = 'project_id, version desc'
    _check_company_auto = True
    # Aprobación multinivel (OCA base_tier_validation), mismo patrón que
    # al_construction_material_request: las revisiones se piden con
    # «Solicitar aprobación» y la última aprobación pasa el plan a «Aprobado».
    _state_from = ['draft', 'to_approve']
    _state_to = ['approved']
    _cancel_state = 'cancel'
    _tier_validation_manual_config = False

    name = fields.Char(string='Número', required=True, readonly=True, copy=False, default='/')
    project_id = fields.Many2one(
        'project.project', string='Obra', required=True, index=True, check_company=True,
        domain=[('is_construction_site', '=', True)], tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True, store=True,
        compute='_compute_company_id', precompute=True, readonly=False,
        default=lambda self: self.env.company,
        help='La de la obra; si la obra es compartida entre compañías, la activa al crearlo.')
    currency_id = fields.Many2one(
        related='company_id.currency_id', string='Moneda', store=True)
    user_id = fields.Many2one(
        'res.users', string='Responsable', required=True, default=lambda self: self.env.user,
        tracking=True)
    version = fields.Integer(string='Versión', default=1, readonly=True, copy=False)
    parent_id = fields.Many2one(
        'construction.resource.plan', string='Versión anterior', readonly=True, copy=False,
        check_company=True)
    replan_reason = fields.Text(string='Motivo de la versión', tracking=True)
    state = fields.Selection(
        PLAN_STATES, string='Estado', required=True, default='draft', tracking=True, copy=False)
    date_start = fields.Date(string='Inicio', required=True, tracking=True)
    date_end = fields.Date(string='Fin', required=True, tracking=True)
    exceed_policy = fields.Selection(
        [('warn', 'Solo alerta'), ('approval', 'Aprobación adicional'), ('block', 'Bloquear')],
        string='Si se excede el saldo', required=True, default='approval', tracking=True,
        help='Qué pasa cuando un documento pide más de lo que queda en el plan.')
    exceed_tolerance = fields.Float(
        string='Tolerancia (%)', digits=(5, 2), default=0.0,
        help='Exceso permitido sobre el saldo antes de aplicar la política.')
    lead_days_material = fields.Integer(
        string='Anticipación de material (días)', default=7,
        help='Días antes del inicio de la tarea en que se necesita el material.')
    lead_days_contract = fields.Integer(string='Anticipación de contrata (días)', default=3)
    lead_days_production = fields.Integer(string='Anticipación de producción (días)', default=7)
    budget_analytic_id = fields.Many2one(
        'budget.analytic', string='Presupuesto analítico', readonly=True, copy=False,
        check_company=True, help='Lo crea la aprobación del plan.')
    line_ids = fields.One2many(
        'construction.resource.plan.line', 'plan_id', string='Líneas', copy=True)
    line_count = fields.Integer(string='Nº de líneas', compute='_compute_amounts', store=True)
    allocation_ids = fields.One2many(
        'construction.resource.plan.allocation', 'plan_id', string='Asignaciones')
    allocation_count = fields.Integer(
        string='Nº de asignaciones', compute='_compute_allocation_count')
    amount_material = fields.Monetary(
        string='Material', compute='_compute_amounts', store=True, currency_field='currency_id')
    amount_service = fields.Monetary(
        string='Servicios', compute='_compute_amounts', store=True, currency_field='currency_id')
    amount_contract = fields.Monetary(
        string='Contratas', compute='_compute_amounts', store=True, currency_field='currency_id')
    amount_labor = fields.Monetary(
        string='Personal propio', compute='_compute_amounts', store=True,
        currency_field='currency_id')
    amount_production = fields.Monetary(
        string='Producción', compute='_compute_amounts', store=True,
        currency_field='currency_id')
    amount_total = fields.Monetary(
        string='Planificado', compute='_compute_amounts', store=True,
        currency_field='currency_id')
    unstaged_line_count = fields.Integer(
        string='Líneas sin etapa', compute='_compute_warnings')
    unpriced_line_count = fields.Integer(
        string='Líneas sin costo', compute='_compute_warnings')
    amount_budgeted = fields.Monetary(
        string='Presupuesto', compute='_compute_execution', currency_field='currency_id',
        help='Monto congelado en las líneas al aprobar el plan; en una versión en '
             'preparación, el de la versión vigente.')
    amount_committed = fields.Monetary(
        string='Comprometido', compute='_compute_execution', currency_field='currency_id')
    amount_actual = fields.Monetary(
        string='Real', compute='_compute_execution', currency_field='currency_id')
    amount_remaining = fields.Monetary(
        string='Saldo', compute='_compute_execution', currency_field='currency_id',
        help='Planificado menos comprometido menos real.')
    stage_summary_html = fields.Html(
        string='Resumen por etapa', compute='_compute_stage_summary_html', sanitize=False)
    control_html = fields.Html(
        string='Análisis de control', compute='_compute_control_html', sanitize=False,
        help='Planificado, comprometido, real, saldo y % ejecutado por etapa y tipo de '
             'recurso (P-13).')
    version_count = fields.Integer(string='Versiones', compute='_compute_version_count')
    date_approved = fields.Datetime(string='Aprobado el', readonly=True, copy=False)
    date_closed = fields.Date(string='Cerrado el', readonly=True, copy=False)

    def _compute_allocation_count(self):
        counts = dict(self.env['construction.resource.plan.allocation']._read_group(
            [('plan_id', 'in', self.ids)], ['plan_id'], ['__count']))
        for plan in self:
            plan.allocation_count = counts.get(plan, 0)

    @api.depends('project_id')
    def _compute_company_id(self):
        for record in self:
            record.company_id = (record.project_id.company_id or record.company_id
                                 or self.env.company)

    @api.depends('line_ids.amount_planned', 'line_ids.resource_type')
    def _compute_amounts(self):
        Line = self.env['construction.resource.plan.line']
        totals = {}
        if self.ids:
            for plan, rtype, amount, count in Line._read_group(
                    [('plan_id', 'in', self.ids)], groupby=['plan_id', 'resource_type'],
                    aggregates=['amount_planned:sum', '__count']):
                totals.setdefault(plan.id, {})[rtype] = (amount, count)
        for plan in self:
            data = totals.get(plan.id, {})
            if not plan.id or not data:
                # Registro nuevo o sin líneas en BD: suma en memoria.
                data = {}
                for line in plan.line_ids:
                    amount, count = data.get(line.resource_type, (0.0, 0))
                    data[line.resource_type] = (amount + line.amount_planned, count + 1)
            plan.amount_material = data.get('material', (0.0, 0))[0]
            plan.amount_service = data.get('service', (0.0, 0))[0]
            plan.amount_contract = data.get('contract', (0.0, 0))[0]
            plan.amount_labor = data.get('labor', (0.0, 0))[0]
            plan.amount_production = data.get('production', (0.0, 0))[0]
            plan.amount_total = sum(amount for amount, _count in data.values())
            plan.line_count = sum(count for _amount, count in data.values())

    def _compute_warnings(self):
        Line = self.env['construction.resource.plan.line']
        unstaged = dict(Line._read_group(
            [('plan_id', 'in', self.ids), ('stage', '=', False)], ['plan_id'], ['__count']))
        # «= False» en un número da «IN (0) OR IS NULL»; «= 0» (solo o con
        # «|») deja fuera los costos vacíos de las líneas manuales.
        unpriced = dict(Line._read_group(
            [('plan_id', 'in', self.ids), ('price_unit_planned', '=', False)], ['plan_id'],
            ['__count']))
        for plan in self:
            plan.unstaged_line_count = unstaged.get(plan, 0)
            plan.unpriced_line_count = unpriced.get(plan, 0)

    def _get_stage_amounts(self):
        """Montos por etapa del plan: {etapa: {columna: monto}}. La etapa
        vacía (False) es «Sin etapa». Comprometido y real salen de
        ``construction.resource.plan.line._get_execution_amounts`` (cero
        hasta las fases de asignaciones, contratas y producción)."""
        self.ensure_one()
        Line = self.env['construction.resource.plan.line']
        stages = defaultdict(lambda: dict.fromkeys(
            ('material', 'contract', 'planned', 'budgeted', 'committed', 'actual'), 0.0))
        if not self.id:
            return stages
        for stage, rtype, planned in Line._read_group(
                [('plan_id', '=', self.id)], groupby=['stage', 'resource_type'],
                aggregates=['amount_planned:sum']):
            data = stages[stage]
            # «Contrata» reúne la mano de obra (contrata y personal propio).
            column = 'contract' if rtype in ('contract', 'labor') else 'material'
            data[column] += planned
            data['planned'] += planned
        # Presupuesto: el de este plan si ya se aprobó; en una versión en
        # preparación, el de la versión vigente (la diferencia es lo que
        # cambia la versión nueva).
        budget_plan = self if self.budget_analytic_id else self.parent_id.filtered(
            'budget_analytic_id')
        if budget_plan:
            for stage, budgeted in Line._read_group(
                    [('plan_id', '=', budget_plan.id)], groupby=['stage'],
                    aggregates=['amount_budgeted:sum']):
                stages[stage]['budgeted'] += budgeted
        for stage, (committed, actual) in self.line_ids._get_execution_amounts().items():
            stages[stage]['committed'] += committed
            stages[stage]['actual'] += actual
        return stages

    @api.depends('line_ids.amount_planned', 'line_ids.amount_budgeted')
    def _compute_execution(self):
        for plan in self:
            stages = plan._get_stage_amounts()
            plan.amount_budgeted = sum(d['budgeted'] for d in stages.values())
            plan.amount_committed = sum(d['committed'] for d in stages.values())
            plan.amount_actual = sum(d['actual'] for d in stages.values())
            plan.amount_remaining = (plan.amount_total - plan.amount_committed
                                     - plan.amount_actual)

    @api.depends('line_ids.amount_planned', 'line_ids.amount_budgeted', 'line_ids.stage',
                 'parent_id.line_ids.amount_budgeted')
    def _compute_stage_summary_html(self):
        """Resumen por etapa (P-03): material, contrata, planificado,
        presupuesto, diferencia, comprometido, real y saldo."""
        headers = [self.env._('Etapa'), self.env._('Material'), self.env._('Contrata'),
                   self.env._('Planificado'), self.env._('Presupuesto'),
                   self.env._('Diferencia'), self.env._('Comprometido'), self.env._('Real'),
                   self.env._('Saldo')]
        stage_labels = dict(STAGES)
        for plan in self:
            stages = plan._get_stage_amounts()
            if not stages:
                plan.stage_summary_html = False
                continue

            def fmt(value):
                return formatLang(plan.env, value, digits=2) if value else '—'

            rows, total = [], dict.fromkeys(
                ('material', 'contract', 'planned', 'budgeted', 'committed', 'actual'), 0.0)
            for stage in [key for key, _label in STAGES] + [False]:
                if stage not in stages:
                    continue
                data = stages[stage]
                for key in total:
                    total[key] += data[key]
                rows.append((stage_labels.get(stage, self.env._('Sin etapa')), data,
                             not stage))
            rows.append((self.env._('Total'), total, False))
            body = Markup('')
            for index, (label, data, unstaged) in enumerate(rows):
                is_total = index == len(rows) - 1
                remaining = data['planned'] - data['committed'] - data['actual']
                cells = [data['material'], data['contract'], data['planned'], data['budgeted'],
                         data['planned'] - data['budgeted'], data['committed'], data['actual'],
                         remaining]
                row_class = 'table-danger' if unstaged else ('fw-bold' if is_total else '')
                body += Markup('<tr class="%s"><td>%s</td>%s</tr>') % (
                    row_class, label,
                    Markup('').join(Markup('<td class="text-end">%s</td>') % fmt(value)
                                    for value in cells))
            head = Markup('').join(
                Markup('<th class="%s">%s</th>') % ('' if i == 0 else 'text-end', h)
                for i, h in enumerate(headers))
            plan.stage_summary_html = Markup(
                '<table class="table table-sm o_construction_stage_summary">'
                '<thead><tr>%s</tr></thead><tbody>%s</tbody></table>') % (head, body)

    def _get_control_data(self):
        """Análisis de control (P-13): {(etapa, tipo de recurso): {planned,
        committed, actual}} con los montos guardados en las líneas."""
        self.ensure_one()
        result = {}
        if not self.id:
            return result
        for stage, rtype, planned, committed, actual in self.env[
                'construction.resource.plan.line']._read_group(
                [('plan_id', '=', self.id)], groupby=['stage', 'resource_type'],
                aggregates=['amount_planned:sum', 'amount_committed:sum', 'amount_actual:sum']):
            result[(stage, rtype)] = {
                'planned': planned, 'committed': committed, 'actual': actual}
        return result

    @api.depends('line_ids.amount_planned', 'line_ids.amount_committed',
                 'line_ids.amount_actual')
    def _compute_control_html(self):
        """Tabla P-13: etapa › tipo de recurso con planificado, comprometido,
        real, saldo y % ejecutado (real entre planificado)."""
        headers = [self.env._('Etapa › Tipo de recurso'), self.env._('Planificado'),
                   self.env._('Comprometido'), self.env._('Real'), self.env._('Saldo'),
                   self.env._('% ejecutado')]
        stage_labels = dict(STAGES)
        type_labels = dict(RESOURCE_TYPES)
        for plan in self:
            data = plan._get_control_data()
            if not data:
                plan.control_html = False
                continue

            def cells(values):
                remaining = values['planned'] - values['committed'] - values['actual']
                pct = values['actual'] / values['planned'] if values['planned'] else 0.0
                amounts = [values['planned'], values['committed'], values['actual'], remaining]
                return Markup('').join(
                    Markup('<td class="text-end">%s</td>') % (
                        formatLang(plan.env, value, digits=2) if value else '—')
                    for value in amounts) + Markup('<td class="text-end">%s %%</td>') % (
                        formatLang(plan.env, pct * 100, digits=1))

            def add(total, values):
                for key in ('planned', 'committed', 'actual'):
                    total[key] += values[key]

            body = Markup('')
            grand = dict.fromkeys(('planned', 'committed', 'actual'), 0.0)
            for stage in [key for key, _label in STAGES] + [False]:
                rows = [(rtype, values) for (st, rtype), values in data.items() if st == stage]
                if not rows:
                    continue
                subtotal = dict.fromkeys(('planned', 'committed', 'actual'), 0.0)
                for _rtype, values in rows:
                    add(subtotal, values)
                add(grand, subtotal)
                body += Markup('<tr class="fw-bold%s"><td>%s</td>%s</tr>') % (
                    '' if stage else ' table-danger',
                    stage_labels.get(stage, self.env._('Sin etapa')), cells(subtotal))
                for rtype, values in sorted(rows, key=lambda r: list(type_labels).index(r[0])):
                    body += Markup('<tr><td class="ps-4">%s</td>%s</tr>') % (
                        type_labels.get(rtype, rtype), cells(values))
            body += Markup('<tr class="fw-bold table-active"><td>%s</td>%s</tr>') % (
                self.env._('Total obra'), cells(grand))
            head = Markup('').join(
                Markup('<th class="%s">%s</th>') % ('' if i == 0 else 'text-end', h)
                for i, h in enumerate(headers))
            plan.control_html = Markup(
                '<table class="table table-sm o_construction_control">'
                '<thead><tr>%s</tr></thead><tbody>%s</tbody></table>') % (head, body)

    def action_refresh_control(self):
        """«Actualizar control»: recalcula el estado y los montos de las líneas."""
        self.line_ids._refresh_control()
        return True

    def action_open_control_analysis(self):
        """Análisis de control (P-13) del plan en pivote y gráfico."""
        self.ensure_one()
        self.line_ids._refresh_control()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'al_construction_planner.action_construction_plan_control')
        action['name'] = self.env._('Análisis de control · %s', self.display_name)
        action['domain'] = [('plan_id', '=', self.id)]
        action['context'] = {'search_default_group_stage': 1, 'search_default_group_type': 1}
        return action

    def _compute_version_count(self):
        counts = dict(self.with_context(active_test=False)._read_group(
            [('project_id', 'in', self.project_id.ids)], ['project_id'], ['__count']))
        for plan in self:
            plan.version_count = counts.get(plan.project_id, 0)

    @api.constrains('parent_id', 'replan_reason')
    def _check_replan_reason(self):
        for plan in self:
            if plan.parent_id and not (plan.replan_reason or '').strip():
                raise ValidationError(self.env._(
                    'Una versión nueva del plan necesita su motivo.'))

    @api.constrains('project_id', 'state')
    def _check_single_version(self):
        """Por obra: una sola versión vigente (aprobada o en ejecución) y una
        sola en preparación (borrador o en aprobación)."""
        for plan in self:
            for states in (OPEN_STATES, DRAFT_STATES):
                if plan.state in states and self.search_count([
                        ('project_id', '=', plan.project_id.id),
                        ('state', 'in', states), ('id', '!=', plan.id)]):
                    raise ValidationError(self.env._(
                        'La obra %s ya tiene un plan %s.', plan.project_id.display_name,
                        'vigente' if states == OPEN_STATES else 'en preparación'))

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for plan in self:
            if plan.date_start and plan.date_end and plan.date_start > plan.date_end:
                raise ValidationError(self.env._('El plan termina antes de empezar.'))

    @api.onchange('project_id')
    def _onchange_project_id(self):
        project = self.project_id
        if project:
            self.date_start = self.date_start or project.date_start or fields.Date.context_today(self)
            self.date_end = self.date_end or project.date or (
                self.date_start + timedelta(days=90))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'construction.resource.plan') or '/'
            project = self.env['project.project'].browse(vals.get('project_id'))
            if project and 'version' not in vals:
                last = self.with_context(active_test=False).search(
                    [('project_id', '=', project.id)], order='version desc', limit=1)
                vals['version'] = (last.version or 0) + 1
            if project:
                vals.setdefault('date_start', project.date_start or fields.Date.context_today(self))
                vals.setdefault('date_end', project.date or fields.Date.to_date(
                    vals['date_start']) + timedelta(days=90))
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        # El estado de las líneas sigue al plan (cancelada) y la tolerancia
        # decide cuándo una línea está excedida.
        if {'state', 'exceed_tolerance'} & set(vals):
            self.line_ids._refresh_control()
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_except_approved(self):
        if any(plan.state not in ('draft', 'cancel') for plan in self):
            raise UserError(self.env._(
                'Solo se elimina un plan en borrador o cancelado: los aprobados quedan como '
                'historia de la obra.'))

    @api.depends('name', 'project_id', 'version')
    def _compute_display_name(self):
        for plan in self:
            plan.display_name = '%s · v%s' % (plan.name, plan.version) if plan.name else ''

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def _check_draft(self):
        for plan in self:
            if plan.state != 'draft':
                raise UserError(self.env._(
                    'El plan %s ya no está en borrador: créele una versión nueva.', plan.name))

    def action_open_generate_wizard(self):
        self.ensure_one()
        self._check_draft()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Generar plan'),
            'res_model': 'construction.plan.generate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_plan_id': self.id},
        }

    def _check_state(self, allowed):
        if any(plan.state not in allowed for plan in self):
            raise UserError(self.env._(
                'La acción no está permitida en el estado actual del plan.'))

    def _get_approval_issues(self):
        """Motivos que impiden pedir la aprobación, con las líneas afectadas."""
        self.ensure_one()
        issues = []
        lines = self.line_ids.filtered(lambda l: l.line_state != 'cancel')
        if not lines:
            issues.append(self.env._('El plan no tiene líneas.'))
        checks = [
            (lines.filtered(lambda l: not l.stage), self.env._('Líneas sin etapa')),
            (lines.filtered(lambda l: l.qty_planned and not l.price_unit_planned),
             self.env._('Líneas sin costo (aplique el costo con «Aplicar costo»)')),
            (lines.filtered(lambda l: l.resource_type in ('contract', 'labor')
                            and not l.activity_id),
             self.env._('Contratas sin actividad')),
        ]
        if not self.project_id.account_id:
            checks.append((lines.filtered(lambda l: not l.analytic_distribution),
                           self.env._('Líneas sin distribución analítica (la obra no tiene '
                                      'cuenta analítica)')))
        for faulty, title in checks:
            if faulty:
                sample = '\n'.join('   · %s' % label for label in faulty[:10]._get_issue_label())
                more = len(faulty) - 10
                issues.append('%s: %s\n%s%s' % (
                    title, len(faulty), sample,
                    self.env._('\n   · y %s más', more) if more > 0 else ''))
        return issues

    def action_request_approval(self):
        """Pide las revisiones que apliquen; si ninguna regla aplica, aprueba
        directamente."""
        self._check_state(('draft',))
        for plan in self:
            issues = plan._get_approval_issues()
            if issues:
                raise UserError(self.env._(
                    'El plan %(plan)s no se puede enviar a aprobación:\n\n%(issues)s',
                    plan=plan.display_name, issues='\n'.join(issues)))
        self.write({'state': 'to_approve'})
        for plan in self:
            reviews = plan.request_validation() if plan.need_validation else False
            if not reviews:
                plan._write_approved()

    def _write_approved(self):
        """Última aprobación: presupuesto analítico, montos congelados en las
        líneas y la versión vigente anterior pasa a «Reemplazado»."""
        # need_validation no tiene depends: su caché conserva el valor de
        # antes de crear las revisiones y OCA intentaría pedirlas de nuevo.
        self.invalidate_recordset(['need_validation', 'review_ids', 'validation_status'])
        for plan in self:
            previous = plan._get_previous_open_version()
            budget = plan._create_budget(parent_budget=previous.budget_analytic_id)
            lines = plan.line_ids.with_context(construction_plan_force=True)
            for amount, same_amount in lines.grouped('amount_planned').items():
                same_amount.write({'amount_budgeted': amount})
            if previous:
                previous._transfer_to_new_version(plan)
                previous.write({'state': 'replaced'})
                previous.message_post(body=self.env._(
                    'Reemplazado por la versión %s.', plan.display_name))
            # Guarda de reentrada: al escribir «Aprobado», tier.validation
            # puede volver a llamar a _validate_tier.
            plan.with_context(al_construction_approving=True).write({
                'state': 'approved',
                'budget_analytic_id': budget.id,
                'date_approved': fields.Datetime.now(),
            })

    def _get_previous_open_version(self):
        self.ensure_one()
        return self.search([
            ('project_id', '=', self.project_id.id), ('state', 'in', OPEN_STATES),
            ('id', '!=', self.id)], limit=1)

    def _transfer_to_new_version(self, new_plan):
        """Gancho de la versión aprobada que reemplaza a ``self``: las
        asignaciones abiertas pasan a la línea nueva que la continúa
        (``previous_line_id``). Las cerradas (documento hecho o cancelado) se
        quedan en la versión anterior como historia, igual que los avances
        liquidados; los no liquidados pasan a la línea nueva."""
        self.ensure_one()
        successors = {
            line.previous_line_id: line
            for line in new_plan.line_ids.filtered(lambda l: l.previous_line_id.plan_id == self)
        }
        # Quien da la última aprobación (un revisor de la regla) puede no
        # tener permiso de escritura en las asignaciones: solo se cambia su
        # línea del plan, sin tocar los documentos.
        allocations_sudo = self.allocation_ids.sudo().filtered(lambda a: a.state == 'open')
        moved = self.env['construction.resource.plan.allocation']
        for line, allocations in allocations_sudo.grouped('plan_line_id').items():
            successor = successors.get(line)
            if successor:
                allocations.write({'plan_line_id': successor.id})
                moved |= allocations
        left = allocations_sudo - moved
        # Avances no liquidados (reportados, validados o rechazados fuera de
        # una liquidación aprobada) pasan con su línea; los liquidados quedan
        # como historia de esta versión.
        progress_sudo = self.env['construction.task.progress'].sudo().search([
            ('plan_id', '=', self.id), ('settled', '=', False)])
        moved_progress = 0
        for line, progresses in progress_sudo.grouped('plan_line_id').items():
            successor = successors.get(line)
            if successor:
                progresses.with_context(construction_progress_force=True).write(
                    {'plan_line_id': successor.id})
                moved_progress += len(progresses)
        if moved_progress:
            new_plan.message_post(body=self.env._(
                'Avances no liquidados pasados a %(plan)s: %(count)s.',
                plan=new_plan.display_name, count=moved_progress))
        if moved or left:
            body = self.env._('Asignaciones abiertas pasadas a %(plan)s: %(count)s.',
                              plan=new_plan.display_name, count=len(moved))
            if left:
                body += ' ' + self.env._(
                    'Se quedan en esta versión %(count)s cuyas líneas no continúan en la '
                    'nueva (%(docs)s).', count=len(left),
                    docs=', '.join(sorted(set(left.mapped('document_name')))[:10]))
            new_plan.message_post(body=body)

    def _get_budget_line_values(self):
        """Una línea de presupuesto por combinación de cuentas analíticas.

        La distribución de cada línea del plan (o, vacía, la cuenta de la
        obra al 100 %) se reparte por sus claves «id1,id2,…»; cada cuenta va
        a la columna de su plan raíz (``account_id`` para el plan de
        proyectos, ``x_plan<N>_id`` para los demás). El redondeo se corrige
        en la combinación mayor para que el total cuadre con el plan."""
        self.ensure_one()
        Account = self.env['account.analytic.account']
        project_account = self.project_id.account_id
        default = {str(project_account.id): 100.0} if project_account else {}
        combos = defaultdict(float)
        key_cache = {}
        for line in self.line_ids.filtered(lambda l: l.line_state != 'cancel'):
            for key, percentage in (line.analytic_distribution or default).items():
                if key not in key_cache:
                    accounts = Account.browse(int(a) for a in key.split(',') if a).exists()
                    key_cache[key] = tuple(sorted(
                        (account.root_plan_id._column_name(), account.id)
                        for account in accounts))
                combos[key_cache[key]] += line.amount_planned * percentage / 100.0
        currency = self.currency_id
        values = [{**dict(combo), 'budget_amount': currency.round(amount)}
                  for combo, amount in combos.items() if combo]
        if values:
            difference = currency.round(sum(combos.values())) - sum(
                v['budget_amount'] for v in values)
            if not currency.is_zero(difference):
                biggest = max(values, key=lambda v: abs(v['budget_amount']))
                biggest['budget_amount'] = currency.round(biggest['budget_amount'] + difference)
        return values

    def _construction_match_budget_line(self, combo):
        """Línea del presupuesto analítico del plan que cubre una combinación
        de cuentas ({columna: id}): la que tiene todas sus cuentas en la
        combinación (sus columnas vacías no filtran, como en el informe de
        presupuesto de Odoo) y, entre ellas, la más específica."""
        self.ensure_one()
        best, best_size = self.env['budget.line'], 0
        for budget_line in self.budget_analytic_id.budget_line_ids:
            values = {fname: budget_line[fname].id for fname in budget_line._get_plan_fnames()
                      if budget_line[fname]}
            if values and len(values) > best_size and all(
                    combo.get(fname) == value for fname, value in values.items()):
                best, best_size = budget_line, len(values)
        return best

    def _create_budget(self, parent_budget=False):
        self.ensure_one()
        line_values = self._get_budget_line_values()
        # sudo: quien aprueba el plan (jefatura) no suele tener permisos de
        # contabilidad; el presupuesto es una consecuencia de la aprobación y
        # sus valores salen del plan, no del usuario.
        budget_sudo = self.env['budget.analytic'].sudo().create({
            'name': '%s · %s' % (self.project_id.name, self.display_name),
            'date_from': self.date_start,
            'date_to': self.date_end,
            'budget_type': 'expense',
            'company_id': self.company_id.id,
            'user_id': self.user_id.id,
            'parent_id': parent_budget.id if parent_budget else False,
            'budget_line_ids': [Command.create(vals) for vals in line_values],
        })
        # Con versión anterior, su presupuesto pasa a «Revisado» (archivado):
        # es el mecanismo de revisiones de account_budget.
        budget_sudo.action_budget_confirm()
        return budget_sudo.sudo(False)

    def _validate_tier(self, tiers=False):
        res = super()._validate_tier(tiers)
        if not self.env.context.get('al_construction_approving'):
            for plan in self:
                if plan.state == 'to_approve' and plan.validation_status == 'validated':
                    plan._write_approved()
        return res

    def _rejected_tier(self, tiers=False):
        res = super()._rejected_tier(tiers)
        for plan in self:
            if plan.state == 'to_approve' and plan.validation_status == 'rejected':
                # Rechazo: vuelve a borrador (diagrama de estados). Lo escribe
                # el revisor, que no puede editar el plan en revisión: se omite
                # ese control solo para el estado.
                plan.with_context(skip_validation_check=True).write({'state': 'draft'})
                plan.message_post(body=self.env._('Rechazado: el plan vuelve a borrador.'))
        return res

    def action_draft(self):
        self._check_state(('to_approve', 'cancel'))
        # En «En aprobación» las revisiones siguen vivas: se reinician.
        self.filtered(lambda p: p.state == 'to_approve').restart_validation()
        self.write({'state': 'draft'})

    def action_cancel(self):
        self._check_state(('draft', 'to_approve'))
        self.write({'state': 'cancel'})

    def _mark_in_progress(self):
        """Primer documento generado desde el plan (fases 4 a 6): «Aprobado»
        pasa a «En ejecución»."""
        self.filtered(lambda p: p.state == 'approved').write({'state': 'in_progress'})

    def action_close(self):
        """Cierra el plan vigente: queda de solo lectura y su presupuesto
        analítico pasa a «Hecho». No se cierra con documentos abiertos
        (asignaciones de compras, requerimientos, OF u OC de servicio sin
        terminar) ni con liquidaciones de contrata pendientes."""
        if not self.env.user.has_group('al_construction_planner.group_planner_manager'):
            raise UserError(self.env._('Solo el administrador del planificador cierra un plan.'))
        self._check_state(OPEN_STATES)
        for plan in self:
            open_allocations = plan.allocation_ids.filtered(lambda a: a.state == 'open')
            if open_allocations:
                docs = sorted(set(open_allocations.mapped('document_name')))
                raise UserError(self.env._(
                    'El plan %(plan)s tiene documentos abiertos: %(docs)s. Termínelos o '
                    'cancélelos antes de cerrar el plan.',
                    plan=plan.display_name,
                    docs=', '.join(docs[:10]) + (' …' if len(docs) > 10 else '')))
            pending = self.env['construction.contract.settlement'].search([
                ('project_id', '=', plan.project_id.id),
                ('state', 'in', ('draft', 'submitted', 'validated'))])
            unsettled = self.env['construction.task.progress'].search_count([
                ('plan_id', '=', plan.id), ('state', '=', 'validated'),
                '|', ('settlement_id', '=', False), ('settlement_id.state', '=', 'cancel')])
            if pending or unsettled:
                raise UserError(self.env._(
                    'El plan %(plan)s tiene liquidaciones de contrata pendientes (%(names)s) o '
                    '%(count)s avances validados sin liquidar. Apruébelas o anúlelas antes de '
                    'cerrar el plan.', plan=plan.display_name,
                    names=', '.join(pending.mapped('name')[:10]) or '—', count=unsettled))
        self.write({'state': 'closed', 'date_closed': fields.Date.context_today(self)})
        # sudo: mismo motivo que al crearlo (permisos de contabilidad).
        self.budget_analytic_id.sudo().filtered(
            lambda b: b.state == 'confirmed').action_budget_done()

    def action_open_replan_wizard(self):
        self.ensure_one()
        self._check_state(OPEN_STATES)
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Nueva versión del plan'),
            'res_model': 'construction.plan.replan.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_plan_id': self.id},
        }

    def action_open_price_wizard(self):
        self.ensure_one()
        self._check_draft()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Aplicar costo'),
            'res_model': 'construction.plan.price.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_plan_id': self.id},
        }

    def action_view_budget(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Presupuesto analítico'),
            'res_model': 'budget.analytic',
            'view_mode': 'form',
            'res_id': self.budget_analytic_id.id,
        }

    def action_view_versions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Versiones de %s', self.project_id.display_name),
            'res_model': 'construction.resource.plan',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.project_id.id)],
            'context': {'active_test': False, 'create': False},
        }

    def action_view_allocations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Asignaciones de %s', self.display_name),
            'res_model': 'construction.resource.plan.allocation',
            'view_mode': 'list,pivot',
            'domain': [('plan_id', '=', self.id)],
            'context': {'create': False, 'search_default_group_kind': 1},
        }

    def _check_supply_wizard_state(self):
        """Los asistentes de abastecimiento (W-02 a W-04) trabajan sobre el plan
        vigente."""
        for plan in self:
            if plan.state not in OPEN_STATES:
                raise UserError(self.env._(
                    'El plan %s no está vigente: apruébelo antes de comprar, pedir o '
                    'fabricar desde él.', plan.display_name))

    def action_view_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Líneas de %s', self.display_name),
            'res_model': 'construction.resource.plan.line',
            'view_mode': 'list,pivot,graph,form',
            'domain': [('plan_id', '=', self.id)],
            'context': {'default_plan_id': self.id, 'search_default_group_stage': 1},
        }

    def _get_to_validate_message(self):
        # El es.po de base_tier_validation no traduce este aviso: se da aquí
        # en español.
        icon = Markup('<i class="fa fa-lg fa-info-circle"></i>')
        pending = self.review_ids.filtered(lambda r: r.status == 'pending')[:1]
        if pending and pending.todo_by:
            text = self.env._('Pendiente de aprobación por %s', pending.todo_by)
        else:
            text = self.env._('Este plan de recursos necesita aprobación')
        return Markup('%s %s') % (icon, text)

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        """Quita los botones OCA «Request/Restart Validation»: el flujo usa
        «Solicitar aprobación» y «Volver a borrador», que además mueven el
        estado. Se conservan validar/rechazar y el bloque de revisiones."""
        res = super().get_view(view_id=view_id, view_type=view_type, **options)
        if view_type == 'form':
            doc = etree.XML(res['arch'])
            for node in doc.xpath(
                    "//button[@name='request_validation' or @name='restart_validation']"):
                node.getparent().remove(node)
            res['arch'] = etree.tostring(doc, encoding='unicode')
        return res


class ConstructionResourcePlanLine(models.Model):
    """Recurso planificado en un nivel de la obra: material, servicio,
    contrata, personal propio o producción."""
    _name = 'construction.resource.plan.line'
    _description = 'Línea del plan de recursos'
    _inherit = ['analytic.mixin']
    _order = 'plan_id, floor_task_id, apartment_task_id, space_task_id, module_task_id, stage, id'
    _check_company_auto = True

    plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan', required=True, ondelete='cascade',
        index=True, check_company=True)
    plan_state = fields.Selection(related='plan_id.state', string='Estado del plan')
    project_id = fields.Many2one(
        related='plan_id.project_id', string='Obra', store=True, index=True)
    company_id = fields.Many2one(
        related='plan_id.company_id', string='Compañía', store=True, index=True)
    currency_id = fields.Many2one(related='plan_id.currency_id', string='Moneda')
    task_id = fields.Many2one(
        'project.task', string='Nivel', index=True, check_company=True,
        help='Tarea de piso, departamento, ambiente o módulo. Vacía: la obra.')
    task_level = fields.Selection(
        string='Tipo de nivel', related='task_id.construction_level', store=True)
    # Ancestros por nivel: base de la acumulación del árbol y del filtro por
    # selección (read_group por nivel, sin recursión en Python).
    floor_task_id = fields.Many2one(
        'project.task', string='Piso', compute='_compute_ancestors', store=True, index=True,
        check_company=True)
    apartment_task_id = fields.Many2one(
        'project.task', string='Departamento', compute='_compute_ancestors', store=True,
        index=True, check_company=True)
    space_task_id = fields.Many2one(
        'project.task', string='Ambiente', compute='_compute_ancestors', store=True, index=True,
        check_company=True)
    module_task_id = fields.Many2one(
        'project.task', string='Módulo', compute='_compute_ancestors', store=True, index=True,
        check_company=True)
    resource_type = fields.Selection(
        RESOURCE_TYPES, string='Tipo de recurso', required=True, default='material')
    stage = fields.Selection(STAGES, string='Etapa')
    product_id = fields.Many2one(
        'product.product', string='Producto', check_company=True, index=True)
    activity_id = fields.Many2one(
        'construction.labor.activity', string='Actividad (driver)', check_company=True,
        index=True)
    partner_id = fields.Many2one(
        'res.partner', string='Contrata o proveedor', check_company=True, index=True)
    role_id = fields.Many2one('planning.role', string='Rol')
    typology_id = fields.Many2one(
        'construction.typology', string='Tipología', check_company=True)
    product_uom_id = fields.Many2one('uom.uom', string='Unidad', required=True)
    qty_planned = fields.Float(string='Cantidad', digits='Product Unit', required=True)
    price_unit_planned = fields.Monetary(
        string='Costo unitario', currency_field='currency_id',
        help='Lo escribe el planificador después de revisar los precios de compra; en '
             'contratas, la tarifa vigente es la referencia.')
    amount_planned = fields.Monetary(
        string='Monto', compute='_compute_amount_planned', store=True,
        currency_field='currency_id')
    price_basis = fields.Char(
        string='Base del costo',
        help='Qué miró el planificador al fijar el costo (p. ej. «media móvil 4 semanas '
             'al 28/09: 122.84»).')
    price_basis_date = fields.Date(string='Fecha de la base')
    amount_budgeted = fields.Monetary(
        string='Presupuesto', readonly=True, copy=False, currency_field='currency_id',
        help='Monto de la línea congelado al aprobar el plan.')
    # Control (P-13): almacenados para filtrar, agrupar y analizar en pivote.
    # No dependen de campos almacenados (salen de compras, inventario,
    # fabricación, avances, turnos y hojas de horas): los actualiza
    # ``_refresh_control`` con cada evento de esos documentos y la acción
    # programada de control (ver DISENO_TECNICO.md, fase 7).
    amount_committed = fields.Monetary(
        string='Comprometido', readonly=True, copy=False, currency_field='currency_id',
        help='Pedido o comprado sin consumir, OC de servicio sin recibir y turnos sin horas '
             'registradas.')
    amount_actual = fields.Monetary(
        string='Real', readonly=True, copy=False, currency_field='currency_id',
        help='Consumido al costo del plan, recibido en la OC de servicio y horas registradas '
             'por el costo hora del empleado.')
    amount_remaining = fields.Monetary(
        string='Saldo', readonly=True, copy=False, currency_field='currency_id',
        help='Planificado menos comprometido menos real.')
    executed_pct = fields.Float(
        string='% ejecutado', readonly=True, copy=False, aggregator='avg',
        help='Real entre planificado.')
    date_needed = fields.Date(
        string='Fecha de necesidad', compute='_compute_date_needed', store=True,
        readonly=False, help='Inicio de la tarea menos la anticipación del tipo de recurso.')
    supply_mode = fields.Selection(
        [('central', 'Almacén central'), ('direct', 'Directo a obra')],
        string='Abastecimiento', default='central')
    source = fields.Selection(
        [('generated', 'Generada'), ('manual', 'Manual'), ('replan', 'Replanificación')],
        string='Origen', default='manual', readonly=True)
    source_ref = fields.Char(string='Referencia del origen', readonly=True)
    previous_line_id = fields.Many2one(
        'construction.resource.plan.line', string='Línea anterior', readonly=True,
        check_company=True)
    allocation_ids = fields.One2many(
        'construction.resource.plan.allocation', 'plan_line_id', string='Asignaciones')
    # Cantidades de ejecución (especificación, «Reglas de cálculo»), en la
    # unidad de la línea. Se leen sin los permisos de compras, inventario y
    # fabricación del usuario: solo se muestran.
    qty_requested = fields.Float(
        string='Pedido', compute='_compute_execution_qty', digits='Product Unit',
        compute_sudo=True,
        help='Material: requerimientos de obra y OF. Contrata: OC de servicio. Personal '
             'propio: horas de turnos.')
    qty_purchased = fields.Float(
        string='Comprado', compute='_compute_execution_qty', digits='Product Unit',
        compute_sudo=True,
        help='Compra masiva y compras confirmadas del faltante de los requerimientos.')
    qty_dispatched = fields.Float(
        string='Despachado', compute='_compute_execution_qty', digits='Product Unit',
        compute_sudo=True, help='Llegado a la obra y entregado a la planta para las OF.')
    qty_consumed = fields.Float(
        string='Consumido', compute='_compute_execution_qty', digits='Product Unit',
        compute_sudo=True, help='Consumo en obra y componentes consumidos de las OF.')
    qty_remaining = fields.Float(
        string='Saldo por pedir', compute='_compute_execution_qty', digits='Product Unit',
        compute_sudo=True, help='Planificado menos pedido.')
    resource_name = fields.Char(
        string='Actividad o producto', compute='_compute_resource_name',
        help='La actividad (driver) de contratas y personal propio; el producto o el rol en '
             'las demás líneas.')
    # Avance por driver (fase 5): la contrata reporta unidades y el sistema
    # calcula el porcentaje.
    progress_ids = fields.One2many(
        'construction.task.progress', 'plan_line_id', string='Avances')
    qty_executed = fields.Float(
        string='Ejecutado', compute='_compute_progress_qty', digits='Product Unit',
        compute_sudo=True,
        help='Contrata: avances validados. Personal propio por horas: horas de la hoja de '
             'horas del nivel y sus descendientes con empleados del rol. Material: consumido.')
    qty_settled = fields.Float(
        string='Liquidado', compute='_compute_progress_qty', digits='Product Unit',
        compute_sudo=True, help='Avances que entraron a una liquidación aprobada.')
    progress_pct = fields.Float(
        string='Avance', compute='_compute_progress_qty', compute_sudo=True,
        help='Ejecutado entre planificado, hasta 100 %.')
    line_state = fields.Selection(
        [('planned', 'Planificada'), ('partial', 'Parcial'), ('purchasing', 'En compra'),
         ('done', 'Completa'), ('exceeded', 'Excedida'), ('cancel', 'Cancelada')],
        string='Estado', default='planned', required=True, readonly=True, copy=False,
        index=True,
        help='En este orden: Excedida (pedido sobre lo planificado más la tolerancia), '
             'Completa, En compra, Parcial y Planificada. Se actualiza con cada documento '
             'del plan.')

    @api.depends('task_id', 'task_id.construction_level', 'task_id.construction_floor_task_id',
                 'task_id.construction_apartment_task_id', 'task_id.construction_space_task_id')
    def _compute_ancestors(self):
        for line in self:
            task = line.task_id
            line.floor_task_id = task.construction_floor_task_id
            line.apartment_task_id = task.construction_apartment_task_id
            line.space_task_id = task.construction_space_task_id
            line.module_task_id = task if task.construction_level == 'module' else False

    @api.depends('qty_planned', 'price_unit_planned')
    def _compute_amount_planned(self):
        for line in self:
            line.amount_planned = line.currency_id.round(line.qty_planned * line.price_unit_planned) \
                if line.currency_id else line.qty_planned * line.price_unit_planned

    def _get_line_execution(self):
        """{línea: (comprometido, real)}.

        Material, servicio y producción, al costo del plan: comprometido es lo
        pedido o comprado aún no consumido; real, lo consumido. Contratas: lo
        asignado a la OC de servicio no recibido y lo recibido, a la tarifa de
        la OC. Personal propio: además, horas registradas por el costo hora
        del empleado (real) y horas de turnos aún sin registrar (comprometido)."""
        result = {}
        for line in self:
            committed = actual = 0.0
            if line.resource_type in ('material', 'service', 'production'):
                price = line.price_unit_planned
                covered = max(line.qty_requested, line.qty_purchased)
                committed = max(covered - line.qty_consumed, 0.0) * price
                actual = line.qty_consumed * price
            else:
                if line.resource_type == 'labor':
                    committed, actual = line._get_labor_amounts()
                for allocation in line.allocation_ids.filtered(
                        lambda a: a.kind == 'service_order' and a.state != 'cancel'):
                    # La tarifa de la OC se lee aunque el usuario del plan no
                    # tenga acceso a compras: solo para valorizar.
                    po_line_sudo = allocation.sudo().purchase_line_id
                    price = po_line_sudo.price_unit
                    committed += max(allocation.qty_allocated - allocation.qty_done, 0.0) * price
                    actual += allocation.qty_done * price
            currency = line.currency_id
            result[line] = (currency.round(committed) if currency else committed,
                            currency.round(actual) if currency else actual)
        return result

    @api.depends('qty_planned', 'allocation_ids.qty_allocated', 'allocation_ids.state',
                 'allocation_ids.qty_purchased', 'allocation_ids.qty_dispatched',
                 'allocation_ids.qty_consumed')
    def _compute_execution_qty(self):
        for line in self:
            allocations = line.allocation_ids
            line.qty_requested = sum(a._get_requested_qty() for a in allocations)
            line.qty_purchased = sum(allocations.mapped('qty_purchased'))
            line.qty_dispatched = sum(allocations.mapped('qty_dispatched'))
            line.qty_consumed = sum(allocations.mapped('qty_consumed'))
            line.qty_remaining = line.qty_planned - line.qty_requested

    def _is_hour_based(self):
        """Personal propio medido en horas: su ejecutado sale de la hoja de horas."""
        self.ensure_one()
        hour = self.env.ref('uom.product_uom_hour', raise_if_not_found=False)
        return bool(self.resource_type == 'labor' and hour and self.product_uom_id
                    and self.product_uom_id._has_common_reference(hour))

    def _get_role(self):
        self.ensure_one()
        return self.role_id or self.activity_id.role_id

    def _get_timesheet_by_employee(self):
        """{empleado: horas} de la hoja de horas del nivel de la línea y sus
        descendientes con empleados del rol de la línea (o de su actividad)."""
        self.ensure_one()
        if not self.task_id:
            return {}
        domain = [('task_id', 'child_of', self.task_id.id), ('project_id', '=', self.project_id.id),
                  ('employee_id', '!=', False)]
        # Hasta una fecha de corte: la entrega semanal (fase 10).
        if self.env.context.get('construction_date_to'):
            domain.append(('date', '<=', self.env.context['construction_date_to']))
        role = self._get_role()
        if role:
            domain.append(('employee_id.planning_role_ids', 'in', role.ids))
        # sudo: las horas de otros empleados se suman sin dar acceso a sus
        # registros; solo para el avance y el costo de la línea.
        lines_sudo = self.env['account.analytic.line'].sudo()
        return {employee: hours or 0.0 for employee, hours in lines_sudo._read_group(
            domain, ['employee_id'], ['unit_amount:sum'])}

    def _get_timesheet_hours(self):
        """Horas registradas de la línea, en su unidad."""
        self.ensure_one()
        hours = sum(self._get_timesheet_by_employee().values())
        hour = self.env.ref('uom.product_uom_hour')
        return hour._compute_quantity(hours, self.product_uom_id) if self.product_uom_id else hours

    def _get_labor_amounts(self):
        """(comprometido, real) del personal propio: real = horas registradas
        por el costo hora de cada empleado; comprometido = horas de sus turnos
        de la línea aún no registradas, al mismo costo."""
        self.ensure_one()
        registered = self._get_timesheet_by_employee()
        # sudo: el costo hora y los turnos son de RR. HH. y Planificación; se
        # leen solo para valorizar la línea.
        actual = sum(employee.sudo().hourly_cost * hours for employee, hours in registered.items())
        planned = defaultdict(float)
        for allocation in self.allocation_ids.filtered(
                lambda a: a.kind == 'planning_slot' and a.state != 'cancel'):
            slot_sudo = allocation.sudo().slot_id
            employee = slot_sudo.employee_id
            if employee:
                planned[employee] += slot_sudo.allocated_hours
        committed = sum(
            max(hours - registered.get(employee, 0.0), 0.0) * employee.sudo().hourly_cost
            for employee, hours in planned.items())
        return committed, actual

    @api.depends('activity_id', 'product_id', 'role_id')
    def _compute_resource_name(self):
        for line in self:
            line.resource_name = (line.activity_id or line.product_id or line.role_id).display_name

    @api.depends('qty_planned', 'resource_type', 'qty_consumed', 'progress_ids.state',
                 'progress_ids.qty', 'progress_ids.settled')
    def _compute_progress_qty(self):
        Progress = self.env['construction.task.progress']
        executed = defaultdict(float)
        settled = defaultdict(float)
        real = self.filtered(lambda l: l.id and l.resource_type in DRIVER_TYPES)
        if real:
            for line, is_settled, qty in Progress._read_group(
                    [('plan_line_id', 'in', real.ids), ('state', '=', 'validated')],
                    ['plan_line_id', 'settled'], ['qty:sum']):
                executed[line.id] += qty or 0.0
                if is_settled:
                    settled[line.id] += qty or 0.0
        for line in self:
            if line.resource_type not in DRIVER_TYPES:
                qty = line.qty_consumed
            elif line.id and line._is_hour_based():
                qty = line._get_timesheet_hours()
            else:
                qty = executed.get(line.id, 0.0)
            line.qty_executed = qty
            line.qty_settled = settled.get(line.id, 0.0)
            line.progress_pct = min(qty / line.qty_planned, 1.0) if line.qty_planned else 0.0

    def _construction_valued_execution(self, day):
        """Ejecutado valorizado de las líneas hasta ``day`` (inclusive), por
        tipo: {línea: {'contract', 'labor', 'material'}}. Es el numerador del
        avance de la partida (especificación, «Avance de la partida»):
        contratas y personal propio por driver = avances validados con fecha
        hasta el corte × tarifa del plan; personal propio por horas = horas
        registradas × costo hora del empleado; material, servicio y
        producción = consumido hasta el corte × costo del plan."""
        result = {line: {'contract': 0.0, 'labor': 0.0, 'material': 0.0} for line in self}
        if not self:
            return result
        day = fields.Date.to_date(day)
        drivers = self.filtered(lambda l: l.resource_type in DRIVER_TYPES)
        hour_based = drivers.filtered(lambda l: l._is_hour_based())
        by_driver = drivers - hour_based
        if by_driver:
            # sudo: se valoriza lo validado de todas las contratas aunque quien
            # prepara la entrega no vea sus avances.
            progress_sudo = self.env['construction.task.progress'].sudo()
            for line, qty in progress_sudo._read_group(
                    [('plan_line_id', 'in', by_driver.ids), ('state', '=', 'validated'),
                     ('date', '<=', day)], ['plan_line_id'], ['qty:sum']):
                line = self.browse(line.id)
                result[line][line.resource_type] += (qty or 0.0) * line.price_unit_planned
        for line in hour_based:
            registered = line.with_context(
                construction_date_to=day)._get_timesheet_by_employee()
            # sudo: el costo hora es de RR. HH.; solo para valorizar la línea.
            result[line]['labor'] += sum(
                employee.sudo().hourly_cost * hours for employee, hours in registered.items())
        materials = self - drivers
        allocations = materials.allocation_ids
        if allocations:
            Allocation = self.env['construction.resource.plan.allocation']
            for allocation, qty in Allocation._construction_consumed_at(
                    allocations, day).items():
                line = allocation.plan_line_id
                result[line]['material'] += qty * line.price_unit_planned
        return result

    def _get_reported_qty(self):
        """Avance reportado y aún no validado de la línea."""
        self.ensure_one()
        return self.env['construction.task.progress']._read_group(
            [('plan_line_id', '=', self.id), ('state', '=', 'draft')], [], ['qty:sum'])[0][0]

    def _get_tolerance_qty(self):
        self.ensure_one()
        return self.qty_planned * (self.plan_id.exceed_tolerance or 0.0) / 100.0

    def _get_line_state(self):
        self.ensure_one()
        if self.plan_id.state == 'cancel':
            return 'cancel'
        uom = self.product_uom_id
        if not uom:
            return 'planned'
        planned = self.qty_planned
        allocations = self.allocation_ids
        if uom.compare(self.qty_requested, planned + self._get_tolerance_qty()) > 0:
            return 'exceeded'
        if self.resource_type in DRIVER_TYPES:
            # Contrata y personal propio: el driver acumulado (avances
            # validados u horas) sobre lo planificado más la tolerancia es
            # «Excedida»; si llega a lo planificado, o todo se asignó y se
            # recibió en la OC, «Completa».
            executed = self.qty_executed
            if uom.compare(executed, planned + self._get_tolerance_qty()) > 0:
                return 'exceeded'
            if not uom.is_zero(planned) and uom.compare(executed, planned) >= 0:
                return 'done'
            if not uom.is_zero(planned) and uom.compare(self.qty_requested, planned) >= 0 \
                    and not allocations.filtered(lambda a: a.state == 'open'):
                return 'done'
        elif not uom.is_zero(planned) and uom.compare(self.qty_dispatched, planned) >= 0:
            return 'done'
        purchasing = allocations.filtered(
            lambda a: a.state == 'open' and (
                a.kind == 'purchase_request'
                or (a.kind == 'material_request'
                    and a.material_request_line_id.line_state == 'purchasing')))
        if purchasing:
            return 'purchasing'
        if any(not uom.is_zero(qty) for qty in (
                self.qty_requested, self.qty_purchased, self.qty_dispatched)):
            return 'partial'
        return 'planned'

    def _get_execution_amounts(self):
        """Comprometido y real acumulados por etapa: {etapa: (comp., real)}."""
        result = defaultdict(lambda: (0.0, 0.0))
        for line, (committed, actual) in self._get_line_execution().items():
            if committed or actual:
                prev_committed, prev_actual = result[line.stage]
                result[line.stage] = (prev_committed + committed, prev_actual + actual)
        return result

    # Campos no almacenados de los que salen el estado y los montos de
    # control: se descartan de la caché antes de recalcular, porque cambian
    # con documentos de otros modelos sin dependencia declarada.
    _CONTROL_SOURCE_FIELDS = (
        'qty_requested', 'qty_purchased', 'qty_dispatched', 'qty_consumed', 'qty_remaining',
        'qty_executed', 'qty_settled', 'progress_pct')
    # Campos de la línea que cambian su control.
    _CONTROL_TRIGGERS = {
        'qty_planned', 'price_unit_planned', 'product_uom_id', 'resource_type', 'role_id',
        'activity_id', 'task_id', 'plan_id'}

    def _refresh_control(self):
        """Recalcula y guarda el estado de la línea y sus montos de control
        (comprometido, real, saldo, % ejecutado). Lo llaman los eventos de
        los documentos del plan (asignaciones, compras, requerimientos, OF,
        movimientos, avances, turnos y hojas de horas), el cambio de estado
        del plan y la acción programada de control."""
        # sudo: el control mira compras, inventario, fabricación, turnos y
        # horas que quien dispara el evento puede no ver; solo se guardan el
        # estado y los montos de la propia línea.
        lines_sudo = self.sudo().exists()
        if not lines_sudo:
            return
        self.env['construction.resource.plan.allocation'].invalidate_model(
            ['state', 'qty_done', 'qty_purchased', 'qty_dispatched', 'qty_consumed'])
        lines_sudo.invalidate_recordset(list(self._CONTROL_SOURCE_FIELDS))
        execution = lines_sudo._get_line_execution()
        updates = defaultdict(lambda: lines_sudo.browse())
        for line in lines_sudo:
            committed, actual = execution.get(line, (0.0, 0.0))
            currency = line.currency_id
            remaining = line.amount_planned - committed - actual
            pct = actual / line.amount_planned if line.amount_planned else 0.0
            vals = {
                'line_state': line._get_line_state(),
                'amount_committed': committed,
                'amount_actual': actual,
                'amount_remaining': currency.round(remaining) if currency else remaining,
                'executed_pct': round(pct, 6),
            }
            if any(line[key] != value for key, value in vals.items()):
                updates[tuple(sorted(vals.items()))] |= line
        for vals, lines in updates.items():
            lines.with_context(construction_plan_force=True).write(dict(vals))

    @api.model
    def _cron_refresh_control(self):
        """Red de seguridad del control: los turnos que terminan con el paso
        del tiempo y cualquier evento que no pase por el ORM."""
        lines = self.search([('plan_id.state', 'in', OPEN_STATES)])
        for ids in split_every(1000, lines.ids):
            self.browse(ids)._refresh_control()

    def _get_consumed_qty(self):
        """Cantidad ya pedida o ejecutada de la línea que se queda en esta
        versión: la base de «copiar solo saldos» al replanificar. Son las
        asignaciones cerradas; las abiertas pasan a la versión nueva al
        aprobarla (``_transfer_to_new_version``) y siguen contando allí."""
        self.ensure_one()
        return sum(a._get_requested_qty()
                   for a in self.allocation_ids.filtered(lambda a: a.state != 'open'))

    def _get_issue_label(self):
        """Texto corto de cada línea para los avisos de aprobación."""
        return [' · '.join(filter(None, [
            line.task_id.display_name or line.project_id.display_name,
            (line.product_id or line.activity_id).display_name,
        ])) for line in self]

    @api.depends('task_id', 'resource_type', 'plan_id.date_start', 'plan_id.lead_days_material',
                 'plan_id.lead_days_contract', 'plan_id.lead_days_production')
    def _compute_date_needed(self):
        for line, date_needed in self._get_default_date_needed().items():
            line.date_needed = date_needed

    def _get_default_date_needed(self):
        """{línea: inicio de su tarea (o del plan) menos la anticipación de su
        tipo de recurso}. Base de la fecha de necesidad y de «Cambiar fechas»."""
        start_field = self.env['al.gantt.field.map'].get_map().get('date_start')
        result = {}
        for line in self:
            plan = line.plan_id
            start = line.task_id[start_field] if line.task_id and start_field else False
            start = fields.Date.to_date(start) if start else plan.date_start
            lead = {
                'material': plan.lead_days_material, 'service': plan.lead_days_material,
                'contract': plan.lead_days_contract, 'labor': plan.lead_days_contract,
                'production': plan.lead_days_production,
            }.get(line.resource_type, 0)
            result[line] = start - timedelta(days=lead or 0) if start else False
        return result

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id and not self.product_uom_id:
            self.product_uom_id = self.product_id.uom_id

    @api.onchange('activity_id')
    def _onchange_activity_id(self):
        activity = self.activity_id
        if activity:
            self.product_uom_id = activity.uom_id
            self.stage = self.stage or activity.stage
            self.product_id = self.product_id or activity.product_id
            if not self.price_unit_planned:
                self.price_unit_planned = activity._get_rate(
                    self.plan_id.project_id, self.partner_id)[0]

    @api.constrains('resource_type', 'activity_id')
    def _check_activity(self):
        for line in self:
            if line.resource_type in ('contract', 'labor') and not line.activity_id:
                raise ValidationError(self.env._(
                    'Las líneas de contrata y de personal propio necesitan su actividad (driver).'))

    @api.constrains('task_id', 'plan_id')
    def _check_task_project(self):
        for line in self:
            if line.task_id and line.task_id.project_id != line.plan_id.project_id:
                raise ValidationError(self.env._(
                    'El nivel %s no pertenece a la obra del plan.', line.task_id.display_name))

    # Líneas editables solo con el plan en borrador (especificación).
    _LOCKED_ALLOWED = {'date_needed', 'line_state', 'amount_committed', 'amount_actual',
                       'amount_remaining', 'executed_pct'}

    def _check_plan_editable(self, vals=None):
        if self.env.context.get('construction_plan_force'):
            return
        if vals is not None and set(vals) <= self._LOCKED_ALLOWED:
            return
        locked = self.plan_id.filtered(lambda p: p.state != 'draft')
        if locked:
            raise UserError(self.env._(
                'Las líneas de %s no se pueden cambiar: el plan ya no está en borrador.',
                ', '.join(locked.mapped('name'))))

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._check_plan_editable()
        lines._refresh_control()
        return lines

    def write(self, vals):
        self._check_plan_editable(vals)
        res = super().write(vals)
        if self._CONTROL_TRIGGERS & set(vals):
            self._refresh_control()
        return res

    def unlink(self):
        self._check_plan_editable()
        return super().unlink()

    def action_open_price_wizard(self):
        """«Aplicar costo» desde la lista de líneas: las seleccionadas, que
        deben ser de un solo plan y un solo producto."""
        plan = self.plan_id
        if len(plan) != 1 or len(self.product_id) != 1 or not all(self.mapped('product_id')):
            raise UserError(self.env._(
                'Seleccione líneas de un solo plan y de un solo producto.'))
        action = plan.action_open_price_wizard()
        action['context'] = {
            'default_plan_id': plan.id,
            'default_product_id': self.product_id.id,
            'default_line_ids': [Command.set(self.ids)],
        }
        return action
