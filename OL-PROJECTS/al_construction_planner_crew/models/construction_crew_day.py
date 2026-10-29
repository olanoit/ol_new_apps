# -*- coding: utf-8 -*-
"""Cuadrillas en jornales (v1.8, M18-06 y M18-07).

Las cuadrillas se planifican y se miden en jornales. La unidad es la de la
obra (por defecto la de la compañía, que fija el perfil): hora, medio día o
día completo, con el mismo redondeo que los tipos de entrada de trabajo de
la nómina de Odoo (``round_days`` sin redondeo, medio día o día y
``round_days_type`` al más cercano, hacia arriba o hacia abajo).

Cada rol de cuadrilla tiene un costo de referencia por jornal: el del puesto
del régimen general (``hr.job``) o, con la planilla de construcción civil, el
jornal de su categoría (operario, oficial, peón) en la tabla vigente.

``construction.crew.day`` reúne lo planificado (al asignar la cuadrilla) y lo
ejecutado (los días marcados en la sede de la obra, con la marcación) por
obra, etapa y sub etapa, en jornales y en soles: es el análisis de control de
las cuadrillas."""
from odoo import api, fields, models
from odoo.tools.float_utils import float_round

# Mismos códigos que hr.work.entry.type (hr_payroll): round_days y
# round_days_type.
TIME_UNITS = [
    ('NO', 'Hora'),
    ('HALF', 'Medio día'),
    ('FULL', 'Día completo'),
]
ROUND_TYPES = [
    ('HALF-UP', 'Al más cercano'),
    ('UP', 'Hacia arriba'),
    ('DOWN', 'Hacia abajo'),
]


def round_days(days, unit, round_type):
    """Jornales redondeados como una entrada de trabajo de la nómina
    (``hr.payslip._round_days``): sin redondeo, al medio día o al día."""
    if unit in ('HALF', 'FULL'):
        return float_round(days, precision_rounding=0.5 if unit == 'HALF' else 1,
                           rounding_method=round_type or 'HALF-UP')
    return days


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_crew_time_unit = fields.Selection(
        TIME_UNITS, string='Unidad de las cuadrillas', default='FULL',
        help='En qué se miden los jornales de las cuadrillas propias: horas (sin redondeo), '
             'medio día o día completo. Es el redondeo de los tipos de entrada de trabajo de '
             'la nómina.')
    construction_crew_round_type = fields.Selection(
        ROUND_TYPES, string='Redondeo de los jornales', default='HALF-UP')
    construction_crew_hours_per_day = fields.Float(
        string='Horas por jornal', default=8.0,
        help='Horas de un jornal completo: convierte las horas marcadas en jornales.')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_crew_time_unit = fields.Selection(
        related='company_id.construction_crew_time_unit', readonly=False)
    construction_crew_round_type = fields.Selection(
        related='company_id.construction_crew_round_type', readonly=False)
    construction_crew_hours_per_day = fields.Float(
        related='company_id.construction_crew_hours_per_day', readonly=False)


class ProjectProject(models.Model):
    _inherit = 'project.project'

    construction_crew_time_unit = fields.Selection(
        TIME_UNITS, string='Unidad de las cuadrillas',
        compute='_compute_construction_crew_time_unit', store=True, readonly=False,
        help='La de la compañía; cada obra la puede cambiar.')

    @api.depends('company_id')
    def _compute_construction_crew_time_unit(self):
        for project in self:
            company = project.company_id or self.env.company
            project.construction_crew_time_unit = project.construction_crew_time_unit \
                or company.construction_crew_time_unit or 'FULL'

    def _construction_round_days(self, days):
        self.ensure_one()
        company = self.company_id or self.env.company
        return round_days(days, self.construction_crew_time_unit or 'FULL',
                          company.construction_crew_round_type)


class HrJob(models.Model):
    _inherit = 'hr.job'

    construction_daily_cost = fields.Monetary(
        string='Costo por jornal', currency_field='construction_currency_id',
        help='Costo de referencia de un jornal del puesto (régimen general): valoriza las '
             'cuadrillas planificadas y los jornales marcados.')
    construction_currency_id = fields.Many2one(
        'res.currency', compute='_compute_construction_currency_id')

    @api.depends('company_id')
    def _compute_construction_currency_id(self):
        for job in self:
            job.construction_currency_id = (job.company_id or self.env.company).currency_id


