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
  (Ley 30334 si ``with_bonus``); mismas líneas ``hr.gratification.line``
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
from .hr_benefits_engine import (
    employee_lot_slip, ensure_slips_draft, recompute_slips)
from .hr_benefits_engine import compute_locked


class HrLiquidation(models.Model):
    _name = 'hr.liquidation'
    _description = 'Liquidación de cese'
    _inherit = ['mail.thread', 'mail.activity.mixin']
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
             'usa el motor para delimitar los semestres truncos.', aggregator=False, tracking=True)
    with_bonus = fields.Boolean(
        string='Con bonificación extraordinaria', default=True,
        help='Añade la bonificación extraordinaria de la Ley 30334 sobre la '
             'gratificación trunca.', tracking=True)
    months_and_days = fields.Boolean(
        string='Incluir días sueltos', default=False,
        help='Incluye los días sueltos (además de los meses completos) '
             'en el prorrateo de la gratificación trunca.', tracking=True)
    exchange_type = fields.Float(
        string='Tipo de cambio', default=1.0,
        help='Para convertir a dólares la CTS trunca de las cuentas en esa '
             'moneda.', tracking=True)
    gratification_type = fields.Selection(
        selection=[('07', 'Gratificación Fiestas Patrias'),
                   ('12', 'Gratificación Navidad')],
        string='Semestre de la gratificación', required=True, tracking=True)
    cts_type = fields.Selection(
        selection=[('11', 'CTS Mayo - Octubre'),
                   ('05', 'CTS Noviembre - Abril')],
        string='Semestre de la CTS', required=True, tracking=True)
    payslip_run_id = fields.Many2one(
        'hr.payslip.run', string='Lote de nómina', required=True,
        check_company=True, tracking=True)
    gratification_line_ids = fields.One2many(
        'hr.gratification.line', 'liquidation_id',
        string='Gratificación trunca')
    cts_line_ids = fields.One2many(
        'hr.cts.line', 'liquidation_id', string='CTS trunca')
    vacation_line_ids = fields.One2many(
        'hr.liquidation.vacation.line', 'liquidation_id',
        string='Vacaciones truncas')
    liq_ext_concept_ids = fields.One2many(
        'hr.liquidation.extra_concepts', 'liquidation_id',
        string='Otros conceptos')
    employee_ids = fields.Many2many(
        'hr.employee', 'hr_liquidation_employee_rel', 'liquidation_id',
        'employee_id', string='Trabajadores cesados', check_company=True)
    employee_count = fields.Integer(string='N.º de cesados', compute='_compute_employee_count')
    state = fields.Selection(
        selection=[('draft', 'Borrador'), ('exported', 'Exportado')],
        string='Estado', default='draft', tracking=True)

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
        if self.cts_type == '05' \
                and self.payslip_run_id.date_start.month == 11:
            # Igual en noviembre: la CTS de may-oct se deposita hasta el 15
            # y el depósito regular '11' no incluye al cesado (situación
            # 0). Si no se depositó antes del cese, se paga en la
            # liquidación (D.S. 001-97-TR); el motor la omite si ya se
            # depositó.
            param.compute_benefits(self, '11', liquidation=self)
        # Sin un mes de servicios no hay CTS trunca (D.S. 001-97-TR: se
        # devenga desde el primer mes; luego, por treintavos).
        short = self._get_cessation_slips().filtered(
            lambda slip: not self._has_one_month(slip.employee_id,
                                                 slip.version_id))
        self.cts_line_ids.filtered(
            lambda line: not line.preserve_record
            and line.employee_id in short.employee_id).unlink()
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
        slip_by_employee = {
            employee: employee_lot_slip(lot, employee)
            for employee in self.gratification_line_ids.employee_id
            | self.cts_line_ids.employee_id
            | self.vacation_line_ids.employee_id
            | self.liq_ext_concept_ids.employee_id}
        slips = self.env['hr.payslip'].union(slip_by_employee.values())
        ensure_slips_draft(slips)

        def employee_slip(employee):
            return slip_by_employee[employee]

        # Importe por (boleta, input): dos conceptos con el mismo input se
        # suman en vez de pisarse.
        amounts = {}

        def add_input(slip, input_type, amount):
            if slip and input_type:
                key = (slip[:1], input_type)
                amounts[key] = amounts.get(key, 0.0) + amount

        # Un cesado de julio puede tener dos truncas (ene-jun y jul): el
        # input lleva la suma, no la última línea.
        for employee, lines in \
                self.gratification_line_ids.grouped('employee_id').items():
            slip = employee_slip(employee)
            add_input(
                slip, param.truncated_gratification_input_id,
                sum(lines.mapped('total_grat')))
            add_input(
                slip, param.truncated_bonus_nine_input_id,
                sum(lines.mapped('bonus_essalud')))
        # Igual con la CTS: un cese en mayo tiene la trunca de nov-abr y la
        # de mayo; antes la boleta se quedaba solo con la última.
        for employee, lines in \
                self.cts_line_ids.grouped('employee_id').items():
            add_input(
                employee_slip(employee), param.truncated_cts_input_id,
                sum(lines.mapped('total_cts')))
        VacationLine = self.env['hr.vacation.line']
        for line in self.vacation_line_ids:
            slip = employee_slip(line.employee_id)
            accrued, truncated = line._l10n_pe_export_split()
            # El input de vacaciones también lleva el goce del mes
            # exportado desde la liquidación vacacional del mismo lote: se
            # suma en vez de pisarlo.
            accrued += VacationLine._l10n_pe_exported_rest(
                self.payslip_run_id, line.employee_id)
            add_input(slip, param.vacation_input_id, accrued)
            add_input(slip, param.truncated_vacation_input_id, truncated)
            if line.vacation_indemnity:
                # Input propio (INDVAC, PLAME 0504): la indemnización no
                # es remuneración vacacional ni paga aportes.
                add_input(
                    slip, self.env.ref('al_hr_pe.salary_rule_INDVAC'),
                    line.vacation_indemnity)
        for line in self.liq_ext_concept_ids:
            slip = employee_slip(line.employee_id)
            for concept in line.conceptos_lines:
                add_input(slip, concept.name_input_id, concept.amount)
        for (slip, input_type), amount in amounts.items():
            self._set_slip_input(slip, input_type, amount)
        # Adelantos y préstamos de beneficios pendientes: todos los de
        # gratificación, vacaciones y liquidación; los de CTS hasta el 50 %
        # de la CTS trunca (art. 40 del TUO de la Ley de CTS).
        cts_by_employee = self.cts_line_ids.grouped('employee_id')
        for employee, slip in slip_by_employee.items():
            if not slip:
                continue
            slip = slip[:1]
            slip._l10n_pe_discount_benefit_advances(('grat', 'vaca', 'liqui'))
            cts_lines = cts_by_employee.get(employee)
            if cts_lines:
                slip._l10n_pe_discount_benefit_advances('cts', cap=custom_round(
                    sum(cts_lines.mapped('total_cts')) * 0.5, 2))
        recompute_slips(slips)
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

    @api.model
    def _service_year_start(self, admission_date, on_date):
        """Inicio del año de servicios en curso el día siguiente a
        ``on_date``: el aniversario de ingreso (los años se cuentan como en
        el récord vacacional). Si ``on_date`` cierra un año, es el día
        siguiente (no hay periodo trunco)."""
        start = admission_date
        while start + relativedelta(years=1) - relativedelta(days=1) \
                <= on_date:
            start += relativedelta(years=1)
        return start

    @api.model
    def _has_one_month(self, employee, version):
        """¿El cesado tiene al menos un mes de servicios? Sin él no hay
        vacaciones truncas (D.Leg. 713, art. 22) ni CTS trunca
        (D.S. 001-97-TR)."""
        cessation_date = version.contract_date_end
        if not cessation_date:
            return True
        admission_date = self.env['hr.main.parameter'].get_first_version(
            employee, cessation_date).contract_date_start
        span = relativedelta(
            cessation_date + relativedelta(days=1), admission_date)
        return bool(span.years or span.months)

    def get_vacation_lines(self):
        """Genera las líneas de vacaciones del lote de cese.

        * Truncas: desde el inicio del año de servicios en curso (D.L.
          713), meses calendario + días - faltas, sobre la remuneración
          computable (sueldo + asignación familiar + promedios de
          variables de los 6 meses previos al cese). Exigen un mes de
          servicios.
        * Devengadas e indemnización vacacional: de los años cumplidos y
          no gozados (``hr.vacation.rest._l10n_pe_pending_vacation``).
        * Adelantadas: lo gozado de más, que se descuenta.

        Descuento AFP/ONP tomado del snapshot de la boleta del mes.
        """
        self.ensure_one()
        param = self.env['hr.main.parameter'].get_main_parameter(
            self.company_id)
        VacationLine = self.env['hr.liquidation.vacation.line']
        Run = self.env['hr.payslip.run']
        Rest = self.env['hr.vacation.rest'].with_company(self.company_id)
        slips = self._get_cessation_slips(include_less_than_four=False)
        for employee in slips.employee_id:
            month_slip = slips.filtered(
                lambda slip: slip.employee_id == employee)[:1]
            version = month_slip.version_id
            admission_date = self.env['hr.main.parameter'] \
                .get_first_version(employee, month_slip.date_to) \
                .contract_date_start
            if admission_date > month_slip.date_from:
                continue
            cessation_date = version.contract_date_end
            # Vacaciones truncas: basta un mes de servicios (D.Leg. 713,
            # art. 22); con menos no hay línea.
            if not self._has_one_month(employee, version):
                continue
            # Fecha de cómputo: inicio del año de servicios en curso al
            # cese (aniversario de ingreso). Las truncas van desde ahí; los
            # años ya cumplidos y no gozados son vacaciones devengadas, no
            # truncas. Si el cese cierra justo un año, no hay truncas.
            compute_date = self._service_year_start(
                admission_date, cessation_date)

            wage = version.wage
            household_allowance = sum(month_slip.line_ids.filtered(
                lambda line: line.salary_rule_id
                == param.household_allowance_sr_id).mapped('total'))

            # Meses calendario y días desde la fecha de cómputo hasta el
            # cese (como ``get_months_days_difference`` pero sin sumar los
            # días sueltos de los dos extremos: 10-03 → 20-10 son 7 meses
            # y 11 días). De ahí se restan los días del periodo que las
            # boletas no computan (licencia sin goce, meses sin boleta…).
            months = days = lacks = 0
            missing = 0.0
            if compute_date <= cessation_date:
                span = relativedelta(
                    cessation_date + relativedelta(days=1), compute_date)
                months = span.years * 12 + span.months
                days = span.days
                lots = Run.search([
                    ('date_end', '>=', date(
                        compute_date.year, compute_date.month, 1)),
                    ('date_end', '<=', month_slip.date_to),
                    ('company_id', '=', self.company_id.id),
                ])
                # Un mes cuenta una vez aunque tenga varios lotes: vale el
                # lote con más días computables.
                for month_lots in param._l10n_pe_lots_by_month(lots):
                    # Las faltas cuentan para el mes y se descuentan una
                    # vez (``amount_per_lack``).
                    counted, lot_lacks, lot = max(
                        (param._l10n_pe_month_computable_days(
                            lot.slip_ids.filtered(
                                lambda slip: slip.employee_id == employee
                            ).worked_days_line_ids)[:2] + (lot,)
                         for lot in month_lots),
                        key=lambda item: item[0])
                    first = max(lot.date_start, compute_date)
                    last = min(lot.date_end, cessation_date)
                    if last < first:
                        continue
                    # La boleta del mes del aniversario trae los días
                    # anteriores a la fecha de cómputo (del año ya
                    # cumplido): no son de este periodo.
                    before = (compute_date - max(
                        lot.date_start, admission_date)).days
                    if before > 0:
                        counted -= before
                    missing += max(0.0, (last - first).days + 1 - counted)
                    lacks += lot_lacks
                days -= missing
                while days < 0 and months > 0:
                    months -= 1
                    days += 30
                days = max(days, 0)

            # Variables: el mismo criterio que la gratificación y la CTS
            # truncas (6 meses previos al cese o los laborados si son menos).
            averages = param._l10n_pe_truncated_variables(
                employee, cessation_date, admission_date, version=version)
            commission = averages['commission']
            bonus = averages['bonus']
            extra_hours = averages['extra_hours']
            computable_remuneration = (wage + household_allowance
                                       + commission + bonus + extra_hours)
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
            # Años de servicios cumplidos y no gozados (récord y saldos de
            # vacaciones): una remuneración vacacional por los días
            # pendientes y, si venció el plazo para gozarlos (el año
            # siguiente), además la indemnización vacacional (D.Leg. 713,
            # art. 23). Lo gozado o vendido por encima de lo ganado es
            # adelanto y se descuenta de las truncas.
            years, advance_days = Rest._l10n_pe_pending_vacation(
                employee, cessation_date)
            amount_per_vacation_day = computable_remuneration / 30
            accrued_days = sum(year['pending'] for year in years)
            indemnity_days = sum(
                year['pending'] for year in years
                if year['deadline'] < cessation_date
                and not year.get('formative'))
            accrued_vacation = custom_round(
                amount_per_vacation_day * accrued_days, 2)
            vacation_indemnity = custom_round(
                amount_per_vacation_day * indemnity_days, 2)
            advanced_vacation = custom_round(
                amount_per_vacation_day * advance_days, 2)
            total_vacation = custom_round(
                accrued_vacation + truncated_vacation - advanced_vacation, 2)
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
                'accrued_vacation': accrued_vacation,
                'accrued_days': accrued_days,
                'vacation_indemnity': vacation_indemnity,
                'indemnity_days': indemnity_days,
                'advanced_vacation': advanced_vacation,
                'total_vacation': total_vacation,
                'total': custom_round(
                    total_vacation - sum(deductions.values())
                    + vacation_indemnity, 2),
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
                .get_first_version(employee, month_slip.date_to) \
                .contract_date_start
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
            lambda inp: inp.salary_rule_id == input_type)
        if input_line:
            input_line.amount = amount
        else:
            slip.write({'input_line_ids': [(0, 0, {
                'salary_rule_id': input_type.id,
                'amount': amount,
            })]})


