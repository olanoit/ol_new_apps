# -*- coding: utf-8 -*-
"""Cuadrillas con la nómina de construcción civil y la marcación (v1.8,
M18-06 a M18-08).

* El rol de la cuadrilla se vincula a una categoría de construcción civil
  (operario, oficial, peón): su costo de referencia es el jornal básico de la
  categoría en la tabla vigente, y al asignar personas se valida que su
  categoría coincida.
* Lo ejecutado son los jornales marcados en la sede de la obra: las horas de
  cada día entre las horas de un jornal, redondeadas en la unidad de la obra
  (hora, medio día o día), al jornal de la categoría o al costo del puesto.
  Cada día va a la línea del plan del turno de la persona ese día (su etapa y
  sub etapa).
* Cada obra tiene sus sedes de obra; la sede se puede crear sola al marcar
  el proyecto como obra. Las sedes de planta son de la compañía y no se
  vinculan a ningún proyecto: su costo es costo de fabricación y llega a las
  obras con las órdenes de fabricación."""
from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PlanningRole(models.Model):
    _inherit = 'planning.role'

    construction_category_id = fields.Many2one(
        'l10n_pe.hr.construction.category', string='Categoría de construcción civil',
        help='Operario, oficial, peón: el costo de referencia es su jornal básico en la tabla '
             'vigente y las personas de la cuadrilla con este rol deben tener esa categoría.')

    def _construction_reference_cost(self, date=None, company=None):
        self.ensure_one()
        if self.construction_category_id:
            table = self.env['l10n_pe.hr.construction.wage.table']._get_table_for_date(
                date or fields.Date.context_today(self), company or self.env.company)
            line = table.line_ids.filtered(
                lambda l: l.category_id == self.construction_category_id)[:1]
            if line:
                return line.daily_wage
        return super()._construction_reference_cost(date, company)

    def _construction_check_member(self, employee):
        self.ensure_one()
        category = self.construction_category_id
        if category and employee:
            # sudo: la categoría está en el contrato (RR. HH.); solo se compara.
            current = employee.sudo().version_id.l10n_pe_construction_category_id
            if current != category:
                return self.env._(
                    '%(employee)s es %(current)s y el rol %(role)s pide %(category)s.',
                    employee=employee.name, current=current.name or self.env._('sin categoría'),
                    role=self.name, category=category.name)
            return False
        return super()._construction_check_member(employee)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _construction_daily_cost(self, day, hours_per_day):
        """Costo de un jornal de la persona: el jornal de su categoría de
        construcción civil ese día, el costo por jornal de su puesto o su
        costo por hora por las horas de un jornal."""
        self.ensure_one()
        # sudo: costos de RR. HH.; solo valorizan los jornales.
        employee_sudo = self.sudo()
        version = employee_sudo.version_id
        if version.l10n_pe_construction_category_id:
            line = version._l10n_pe_get_wage_line(on_date=day)
            if line:
                return line.daily_wage
        if employee_sudo.job_id.construction_daily_cost:
            return employee_sudo.job_id.construction_daily_cost
        return (employee_sudo.hourly_cost or 0.0) * hours_per_day


class ConstructionCrewDay(models.Model):
    _inherit = 'construction.crew.day'

    attendance_ids = fields.Many2many(
        'hr.attendance', 'construction_crew_day_attendance_rel', 'crew_day_id', 'attendance_id',
        string='Marcaciones')

    @api.model
    def _refresh_executed(self, projects, date_from, date_to):
        """Rehace los jornales ejecutados de ``projects`` entre esas fechas
        desde la marcación en sus sedes de obra."""
        projects = projects.filtered('is_construction_site')
        if not projects or not date_from or not date_to:
            return self.browse()
        # sudo: la marcación y los costos son de RR. HH.; el análisis solo
        # guarda jornales y montos por obra.
        Attendance = self.env['hr.attendance'].sudo()
        sites = self.env['l10n_pe.hr.construction.site'].sudo().search(
            [('project_id', 'in', projects.ids)])
        old = self.sudo().search([('kind', '=', 'executed'), ('project_id', 'in', projects.ids),
                                  ('date', '>=', date_from), ('date', '<=', date_to)])
        old.unlink()
        if not sites:
            return self.browse()
        start = datetime.combine(date_from - timedelta(days=1), time.min)
        end = datetime.combine(date_to + timedelta(days=1), time.max)
        attendances = Attendance.search([
            ('l10n_pe_construction_site_id', 'in', sites.ids), ('check_in', '>=', start),
            ('check_in', '<=', end), ('check_out', '!=', False)])
        days = defaultdict(lambda: {'hours': 0.0, 'attendances': Attendance})
        for attendance in attendances:
            site = attendance.l10n_pe_construction_site_id
            local = pytz.utc.localize(attendance.check_in).astimezone(site._tz())
            day = local.date()
            if not date_from <= day <= date_to:
                continue
            key = (site.project_id, attendance.employee_id, day)
            days[key]['hours'] += attendance.worked_hours or 0.0
            days[key]['attendances'] |= attendance
        Slot = self.env['planning.slot'].sudo()
        values = []
        for (project, employee, day), data in days.items():
            company = project.company_id or self.env.company
            hours_per_day = company.construction_crew_hours_per_day or 8.0
            worked = project._construction_round_days(data['hours'] / hours_per_day)
            if not worked:
                continue
            day_start = datetime.combine(day, time.min)
            slot = Slot.search([
                ('resource_id.employee_id', '=', employee.id), ('project_id', '=', project.id),
                ('construction_plan_line_id', '!=', False),
                ('start_datetime', '<=', day_start + timedelta(days=1)),
                ('end_datetime', '>=', day_start)], order='start_datetime desc', limit=1)
            line = slot.construction_plan_line_id
            values.append({
                'kind': 'executed', 'project_id': project.id, 'company_id': company.id,
                'plan_line_id': line.id, 'task_id': line.task_id.id,
                'role_id': slot.role_id.id, 'employee_id': employee.id, 'date': day,
                'days': worked, 'hours': data['hours'],
                'amount': company.currency_id.round(
                    worked * employee._construction_daily_cost(day, hours_per_day)),
                'source': 'attendance',
                'attendance_ids': [(6, 0, data['attendances'].ids)],
            })
        return self.sudo().create(values)

    @api.model
    def _cron_refresh_executed(self, days=14):
        """Jornales ejecutados de las últimas semanas de las obras con sede."""
        today = fields.Date.context_today(self)
        projects = self.env['l10n_pe.hr.construction.site'].sudo().search(
            [('project_id', '!=', False)]).project_id
        self._refresh_executed(projects, today - timedelta(days=days), today)


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    def _construction_refresh_crew_days(self):
        """Los jornales ejecutados siguen a la marcación de la obra."""
        by_project = defaultdict(set)
        for attendance in self.sudo():
            project = attendance.l10n_pe_construction_site_id.project_id
            if project and attendance.check_in:
                day = fields.Date.to_date(attendance.check_in)
                by_project[project].update({day - timedelta(days=1), day, day + timedelta(days=1)})
        CrewDay = self.env['construction.crew.day']
        for project, days in by_project.items():
            CrewDay._refresh_executed(project, min(days), max(days))

    @api.model_create_multi
    def create(self, vals_list):
        attendances = super().create(vals_list)
        attendances._construction_refresh_crew_days()
        return attendances

    def write(self, vals):
        before = self.sudo().filtered(lambda a: a.l10n_pe_construction_site_id.project_id)
        res = super().write(vals)
        if {'check_in', 'check_out', 'l10n_pe_construction_site_id', 'employee_id'} & set(vals):
            (before | self)._construction_refresh_crew_days()
        return res


