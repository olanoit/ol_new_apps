# -*- coding: utf-8 -*-
"""Motor de cálculo de la boleta de construcción civil.

Las reglas salariales no calculan a mano: piden los importes a estos
helpers, que aplican el redondeo del convenio —**una sola vez sobre el
importe del periodo**, no multiplicando el diario redondeado por los
días—. Ver §2.7 del análisis: en el oficial, seis céntimos por semana
separan un camino del otro, y en el operario ambos coinciden por
casualidad.

El jornal se fotografía al calcular la boleta, como el resto de
snapshots peruanos (RMV, tasas AFP): una boleta de marzo tiene que seguir
mostrando el jornal de marzo aunque en abril entre un convenio nuevo.
"""
from odoo import api, fields, models

from odoo.addons.al_hr_pe.tools import custom_round

from .hr_construction_masters import round_percent

#: Códigos de los conceptos de días que cuentan como jornada pagada.
#: El D.S.O. se calcula aparte: no es un día trabajado, es el descanso
#: que genera trabajar seis.
WORKED_DAY_CODES = ('DLAB', 'FER', 'DVAC', 'DMED', 'DPAT', 'LCGH')


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    l10n_pe_is_construction = fields.Boolean(
        related='version_id.l10n_pe_is_construction', store=True)
    l10n_pe_daily_wage = fields.Float(
        string='Jornal básico', digits='Payroll',
        compute='_compute_l10n_pe_construction_snapshot', store=True,
        readonly=False,
        help='Jornal del convenio vigente a la fecha de la boleta. '
             'Snapshot: se congela al calcular para que una boleta '
             'antigua no cambie cuando entre el convenio siguiente.')
    l10n_pe_wage_line_id = fields.Many2one(
        'l10n_pe.hr.construction.wage.line', string='Línea del convenio',
        compute='_compute_l10n_pe_construction_snapshot', store=True,
        readonly=False)
    l10n_pe_construction_category_id = fields.Many2one(
        related='version_id.l10n_pe_construction_category_id', store=True)

    @api.depends('version_id', 'date_to',
                 'version_id.l10n_pe_construction_category_id')
    def _compute_l10n_pe_construction_snapshot(self):
        for payslip in self:
            version = payslip.version_id
            line = payslip.env['l10n_pe.hr.construction.wage.line']
            if version and version.l10n_pe_is_construction:
                line = version._l10n_pe_get_wage_line(payslip.date_to)
            payslip.l10n_pe_wage_line_id = line
            payslip.l10n_pe_daily_wage = line.daily_wage if line else 0.0

    def _voucher_extra_hour_types(self, param, wd_types):
        """La boleta también cuenta como sobretiempo las extras al 60 %.

        Son propias del régimen —el general no las conoce— y sin esto
        la casilla «horas sobretiempo» saldría en cero aunque el importe
        estuviera pagado.
        """
        types = super()._voucher_extra_hour_types(param, wd_types)
        if not param.wd_ext:
            he60 = self.env.ref('al_hr_pe_construction.wd_HE60',
                                raise_if_not_found=False)
            if he60:
                types |= he60
        return types

    # ------------------------------------------------------------------
    # Días y horas del periodo
    # ------------------------------------------------------------------
    def _l10n_pe_construction_days(self):
        """Días efectivamente pagados en el periodo."""
        self.ensure_one()
        lines = self.worked_days_line_ids.filtered(
            lambda wd: wd.work_entry_type_id.code in WORKED_DAY_CODES)
        return sum(lines.mapped('number_of_days'))

    def _l10n_pe_construction_hours(self, code):
        """Horas de un concepto de sobretiempo."""
        self.ensure_one()
        lines = self.worked_days_line_ids.filtered(
            lambda wd: wd.work_entry_type_id.code == code)
        return sum(lines.mapped('number_of_hours'))

    # ------------------------------------------------------------------
    # Importes del convenio
    # ------------------------------------------------------------------
    def _l10n_pe_construction_amount(self, concept, days=None):
        """Importe de un concepto del convenio para el periodo.

        `concept` es una de las claves de ``_period_amounts``: jornal,
        dso, buc, movilidad, indemnizacion o vacaciones.
        """
        self.ensure_one()
        line = self.l10n_pe_wage_line_id
        if not line:
            return 0.0
        days = self._l10n_pe_construction_days() if days is None else days
        if not days:
            return 0.0
        # El snapshot manda sobre la tabla: si el usuario ajustó el jornal
        # de esta boleta a mano, el cálculo debe seguirlo.
        if self.l10n_pe_daily_wage and self.l10n_pe_daily_wage != line.daily_wage:
            line = line.new({
                'daily_wage': self.l10n_pe_daily_wage,
                'mobility_amount': line.mobility_amount,
                'buc_percent': line.buc_percent,
                'category_id': line.category_id.id,
            })
        return line._period_amounts(days).get(concept, 0.0)

    def _l10n_pe_construction_overtime(self, code, rate):
        """Sobretiempo: horas × valor hora × sobretasa.

        La sobretasa se aplica al valor hora **sin redondear** (jornal ÷ 8):
        con 89.30 la hora es 11.1625 y el 100 % son 22.33, no 22.32.
        """
        self.ensure_one()
        hours = self._l10n_pe_construction_hours(code)
        if not hours or not self.l10n_pe_daily_wage:
            return 0.0
        return custom_round(hours * (self.l10n_pe_daily_wage / 8.0) * rate)

    # ------------------------------------------------------------------
    # Beneficios que en este régimen se pagan con la planilla
    # ------------------------------------------------------------------
    def _l10n_pe_construction_overtime_simple(self):
        """Horas extras valuadas a hora simple.

        Es la base con la que entran en la indemnización: la tabla da
        1.67 por hora extra en el operario, que es el 15 % de 11.16 —el
        valor hora simple—, no de la hora ya recargada.
        """
        self.ensure_one()
        hours = (self._l10n_pe_construction_hours('HE60')
                 + self._l10n_pe_construction_hours('HE100'))
        if not hours or not self.l10n_pe_daily_wage:
            return 0.0
        return hours * (self.l10n_pe_daily_wage / 8.0)

    def _l10n_pe_construction_cts(self):
        """Indemnización 15 %: la CTS de este régimen, pagada en planilla.

        Base: el jornal del periodo más las horas extras a valor simple.
        """
        self.ensure_one()
        line = self.l10n_pe_wage_line_id
        if not line:
            return 0.0
        base = (self.l10n_pe_daily_wage * self._l10n_pe_construction_days()
                + self._l10n_pe_construction_overtime_simple())
        return round_percent(base, 15)

    def _l10n_pe_construction_accrual_days(self):
        """Días con los que se devengan gratificación y asignación escolar.

        La tabla del convenio los multiplica por **7** cuando el jornal va
        por 6: el devengo corre por días calendario, incluido el descanso
        que genera la semana trabajada. Se mantiene la proporción para
        semanas incompletas, que es lo coherente con un vínculo por obra
        donde se paga lo trabajado.
        """
        self.ensure_one()
        return self._l10n_pe_construction_days() * 7.0 / 6.0

    def _l10n_pe_construction_gratification(self):
        """Gratificación proporcional: 40 jornales al año, por devengo.

        Las dos valen lo mismo pero se devengan en ventanas distintas:
        Fiestas Patrias en 7 meses (enero-julio, 210 días) y Navidad en 5
        (agosto-diciembre, 150). Por eso la diaria de Navidad es mayor
        con el mismo jornal.
        """
        self.ensure_one()
        if not self.l10n_pe_daily_wage or not self.date_to:
            return 0.0
        accrual = 210.0 if self.date_to.month <= 7 else 150.0
        return custom_round(
            self.l10n_pe_daily_wage * 40.0
            * self._l10n_pe_construction_accrual_days() / accrual)

    def _l10n_pe_construction_extra_bonus(self):
        """Bonificación extraordinaria de la Ley 30334.

        La gratificación no paga ONP/AFP, y el 9 % que el empleador se
        ahorra en EsSalud se entrega al trabajador.
        """
        self.ensure_one()
        return round_percent(
            self._l10n_pe_construction_gratification(),
            self.company_id.l10n_pe_construction_grat_bonus_rate)

    def _l10n_pe_construction_school(self):
        """Asignación escolar: 30 jornales al año por cada hijo con derecho."""
        self.ensure_one()
        if not self.l10n_pe_daily_wage or not self.date_to:
            return 0.0
        company = self.company_id
        children = self.employee_id.sudo().l10n_pe_dependent_ids.filtered(
            lambda dependent: dependent._is_family_allowance_source(
                self.date_to,
                age_limit=company.l10n_pe_construction_school_age,
                studying_limit=company.l10n_pe_construction_school_age_study))
        if not children:
            return 0.0
        return custom_round(
            self.l10n_pe_daily_wage * 30.0 / 360.0
            * self._l10n_pe_construction_accrual_days() * len(children))

    # ------------------------------------------------------------------
    # CONAFOVICER
    # ------------------------------------------------------------------
    def _l10n_pe_construction_conafovicer_base(self):
        """Base del CONAFOVICER: jornal básico **más el dominical**.

        Las fuentes secundarias dicen «2 % del jornal básico», pero la
        tabla del convenio lo desmiente: el operario retiene 12.50 a la
        semana y el 2 % de 535.80 son 10.72. Con el D.S.O. dentro,
        (535.80 + 89.30) × 2 % = 12.50, y cuadra igual en oficial (9.77)
        y peón (8.79).
        """
        self.ensure_one()
        return (self._l10n_pe_construction_amount('jornal')
                + self._l10n_pe_construction_amount('dso'))

    def _l10n_pe_construction_conafovicer(self):
        """Retención para el CONAFOVICER (D.L. 21067)."""
        self.ensure_one()
        return round_percent(
            self._l10n_pe_construction_conafovicer_base(),
            self.company_id.l10n_pe_conafovicer_rate)

    # ------------------------------------------------------------------
    # Aportes del empleador
    # ------------------------------------------------------------------
    def _l10n_pe_construction_employer_rate(self, field_name, base):
        """Aporte del empleador sobre la remuneración computable.

        La base llega por parámetro —desde el `TREM` del localdict— y no
        se lee de ``line_ids``: durante el cálculo las líneas todavía no
        existen, así que buscarlas ahí devolvería siempre cero.

        Que la base sea jornal + D.S.O. + BUC lo confirman los descuentos
        de la tabla: el operario aporta 103.55 de ONP, el 13 % de 796.56.
        """
        self.ensure_one()
        rate = self.company_id[field_name]
        if not rate or not base:
            return 0.0
        return round_percent(base, rate)

    def _l10n_pe_construction_sctr(self, coverage, base):
        """SCTR: solo si el trabajador tiene esa cobertura marcada.

        Es un seguro por actividad de riesgo, no un aporte general: se
        paga por quien está expuesto, no por toda la planilla.
        """
        self.ensure_one()
        version = self.version_id
        covered = (version.l10n_pe_sctr_pension if coverage == 'pension'
                   else version.l10n_pe_sctr_health)
        if not covered:
            return 0.0
        return self._l10n_pe_construction_employer_rate(
            'l10n_pe_sctr_%s_rate' % coverage, base)

    def _l10n_pe_construction_bonus(self, code, days=None):
        """Importe de una bonificación del catálogo en el periodo.

        Suma las bonificaciones enlazadas a la regla `code` que le
        corresponden al trabajador: las del puesto, las de la obra y su
        BAE. Así, añadir una bonificación nueva al convenio es crear un
        registro de catálogo y apuntarlo a la regla, sin tocar código.
        """
        self.ensure_one()
        version = self.version_id
        if not version or not self.l10n_pe_daily_wage:
            return 0.0
        days = self._l10n_pe_construction_days() if days is None else days
        if not days:
            return 0.0
        bonuses = version._l10n_pe_construction_bonuses().filtered(
            lambda b: b.salary_rule_code == code)
        total = 0.0
        for bonus in bonuses:
            if bonus.computation == 'fixed':
                total += (bonus.amount or 0.0) * days
            else:
                # Porcentaje sobre el jornal del periodo, redondeando una
                # sola vez, igual que el BUC.
                total += round_percent(self.l10n_pe_daily_wage * days,
                                       bonus.percent or 0.0)
        return custom_round(total)
