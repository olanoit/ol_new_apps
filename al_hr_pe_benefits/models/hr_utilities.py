# -*- coding: utf-8 -*-
"""Participación de los trabajadores en las utilidades (D.L. 892).

Portado de ``hr_utilities`` (v18). La renta anual antes de impuestos
multiplicada por el % legal del giro se reparte:

* **50 % por días laborados**: días trabajados − faltas del ejercicio
  (worked days ``wd_dtrab`` − ``wd_falt``).
* **50 % por remuneraciones**: total anual de la regla salarial
  configurada (``rule_total_income``).

El descuadre por redondeo de ambos repartos se ajusta contra la última
línea (paridad v18). El total por trabajador se exporta como input
(``hr_input_for_results``) al lote de nóminas del pago.

Cambios v19: ``account.fiscal.year`` (eliminado) → campo entero
``year``; ``hr.contract`` → ``hr.version``; sin SQL ``.format()``
(agregación por ORM); la distribución analítica del contrato v18 no
tiene equivalente en ``hr.version``. La liquidación PDF, el Excel y el
envío por correo quedan para la Fase 7. Los campos de configuración
(``rule_total_income``, ``wd_dtrab``, ``wd_falt``,
``hr_input_for_results``) los añade ``hr_benefits_engine`` a
`hr.main.parameter`; aquí se leen con ``getattr`` con guard.
"""
from datetime import date

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_hr_pe.tools import custom_round
from .hr_benefits_engine import notify_success