class L10nPeHrConstructionSite(models.Model):
    _inherit = 'l10n_pe.hr.construction.site'

    site_kind = fields.Selection(
        [('site', 'Obra'), ('plant', 'Planta')], string='Tipo de sede', default='site',
        required=True,
        help='Obra: de un proyecto, su costo de personal es de la obra. Planta: producción '
             'central de la compañía, sin proyecto; su costo es de fabricación y llega a las '
             'obras con las órdenes de fabricación.')

    @api.constrains('site_kind', 'project_id')
    def _check_site_kind(self):
        for site in self:
            if site.site_kind == 'plant' and site.project_id:
                raise ValidationError(self.env._(
                    'La sede de planta %s es de la compañía: no se vincula a una obra.',
                    site.name))

    @api.onchange('site_kind')
    def _onchange_site_kind(self):
        if self.site_kind == 'plant':
            self.project_id = False


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_site_auto_create = fields.Boolean(
        string='Crear la sede de obra con la obra',
        help='Al marcar un proyecto como obra se crea su sede de marcación con su nombre y su '
             'cuenta analítica, y la ubicación, el radio y la hora límite por defecto.')
    construction_site_latitude = fields.Float(string='Latitud por defecto', digits=(10, 7))
    construction_site_longitude = fields.Float(string='Longitud por defecto', digits=(10, 7))
    construction_site_radius_m = fields.Integer(string='Radio por defecto (m)', default=200)
    construction_site_entry_deadline = fields.Float(
        string='Hora límite por defecto', default=7.0 + 50 / 60.0)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_site_auto_create = fields.Boolean(
        related='company_id.construction_site_auto_create', readonly=False)
    construction_site_latitude = fields.Float(
        related='company_id.construction_site_latitude', readonly=False)
    construction_site_longitude = fields.Float(
        related='company_id.construction_site_longitude', readonly=False)
    construction_site_radius_m = fields.Integer(
        related='company_id.construction_site_radius_m', readonly=False)
    construction_site_entry_deadline = fields.Float(
        related='company_id.construction_site_entry_deadline', readonly=False)


class ProjectProject(models.Model):
    _inherit = 'project.project'

    @api.model_create_multi
    def create(self, vals_list):
        projects = super().create(vals_list)
        projects._construction_create_site()
        return projects

    def write(self, vals):
        res = super().write(vals)
        if vals.get('is_construction_site'):
            self._construction_create_site()
        return res

    def _construction_create_site(self):
        """Sede de obra del proyecto marcado como obra (M18-08), si la
        compañía lo pide y aún no tiene una."""
        values = []
        for project in self.filtered(lambda p: p.is_construction_site and not p.is_template):
            company = project.company_id or self.env.company
            if not company.construction_site_auto_create or project.construction_hr_site_ids:
                continue
            values.append({
                'name': project.name, 'company_id': company.id, 'project_id': project.id,
                'site_kind': 'site',
                'analytic_account_id': project.account_id.id or False,
                'latitude': company.construction_site_latitude,
                'longitude': company.construction_site_longitude,
                'radius_m': company.construction_site_radius_m or 200,
                'entry_deadline': company.construction_site_entry_deadline,
                'date_start': project.date_start,
            })
        if values:
            # sudo: la sede es de RR. HH.; la crea el sistema al marcar la
            # obra, con los datos de la obra y los valores de la compañía.
            self.env['l10n_pe.hr.construction.site'].sudo().create(values)
