# -*- coding: utf-8 -*-
"""Liquidación de cese: beneficios sociales truncos al fin del vínculo.

Cuando un trabajador cesa se liquidan los beneficios devengados y no
pagados del lote de nómina del mes de cese:

* **CTS trunca** (``cts_line_ids``): meses/días desde el último
  depósito hasta el cese (D.S. 001-97-TR); las líneas las genera el
  motor ``hr.main.parameter.compute_benefits(..., liquidation=self)``
  sobre ``hr.cts.line`` con ``liquidation_id``.
* **Gratificación trunca** (``gratification_line_ids``): meses del
  semestre vigente al cese (Ley 27735) + bono EsSalud trunco
  (Ley 29351 si ``with_bonus``); mismas líneas ``hr.gratification.line``
  colgadas de ``liquidation_id``.
* **Vacaciones truncas y devengadas** (``vacation_line_ids``): saldo
  no gozado al cese (D.L. 713 art. 23), con descuento AFP/ONP.
* **Conceptos extra** (``liq_ext_concept_ids``): pagos/descuentos
  adicionales al cese (indemnización LPCL art. 38, gratificación
  extraordinaria, etc.) mapeados a inputs de nómina.

Estados: ``draft`` (calculando) → ``exported`` (volcada al payslip de
liquidación vía los inputs truncos de ``hr.main.parameter``).

Portado de ``hr_social_benefits/models/hr_liquidation.py`` (v18).
Cambios v19: ``hr.contract`` → ``hr.version``; ``account.fiscal.year``
(eliminado) → campo entero ``year``; sin SQL; Excel/PDF quedan para la
Fase 7 y los asientos contables para la Fase 5.
"""
from calendar import monthrange
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.addons.al_hr_pe.models.display_name import pe_join

from odoo.addons.al_hr_pe.tools import custom_round
from .hr_benefits_engine import (
    ensure_draft, ensure_line_draft, notify_success)