class HrUtilities(models.Model):
    _name = 'hr.utilities'
    _description = 'Utilidades (D.L. 892)'
    _order = 'year desc'
    _check_company_auto = True

    name = fields.Char(compute='_compute_name', store=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    # v18: fiscal_year_id (account.fiscal.year, eliminado en v19).
    year = fields.Integer(
        string='Ejercicio', required=True,
        default=lambda self: fields.Date.context_today(self).year - 1,
        help='Ejercicio gravable cuya renta se reparte.')
    annual_rent = fields.Float(
        string='Renta anual antes de impuestos', digits=(64, 2))
    percentage = fields.Float(string='Porcentaje', digits=(12, 2))
    distribution = fields.Float(string='Distribución', digits=(64, 2))
    utilities_line_ids = fields.One2many(
        'hr.utilities.line', 'main_id', string='Líneas')
    sum_salary_year = fields.Float(
        string='Total sueldos de todo el año', digits=(12, 2))
    sum_number_of_days_year = fields.Float(
        string='Total días laborados de todo el año', digits=(12, 2))
    factor_salary = fields.Float(string='Factor sueldos', digits=(12, 18))
    factor_number_of_days = fields.Float(
        string='Factor días trabajados', digits=(12, 18))
    state = fields.Selection(
        selection=[('draft', 'Borrador'), ('exported', 'Exportado')],
        string='Estado', default='draft')
    payslip_run_id = fields.Many2one(
        'hr.payslip.run', string='Lote de nómina', required=True,
        check_company=True,
        help='Lote mensual donde se pagan las utilidades.')
    utili_count = fields.Integer(compute='_compute_utilities_count')

    _unique_year = models.Constraint(
        'UNIQUE(company_id, year)',
        'Ya existe un reparto de utilidades de ese ejercicio para la '
        'compañía.')

    @api.depends('year')
    def _compute_name(self):
        for record in self:
            record.name = 'Utilidades %s' % (record.year or '')

    @api.depends('utilities_line_ids')
    def _compute_utilities_count(self):
        for record in self:
            record.utili_count = len(record.utilities_line_ids)

    @api.onchange('annual_rent', 'percentage')
    def _change_percentage_rent(self):
        for record in self:
            record.distribution = \
                record.annual_rent * (record.percentage / 100)

    def action_open_utili(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.utilities.line',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('id', 'in', self.utilities_line_ids.ids)],
            'name': self.env._('Liquidaciones de utilidades'),
        }

    def turn_draft(self):
        self.write({'state': 'draft'})

    def compute_utilities_line_all(self):
        """Recalcula el reparto completo tras ajustes manuales."""
        self._distribute()
        return notify_success(self.env._('Se recalculó exitosamente.'))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _check_configuration(self, param):
        """Port de ``check_utility_values`` v18 (los campos los añade
        ``hr_benefits_engine``; mientras no existan cuentan como
        faltantes)."""
        missing = [label for field_name, label in [
            ('rule_total_income', 'R.S. rem. afecta a utilidades'),
            ('wd_dtrab', 'W.D. días trabajados'),
            ('wd_falt', 'W.D. faltas'),
            ('hr_input_for_results', 'Input utilidades'),
        ] if not getattr(param, field_name, False)]
        if missing:
            raise UserError(self.env._(
                'Faltan configuraciones de utilidades en los Parámetros '
                'Principales de Nómina: %(fields)s.',
                fields=', '.join(missing)))

    def _distribute(self):
        """Reparte 50 % por remuneraciones y 50 % por días laborados y
        ajusta el descuadre de redondeo en la última línea (v18)."""
        for record in self:
            lines = record.utilities_line_ids
            record._change_percentage_rent()
            record.sum_salary_year = sum(lines.mapped('salary'))
            record.sum_number_of_days_year = \
                sum(lines.mapped('number_of_days'))
            record.factor_salary = 0.0
            record.factor_number_of_days = 0.0
            if not lines:
                continue
            if not record.sum_salary_year \
                    or not record.sum_number_of_days_year:
                raise UserError(self.env._(
                    'No hay sueldos o días laborados en el ejercicio '
                    'para repartir las utilidades.'))
            half = record.distribution * 0.50
            record.factor_salary = half / record.sum_salary_year
            record.factor_number_of_days = \
                half / record.sum_number_of_days_year
            total_salary = total_days = 0.0
            for line in lines:
                line.for_salary = custom_round(
                    line.salary * record.factor_salary, 2)
                total_salary += line.for_salary
                line.for_number_of_days = custom_round(
                    line.number_of_days * record.factor_number_of_days, 2)
                total_days += line.for_number_of_days
            # Ajuste de redondeo contra la última línea (paridad v18).
            last = lines[-1]
            last.for_salary = custom_round(
                last.for_salary + (half - total_salary), 2)
            last.for_number_of_days = custom_round(
                last.for_number_of_days + (half - total_days), 2)
            for line in lines:
                if line.for_salary and line.for_number_of_days:
                    line.total_utilities = custom_round(
                        line.for_salary + line.for_number_of_days, 2)

    # ------------------------------------------------------------------
    # Cálculo y exportación
    # ------------------------------------------------------------------
    def calculate(self):
        """Genera las líneas del ejercicio (una por trabajador con la
        regla de remuneración afecta) y ejecuta el reparto."""
        self.ensure_one()
        Line = self.env['hr.utilities.line']
        self.utilities_line_ids.filtered(
            lambda line: not line.preserve_record).unlink()
        param = self.env['hr.main.parameter'].get_main_parameter(
            self.company_id)
        self._check_configuration(param)
        rule = getattr(param, 'rule_total_income')
        wd_dtrab = getattr(param, 'wd_dtrab')
        wd_falt = getattr(param, 'wd_falt')
        slips = self.env['hr.payslip'].search([
            ('date_to', '>=', date(self.year, 1, 1)),
            ('date_to', '<=', date(self.year, 12, 31)),
            ('company_id', '=', self.company_id.id),
        ])
        data = {}
        for slip in slips:
            rule_lines = slip.line_ids.filtered(
                lambda line: line.salary_rule_id == rule)
            worked_days = slip.worked_days_line_ids
            bucket = data.setdefault(slip.employee_id, {
                'salary': 0.0, 'days': 0.0, 'has_rule': False})
            if rule_lines:
                bucket['has_rule'] = True
                bucket['salary'] += sum(rule_lines.mapped('total'))
            bucket['days'] += sum(worked_days.filtered(
                lambda line: line.work_entry_type_id in wd_dtrab
            ).mapped('number_of_days'))
            bucket['days'] -= sum(worked_days.filtered(
                lambda line: line.work_entry_type_id in wd_falt
            ).mapped('number_of_days'))
        for employee in sorted(data, key=lambda emp: emp.id):
            bucket = data[employee]
            if not bucket['has_rule']:
                continue
            # TODO(fase3-revisar): distribution_id (distribución
            # analítica del contrato v18) sin equivalente en hr.version.
            first_version = param.get_first_version(employee)
            Line.create({
                'main_id': self.id,
                'employee_document': employee.identification_id or '',
                'employee': employee.display_name,
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                'admission_date': first_version.contract_date_start,
                'salary': bucket['salary'],
                'number_of_days': bucket['days'],
            })
        self._distribute()
        preserved_employees = self.utilities_line_ids.filtered(
            'preserve_record').employee_id
        self.utilities_line_ids.filtered(
            lambda line: not line.preserve_record
            and line.employee_id in preserved_employees).unlink()
        return notify_success(self.env._('Se calculó exitosamente.'))

    def export_utilities(self):
        """Vuelca el total de cada línea al input de utilidades de la
        boleta del trabajador en el lote de pago."""
        self.ensure_one()
        param = self.env['hr.main.parameter'].get_main_parameter(
            self.company_id)
        self._check_configuration(param)
        input_utilities = getattr(param, 'hr_input_for_results')
        for line in self.utilities_line_ids:
            slip = self.payslip_run_id.slip_ids.filtered(
                lambda slip: slip.employee_id == line.employee_id)[:1]
            if not slip:
                continue
            slip._set_pe_input_amount(input_utilities, line.total_utilities)
        self.state = 'exported'
        return notify_success(self.env._(
            'Se envió al lote de nóminas exitosamente.'))


class HrUtilitiesLine(models.Model):
    _name = 'hr.utilities.line'
    _description = 'Línea de utilidad'
    _order = 'employee_id'
    _check_company_auto = True

    main_id = fields.Many2one(
        'hr.utilities', string='Utilidades', ondelete='cascade',
        required=True, index=True)
    company_id = fields.Many2one(
        related='main_id.company_id', string='Compañía', store=True,
        index=True)
    employee_document = fields.Char(string='N° documento')
    employee = fields.Char(string='Empleado')
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado (registro)', check_company=True)
    version_id = fields.Many2one(
        'hr.version', string='Contrato (versión)', check_company=True)
    last_name = fields.Char(
        related='employee_id.last_name', string='Apellido paterno')
    m_last_name = fields.Char(
        related='employee_id.m_last_name', string='Apellido materno')
    names = fields.Char(related='employee_id.names', string='Nombres')
    admission_date = fields.Date(string='Fecha de ingreso')
    distribution_id = fields.Char(string='Distribución analítica')
    salary = fields.Float(string='Sueldos', digits=(12, 2))
    number_of_days = fields.Float(string='Días laborados', digits=(12, 2))
    for_salary = fields.Float(string='Por sueldos', digits=(12, 2))
    for_number_of_days = fields.Float(
        string='Por días laborados', digits=(12, 2))
    total_utilities = fields.Float(
        string='Total utilidades', digits=(12, 2))
    preserve_record = fields.Boolean(string='No recalcular')

    @api.depends('employee')
    def _compute_display_name(self):
        """Snapshot del nombre al momento del cálculo: usar
        ``employee_id.name`` recalcularía el nombre si el empleado se
        renombra después del cierre, indeseable en reportes legales."""
        for line in self:
            line.display_name = line.employee or ''

    def compute_utilitie_line(self):
        """Recalcula el reparto completo del registro padre; elimina la
        línea si queda sin participación (paridad v18)."""
        for record in self:
            record.main_id._distribute()
            if not record.total_utilities > 0 \
                    and not self.env.context.get('line_form'):
                record.unlink()
