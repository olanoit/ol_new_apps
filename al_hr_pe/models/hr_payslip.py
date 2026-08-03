# -*- coding: utf-8 -*-
from collections import defaultdict
from types import SimpleNamespace

from odoo import api, fields, models


class HrPayslip(models.Model):
    """Extensión peruana de la boleta.

    Snapshot: los valores que las reglas leen (RMV, asignación familiar,
    tasas AFP) se fotografían al calcular la boleta — patrón v18
    conservado a propósito (plan §6.1): una boleta de marzo debe seguir
    mostrando las tasas de marzo aunque la SBS las cambie en abril.
    ``compute='...'`` + ``store=True`` + ``readonly=False`` permite además
    el ajuste manual puntual.
    """
    _inherit = 'hr.payslip'

    periodo_id = fields.Many2one(
        'hr.period', string='Periodo', check_company=True, index=True,
        compute='_compute_periodo_id', store=True, readonly=False)
    rmv = fields.Float(
        string='R.M.V.', compute='_compute_l10n_pe_snapshot', store=True,
        readonly=False,
        help='RMV vigente al calcular la boleta (snapshot de los '
             'Parámetros Principales).')
    family_allowance = fields.Float(
        string='Asignación familiar', compute='_compute_l10n_pe_snapshot',
        store=True, readonly=False)
    membership_id = fields.Many2one(
        related='version_id.membership_id', string='Afiliación', store=True)
    l10n_pe_retirement_fund = fields.Float(
        string='% Fondo de pensiones', compute='_compute_l10n_pe_snapshot',
        store=True, readonly=False)
    l10n_pe_commission = fields.Float(
        string='% Comisión AFP', compute='_compute_l10n_pe_snapshot',
        store=True, readonly=False,
        help='Comisión según el tipo del afiliado (flujo o mixta).')
    l10n_pe_prima_insurance = fields.Float(
        string='% Prima de seguro', compute='_compute_l10n_pe_snapshot',
        store=True, readonly=False)
    l10n_pe_insurable_remuneration = fields.Float(
        string='Tope asegurable', compute='_compute_l10n_pe_snapshot',
        store=True, readonly=False)
    l10n_pe_family_allowance_ok = fields.Boolean(
        string='Tiene derecho a asignación familiar',
        compute='_compute_l10n_pe_family_allowance_ok', store=True,
        readonly=False,
        help='Se deriva de los derechohabientes del trabajador a la fecha '
             'de fin del periodo: hijos menores de 18 años, o de hasta 24 '
             'que cursen estudios superiores (Ley 25129). Snapshot: se '
             'puede ajustar a mano en un caso puntual.')

    @api.depends('employee_id', 'date_to',
                 'employee_id.l10n_pe_dependent_ids.date_end',
                 'employee_id.l10n_pe_dependent_ids.birthday',
                 'employee_id.l10n_pe_dependent_ids.is_studying')
    def _compute_l10n_pe_family_allowance_ok(self):
        for payslip in self:
            employee = payslip.employee_id
            payslip.l10n_pe_family_allowance_ok = bool(
                employee and employee._l10n_pe_has_family_allowance(
                    payslip.date_to))

    # Totales PLAME de la boleta (por categorías configuradas en data)
    worker_contributions = fields.Float(
        string='Aportes del trabajador',
        compute='_compute_l10n_pe_totals', store=True)
    net_discounts = fields.Float(
        string='Descuentos al neto',
        compute='_compute_l10n_pe_totals', store=True)
    employer_contributions = fields.Float(
        string='Aportes del empleador',
        compute='_compute_l10n_pe_totals', store=True)

    @api.depends('date_from', 'company_id')
    def _compute_periodo_id(self):
        Period = self.env['hr.period']
        for slip in self:
            if slip.periodo_id or not slip.date_from:
                slip.periodo_id = slip.periodo_id
                continue
            # El más ajustado que contenga la boleta entera: con semanas
            # y meses conviviendo, una boleta semanal cabe en ambos.
            slip.periodo_id = Period._get_period_for_payslip(
                slip.company_id, slip.date_from, slip.date_to)

    @api.depends('version_id', 'company_id', 'date_from')
    def _compute_l10n_pe_snapshot(self):
        Param = self.env['hr.main.parameter']
        for slip in self:
            param = Param.search(
                [('company_id', '=', slip.company_id.id)], limit=1)
            slip.rmv = param.rmv if param else 0.0
            slip.family_allowance = param.family_allowance if param else 0.0
            membership = slip.version_id.membership_id
            slip.l10n_pe_retirement_fund = membership.retirement_fund
            slip.l10n_pe_prima_insurance = membership.prima_insurance
            slip.l10n_pe_insurable_remuneration = \
                membership.insurable_remuneration
            if slip.version_id.l10n_pe_commission_type == 'mixed':
                slip.l10n_pe_commission = membership.mixed_commision
            else:
                slip.l10n_pe_commission = membership.fixed_commision

    def _get_localdict(self):
        """Las fórmulas PE leen ``inputs['CODIGO'].amount`` para conceptos
        opcionales (bonos, adelantos…): un input ausente vale 0 (semántica
        v18, donde todas las líneas se generaban aunque fueran cero)."""
        localdict = super()._get_localdict()
        if self.struct_id.country_id.code == 'PE':
            localdict['inputs'] = defaultdict(
                lambda: SimpleNamespace(amount=0.0, name=''),
                localdict['inputs'])
        return localdict

    def _get_worked_day_lines(self, domain=None, check_out_of_version=True):
        """Las fórmulas PE acceden por código (``worked_days['FAL']``…)
        y esperan que TODOS los conceptos peruanos tengan línea aunque
        valgan cero (patrón is_automatic del v18): se completan las que
        el motor nativo no generó."""
        res = super()._get_worked_day_lines(
            domain=domain, check_out_of_version=check_out_of_version)
        if self.struct_id.country_id.code != 'PE':
            return res
        # La asistencia nativa (calendario) se remapea al concepto PE
        # DLAB: v18 pisaba el código del tipo nativo, aquí se sustituye
        # solo en la boleta peruana sin tocar datos de otros países.
        attendance = self.env.ref(
            'hr_work_entry.work_entry_type_attendance',
            raise_if_not_found=False)
        dlab = self.env.ref('al_hr_pe.wd_DLAB', raise_if_not_found=False)
        if attendance and dlab:
            for vals in res:
                if vals.get('work_entry_type_id') == attendance.id:
                    vals['work_entry_type_id'] = dlab.id
        present = {
            self.env['hr.work.entry.type'].browse(
                vals['work_entry_type_id']).code
            for vals in res if vals.get('work_entry_type_id')}
        missing = self.env['hr.work.entry.type'].search([
            ('country_id.code', '=', 'PE'), ('code', 'not in', list(present)),
        ])
        for wet in missing:
            res.append({
                'sequence': 100,
                'work_entry_type_id': wet.id,
                'number_of_days': 0.0,
                'number_of_hours': 0.0,
            })
        # DOM (días de descanso): complemento hasta los días calendario
        # del periodo. La convención peruana trabaja el mes completo
        # (DLAB + DOM + ausencias = días del mes); el motor nativo solo
        # cuenta días laborables del calendario.
        dom = self.env.ref('al_hr_pe.wd_DOM', raise_if_not_found=False)
        if dom and self.date_from and self.date_to:
            period_days = (self.date_to - self.date_from).days + 1
            other_days = sum(
                vals.get('number_of_days', 0.0) for vals in res
                if vals.get('work_entry_type_id') != dom.id)
            for vals in res:
                if vals.get('work_entry_type_id') == dom.id:
                    vals['number_of_days'] = max(
                        0.0, period_days - other_days)
        return res

    @api.depends('line_ids.total', 'line_ids.category_id')
    def _compute_l10n_pe_totals(self):
        """Totales PLAME sumando por categoría (sin códigos de regla
        hardcodeados — plan §5.2)."""
        categ = {
            'worker': self.env.ref(
                'al_hr_pe.APOR_TRA', raise_if_not_found=False),
            'net': self.env.ref(
                'al_hr_pe.DES_NET', raise_if_not_found=False),
            'employer': self.env.ref(
                'al_hr_pe.APOR_EMP', raise_if_not_found=False),
        }
        for slip in self:
            by_cat = {}
            for line in slip.line_ids:
                by_cat.setdefault(line.category_id, 0.0)
                by_cat[line.category_id] += line.total
            slip.worker_contributions = abs(by_cat.get(categ['worker'], 0.0))
            slip.net_discounts = abs(by_cat.get(categ['net'], 0.0))
            slip.employer_contributions = abs(
                by_cat.get(categ['employer'], 0.0))


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    rate = fields.Float(
        string='Sobretasa (%)',
        compute='_compute_rate',
        help='Sobretasa del concepto en porcentaje: 25 para las horas '
             'extra al 25 %, 100 para el trabajo en día de descanso. '
             'Se deriva del factor nativo del tipo de entrada de '
             'trabajo (``amount_rate``: 1.25 → 25 %). Las reglas '
             'salariales de la v18 leen este campo directamente.')

    @api.depends('work_entry_type_id.amount_rate')
    def _compute_rate(self):
        for line in self:
            factor = line.work_entry_type_id.amount_rate or 1.0
            line.rate = (factor - 1.0) * 100.0


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    periodo_id = fields.Many2one(
        'hr.period', string='Periodo', check_company=True, index=True)
    l10n_pe_plame_period_id = fields.Many2one(
        'hr.period', string='Periodo PLAME',
        compute='_compute_l10n_pe_plame_period_id', store=True,
        help='Mes con el que se declara. La PLAME va por mes; los lotes '
             'semanales de construcción civil se declaran en el mes del '
             'que cuelga su periodo.')

    @api.depends('periodo_id', 'periodo_id.parent_id')
    def _compute_l10n_pe_plame_period_id(self):
        for run in self:
            run.l10n_pe_plame_period_id = (
                run.periodo_id._l10n_pe_plame_period()
                if run.periodo_id else False)

    def get_period(self):
        self.ensure_one()
        if not self.periodo_id:
            from odoo.exceptions import UserError
            raise UserError(self.env._(
                'El lote no tiene periodo asignado.'))
        return self.periodo_id

    def _l10n_pe_plame_slips(self):
        """Boletas que entran en la PLAME de este lote.

        Si el lote es semanal, la declaración es del **mes entero**: se
        toman las boletas de todas las semanas de ese mes, no solo las
        del lote. Declarar una semana suelta dejaría fuera el resto del
        periodo que SUNAT espera en un único envío.
        """
        self.ensure_one()
        month = self.l10n_pe_plame_period_id
        if not month or month == self.periodo_id:
            return self.slip_ids
        periods = month | month.child_ids
        return self.env['hr.payslip'].search([
            ('periodo_id', 'in', periods.ids),
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ('validated', 'paid')),
        ])
