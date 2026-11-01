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
* Asignación familiar: 10 % de la RMV vigente a la fecha (tabla
  ``hr.rule.parameter``, Ley 25129) — nunca el literal 102.5 del v18.
* Devengue trunco del año vacacional en curso a 2.5 días/mes con los
  helpers ``get_months_days_difference``/``get_months_of_30_days``.
"""
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.addons.al_hr_pe.models.display_name import pe_join, pe_range
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
    _inherit = 'hr.benefits.line.mixin'
    _order = 'employee_id, date_aplication'
    _check_company_auto = True

    employee_id = fields.Many2one(
        'hr.employee', string='Trabajador', required=True, index=True,
        check_company=True)
    identification_id = fields.Char(
        related='employee_id.identification_id', string='N.º de documento')
    date_aplication = fields.Date(
        string='Fecha del movimiento',
        help='Fecha en que se devenga o se goza. En un saldo anterior, la '
             'fecha de corte: el saldo incluye todo lo devengado y gozado '
             'hasta ese día, y el cálculo sigue desde el día siguiente con '
             'los años contados desde el ingreso.', tracking=True)
    date_from = fields.Date(
        string='Inicio del año vacacional',
        help='El año vacacional se cuenta desde la fecha de ingreso.', tracking=True)
    date_end = fields.Date(string='Fin del año vacacional', tracking=True)
    internal_motive = fields.Selection(
        [('rest', 'Saldo anterior'), ('normal', 'Vacaciones')],
        string='Tipo de movimiento', default='normal',
        help='Saldo anterior: saldo inicial cargado a mano, que el cálculo '
             'respeta. Vacaciones: movimiento calculado (devengue a 2,5 '
             'días por mes o goce).', tracking=True)
    motive = fields.Char(string='Motivo')
    # v18 usaba Integer; Float para soportar el devengue trunco a
    # 2.5 días/mes (p. ej. 7.5 días a los 3 meses).
    days = fields.Float(
        string='Días', digits=(16, 2),
        help='Positivo: días devengados. Negativo: días gozados.', tracking=True)
    days_rest = fields.Float(string='Saldo en días', digits=(16, 2))
    year = fields.Char(string='Año vacacional')
    amount = fields.Float(string='Importe', tracking=True)
    amount_rest = fields.Float(string='Saldo en importe')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    is_saldo_final = fields.Boolean(
        string='Saldo final', default=False,
        help='Último movimiento del trabajador: su saldo es el vigente.')

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
        Record = self.env['hr.vacation.record']
        for employee in employees_to_process:
            version = employee.version_id
            # Jornada menor a 4 horas: sin vacaciones (D.Leg. 713, art. 12),
            # igual que la liquidación vacacional. El practicante sí tiene
            # su descanso subvencionado (Ley 28518, art. 47).
            if not version \
                    or version.l10n_pe_labor_regime not in (
                        'general', 'small', 'micro', 'practicante') \
                    or version.l10n_pe_less_than_four \
                    or not version.contract_date_start:
                continue

            previous_balance = self.search([
                ('employee_id', '=', employee.id),
                ('internal_motive', '=', 'rest'),
                ('company_id', '=', company.id),
            ], limit=1, order='date_aplication desc')
            # Inicio del vínculo (mismo criterio que la liquidación): la
            # versión actual puede ser de un contrato renovado que empieza
            # después del ingreso. Los años se anclan siempre al ingreso,
            # aunque el saldo inicial tenga otra fecha de corte.
            admission = param.get_first_version(
                employee).contract_date_start
            end_calculation_date = min(
                today, version.contract_date_end or today)
            # El practicante no tiene asignación familiar (percibe una
            # subvención, no una remuneración).
            compute_af = param.compute_af_vac \
                and version.l10n_pe_labor_regime != 'practicante'
            # Asignación familiar: 10 % de la RMV vigente a la fecha (tabla
            # por fecha, como la boleta), no el valor fijo de Parámetros
            # Principales. Derechohabientes por edad (Ley 25129), no el
            # campo manual ``children``.
            family_allowance = self._l10n_pe_family_allowance(
                param, end_calculation_date) \
                if compute_af and employee._l10n_pe_has_family_allowance(
                    end_calculation_date) else 0.0
            contract_amount = version.wage + family_allowance
            for movement in self._l10n_pe_accrual_movements(
                    employee, admission, end_calculation_date,
                    previous_balance.date_aplication):
                amount = custom_round(
                    contract_amount * movement['days'] / 30.0, 2)
                self.create({
                    'employee_id': employee.id,
                    'internal_motive': 'normal',
                    'year': str(movement['date_from'].year),
                    'company_id': company.id,
                    'date_aplication': movement['date_end'],
                    'date_from': movement['date_from'],
                    'date_end': movement['date_end'],
                    'motive': movement['motive'],
                    'days': movement['days'],
                    'days_rest': movement['days'],
                    'amount': amount,
                    'amount_rest': amount,
                })

            # Goces registrados por boleta (hr.accrual.vacation).
            accrued_vacations = self.env['hr.accrual.vacation'].search([
                ('employee_id', '=', employee.id),
                ('company_id', '=', company.id),
            ])
            for accrual in accrued_vacations:
                # El goce exportado desde la liquidación vacacional lleva
                # su propio importe (una boleta puede tener varios goces);
                # el registrado a mano, el VAC de la boleta. v18 hacía
                # ``.filtered(...).total`` (crasheaba con varias líneas
                # VAC); aquí se suma.
                if accrual.vacation_line_id:
                    vacation_amount = accrual.vacation_line_id.total_vacation
                else:
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

    @api.model
    def _l10n_pe_family_allowance(self, param, on_date):
        """Asignación familiar vigente a ``on_date``: 10 % de la RMV de la
        tabla por fecha (``hr.rule.parameter``), la misma que usa la
        boleta; el valor de Parámetros Principales solo como respaldo."""
        rmv = self.env['hr.rule.parameter']._l10n_pe_get_rmv(on_date)
        return custom_round(rmv * 0.10, 2) if rmv else param.family_allowance

    @api.model
    def _l10n_pe_days_per_year(self, employee, on_date):
        """Días de vacaciones por año del régimen vigente a ``on_date``:
        30 en el general y 15 en la pequeña y la microempresa (REMYPE,
        D.S. 013-2013-PRODUCE). Cada año con el régimen de ESE año: el
        que pasó de la microempresa al general no recalcula los años
        anteriores con 30 días."""
        version = employee._get_version(on_date) or employee.version_id
        regime = version.l10n_pe_labor_regime
        if regime == 'general':
            return 30.0
        # Practicante: 15 días de descanso subvencionado por cada 12 meses
        # de convenio (Ley 28518, art. 47).
        return 15.0 if regime in ('small', 'micro', 'practicante') else 0.0

    @api.model
    def _l10n_pe_accrual_movements(self, employee, admission, date_to,
                                   balance_date=False):
        """Devengue del trabajador desde el ingreso hasta ``date_to``.

        Lista de movimientos (dict con ``date_from``, ``date_end``,
        ``motive``, ``days`` y ``complete``): un año de servicios completo
        da los días del régimen de ese año SOLO si cumple el récord
        (D.Leg. 713, art. 10; sin boletas para evaluarlo, «sin datos», se
        generan y el motivo lo avisa); el año en curso (o cortado por el
        cese) devenga la parte proporcional.

        Los años se cuentan siempre desde el ingreso. Con un saldo inicial
        (``balance_date``, fecha de corte), lo devengado hasta esa fecha
        ya está en el saldo: los años que terminan antes no se generan y
        el que la contiene devenga solo la parte posterior al corte.
        """
        param = self.env['hr.main.parameter'].get_main_parameter(
            self.env.company)
        Record = self.env['hr.vacation.record']
        movements = []
        current_date = admission
        while current_date < date_to:
            period_end = current_date + relativedelta(years=1) \
                - timedelta(days=1)
            next_date = period_end + timedelta(days=1)
            if balance_date and period_end <= balance_date:
                current_date = next_date
                continue
            start = current_date
            if balance_date and balance_date >= current_date:
                start = balance_date + timedelta(days=1)
            days_per_year = self._l10n_pe_days_per_year(
                employee, min(period_end, date_to))
            monthly_rate = days_per_year / 12.0
            complete = period_end <= date_to
            year_version = employee._get_version(
                min(period_end, date_to)) or employee.version_id
            if year_version.l10n_pe_labor_regime == 'practicante':
                # Modalidad formativa (Ley 28518, art. 47): 15 días por
                # cada 12 meses de convenio cumplidos, sin récord de días
                # efectivos ni truncas (son del D.Leg. 713).
                if complete:
                    movements.append({
                        'date_from': start,
                        'date_end': period_end,
                        'year_from': current_date,
                        'year_to': period_end,
                        'motive': 'Descanso subvencionado %s (Ley 28518)'
                                  % current_date.year,
                        'days': days_per_year if start == current_date
                        else custom_round(days_per_year * (
                            (period_end - start).days + 1)
                            / ((period_end - current_date).days + 1), 2),
                        'complete': True,
                        'formative': True,
                    })
                current_date = next_date
                continue
            period_to = min(period_end, date_to)
            if start == current_date and complete:
                days = days_per_year
            else:
                # Parte proporcional a días/mes del régimen (helpers del
                # mes comercial de 30 días).
                days_diff, months_diff = param.get_months_days_difference(
                    start, period_to)
                days = custom_round(
                    months_diff * monthly_rate
                    + days_diff * (monthly_rate / 30.0), 2)
            if complete:
                record = Record._l10n_pe_get_record(
                    employee, current_date, period_end)
                motive = 'Vacaciones devengadas %s' % current_date.year
                if record.state in ('fails', 'not_applicable'):
                    days = 0.0
                    motive = 'Vacaciones no generadas %s: no cumple ' \
                             'el récord vacacional (%s)' % (
                                 current_date.year,
                                 record.evaluation_note or '')
                elif record.state == 'no_data':
                    motive += ' (récord sin datos: verificar)'
            else:
                if not days:
                    break
                motive = 'Vacaciones truncas %s' % current_date.year
            movements.append({
                'date_from': start,
                'date_end': period_to,
                'year_from': current_date,
                'year_to': period_end,
                'motive': motive,
                'days': days,
                'complete': complete,
            })
            current_date = next_date
        return movements

    @api.model
    def _l10n_pe_pending_vacation(self, employee, on_date):
        """Días ganados y no gozados de los años de servicio completos a
        ``on_date`` (récord y saldos de vacaciones), para la liquidación
        de cese y el aviso del goce sin saldo.

        Devuelve ``(años, adelanto)``: ``años`` es una lista de dict
        (``date_from``, ``date_to``, ``days``, ``pending``, ``deadline``)
        y ``adelanto`` los días gozados (o vendidos) por encima de lo
        ganado. Los goces y ventas (``hr.accrual.vacation``) consumen
        primero el año más antiguo. ``deadline`` es el último día del año
        siguiente al de servicios: el plazo para gozarlo (D.Leg. 713,
        art. 23). Un saldo inicial positivo se trata como un año que
        termina en su fecha de corte.
        """
        company = self.env.company
        param = self.env['hr.main.parameter'].get_main_parameter(company)
        admission = param.get_first_version(
            employee, on_date).contract_date_start
        balance = self.search([
            ('employee_id', '=', employee.id),
            ('internal_motive', '=', 'rest'),
            ('company_id', '=', company.id),
            ('date_aplication', '<=', on_date),
        ], limit=1, order='date_aplication desc')
        balance_date = balance.date_aplication
        years = []
        consumed = 0.0
        if balance and balance_date >= admission:
            if balance.days_rest > 0:
                years.append({
                    'date_from': balance.date_from or admission,
                    'date_to': balance_date,
                    'days': balance.days_rest,
                })
            else:
                consumed -= balance.days_rest
        else:
            balance_date = False
        for movement in self._l10n_pe_accrual_movements(
                employee, admission, on_date, balance_date):
            if movement['complete'] and movement['days']:
                years.append({
                    'date_from': movement['year_from'],
                    'date_to': movement['year_to'],
                    'days': movement['days'],
                    # Practicante: sin indemnización vacacional (es del
                    # D.Leg. 713).
                    'formative': movement.get('formative', False),
                })
        accruals = self.env['hr.accrual.vacation'].search([
            ('employee_id', '=', employee.id),
            ('company_id', '=', company.id),
        ])
        for accrual in accruals:
            accrual_date = accrual.date_aplication \
                or accrual.slip_id.date_from
            if accrual_date and accrual_date <= on_date \
                    and not (balance_date and accrual_date <= balance_date):
                consumed += accrual.days
        for year in years:
            taken = min(year['days'], consumed)
            consumed -= taken
            year['pending'] = year['days'] - taken
            year['deadline'] = year['date_to'] + relativedelta(years=1)
        return years, consumed

    def action_show_details(self):
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

    @api.depends('employee_id', 'date_from', 'date_end')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = pe_join(rec.employee_id.name, pe_range(rec.env, rec.date_from, rec.date_end))


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
        'hr.payslip', string='Boleta', ondelete='cascade', required=True,
        check_company=True)
    company_id = fields.Many2one(
        related='slip_id.company_id', store=True, string='Compañía',
        index=True)
    periodo_id = fields.Many2one(
        'hr.period', string='Periodo', required=True, check_company=True)
    days = fields.Integer(string='Días de vacaciones')
    employee_id = fields.Many2one(
        related='slip_id.employee_id', store=True, string='Trabajador',
        index=True)
    date_aplication = fields.Date(string='Fecha de aplicación')
    request_date_from = fields.Date(string='Fecha inicio')
    request_date_to = fields.Date(string='Fecha fin')
    motive = fields.Char(string='Motivo')
    kind = fields.Selection(
        [('rest', 'Goce'), ('sale', 'Venta')], string='Tipo',
        default='rest',
        help='Goce: días de descanso. Venta: días compensados en dinero '
             '(D.Leg. 713, art. 19). Los dos se restan del saldo.')
    vacation_line_id = fields.Many2one(
        'hr.vacation.line', string='Línea de liquidación vacacional',
        ondelete='cascade', index='btree_not_null', readonly=True,
        help='Goce o venta exportado desde la liquidación vacacional que '
             'creó este movimiento; al volver la liquidación a borrador se '
             'borra.')

    @api.depends('employee_id', 'periodo_id', 'days')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = pe_join(rec.employee_id.name, rec.periodo_id.display_name, '%s días' % rec.days if rec.days else '')


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
    _check_company_auto = True

    employee_ids = fields.Many2many(
        'hr.employee', 'hr_vacation_rest_wizard_employee_rel',
        'wizard_id', 'employee_id', string='Empleados', check_company=True)
    show_all = fields.Boolean(
        string='Todos los empleados', default=True,
        help='Si está activo se recalculan e incluyen todos los '
             'empleados de la compañía.')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, readonly=True,
        default=lambda self: self.env.company)

    def action_compute_balances(self):
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