class HrLiquidationVacationLine(models.Model):
    _name = 'hr.liquidation.vacation.line'
    _description = 'Línea de vacaciones truncas en liquidación'
    _inherit = 'hr.benefits.line.mixin'
    _order = 'employee_id'
    _check_company_auto = True

    # La cabecera (lote o liquidación) ya no está en un estado editable: la
    # vista deja la línea de solo lectura.
    l10n_pe_locked = fields.Boolean(
        string='Bloqueada', compute='_compute_l10n_pe_locked')

    @api.depends('liquidation_id.state')
    def _compute_l10n_pe_locked(self):
        compute_locked(self, {'liquidation_id': ('draft',)})

    liquidation_id = fields.Many2one(
        'hr.liquidation', string='Liquidación', ondelete='cascade',
        required=True, index=True,
        check_company=True)
    company_id = fields.Many2one(
        related='liquidation_id.company_id', string='Compañía',
        store=True, index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Trabajador', check_company=True)
    version_id = fields.Many2one(
        'hr.version', string='Contrato (versión)', check_company=True)
    identification_id = fields.Char(
        related='employee_id.identification_id', string='N.º de documento')
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
    months = fields.Integer(string='Meses completos')
    # Decimal: el cómputo usa días fraccionarios y, guardados como
    # entero, «Recalcular» daba otro importe que el cálculo inicial.
    days = fields.Float(string='Días adicionales', digits=(16, 2))
    lacks = fields.Float(string='Faltas (días)', digits=(16, 2))
    wage = fields.Float(string='Sueldo')
    household_allowance = fields.Float(string='Asignación familiar')
    commission = fields.Float(string='Promedio de comisiones')
    bonus = fields.Float(string='Promedio de bonificaciones')
    extra_hours = fields.Float(string='Promedio de horas extras')
    computable_remuneration = fields.Float(
        string='Remuneración computable',
        help='Sueldo + asignación familiar + promedios de comisiones, '
             'bonificaciones y horas extras.')
    amount_per_month = fields.Float(
        string='Importe por mes completo',
        help='Remuneración computable ÷ 12 (÷ 24 fuera del régimen general).')
    amount_per_day = fields.Float(
        string='Importe por día', help='Importe por mes ÷ 30.')
    amount_per_lack = fields.Float(
        string='Descuento por faltas', help='Importe por día × faltas.')
    vacation_per_month = fields.Float(
        string='Vac. por meses completos', help='Importe por mes × meses.')
    vacation_per_day = fields.Float(
        string='Vac. por días', help='Importe por día × días.')
    truncated_vacation = fields.Float(
        string='Vacaciones truncas',
        help='Vacaciones por meses + por días − descuento por faltas: la '
             'parte del año vacacional en curso al cese.')
    advanced_vacation = fields.Float(
        string='Vacaciones adelantadas',
        help='Vacaciones ya pagadas por adelantado: se descuentan.', tracking=True)
    accrued_vacation = fields.Float(
        string='Vacaciones devengadas',
        help='Vacaciones de años completos ganadas y no gozadas: se suman. '
             'Salen del récord y de los saldos de vacaciones (años que '
             'cumplen el récord menos los días gozados o vendidos, primero '
             'los del año más antiguo).')
    accrued_days = fields.Float(
        string='Días devengados no gozados', digits=(16, 2),
        help='Días de los años de servicios cumplidos que no se gozaron ni '
             'vendieron.')
    vacation_indemnity = fields.Float(
        string='Indemnización vacacional',
        help='D.Leg. 713, art. 23: una remuneración por cada período '
             'devengado que no se gozó dentro del año siguiente. No paga '
             'AFP/ONP ni EsSalud; va a la boleta por su propio input '
             'INDVAC (PLAME 0504).')
    indemnity_days = fields.Float(
        string='Días con plazo de goce vencido', digits=(16, 2),
        help='Días devengados no gozados cuyo plazo para gozarlos (el año '
             'siguiente al de servicios) venció antes del cese.')
    total_vacation = fields.Float(
        string='Total vacaciones',
        help='Devengadas + truncas − adelantadas (base de los aportes).')
    onp = fields.Float(string='ONP')
    afp_jub = fields.Float(string='AFP: aporte obligatorio')
    afp_si = fields.Float(string='AFP: prima de seguro')
    afp_mixed_com = fields.Float(string='AFP: comisión mixta')
    afp_fixed_com = fields.Float(
        string='AFP: comisión por flujo',
        help='Comisión de la AFP sobre la remuneración (comisión por flujo).')
    total = fields.Float(
        string='Neto de vacaciones',
        help='Total vacaciones − aportes + indemnización vacacional.')
    preserve_record = fields.Boolean(
        string='No recalcular',
        help='Al procesar de nuevo, la línea se conserva tal cual, con sus '
             'ajustes manuales.', tracking=True)

    def _l10n_pe_export_split(self):
        """(devengadas, truncas) que van a la boleta. Las vacaciones
        adelantadas ya pagaron aportes cuando se gozaron: se restan de las
        truncas (y, si no alcanzan, de las devengadas) en vez de ir como
        descuento neto ADE_VAC, que dejaba los aportes de la boleta sobre
        las truncas completas y no cuadraba con la línea."""
        self.ensure_one()
        truncated = self.truncated_vacation - self.advanced_vacation
        accrued = self.accrued_vacation + min(truncated, 0.0)
        return accrued, max(truncated, 0.0)

    @api.model
    def _l10n_pe_exported_accrued(self, lot, employee):
        """Vacaciones devengadas de las liquidaciones de cese ya exportadas
        al lote ``lot`` para ``employee`` (van al mismo input que el goce
        de la liquidación vacacional)."""
        lines = self.search([
            ('liquidation_id.payslip_run_id', '=', lot.id),
            ('liquidation_id.state', '=', 'exported'),
            ('employee_id', '=', employee.id),
        ])
        return sum(line._l10n_pe_export_split()[0] for line in lines)

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

    # La cabecera (lote o liquidación) ya no está en un estado editable: la
    # vista deja la línea de solo lectura.
    l10n_pe_locked = fields.Boolean(
        string='Bloqueada', compute='_compute_l10n_pe_locked')

    @api.depends('liquidation_id.state')
    def _compute_l10n_pe_locked(self):
        compute_locked(self, {'liquidation_id': ('draft',)})

    liquidation_id = fields.Many2one(
        'hr.liquidation', string='Liquidación', ondelete='cascade',
        required=True, index=True,
        check_company=True)
    company_id = fields.Many2one(
        related='liquidation_id.company_id', string='Compañía',
        store=True, index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Trabajador', check_company=True)
    version_id = fields.Many2one(
        'hr.version', string='Contrato (versión)', check_company=True)
    identification_id = fields.Char(
        related='employee_id.identification_id', string='N.º de documento')
    admission_date = fields.Date(string='Fecha de ingreso')
    cessation_date = fields.Date(string='Fecha de cese')
    conceptos_lines = fields.One2many(
        'hr.extra.concept.line', 'extra_concept_id',
        string='Conceptos')
    income = fields.Float(
        string='Otros ingresos', compute='_compute_totals', store=True)
    expenses = fields.Float(
        string='Otros descuentos', compute='_compute_totals', store=True)
    preserve_record = fields.Boolean(
        string='No recalcular',
        help='Al procesar de nuevo, la línea se conserva tal cual, con sus '
             'ajustes manuales.')
    # Indemnización por despido arbitrario (asistente del popup).
    l10n_pe_cessation_reason = fields.Selection(
        [('arbitrary', 'Despido arbitrario'),
         ('other', 'Otro motivo (sin indemnización)')],
        string='Motivo del cese', default='other',
        help='Solo el despido arbitrario (sin causa justa o sin probarla) '
             'da indemnización: D.S. 003-97-TR, arts. 34, 38 y 76. La '
             'renuncia, el término del contrato o el despido por causa '
             'justa no la dan.')
    l10n_pe_contract_kind = fields.Selection(
        [('indefinite', 'Plazo indeterminado'), ('fixed', 'Plazo fijo')],
        string='Tipo de contrato', default='indefinite',
        help='Plazo indeterminado: 1,5 remuneraciones mensuales por año de '
             'servicios (fracciones por dozavos y treintavos), tope 12. '
             'Plazo fijo: 1,5 remuneraciones por cada mes que faltaba para '
             'el fin pactado, tope 12. En la pequeña empresa son 20 '
             'remuneraciones diarias por año (tope 120) y en la '
             'microempresa 10 (tope 90).')
    l10n_pe_labor_regime = fields.Selection(
        related='version_id.l10n_pe_labor_regime', string='Régimen laboral')
    l10n_pe_planned_end = fields.Date(
        string='Fin pactado del contrato',
        help='Contrato a plazo fijo: fecha en que debía terminar. La '
             'indemnización cubre los meses que faltaban desde el cese.')
    l10n_pe_indemnity_base = fields.Float(
        string='Remuneración mensual',
        help='Remuneración mensual ordinaria para la indemnización. Si se '
             'deja en cero, se toma la remuneración computable de las '
             'vacaciones truncas (o sueldo + asignación familiar).')
    l10n_pe_indemnity = fields.Float(
        string='Indemnización calculada', readonly=True,
        help='Se escribe en el concepto INDEM del cesado al calcular. Se '
             'paga junto con los beneficios sociales, dentro de las 48 '
             'horas del cese.')

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

    def _l10n_pe_indemnity_base(self):
        """Remuneración mensual de la indemnización: la indicada o, si no
        hay, la computable de las vacaciones truncas del cesado (o sueldo
        + asignación familiar de la boleta)."""
        self.ensure_one()
        if self.l10n_pe_indemnity_base:
            return self.l10n_pe_indemnity_base
        vacation = self.liquidation_id.vacation_line_ids.filtered(
            lambda line: line.employee_id == self.employee_id)[:1]
        if vacation:
            return vacation.computable_remuneration
        param = self.env['hr.main.parameter'].get_main_parameter(
            self.company_id)
        slip = self.liquidation_id.payslip_run_id.slip_ids.filtered(
            lambda slip: slip.employee_id == self.employee_id)[:1]
        household_allowance = sum(slip.line_ids.filtered(
            lambda line: line.salary_rule_id
            == param.household_allowance_sr_id).mapped('total'))
        return self.version_id.wage + household_allowance

    def _l10n_pe_compute_indemnity(self):
        """Indemnización por despido arbitrario (D.S. 003-97-TR, arts. 38
        y 76; pequeña y microempresa: TUO de la Ley MYPE, D.S.
        013-2013-PRODUCE)."""
        self.ensure_one()
        if self.l10n_pe_cessation_reason != 'arbitrary' \
                or not self.cessation_date:
            return 0.0
        base = self._l10n_pe_indemnity_base()
        after_cessation = self.cessation_date + relativedelta(days=1)
        service = relativedelta(after_cessation, self.admission_date) \
            if self.admission_date else relativedelta()
        # Fracciones de año por dozavos y treintavos.
        years = service.years + service.months / 12 + service.days / 360
        regime = self.version_id.l10n_pe_labor_regime
        if regime in ('small', 'micro'):
            per_year, cap = (20, 120) if regime == 'small' else (10, 90)
            daily = base / 30
            return custom_round(min(daily * per_year * years, daily * cap), 2)
        if self.l10n_pe_contract_kind == 'fixed':
            if not self.l10n_pe_planned_end \
                    or self.l10n_pe_planned_end < after_cessation:
                return 0.0
            rest = relativedelta(
                self.l10n_pe_planned_end + relativedelta(days=1),
                after_cessation)
            months = rest.years * 12 + rest.months + rest.days / 30
            return custom_round(min(1.5 * base * months, 12 * base), 2)
        return custom_round(min(1.5 * base * years, 12 * base), 2)

    def action_compute_indemnity(self):
        """Calcula la indemnización por despido arbitrario y la deja en el
        concepto INDEM del cesado (reemplaza el que hubiera)."""
        self.ensure_one()
        ensure_line_draft(self, 'liquidation_id')
        rule = self.env.ref('al_hr_pe.salary_rule_INDEM')
        amount = self._l10n_pe_compute_indemnity()
        self.conceptos_lines.filtered(
            lambda line: line.name_input_id == rule).unlink()
        if amount:
            self.conceptos_lines = [(0, 0, {
                'name_input_id': rule.id, 'amount': amount, 'type': 'in'})]
        self.l10n_pe_indemnity = amount
        return self.action_add_concepts()

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
        'hr.salary.rule', domain=[('input_usage_payslip', '=', True)], string='Concepto')
    amount = fields.Float(string='Importe')
    type = fields.Selection(
        selection=[('in', 'Ingreso'), ('out', 'Descuento')],
        string='Tipo', default='in')

    @api.depends('extra_concept_id', 'name_input_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = pe_join(rec.extra_concept_id.display_name, rec.name_input_id.display_name)