class PlanningRole(models.Model):
    _inherit = 'planning.role'

    # El rol de la cuadrilla es el mismo registro que el tipo de turno del
    # monitor de asistencia de la nómina (M18-06): solo se le agrega de dónde
    # sale su costo.
    construction_job_id = fields.Many2one(
        'hr.job', string='Puesto (régimen general)',
        help='Las personas de la cuadrilla con este rol deben tener este puesto; el costo de '
             'referencia es su costo por jornal.')
    construction_daily_cost = fields.Float(
        string='Costo por jornal', digits='Product Price',
        help='Costo de referencia si el rol no tiene puesto ni categoría de construcción '
             'civil.')

    def _construction_reference_cost(self, date=None, company=None):
        """Costo de referencia de un jornal del rol."""
        self.ensure_one()
        return self.construction_job_id.construction_daily_cost or self.construction_daily_cost

    def _construction_check_member(self, employee):
        """La persona asignada al rol tiene su puesto (o su categoría, con la
        planilla de construcción civil): mensaje de error o False."""
        self.ensure_one()
        job = self.construction_job_id
        if job and employee and employee.job_id != job:
            return self.env._(
                '%(employee)s no tiene el puesto %(job)s que pide el rol %(role)s.',
                employee=employee.name, job=job.name, role=self.name)
        return False


class ConstructionCrewDay(models.Model):
    """Jornales planificados y ejecutados de las cuadrillas propias."""
    _name = 'construction.crew.day'
    _description = 'Jornales de las cuadrillas'
    _order = 'date desc, id desc'
    _check_company_auto = True

    kind = fields.Selection(
        [('planned', 'Planificado'), ('executed', 'Ejecutado')], string='Tipo', required=True,
        index=True)
    project_id = fields.Many2one('project.project', string='Obra', required=True, index=True,
                                 check_company=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, index=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    plan_line_id = fields.Many2one(
        'construction.resource.plan.line', string='Línea del plan', index=True,
        ondelete='set null', check_company=True)
    task_id = fields.Many2one('project.task', string='Nivel', index=True)
    stage = fields.Selection(related='plan_line_id.stage', string='Etapa', store=True)
    stage_parent = fields.Selection(related='plan_line_id.stage_parent', string='Etapa padre',
                                    store=True)
    role_id = fields.Many2one('planning.role', string='Rol', index=True)
    employee_id = fields.Many2one('hr.employee', string='Persona', index=True)
    date = fields.Date(string='Fecha', required=True, index=True)
    days = fields.Float(string='Jornales', digits=(16, 2), aggregator='sum')
    hours = fields.Float(string='Horas', digits=(16, 2), aggregator='sum')
    amount = fields.Monetary(string='Costo', currency_field='currency_id', aggregator='sum')
    slot_id = fields.Many2one('planning.slot', string='Turno', ondelete='cascade', index=True)
    source = fields.Selection(
        [('crew', 'Asignar cuadrilla'), ('attendance', 'Marcación')], string='Origen',
        required=True, default='crew')

    @api.model
    def _create_planned(self, slots, days_by_slot):
        """Jornales planificados de los turnos creados por «Asignar cuadrilla»
        al costo de referencia de su rol."""
        values = []
        for slot in slots:
            line = slot.construction_plan_line_id
            role = slot.role_id
            days = days_by_slot.get(slot.id, 0.0)
            if not days:
                continue
            cost = role._construction_reference_cost(slot.start_datetime.date(),
                                                     line.company_id) if role else 0.0
            values.append({
                'kind': 'planned', 'project_id': line.project_id.id,
                'company_id': line.company_id.id, 'plan_line_id': line.id,
                'task_id': line.task_id.id, 'role_id': role.id,
                'employee_id': slot.resource_ids.employee_id[:1].id, 'date': slot.start_datetime.date(),
                'days': days, 'hours': slot.allocated_hours,
                'amount': line.currency_id.round(days * cost), 'slot_id': slot.id,
                'source': 'crew'})
        return self.sudo().create(values)


class ConstructionResourcePlan(models.Model):
    _inherit = 'construction.resource.plan'

    def action_open_crew_days(self):
        """Jornales de las cuadrillas del plan: planificados contra ejecutados
        por etapa y sub etapa."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'al_construction_planner_crew.action_construction_crew_day')
        action['domain'] = [('project_id', '=', self.project_id.id)]
        action['name'] = self.env._('Jornales · %s', self.project_id.display_name)
        return action

