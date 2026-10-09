# -*- coding: utf-8 -*-
"""Participación de los trabajadores en las utilidades (D.L. 892).

Portado de ``hr_utilities`` (v18). La renta anual antes de impuestos
multiplicada por el % legal del giro se reparte:

* **50 % por días laborados**: días trabajados − faltas del ejercicio
  (worked days ``wd_dtrab`` − ``wd_falt``).
* **50 % por remuneraciones**: total anual de la regla salarial
  configurada (``rule_total_income``).

El descuadre por redondeo de ambos repartos se ajusta contra la última
línea (paridad v18). La participación de cada trabajador se limita a 18
remuneraciones mensuales vigentes al cierre del ejercicio (D.L. 892,
art. 2); el exceso no se reparte (va al FONDOEMPLEO) y queda registrado
en la línea. El total por trabajador se exporta como input
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
from .hr_benefits_engine import compute_locked


class HrUtilities(models.Model):
    _name = 'hr.utilities'
    _description = 'Utilidades (D.L. 892)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'year desc'
    _check_company_auto = True

    name = fields.Char(string='Nombre', compute='_compute_name', store=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    # v18: fiscal_year_id (account.fiscal.year, eliminado en v19).
    year = fields.Integer(
        string='Ejercicio', required=True,
        default=lambda self: fields.Date.context_today(self).year - 1,
        help='Ejercicio gravable cuya renta se reparte.', aggregator=False, tracking=True)
    annual_rent = fields.Float(
        string='Renta anual antes de impuestos', digits=(64, 2),
        help='Renta neta imponible del ejercicio, antes del impuesto a la '
             'renta.', tracking=True)
    percentage = fields.Float(
        string='Porcentaje de participación', digits=(12, 2),
        help='Según la actividad de la empresa: 10 % pesqueras, de '
             'telecomunicaciones e industriales; 8 % mineras, de comercio y '
             'restaurantes; 5 % las demás (D.Leg. 892).', tracking=True)
    distribution = fields.Float(
        string='Monto a repartir', digits=(64, 2),
        help='Renta anual × porcentaje de participación. La mitad se reparte '
             'por días laborados y la otra mitad por remuneraciones.')
    utilities_line_ids = fields.One2many(
        'hr.utilities.line', 'main_id', string='Trabajadores')
    sum_salary_year = fields.Float(
        string='Remuneraciones del ejercicio', digits=(12, 2),
        help='Suma de las remuneraciones de todos los trabajadores.')
    sum_number_of_days_year = fields.Float(
        string='Días laborados del ejercicio', digits=(12, 2),
        help='Suma de los días laborados de todos los trabajadores.')
    factor_salary = fields.Float(
        string='Factor por remuneraciones', digits=(12, 18),
        help='(Monto a repartir ÷ 2) ÷ remuneraciones del ejercicio.')
    factor_number_of_days = fields.Float(
        string='Factor por días laborados', digits=(12, 18),
        help='(Monto a repartir ÷ 2) ÷ días laborados del ejercicio.')
    state = fields.Selection(
        selection=[('draft', 'Borrador'), ('exported', 'Exportado')],
        string='Estado', default='draft', tracking=True)
    payslip_run_id = fields.Many2one(
        'hr.payslip.run', string='Lote de nómina', required=True,
        check_company=True,
        help='Lote mensual donde se pagan las utilidades.', tracking=True)
    utili_count = fields.Integer(string='Repartos', compute='_compute_utilities_count')

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

    # Botones, en el mismo orden que en la vista
    # ------------------------------------------------------------------
    # Cálculo y exportación
    # ------------------------------------------------------------------
    def action_process(self):
        """Genera las líneas del ejercicio (una por trabajador con la
        regla de remuneración afecta) y ejecuta el reparto."""
        self.ensure_one()
        Line = self.env['hr.utilities.line']
        preserved = self.utilities_line_ids.filtered('preserve_record')
        (self.utilities_line_ids - preserved).unlink()
        param = self.env['hr.main.parameter'].get_main_parameter(
            self.company_id)
        self._check_configuration(param)
        rule = getattr(param, 'rule_total_income')
        wd_dtrab = getattr(param, 'wd_dtrab')
        wd_falt = getattr(param, 'wd_falt')
        # Solo boletas cerradas y sin las quincenales (su neto ya viaja
        # en la mensual; contarlas duplicaría sueldo y días).
        slips = self.env['hr.payslip'].search([
            ('date_to', '>=', date(self.year, 1, 1)),
            ('date_to', '<=', date(self.year, 12, 31)),
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ('validated', 'paid')),
            ('fortnightly_id', '=', False),
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
        closing_date = date(self.year, 12, 31)
        for employee in sorted(data, key=lambda emp: emp.id):
            bucket = data[employee]
            # Las líneas marcadas «No recalcular» se conservan: no se
            # crea otra para ese trabajador (antes se creaba y se borraba
            # DESPUÉS del reparto, que ya lo había contado dos veces).
            if not bucket['has_rule'] \
                    or employee in preserved.employee_id:
                continue
            # TODO(fase3-revisar): distribution_id (distribución
            # analítica del contrato v18) sin equivalente en hr.version.
            first_version = param.get_first_version(employee)
            closing_version = employee._get_version(closing_date)
            Line.create({
                'main_id': self.id,
                'employee_document': employee.identification_id or '',
                'employee': employee.display_name,
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                'admission_date': first_version.contract_date_start,
                'salary': bucket['salary'],
                'number_of_days': bucket['days'],
                'monthly_remuneration': self._closing_remuneration(
                    employee, closing_version, param, closing_date),
            })
        self._distribute()
        return notify_success(self.env._('Se calculó exitosamente.'))

    def action_recompute(self):
        """Recalcula el reparto completo tras ajustes manuales."""
        self._distribute()
        return notify_success(self.env._('Se recalculó exitosamente.'))

    def action_export_to_payslips(self):
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

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_open_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.utilities.line',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('id', 'in', self.utilities_line_ids.ids)],
            'name': self.env._('Liquidaciones de utilidades'),
        }

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

    @api.model
    def _closing_remuneration(self, employee, version, param, on_date):
        """Remuneración mensual vigente al cierre del ejercicio (base
        del tope de 18 remuneraciones): sueldo de la versión vigente más
        la asignación familiar si corresponde en esa fecha."""
        amount = version.wage or 0.0
        if employee._l10n_pe_has_family_allowance(on_date):
            amount += param.family_allowance
        return amount

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
                total = custom_round(
                    line.for_salary + line.for_number_of_days, 2)
                # Tope D.L. 892 art. 2: 18 remuneraciones mensuales
                # vigentes al cierre; el exceso va al FONDOEMPLEO.
                cap = custom_round(18 * line.monthly_remuneration, 2) \
                    if line.monthly_remuneration > 0 else 0.0
                if cap and total > cap:
                    line.excess_utilities = custom_round(total - cap, 2)
                    total = cap
                else:
                    line.excess_utilities = 0.0
                line.total_utilities = total


class HrUtilitiesLine(models.Model):
    _name = 'hr.utilities.line'
    _description = 'Línea de utilidad'
    _inherit = 'hr.benefits.line.mixin'
    _order = 'employee_id'
    _check_company_auto = True

    # La cabecera (lote o liquidación) ya no está en un estado editable: la
    # vista deja la línea de solo lectura.
    l10n_pe_locked = fields.Boolean(
        string='Bloqueada', compute='_compute_l10n_pe_locked')

    @api.depends('main_id.state')
    def _compute_l10n_pe_locked(self):
        compute_locked(self, {'main_id': ('draft',)})

    main_id = fields.Many2one(
        'hr.utilities', string='Utilidades', ondelete='cascade',
        required=True, index=True,
        check_company=True)
    company_id = fields.Many2one(
        related='main_id.company_id', string='Compañía', store=True,
        index=True)
    employee_document = fields.Char(string='N.º de documento')
    employee = fields.Char(string='Trabajador')
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
    salary = fields.Float(
        string='Remuneraciones del año', digits=(12, 2))
    number_of_days = fields.Float(
        string='Días laborados del año', digits=(12, 2))
    for_salary = fields.Float(
        string='Por remuneraciones', digits=(12, 2),
        help='Remuneraciones del año × factor por remuneraciones.')
    for_number_of_days = fields.Float(
        string='Por días laborados', digits=(12, 2),
        help='Días laborados del año × factor por días laborados.')
    total_utilities = fields.Float(
        string='Utilidades a pagar', digits=(12, 2),
        help='Participación por remuneraciones + por días, con el tope de '
             '18 remuneraciones mensuales.')
    monthly_remuneration = fields.Float(
        string='Rem. mensual al cierre', digits=(12, 2),
        help='Remuneración mensual vigente al cierre del ejercicio. La '
             'participación no puede superar 18 veces este importe '
             '(D.L. 892, art. 2).')
    excess_utilities = fields.Float(
        string='Exceso del tope', digits=(12, 2),
        help='Parte de la participación que supera el tope de 18 '
             'remuneraciones: no se paga al trabajador.')
    preserve_record = fields.Boolean(
        string='No recalcular',
        help='Al procesar de nuevo, la línea se conserva tal cual, con sus '
             'ajustes manuales.', tracking=True)

    @api.depends('employee')
    def _compute_display_name(self):
        """Snapshot del nombre al momento del cálculo: usar
        ``employee_id.name`` recalcularía el nombre si el empleado se
        renombra después del cierre, indeseable en reportes legales."""
        for line in self:
            line.display_name = line.employee or ''

    def action_compute(self):
        """Recalcula el reparto completo del registro padre; elimina la
        línea si queda sin participación (paridad v18)."""
        for record in self:
            record.main_id._distribute()
            if not record.total_utilities > 0 \
                    and not self.env.context.get('line_form'):
                record.unlink()
