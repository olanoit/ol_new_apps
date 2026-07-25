# -*- coding: utf-8 -*-
"""Récord vacacional (D.L. 713): saldos y devengue mensual.

Port de ``hr_vacations`` v18 (hr.vacation.rest + hr.accrual.vacation +
wizard de recálculo). Cambios v19:

* contrato → versión (``hr.version``): el vínculo vigente es
  ``employee.version_id`` y el devengue arranca de su
  ``contract_date_start``.
* FIX multicompañía: el recálculo v18 hacía
  ``search([('internal_motive', '=', 'normal')]).unlink()`` SIN filtro de
  compañía ni empleado — borraba los saldos de TODAS las compañías y de
  todos los empleados. Aquí sólo se borran los registros ``normal`` de
  los empleados que se recalculan y de la compañía activa.
* Asignación familiar desde ``hr.main.parameter.family_allowance``
  (10 % RMV, Ley 25129) — nunca el literal 102.5 del v18.
* Devengue trunco del año vacacional en curso a 2.5 días/mes con los
  helpers ``get_months_days_difference``/``get_months_of_30_days``.
"""
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_hr_pe.tools import custom_round


class HrVacationRest(models.Model):
    """Saldo de vacaciones por empleado y periodo de devengue.

    Cada registro representa la posición del trabajador respecto a su
    derecho vacacional anual:

    * ``date_from..date_end``: año vacacional (D.L. 713 Art. 11 — el año
      comienza desde la fecha de ingreso o la última liquidación).
    * ``days``: días devengados (o gozados, en negativo) del movimiento.
    * ``days_rest``/``amount_rest``: saldo acumulado a la fecha.
    * ``internal_motive``: ``rest`` = saldo inicial arrastrado (manual,
      el recálculo lo respeta); ``normal`` = movimiento calculado.
    """
    _name = 'hr.vacation.rest'
    _description = 'Saldos de vacaciones'
    _order = 'employee_id, date_aplication'
    _check_company_auto = True

    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', required=True, index=True,
        check_company=True)
    identification_id = fields.Char(
        related='employee_id.identification_id', string='Nro. de documento')
    date_aplication = fields.Date(string='Fecha de aplicación')
    date_from = fields.Date(string='Periodo inicio')
    date_end = fields.Date(string='Periodo fin')
    internal_motive = fields.Selection(
        [('rest', 'Saldo anterior'), ('normal', 'Vacaciones')],
        string='Motivo interno', default='normal')
    motive = fields.Char(string='Motivo')
    # v18 usaba Integer; Float para soportar el devengue trunco a
    # 2.5 días/mes (p. ej. 7.5 días a los 3 meses).
    days = fields.Float(string='Días', digits=(16, 2))
    days_rest = fields.Float(string='Saldo en días', digits=(16, 2))
    year = fields.Char(string='Año')
    amount = fields.Float(string='Importe')
    amount_rest = fields.Float(string='Saldo importe')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    is_saldo_final = fields.Boolean(string='Saldo final', default=False)

    def get_vacation_employee(self, employees, show_all):
        """Recalcula los saldos de vacaciones (movimientos ``normal``).

        FIX v18: el borrado previo al recálculo se acota a los empleados
        procesados y a la compañía activa (v18 borraba TODOS los
        registros ``normal`` de la base de datos).
        """
        company = self.env.company
        param = self.env['hr.main.parameter'].get_main_parameter(company)
        if show_all:
            employees_to_process = self.env['hr.employee'].search(
                [('company_id', '=', company.id)])
        else:
            employees_to_process = employees.filtered(
                lambda e: e.company_id == company)
        if not employees_to_process:
            return

        # Sólo los movimientos calculados de estos empleados/compañía;
        # los saldos iniciales ('rest') nunca se tocan.
        self.search([
            ('internal_motive', '=', 'normal'),
            ('company_id', '=', company.id),
            ('employee_id', 'in', employees_to_process.ids),
        ]).unlink()

        today = fields.Date.context_today(self)
        for employee in employees_to_process:
            version = employee.version_id
            if not version \
                    or version.l10n_pe_labor_regime not in (
                        'general', 'small', 'micro') \
                    or not version.contract_date_start:
                continue

            previous_balance = self.search([
                ('employee_id', '=', employee.id),
                ('internal_motive', '=', 'rest'),
                ('company_id', '=', company.id),
            ], limit=1, order='date_aplication desc')
            if previous_balance and previous_balance.date_aplication:
                start_date = previous_balance.date_aplication \
                    - relativedelta(years=1)
            else:
                start_date = version.contract_date_start

            # Asignación familiar de Parámetros Principales (10 % RMV),
            # nunca hardcodeada.
            compute_af = getattr(param, 'compute_af_vac', True)
            family_allowance = param.family_allowance \
                if compute_af and version.children > 0 else 0.0
            contract_amount = version.wage + family_allowance

            end_calculation_date = min(
                today, version.contract_date_end or today)
            current_date = start_date
            while current_date < end_calculation_date:
                period_end = current_date + relativedelta(years=1) \
                    - timedelta(days=1)
                if period_end < today:
                    # Año vacacional completo: 12 meses × 2.5 = 30 días.
                    vals = {
                        'date_aplication': period_end,
                        'date_from': current_date,
                        'date_end': period_end,
                        'motive': 'Vacaciones devengadas %s'
                                  % current_date.year,
                        'days': 30.0,
                        'days_rest': 30.0,
                        'amount': contract_amount,
                        'amount_rest': contract_amount,
                    }
                else:
                    # Año vacacional en curso: devengue trunco a
                    # 2.5 días/mes (helpers del mes comercial de 30 días).
                    period_to = min(end_calculation_date, period_end)
                    days_diff, months_diff = \
                        param.get_months_days_difference(
                            current_date, period_to)
                    accrued_days = custom_round(
                        months_diff * 2.5 + days_diff * (2.5 / 30.0), 2)
                    if not accrued_days:
                        break
                    accrued_amount = custom_round(
                        contract_amount * accrued_days / 30.0, 2)
                    vals = {
                        'date_aplication': period_to,
                        'date_from': current_date,
                        'date_end': period_to,
                        'motive': 'Vacaciones truncas %s'
                                  % current_date.year,
                        'days': accrued_days,
                        'days_rest': accrued_days,
                        'amount': accrued_amount,
                        'amount_rest': accrued_amount,
                    }
                vals.update({
                    'employee_id': employee.id,
                    'internal_motive': 'normal',
                    'year': str(current_date.year),
                    'company_id': company.id,
                })
                self.create(vals)
                current_date = period_end + timedelta(days=1)

            # Goces registrados por boleta (hr.accrual.vacation).
            accrued_vacations = self.env['hr.accrual.vacation'].search([
                ('employee_id', '=', employee.id),
                ('company_id', '=', company.id),
            ])
            for accrual in accrued_vacations:
                # v18 hacía ``.filtered(...).total`` (crasheaba con varias
                # líneas VAC); aquí se suma.
                vacation_amount = sum(accrual.slip_id.line_ids.filtered(
                    lambda line: line.salary_rule_id.code == 'VAC'
                    and line.total > 0).mapped('total'))
                date_aplication = accrual.date_aplication \
                    or accrual.slip_id.date_from
                self.create({
                    'employee_id': employee.id,
                    'date_aplication': date_aplication,
                    'date_from': accrual.request_date_from
                    or accrual.slip_id.date_from,
                    'date_end': accrual.request_date_to
                    or accrual.slip_id.date_to,
                    'internal_motive': 'normal',
                    'motive': accrual.motive,
                    'days': accrual.days * -1,
                    'days_rest': accrual.days * -1,
                    'year': str(date_aplication.year)
                    if date_aplication else '',
                    'amount': vacation_amount * -1,
                    'amount_rest': vacation_amount * -1,
                    'company_id': company.id,
                })

            # Saldos acumulados cronológicos.
            vacation_records = self.search([
                ('employee_id', '=', employee.id),
                ('company_id', '=', company.id),
            ])
            day_balance = amount_balance = 0.0
            sorted_records = vacation_records.sorted(
                key=lambda r: r.date_aplication or fields.Date.to_date(
                    '1900-01-01'))
            for record in sorted_records:
                if record.internal_motive == 'rest':
                    day_balance = record.days_rest
                    amount_balance = record.amount_rest
                else:
                    day_balance += record.days
                    amount_balance += record.amount
                record.write({
                    'days_rest': day_balance,
                    'amount_rest': amount_balance,
                    'is_saldo_final': False,
                })
            if sorted_records:
                sorted_records[-1].is_saldo_final = True

    def view_detail(self):
        """Movimientos del récord vacacional del empleado."""
        self.ensure_one()
        return {
            'name': self.env._('Saldos de vacaciones'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.vacation.rest',
            'view_mode': 'list',
            'views': [(self.env.ref(
                'al_hr_pe_benefits.hr_vacation_rest_view_list').id, 'list')],
            'domain': [('employee_id', '=', self.employee_id.id)],
            'target': 'current',
        }


class HrAccrualVacation(models.Model):
    """Devengue/goce mensual de vacaciones por boleta.

    Tabla intermedia entre ``hr.payslip`` y el récord vacacional: cada
    registro son los días de vacaciones gozados (o devengados) en el
    periodo de la boleta; el recálculo de ``hr.vacation.rest`` los
    convierte en movimientos negativos del saldo.
    """
    _name = 'hr.accrual.vacation'
    _description = 'Vacaciones acumuladas'
    _check_company_auto = True

    slip_id = fields.Many2one(
        'hr.payslip', string='Boleta', ondelete='cascade', required=True)
    company_id = fields.Many2one(
        related='slip_id.company_id', store=True, string='Compañía',
        index=True)
    periodo_id = fields.Many2one(
        'hr.period', string='Periodo', required=True, check_company=True)
    days = fields.Integer(string='Días de vacaciones')
    employee_id = fields.Many2one(
        related='slip_id.employee_id', store=True, string='Empleado',
        index=True)
    date_aplication = fields.Date(string='Fecha de aplicación')
    request_date_from = fields.Date(string='Fecha inicio')
    request_date_to = fields.Date(string='Fecha fin')
    motive = fields.Char(string='Motivo')


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    accrual_vacation_ids = fields.One2many(
        'hr.accrual.vacation', 'slip_id', string='Devengue de vacaciones')


class HrVacationRestWizard(models.TransientModel):
    """Recalcula el récord vacacional y muestra los saldos vigentes.

    v18 ofrecía además exportar a Excel escribiendo en
    ``dir_create_file`` (eliminado en v19).
    # TODO(fase3-revisar): reponer el Excel del reporte de control de
    # vacaciones vía ir.attachment (patrón _l10n_pe_download_attachment).
    """
    _name = 'hr.vacation.rest.wizard'
    _description = 'Asistente de récord vacacional'

    employee_ids = fields.Many2many(
        'hr.employee', 'hr_vacation_rest_wizard_employee_rel',
        'wizard_id', 'employee_id', string='Empleados',
        domain="[('company_id', '=', company_id)]")
    show_all = fields.Boolean(
        string='Todos los empleados', default=True,
        help='Si está activo se recalculan e incluyen todos los '
             'empleados de la compañía.')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, readonly=True,
        default=lambda self: self.env.company)

    def generate_vacation_report(self):
        self.ensure_one()
        if not self.show_all and not self.employee_ids:
            raise UserError(self.env._(
                'Seleccione al menos un empleado o marque «Todos los '
                'empleados».'))
        self.env['hr.vacation.rest'].get_vacation_employee(
            self.employee_ids, self.show_all)
        domain = [
            ('company_id', '=', self.company_id.id),
            ('is_saldo_final', '=', True),
        ]
        if not self.show_all:
            domain.append(('employee_id', 'in', self.employee_ids.ids))
        return {
            'name': self.env._('Saldos de vacaciones'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.vacation.rest',
            'view_mode': 'list',
            'views': [(self.env.ref(
                'al_hr_pe_benefits.hr_vacation_rest_view_list_resumen').id,
                'list')],
            'search_view_id': self.env.ref(
                'al_hr_pe_benefits.hr_vacation_rest_view_search').id,
            'domain': domain,
            'context': {'create': False},
        }