class HrLiquidation(models.Model):
    _name = 'hr.liquidation'
    _description = 'Liquidación de cese'
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(string='Nombre')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    year = fields.Integer(
        string='Año', required=True,
        default=lambda self: fields.Date.context_today(self).year,
        help='Año del cese (sustituye al año fiscal contable v18); lo '
             'usa el motor para delimitar los semestres truncos.', aggregator=False)
    with_bonus = fields.Boolean(
        string='Bono extraordinario', default=True,
        help='Añade el Bono Extraordinario Ley 29351 sobre la '
             'gratificación trunca.')
    months_and_days = fields.Boolean(
        string='Calcular días grati.', default=False,
        help='Incluye los días sueltos (además de los meses completos) '
             'en el prorrateo de la gratificación trunca.')
    exchange_type = fields.Float(string='Tipo de cambio', default=1.0)
    gratification_type = fields.Selection(
        selection=[('07', 'Gratificación Fiestas Patrias'),
                   ('12', 'Gratificación Navidad')],
        string='Tipo gratificación', required=True)
    cts_type = fields.Selection(
        selection=[('11', 'CTS Mayo - Octubre'),
                   ('05', 'CTS Noviembre - Abril')],
        string='Tipo CTS', required=True)
    payslip_run_id = fields.Many2one(
        'hr.payslip.run', string='Lote de nómina', required=True,
        check_company=True)
    gratification_line_ids = fields.One2many(
        'hr.gratification.line', 'liquidation_id',
        string='Cálculo de gratificaciones truncas')
    cts_line_ids = fields.One2many(
        'hr.cts.line', 'liquidation_id', string='Cálculo de CTS trunca')
    vacation_line_ids = fields.One2many(
        'hr.liquidation.vacation.line', 'liquidation_id',
        string='Cálculo de vacaciones truncas')
    liq_ext_concept_ids = fields.One2many(
        'hr.liquidation.extra_concepts', 'liquidation_id',
        string='Otros conceptos')
    employee_ids = fields.Many2many(
        'hr.employee', 'hr_liquidation_employee_rel', 'liquidation_id',
        'employee_id', string='Empleados', check_company=True)
    employee_count = fields.Integer(string='Empleados', compute='_compute_employee_count')
    state = fields.Selection(
        selection=[('draft', 'Borrador'), ('exported', 'Exportado')],
        string='Estado', default='draft')

    _unique_run = models.Constraint(
        'UNIQUE(company_id, payslip_run_id)',
        'Ya existe una liquidación de cese para ese lote de nómina en '
        'la compañía.')

    @api.depends('employee_ids')
    def _compute_employee_count(self):
        """Smart-button: empleados incluidos en la liquidación."""
        for record in self:
            record.employee_count = len(record.employee_ids)

    @api.model
    def _last_anniversary(self, admission_date, on_date):
        """Último aniversario de ingreso ≤ ``on_date`` (el 29-feb cae el
        28 en años no bisiestos). Dentro del primer año, el ingreso."""
        if (on_date - admission_date).days <= 365:
            return admission_date
        year = on_date.year
        while True:
            day = min(admission_date.day,
                      monthrange(year, admission_date.month)[1])
            anniversary = date(year, admission_date.month, day)
            if anniversary <= on_date:
                return anniversary
            year -= 1

    @api.onchange('payslip_run_id')
    def _get_type(self):
        """Deduce año, semestre de gratificación y de CTS del lote."""
        for record in self:
            if not record.payslip_run_id or \
                    not record.payslip_run_id.date_start:
                continue
            date_start = record.payslip_run_id.date_start
            month = date_start.month
            record.year = date_start.year
            record.gratification_type = '12' if month > 6 else '07'
            if 10 < month <= 12 or 1 <= month < 5:
                record.cts_type = '05'
            else:
                record.cts_type = '11'
            record.name = self.env._(
                'Liquidación %(lot)s', lot=record.payslip_run_id.name)

    # Botones, en el mismo orden que en la vista
    # ------------------------------------------------------------------
    # Cálculo
    # ------------------------------------------------------------------
    def action_process(self):
        """Genera/recalcula los 4 bloques de la liquidación.

        Borra las líneas no preservadas, delega CTS y gratificación
        truncas al motor (``compute_benefits`` con ``liquidation=self``),
        calcula las vacaciones truncas y los conceptos extra, y descarta
        los duplicados de los empleados con overrides manuales
        (``preserve_record``), igual que ``hr.cts.get_cts``.
        """
        self.ensure_one()
        ensure_draft(self)
        param = self.env['hr.main.parameter']
        for lines in (self.gratification_line_ids, self.cts_line_ids,
                      self.vacation_line_ids, self.liq_ext_concept_ids):
            lines.filtered(lambda line: not line.preserve_record).unlink()
        param.compute_benefits(self, self.gratification_type,
                               liquidation=self)
        if self.gratification_type == '12' \
                and self.payslip_run_id.date_start.month == 7:
            # Cese en julio antes del pago de Fiestas Patrias (15-jul): sin
            # trabajar a esa fecha no hay gratificación regular '07', así
            # que ene-jun se paga como trunca (Ley 27735 art. 7). El motor
            # la omite si ya se abonó en una gratificación regular.
            param.compute_benefits(self, '07', liquidation=self)
        param.compute_benefits(self, self.cts_type, liquidation=self)
        if self.cts_type == '11' \
                and self.payslip_run_id.date_start.month == 5:
            # Cese en mayo antes del depósito (hasta el 15): la CTS de
            # nov-abr no la toma el depósito regular '05' (solo incluye
            # activos), así que se paga aquí. El motor la omite si ya se
            # depositó.
            param.compute_benefits(self, '05', liquidation=self)
        self.get_vacation_lines()
        self.get_extra_concepts_lines()
        for lines in (self.gratification_line_ids, self.cts_line_ids,
                      self.vacation_line_ids, self.liq_ext_concept_ids):
            preserved_employees = \
                lines.filtered('preserve_record').employee_id
            lines.filtered(
                lambda line: not line.preserve_record
                and line.employee_id in preserved_employees).unlink()
        return notify_success(self.env._('Se calculó exitosamente.'))

    def action_recompute(self):
        """Recalcula los 3 conceptos truncos en una pasada (botón
        «Recalcular»: útil si cambió el sueldo del cesado o se editaron
        los promedios de las líneas)."""
        self.ensure_one()
        ensure_draft(self)
        self.gratification_line_ids.action_compute()
        self.cts_line_ids.action_compute()
        self.vacation_line_ids.action_compute()
        return notify_success(self.env._('Se recalculó exitosamente.'))

    def action_export_to_payslips(self):
        """Cierra la liquidación y vuelca los conceptos al payslip.

        Escribe en el payslip de cada cesado los inputs truncos
        configurados en ``hr.main.parameter``
        (``truncated_gratification_input_id``,
        ``truncated_bonus_nine_input_id``, ``truncated_cts_input_id``,
        ``vacation_input_id``, ``truncated_vacation_input_id``) y los
        inputs de cada línea de conceptos extra. Marca ``exported``.
        """
        self.ensure_one()
        ensure_draft(self)
        param = self.env['hr.main.parameter'].get_main_parameter(
            self.company_id)
        param.check_liquidation_values()
        lot = self.payslip_run_id

        def employee_slip(employee):
            return lot.slip_ids.filtered(
                lambda slip: slip.employee_id == employee)

        # Un cesado de julio puede tener dos truncas (ene-jun y jul): el
        # input lleva la suma, no la última línea.
        for employee, lines in \
                self.gratification_line_ids.grouped('employee_id').items():
            slip = employee_slip(employee)
            self._set_slip_input(
                slip, param.truncated_gratification_input_id,
                sum(lines.mapped('total_grat')))
            self._set_slip_input(
                slip, param.truncated_bonus_nine_input_id,
                sum(lines.mapped('bonus_essalud')))
        for line in self.cts_line_ids:
            slip = employee_slip(line.employee_id)
            self._set_slip_input(
                slip, param.truncated_cts_input_id, line.total_cts)
        for line in self.vacation_line_ids:
            slip = employee_slip(line.employee_id)
            self._set_slip_input(
                slip, param.vacation_input_id, line.accrued_vacation)
            self._set_slip_input(
                slip, param.truncated_vacation_input_id,
                line.truncated_vacation)
            if line.vacation_indemnity:
                self._set_slip_input(
                    slip, self.env.ref('al_hr_pe.input_type_INDVAC'),
                    line.vacation_indemnity)
            # Las vacaciones adelantadas se restaban solo en el total de la
            # línea: la boleta pagaba las truncas completas.
            if line.advanced_vacation:
                self._set_slip_input(
                    slip, self.env.ref('al_hr_pe.input_type_ADE_VAC'),
                    line.advanced_vacation)
        for line in self.liq_ext_concept_ids:
            slip = employee_slip(line.employee_id)
            for concept in line.conceptos_lines:
                self._set_slip_input(
                    slip, concept.name_input_id, concept.amount)
        self.state = 'exported'
        return notify_success(self.env._('Se exportó exitosamente.'))

    def action_draft(self):
        """Reabre la liquidación a borrador para permitir recálculo."""
        self.write({'state': 'draft'})

    def action_add_employees(self):
        """Abre la lista de empleados incluidos en la liquidación."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('id', 'in', self.employee_ids.ids)],
            'name': self.env._('Empleados'),
        }

    def _get_cessation_slips(self, include_less_than_four=True):
        """Boletas del lote cuyo trabajador cesa dentro del periodo."""
        self.ensure_one()
        return self.payslip_run_id.slip_ids.filtered(
            lambda slip:
            slip.version_id.l10n_pe_labor_regime
            in ('general', 'small', 'micro')
            and slip.version_id.situation_code == '0'
            and slip.version_id.contract_date_end
            and slip.date_from <= slip.version_id.contract_date_end
            and slip.date_to >= slip.version_id.contract_date_end
            and (include_less_than_four
                 or not slip.version_id.l10n_pe_less_than_four))

    def get_vacation_lines(self):
        """Genera las líneas de vacaciones truncas del lote de cese.

        Cómputo desde el último aniversario de ingreso (D.L. 713):
        meses completos + días sueltos - faltas, sobre la remuneración
        computable (sueldo + asignación familiar + promedios de
        variables de los 6 meses previos al cese), con descuento
        AFP/ONP tomado del snapshot de la boleta del mes.
        """
        self.ensure_one()
        param = self.env['hr.main.parameter'].get_main_parameter(
            self.company_id)
        VacationLine = self.env['hr.liquidation.vacation.line']
        Run = self.env['hr.payslip.run']
        year = self.year
        slips = self._get_cessation_slips(include_less_than_four=False)
        for employee in slips.employee_id:
            month_slip = slips.filtered(
                lambda slip: slip.employee_id == employee)[:1]
            version = month_slip.version_id
            admission_date = self.env['hr.main.parameter'] \
                .get_first_version(employee).contract_date_start
            if admission_date > month_slip.date_from:
                continue
            cessation_date = version.contract_date_end
            # Fecha de cómputo: último aniversario de ingreso anterior o
            # igual al cese. Las truncas van desde ahí; los años ya
            # cumplidos y no gozados son vacaciones devengadas (campo
            # «Vac. devengadas»), no truncas.
            compute_date = self._last_anniversary(
                admission_date, cessation_date)
            dias_fracc = compute_date.day - 1
            if (cessation_date - admission_date).days <= 365:
                compute_date = admission_date
                dias_fracc = 0

            wage = version.wage
            household_allowance = sum(month_slip.line_ids.filtered(
                lambda line: line.salary_rule_id
                == param.household_allowance_sr_id).mapped('total'))

            # Meses/días/faltas desde la fecha de cómputo hasta el cese.
            months = days = lacks = 0
            compute_payslip_date = \
                date(compute_date.year, compute_date.month, 1)
            lots = Run.search([
                ('date_end', '>=', compute_payslip_date),
                ('date_end', '<=', month_slip.date_to),
                ('company_id', '=', self.company_id.id),
            ])
            for lot in lots:
                worked_days = lot.slip_ids.filtered(
                    lambda slip: slip.employee_id == employee
                ).mapped('worked_days_line_ids')
                # Las faltas cuentan para el mes y se descuentan una vez.
                counted, lot_lacks, _medical = \
                    param._l10n_pe_month_computable_days(worked_days)
                if lot.date_start < compute_date <= lot.date_end:
                    counted -= dias_fracc
                if counted >= (lot.date_end - lot.date_start).days + 1:
                    months += 1
                else:
                    days += counted
                lacks += lot_lacks

            # Ventana de conceptos variables: 6 meses previos al cese
            # (el mes de cese solo computa si termina en fin de mes).
            date_limit_to = cessation_date
            last_day = monthrange(date_limit_to.year, date_limit_to.month)[1]
            if last_day == date_limit_to.day:
                date_limit_from = date_limit_to - relativedelta(months=5)
                date_limit_from = \
                    date(date_limit_from.year, date_limit_from.month, 1)
            else:
                date_limit_from = date_limit_to - relativedelta(months=6)
                date_limit_from = \
                    date(date_limit_from.year, date_limit_from.month, 1)
                date_limit_to = date_limit_to - relativedelta(months=1)
                date_limit_to = date(
                    date_limit_to.year, date_limit_to.month,
                    monthrange(date_limit_to.year, date_limit_to.month)[1])
            var_lots = Run.search([
                ('date_end', '>=', date_limit_from),
                ('date_end', '<=', date_limit_to),
                ('company_id', '=', self.company_id.id),
            ])
            employee_slips = var_lots.slip_ids.filtered(
                lambda slip: slip.employee_id == employee)
            bonus_months = param._count_months(employee_slips)
            salary_rules = employee_slips.mapped('line_ids')
            commissions = salary_rules.filtered(
                lambda line: line.salary_rule_id in param.commission_sr_ids
                and line.total > 0)
            bonus_lines = salary_rules.filtered(
                lambda line: line.salary_rule_id in param.bonus_sr_ids
                and line.total > 0)
            extra_hours_lines = salary_rules.filtered(
                lambda line: line.salary_rule_id == param.extra_hours_sr_id
                and line.total > 0)

            commission = param.calculate_bonus(
                admission_date, date_limit_from, bonus_months, commissions)
            bonus = param.calculate_bonus(
                admission_date, date_limit_from, bonus_months, bonus_lines)
            extra_hours = param.calculate_bonus(
                admission_date, date_limit_from, bonus_months,
                extra_hours_lines)
            computable_remuneration = (wage + household_allowance
                                       + commission + bonus + extra_hours)
            if days >= 30:
                days, months = param.get_months_of_30_days(days, months)
            if version.l10n_pe_labor_regime == 'general':
                amount_per_month = computable_remuneration / 12
            else:
                amount_per_month = computable_remuneration / 24
            amount_per_day = amount_per_month / 30
            amount_per_lack = amount_per_day * lacks
            vacation_per_month = custom_round(amount_per_month * months, 2)
            vacation_per_day = custom_round(amount_per_day * days, 2)
            truncated_vacation = custom_round(
                vacation_per_month + vacation_per_day - amount_per_lack, 2)
            total_vacation = truncated_vacation
            deductions = VacationLine._get_pension_deductions(
                month_slip, total_vacation)
            vals = {
                'liquidation_id': self.id,
                'employee_id': employee.id,
                'version_id': version.id,
                'admission_date': admission_date,
                'compute_date': compute_date,
                'cessation_date': cessation_date,
                'months': months,
                'days': days,
                'lacks': lacks,
                'wage': wage,
                'household_allowance': household_allowance,
                'commission': commission,
                'bonus': bonus,
                'extra_hours': extra_hours,
                'computable_remuneration': computable_remuneration,
                'amount_per_month': amount_per_month,
                'amount_per_day': amount_per_day,
                'amount_per_lack': amount_per_lack,
                'vacation_per_month': vacation_per_month,
                'vacation_per_day': vacation_per_day,
                'truncated_vacation': truncated_vacation,
                'total_vacation': total_vacation,
                'total': custom_round(
                    total_vacation - sum(deductions.values()), 2),
            }
            vals.update(deductions)
            # TODO(fase4-revisar): distribution_id (distribución
            # analítica del contrato v18) sin equivalente en hr.version.
            VacationLine.create(vals)

    def get_extra_concepts_lines(self):
        """Crea una fila de conceptos extra por cesado y fija
        ``employee_ids`` (smart button)."""
        self.ensure_one()
        slips = self._get_cessation_slips()
        employees = slips.employee_id
        self.employee_ids = [(6, 0, employees.ids)]
        Concepts = self.env['hr.liquidation.extra_concepts']
        for employee in employees:
            month_slip = slips.filtered(
                lambda slip: slip.employee_id == employee)[:1]
            version = month_slip.version_id
            admission_date = self.env['hr.main.parameter'] \
                .get_first_version(employee).contract_date_start
            if admission_date > self.payslip_run_id.date_start:
                continue
            Concepts.create({
                'liquidation_id': self.id,
                'employee_id': employee.id,
                'version_id': version.id,
                'admission_date': admission_date,
                'cessation_date': version.contract_date_end,
            })

    # ------------------------------------------------------------------
    # Exportación al lote de nómina
    # ------------------------------------------------------------------
    @api.model
    def _set_slip_input(self, slip, input_type, amount):
        """Escribe (o crea) el input ``input_type`` del payslip."""
        if not slip or not input_type:
            return
        slip = slip[:1]
        input_line = slip.input_line_ids.filtered(
            lambda inp: inp.input_type_id == input_type)
        if input_line:
            input_line.amount = amount
        else:
            slip.write({'input_line_ids': [(0, 0, {
                'input_type_id': input_type.id,
                'amount': amount,
            })]})


class HrLiquidationVacationLine(models.Model):
    _name = 'hr.liquidation.vacation.line'
    _description = 'Línea de vacaciones truncas en liquidación'
    _order = 'employee_id'
    _check_company_auto = True

    liquidation_id = fields.Many2one(
        'hr.liquidation', string='Liquidación', ondelete='cascade',
        required=True, index=True,
        check_company=True)
    company_id = fields.Many2one(
        related='liquidation_id.company_id', string='Compañía',
        store=True, index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', check_company=True)
    version_id = fields.Many2one(
        'hr.version', string='Contrato (versión)', check_company=True)
    identification_id = fields.Char(
        related='employee_id.identification_id', string='Nro. documento')
    last_name = fields.Char(
        related='employee_id.last_name', string='Apellido paterno')
    m_last_name = fields.Char(
        related='employee_id.m_last_name', string='Apellido materno')
    names = fields.Char(related='employee_id.names', string='Nombres')
    admission_date = fields.Date(string='Fecha de ingreso')
    compute_date = fields.Date(string='Fecha de cómputo')
    cessation_date = fields.Date(string='Fecha de cese')
    membership_id = fields.Many2one(
        related='version_id.membership_id', string='Afiliación')
    distribution_id = fields.Char(string='Distribución analítica')
    months = fields.Integer(string='Meses')
    # Decimal: el cómputo usa días fraccionarios y, guardados como
    # entero, «Recalcular» daba otro importe que el cálculo inicial.
    days = fields.Float(string='Días', digits=(16, 2))
    lacks = fields.Float(string='Faltas', digits=(16, 2))
    wage = fields.Float(string='Sueldo')
    household_allowance = fields.Float(string='Asignación familiar')
    commission = fields.Float(string='Prom. comisión')
    bonus = fields.Float(string='Prom. bonificación')
    extra_hours = fields.Float(string='Prom. horas extras')
    computable_remuneration = fields.Float(string='Remuneración computable')
    amount_per_month = fields.Float(string='Monto por mes')
    amount_per_day = fields.Float(string='Monto por día')
    amount_per_lack = fields.Float(string='(-) Monto por faltas')
    vacation_per_month = fields.Float(string='Vac. por meses')
    vacation_per_day = fields.Float(string='Vac. por días')
    truncated_vacation = fields.Float(string='Vac. truncas')
    advanced_vacation = fields.Float(string='(-) Vac. adelantadas')
    accrued_vacation = fields.Float(string='(+) Vac. devengadas')
    vacation_indemnity = fields.Float(
        string='(+) Indemnización vacacional',
        help='D.Leg. 713, art. 23: una remuneración por cada período '
             'devengado que no se gozó dentro del año siguiente. No paga '
             'AFP/ONP ni EsSalud (sí es renta de 5ta); va a la boleta por '
             'el input INDVAC (PLAME 0504).')
    total_vacation = fields.Float(string='Total vacaciones')
    onp = fields.Float(string='(-) ONP')
    afp_jub = fields.Float(string='(-) AFP jubilación')
    afp_si = fields.Float(string='(-) AFP seguro')
    afp_mixed_com = fields.Float(string='(-) AFP com. mixta')
    afp_fixed_com = fields.Float(string='(-) AFP com. flujo')
    total = fields.Float(string='Neto total')
    preserve_record = fields.Boolean(string='No recalcular')

    @api.model
    def _get_pension_deductions(self, month_slip, total_vacation):
        """Descuentos previsionales sobre el total vacacional.

        Usa el snapshot AFP/ONP de la boleta del mes de cese:
        jubilación y comisión sobre el total; prima de seguro sobre
        ``min(total, tope asegurable)`` y exenta para mayores de 65.
        """
        onp = afp_jub = afp_si = afp_mixed_com = afp_fixed_com = 0.0
        membership = month_slip.membership_id
        if membership.is_afp:
            afp_jub = custom_round(
                month_slip.l10n_pe_retirement_fund / 100 * total_vacation, 2)
            si_base = min(
                total_vacation, month_slip.l10n_pe_insurable_remuneration)
            afp_si = custom_round(
                month_slip.l10n_pe_prima_insurance / 100 * si_base, 2)
            # TODO(fase4-revisar): en v18 la exención por mayor de 65
            # solo se aplicaba en el recálculo manual de la línea; aquí
            # se aplica también en el cálculo inicial.
            if month_slip.l10n_pe_is_older:
                afp_si = 0.0
            afp_commission = custom_round(
                month_slip.l10n_pe_commission / 100 * total_vacation, 2)
            if month_slip.version_id.l10n_pe_commission_type == 'mixed':
                afp_mixed_com = afp_commission
            else:
                afp_fixed_com = afp_commission
        else:
            onp = custom_round(
                month_slip.l10n_pe_retirement_fund / 100 * total_vacation, 2)
        return {
            'onp': onp,
            'afp_jub': afp_jub,
            'afp_si': afp_si,
            'afp_mixed_com': afp_mixed_com,
            'afp_fixed_com': afp_fixed_com,
        }

    def action_compute(self):
        """Recalcula la línea a partir de sus componentes editables
        (incluye adelantadas/devengadas capturadas a mano)."""
        ensure_line_draft(self, 'liquidation_id')
        for record in self:
            month_slip = record.liquidation_id.payslip_run_id.slip_ids \
                .filtered(lambda slip:
                          slip.employee_id == record.employee_id)[:1]
            record.computable_remuneration = (
                record.wage + record.household_allowance + record.commission
                + record.bonus + record.extra_hours)
            if record.version_id.l10n_pe_labor_regime == 'general':
                record.amount_per_month = \
                    record.computable_remuneration / 12
            else:
                record.amount_per_month = \
                    record.computable_remuneration / 24
            record.amount_per_day = record.amount_per_month / 30
            record.amount_per_lack = record.amount_per_day * record.lacks
            record.vacation_per_month = custom_round(
                record.amount_per_month * record.months, 2)
            record.vacation_per_day = custom_round(
                record.amount_per_day * record.days, 2)
            record.truncated_vacation = custom_round(
                record.vacation_per_month + record.vacation_per_day
                - record.amount_per_lack, 2)
            record.total_vacation = (
                record.accrued_vacation + record.truncated_vacation
                - record.advanced_vacation)
            deductions = self._get_pension_deductions(
                month_slip, record.total_vacation)
            record.update(deductions)
            # La indemnización no paga aportes: se suma después.
            record.total = custom_round(
                record.total_vacation - sum(deductions.values())
                + record.vacation_indemnity, 2)
            if record.total <= 0 and not self.env.context.get('line_form'):
                record.unlink()

    @api.depends('liquidation_id', 'employee_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = pe_join(rec.liquidation_id.display_name, rec.employee_id.name)


class HrLiquidationExtraConcepts(models.Model):
    _name = 'hr.liquidation.extra_concepts'
    _description = 'Conceptos adicionales de liquidación'
    _order = 'employee_id'
    _check_company_auto = True

    liquidation_id = fields.Many2one(
        'hr.liquidation', string='Liquidación', ondelete='cascade',
        required=True, index=True,
        check_company=True)
    company_id = fields.Many2one(
        related='liquidation_id.company_id', string='Compañía',
        store=True, index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', check_company=True)
    version_id = fields.Many2one(
        'hr.version', string='Contrato (versión)', check_company=True)
    identification_id = fields.Char(
        related='employee_id.identification_id', string='Nro. documento')
    admission_date = fields.Date(string='Fecha de ingreso')
    cessation_date = fields.Date(string='Fecha de cese')
    conceptos_lines = fields.One2many(
        'hr.extra.concept.line', 'extra_concept_id',
        string='Conceptos extra')
    income = fields.Float(
        string='Ingresos', compute='_compute_totals', store=True)
    expenses = fields.Float(
        string='Descuentos', compute='_compute_totals', store=True)
    preserve_record = fields.Boolean(string='No recalcular')

    @api.depends('conceptos_lines.amount', 'conceptos_lines.type')
    def _compute_totals(self):
        """Totaliza ingresos/descuentos de los conceptos capturados
        (en v18 se actualizaba con un botón; aquí es compute)."""
        for record in self:
            lines = record.conceptos_lines
            record.income = sum(lines.filtered(
                lambda line: line.type == 'in').mapped('amount'))
            record.expenses = sum(lines.filtered(
                lambda line: line.type == 'out').mapped('amount'))

    def action_add_concepts(self):
        """Popup para capturar los conceptos extra del cesado."""
        self.ensure_one()
        view = self.env.ref('al_hr_pe_benefits.hr_extra_concept_view_form')
        return {
            'name': self.env._('Conceptos adicionales'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.liquidation.extra_concepts',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(view.id, 'form')],
            'target': 'new',
        }

    @api.depends('liquidation_id', 'employee_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = pe_join(rec.liquidation_id.display_name, rec.employee_id.name)


class HrExtraConceptLine(models.Model):
    _name = 'hr.extra.concept.line'
    _description = 'Línea de concepto adicional'
    _check_company_auto = True

    extra_concept_id = fields.Many2one(
        'hr.liquidation.extra_concepts', string='Otros conceptos',
        ondelete='cascade', required=True, index=True,
        check_company=True)
    company_id = fields.Many2one(
        related='extra_concept_id.company_id', string='Compañía',
        store=True, index=True)
    name_input_id = fields.Many2one(
        'hr.payslip.input.type', string='Descripción')
    amount = fields.Float(string='Monto')
    type = fields.Selection(
        selection=[('in', 'Ingreso'), ('out', 'Descuento')],
        string='Tipo', default='in')

    @api.depends('extra_concept_id', 'name_input_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = pe_join(rec.extra_concept_id.display_name, rec.name_input_id.display_name)
