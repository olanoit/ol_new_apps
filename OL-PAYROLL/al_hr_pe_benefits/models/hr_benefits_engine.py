# -*- coding: utf-8 -*-
"""Motor de cálculo de beneficios sociales (CTS y gratificación).

Portado de ``hr_social_benefits/models/hr_main_parameter.py`` (v18) con
paridad de fórmulas:

* Remuneración computable = sueldo + asignación familiar (10 % RMV vía
  ``family_allowance``) + promedios de variables (regla de las 3
  apariciones en 6 meses) + 1/6 de gratificación (solo CTS).
* CTS: computable/12 por mes (÷24 pequeña empresa); semestres tipo
  '11' (may-oct, depósito noviembre) y '05' (nov-abr, depósito mayo).
* Gratificación: computable/6 por mes (÷12 pequeña empresa); tipos
  '07' (Fiestas Patrias) y '12' (Navidad); bono extraordinario
  EsSalud = total × % del seguro de la versión (Ley 30334).

El motor queda preparado para la liquidación de cese (Fase 4): las
ramas ``liquidation`` se conservan y sólo se ejecutan cuando se pasa
el registro de liquidación (el modelo ``hr.liquidation`` llega en la
Fase 4 junto con el campo ``liquidation_id`` de las líneas).
"""
import calendar
from collections import Counter
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_hr_pe.tools import custom_round


def notify_success(message):
    """Notificación de éxito (sustituye al popup.it del v18)."""
    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {'type': 'success', 'message': message, 'sticky': False},
    }


def ensure_draft(records):
    """Bloquea recalcular o exportar un registro de BBSS ya exportado.

    La vista oculta los botones, pero la regla vive en el servidor: un
    recálculo tras exportar dejaría la boleta con importes distintos de
    los del registro. Para rehacerlo hay que volver a borrador.
    """
    closed = records.filtered(lambda record: record.state != 'draft')
    if closed:
        raise UserError(records.env._(
            '%(name)s ya está exportado: vuelva a borrador para '
            'recalcularlo o exportarlo de nuevo.',
            name=', '.join(
                record.display_name or record._description
                for record in closed)))


def ensure_state(records, *states):
    """Los botones se ocultan por estado, pero la regla vive en el
    servidor: por RPC se podía reprocesar o reexportar un registro
    cerrado."""
    wrong = records.filtered(lambda record: record.state not in states)
    if wrong:
        raise UserError(records.env._(
            'La operación no está permitida en el estado actual de '
            '%(names)s.', names=', '.join(
                record.display_name or record._description
                for record in wrong)))


def ensure_line_draft(lines, *header_fields):
    """``ensure_draft`` sobre la cabecera (lote o liquidación) de cada
    línea."""
    # Cada campo apunta a un modelo distinto (hr.cts, hr.liquidation…):
    # se valida por separado, no se pueden unir recordsets de modelos
    # distintos.
    for field_name in header_fields:
        headers = lines.mapped(field_name)
        if headers:
            ensure_draft(headers)



def employee_lot_slip(lot, employee):
    """Boleta del trabajador en el lote a la que se exportan los importes.

    Odoo 20 genera una boleta por versión: con un cambio de versión en el
    mes el trabajador tiene varias en el lote. Los importes van a una sola
    (la de la versión vigente al cierre, la de fecha final más reciente);
    escribirlos en todas los pagaba dos veces.
    """
    slips = lot.slip_ids.filtered(
        lambda slip: slip.employee_id == employee and slip.state != 'cancel')
    return slips.sorted(lambda slip: (slip.date_to, slip.id))[-1:]


def ensure_slips_draft(slips):
    """Solo se exporta a boletas en borrador.

    Odoo 20 no recalcula una boleta validada o pagada: el input cambiaría
    sin llegar a sus líneas y el registro quedaría «exportado» con un
    importe que la boleta no refleja.
    """
    closed = slips.filtered(lambda slip: slip.state != 'draft')
    if closed:
        raise UserError(slips.env._(
            'Solo se puede exportar a boletas en borrador. Vuelva a '
            'borrador estas boletas: %(slips)s.',
            slips=', '.join(closed.mapped('display_name'))))


def recompute_slips(slips):
    """Recalcula las boletas a las que se exportó para que sus líneas
    reflejen los inputs nuevos."""
    slips.filtered(lambda slip: slip.state == 'draft').compute_sheet()


def compute_locked(lines, rules):
    """``l10n_pe_locked`` de las líneas: la cabecera ya no se edita.

    ``rules`` es ``{campo_cabecera: estados_editables}``; con varias
    cabeceras (lote o liquidación) basta una cerrada para bloquear.
    """
    for line in lines:
        line.l10n_pe_locked = any(
            line[field] and line[field].state not in editable
            for field, editable in rules.items())


def compute_has_history(lines, date_getter):
    """``l10n_pe_has_history``: el botón «Detalle histórico» rehace el
    detalle con las boletas BASE de los 6 meses previos; sin boletas no hay
    nada que mostrar. Una consulta por (compañía, fecha de cálculo)."""
    Param = lines.env['hr.main.parameter']
    groups = {}
    for line in lines:
        key = (line.company_id, date_getter(line))
        groups[key] = groups.get(key, lines.browse()) | line
    for (company, date_calculate), group in groups.items():
        employee_ids = Param._l10n_pe_history_employee_ids(
            company, date_calculate, group.employee_id) if date_calculate else set()
        for line in group:
            line.l10n_pe_has_history = line.employee_id.id in employee_ids

class HrBenefitsLineMixin(models.AbstractModel):
    """Chatter de las líneas de beneficios.

    Las líneas se crean en bloque al calcular el lote (una por trabajador):
    sin nota «creado» ni seguidores para no llenar el historial; el chatter
    registra solo los cambios a mano de los campos con ``tracking``.
    """
    _name = 'hr.benefits.line.mixin'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Chatter de las líneas de beneficios'

    @api.model_create_multi
    def create(self, vals_list):
        lines = super(HrBenefitsLineMixin, self.with_context(
            mail_create_nolog=True, mail_create_nosubscribe=True,
        )).create(vals_list)
        return lines.with_env(self.env)


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_pe_commission_principal = fields.Boolean(
        string='Comisión como remuneración principal',
        tracking=True, groups='hr.group_hr_user',
        help='Marque si la comisión es la remuneración principal del '
             'trabajador (comisionista). En la gratificación, la CTS y las '
             'truncas su comisión se promedia en los 6 meses aunque no la '
             'haya cobrado en 3 de ellos (remuneración principal '
             'imprecisa, D.S. 001-97-TR art. 17). Sin marcar, la comisión '
             'solo promedia si se percibió en al menos 3 meses del '
             'semestre.')


class HrMainParameter(models.Model):
    _inherit = 'hr.main.parameter'

    # --- Gratificación (nombres v18 conservados) ---
    gratification_input_id = fields.Many2one(
        'hr.salary.rule', domain=[('input_usage_payslip', '=', True)], string='Input gratificación')
    bonus_nine_input_id = fields.Many2one(
        'hr.salary.rule', domain=[('input_usage_payslip', '=', True)], string='Input bonificación 9 %')
    trainee_subsidy_input_id = fields.Many2one(
        'hr.salary.rule', domain=[('input_usage_payslip', '=', True)],
        string='Input media subvención (practicantes)',
        help='Input por el que se paga la subvención adicional de los '
             'practicantes (media subvención cada 6 meses de convenio, Ley '
             '28518 art. 47). Vacío: se usa la regla «Subvención adicional '
             '(practicantes)» (SUBV_AD), sin aportes.')
    bonus_sr_ids = fields.Many2many(
        'hr.salary.rule', 'sr_bonus_main_parameter_rel',
        'main_parameter_id', 'sr_id',
        string='R.S. bonificaciones regulares',
        help='Reglas cuyos importes promedian como bonificación variable '
             '(regla de las 3 apariciones en el semestre).')
    commission_sr_ids = fields.Many2many(
        'hr.salary.rule', 'sr_commission_main_parameter_rel',
        'main_parameter_id', 'sr_id', string='R.S. comisiones')
    extra_hours_sr_id = fields.Many2one(
        'hr.salary.rule', string='R.S. sobretiempo')
    basic_sr_id = fields.Many2one(
        'hr.salary.rule', string='R.S. básico')
    household_allowance_sr_id = fields.Many2one(
        'hr.salary.rule', string='R.S. asignación familiar')
    lack_wd_ids = fields.Many2many(
        'hr.work.entry.type', 'sr_lack_main_parameter_rel',
        'main_parameter_id', 'sr_id', string='W.D. faltas',
        help='Tipos de día que son faltas: el mes sigue completo y cada día '
             'descuenta 1/30 del importe mensual de la CTS o la '
             'gratificación. Por defecto: FAL.')
    working_wd_ids = fields.Many2many(
        'hr.work.entry.type', 'sr_working_main_parameter_rel',
        'main_parameter_id', 'sr_id',
        string='W.D. días laborados (beneficios)',
        help='Tipos de día que computan como laborados para la CTS y la '
             'gratificación. Incluya las vacaciones, la licencia con goce, '
             'la paternidad y la maternidad subsidiada (Ley 27735 art. 7, '
             'D.S. 001-97-TR art. 8): si faltan, ese mes deja de contar. Por '
             'defecto: DLAB, DOM, DVAC, LCGH, DPAT y SMAR.')

    # --- CTS ---
    cts_input_id = fields.Many2one(
        'hr.salary.rule', domain=[('input_usage_payslip', '=', True)], string='Input CTS')
    medical_rest_wd_ids = fields.Many2many(
        'hr.work.entry.type', 'wd_medical_rest_parameter_rel',
        'main_parameter_id', 'wd_id', string='W.D. descanso médico',
        help='Tipos de día de descanso médico: computan como laborados (en '
             'la CTS hasta 60 días por año; el exceso se descuenta). Por '
             'defecto: DMED y SENF.')
    employee_in_charge_id = fields.Many2one(
        'hr.employee', string='Encargado liquidación semestral',
        check_company=True)
    compute_af_vac = fields.Boolean(
        string='Calcular asignación familiar en vacaciones', default=True,
        help='Incluir la asignación familiar en la remuneración computable '
             'del saldo de vacaciones (importe de los días pendientes). No '
             'afecta al goce: en el mes de vacaciones la asignación familiar '
             'ya la paga su propia regla de la boleta.')

    # --- Liquidación de cese (Fase 4) ---
    truncated_gratification_input_id = fields.Many2one(
        'hr.salary.rule', domain=[('input_usage_payslip', '=', True)], string='Input gratificación trunca')
    truncated_bonus_nine_input_id = fields.Many2one(
        'hr.salary.rule', domain=[('input_usage_payslip', '=', True)], string='Input bonificación 9 % trunca')
    truncated_cts_input_id = fields.Many2one(
        'hr.salary.rule', domain=[('input_usage_payslip', '=', True)], string='Input CTS trunca')
    vacation_input_id = fields.Many2one(
        'hr.salary.rule', domain=[('input_usage_payslip', '=', True)], string='Input vacaciones devengadas')
    truncated_vacation_input_id = fields.Many2one(
        'hr.salary.rule', domain=[('input_usage_payslip', '=', True)], string='Input vacaciones truncas')

    # --- Subsidios EsSalud (Fase 4) ---
    vacation_sr_id = fields.Many2one(
        'hr.salary.rule', string='R.S. vacaciones')
    otros_sr_ids = fields.Many2many(
        'hr.salary.rule', 'sr_otros_main_parameter_rel',
        'main_parameter_id', 'sr_id', string='R.S. otros ingresos')
    lack_sr_ids = fields.Many2many(
        'hr.salary.rule', 'lack_main_parameter_rel',
        'main_parameter_id', 'sr_id',
        string='R.S. descuentos por inasistencias')
    maternidad_input_id = fields.Many2one(
        'hr.salary.rule', domain=[('input_usage_payslip', '=', True)], string='Input maternidad')
    enfermedad_input_id = fields.Many2one(
        'hr.salary.rule', domain=[('input_usage_payslip', '=', True)], string='Input enfermedad')

    # --- Utilidades D.L. 892 (Fase 4) ---
    rule_total_income = fields.Many2one(
        'hr.salary.rule', string='R.S. rem. afecta a utilidades')
    wd_dtrab = fields.Many2many(
        'hr.work.entry.type', 'wd_dtrab_main_parameter_rel',
        'main_parameter_id', 'wd_id',
        string='W.D. días trabajados (utilidades)')
    wd_falt = fields.Many2many(
        'hr.work.entry.type', 'wd_falt_main_parameter_rel',
        'main_parameter_id', 'wd_id', string='W.D. faltas (utilidades)')
    hr_input_for_results = fields.Many2one(
        'hr.salary.rule', domain=[('input_usage_payslip', '=', True)], string='Input utilidades')

    # --- Adelantos/préstamos: tipos especiales BBSS + quincena ---
    grat_advance_id = fields.Many2one(
        'hr.advance.type', string='Adelanto de gratificación',
        check_company=True)
    cts_advance_id = fields.Many2one(
        'hr.advance.type', string='Adelanto de CTS', check_company=True)
    liqui_advance_id = fields.Many2one(
        'hr.advance.type', string='Adelanto de liquidación',
        check_company=True)
    vaca_advance_id = fields.Many2one(
        'hr.advance.type', string='Adelanto de vacaciones',
        check_company=True)
    quin_advance_id = fields.Many2one(
        'hr.advance.type', string='Adelanto de quincena',
        check_company=True)
    grat_loan_id = fields.Many2one(
        'hr.loan.type', string='Préstamo de gratificación',
        check_company=True)
    cts_loan_id = fields.Many2one(
        'hr.loan.type', string='Préstamo de CTS', check_company=True)
    liqui_loan_id = fields.Many2one(
        'hr.loan.type', string='Préstamo de liquidación',
        check_company=True)
    vaca_loan_id = fields.Many2one(
        'hr.loan.type', string='Préstamo de vacaciones', check_company=True)
    quin_loan_id = fields.Many2one(
        'hr.loan.type', string='Préstamo de quincena', check_company=True)

    # --- Adelanto quincenal ---
    fortnightly_input_id = fields.Many2one(
        'hr.salary.rule', domain=[('input_usage_payslip', '=', True)], string='Input quincena',
        default=lambda self: self.env.ref(
            'al_hr_pe.salary_rule_ADE_QUIN', raise_if_not_found=False))
    net_fortnightly_sr_id = fields.Many2one(
        'hr.salary.rule', string='R.S. neto quincenal',
        default=lambda self: self.env.ref(
            'al_hr_pe_benefits.rule_NETO_AQ', raise_if_not_found=False))

    # --- Criterio de cálculo de la quincena (reglas *_AQ) ---
    # Las reglas de quincena consultan estos campos: sin ellos, toda
    # regla *_AQ revienta al calcularse.
    fortnightly_type = fields.Selection(
        selection=[
            ('percentage', 'Porcentaje del sueldo'),
            ('days', 'Días efectivamente trabajados'),
        ],
        string='Modo de cálculo de la quincena',
        default='percentage',
        help='"Porcentaje del sueldo": el adelanto quincenal es una '
             'fracción fija de la remuneración (tasa de abajo). '
             '"Días efectivamente trabajados": se liquida la primera '
             'quincena con los días realmente laborados.')
    tasa = fields.Float(
        string='Tasa de la quincena',
        default=0.5,
        digits=(3, 4),
        help='Fracción del sueldo que se adelanta cuando el modo es '
             '"Porcentaje del sueldo" (0.5 = 50 %).')
    compute_af = fields.Boolean(
        string='Pagar asignación familiar en la quincena',
        default=False,
        help='Si está marcado, la asignación familiar se adelanta '
             'proporcionalmente en la boleta de quincena.')
    compute_afiliacion = fields.Boolean(
        string='Descontar aportes previsionales en la quincena',
        default=False,
        help='Si está marcado, AFP/ONP se descuentan ya en la quincena; '
             'lo habitual es descontarlos íntegros en la boleta '
             'mensual.')

    @api.model_create_multi
    def create(self, vals_list):
        # La configuración se crea sola por compañía (get_main_parameter):
        # recibe las mismas semillas que los datos del módulo.
        params = super().create(vals_list)
        params._l10n_pe_set_fortnightly_defaults()
        params._l10n_pe_set_benefit_wd_defaults()
        return params

    # Tipos de día por defecto de los beneficios (códigos de al_hr_pe).
    # Laborados: también las vacaciones, la licencia con goce, la
    # paternidad y la maternidad subsidiada, que son tiempo computable
    # (Ley 27735 art. 7, D.S. 005-2002-TR art. 3, D.S. 001-97-TR art. 8);
    # sin ellos un mes de vacaciones dejaba de contar un sexto. FER
    # (feriado laborado) no: son días que se pagan aparte y ya están en
    # DLAB/DOM, sumarlos los contaría dos veces. Faltas: FAL (la licencia
    # sin goce no es falta: el mes queda incompleto). Descanso médico:
    # DMED y SENF (computan, con el tope de 60 días en la CTS).
    _L10N_PE_BENEFIT_WD_DEFAULTS = {
        'working_wd_ids': ('DLAB', 'DOM', 'DVAC', 'LCGH', 'DPAT', 'SMAR'),
        'lack_wd_ids': ('FAL',),
        'medical_rest_wd_ids': ('DMED', 'SENF'),
    }

    def _l10n_pe_set_benefit_wd_defaults(self):
        """Siembra los tipos de día de los beneficios que estén vacíos
        (compañía nueva o migrada sin configurar); lo configurado a mano
        no se toca."""
        WorkEntryType = self.env['hr.work.entry.type'].sudo()
        for param in self or self.search([]):
            vals = {}
            for field_name, codes in \
                    self._L10N_PE_BENEFIT_WD_DEFAULTS.items():
                if param[field_name]:
                    continue
                types = WorkEntryType.search([
                    ('code', 'in', codes),
                    ('country_id.code', 'in', ('PE', False)),
                ])
                # Un código por tipo (el de Perú si hay dos con el mismo).
                by_code = {}
                for work_entry_type in types.sorted(
                        lambda wet: not wet.country_id):
                    by_code.setdefault(work_entry_type.code, work_entry_type)
                if by_code:
                    vals[field_name] = [(6, 0, [
                        wet.id for wet in by_code.values()])]
            if vals:
                param.write(vals)

    @api.model
    def _l10n_pe_set_fortnightly_defaults(self):
        """Neto quincenal (NETO_AQ) e input del mensual (ADE_QUIN) en los
        parámetros que aún no los tienen: los recibidos o, llamado desde
        los datos del módulo, todos."""
        net_rule = self.env.ref('al_hr_pe_benefits.rule_NETO_AQ',
                                raise_if_not_found=False)
        input_type = self.env.ref('al_hr_pe.salary_rule_ADE_QUIN',
                                  raise_if_not_found=False)
        for param in self or self.search([]):
            vals = {}
            if net_rule and not param.net_fortnightly_sr_id:
                vals['net_fortnightly_sr_id'] = net_rule.id
            if input_type and not param.fortnightly_input_id:
                vals['fortnightly_input_id'] = input_type.id
            if vals:
                param.write(vals)

    def check_gratification_values(self):
        self.ensure_one()
        if not (self.gratification_input_id and self.bonus_sr_ids
                and self.commission_sr_ids and self.extra_hours_sr_id
                and self.basic_sr_id and self.household_allowance_sr_id
                and self.bonus_nine_input_id and self.lack_wd_ids
                and self.working_wd_ids):
            raise UserError(self.env._(
                'Faltan configuraciones en la pestaña Beneficios sociales '
                '(Gratificación) de los Parámetros Principales.'))

    def check_cts_values(self):
        self.ensure_one()
        if not (self.cts_input_id and self.bonus_sr_ids
                and self.commission_sr_ids and self.extra_hours_sr_id
                and self.basic_sr_id and self.household_allowance_sr_id
                and self.lack_wd_ids and self.working_wd_ids):
            raise UserError(self.env._(
                'Faltan configuraciones en la pestaña Beneficios sociales '
                '(CTS) de los Parámetros Principales.'))

    def check_liquidation_values(self):
        self.ensure_one()
        if not (self.truncated_gratification_input_id
                and self.truncated_bonus_nine_input_id
                and self.truncated_cts_input_id
                and self.vacation_input_id
                and self.truncated_vacation_input_id
                and self.basic_sr_id and self.household_allowance_sr_id
                and self.commission_sr_ids and self.bonus_sr_ids
                and self.extra_hours_sr_id and self.lack_wd_ids
                and self.working_wd_ids):
            raise UserError(self.env._(
                'Faltan configuraciones en la pestaña Beneficios '
                'sociales (Liquidación) de los Parámetros Principales.'))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @api.model
    def get_first_version(self, employee, on_date=None):
        """Primer «contrato» del vínculo laboral vigente en ``on_date``
        (por defecto, el último): la versión con ``contract_date_start``
        más antigua de la cadena de contratos contiguos (v18:
        get_first_contract).

        Las versiones con el mismo inicio son un mismo contrato. Una
        renovación sin interrupción continúa el vínculo; un hueco (cese y
        reingreso) lo corta: el vínculo anterior ya se liquidó y no cuenta
        para el récord vacacional ni para los promedios."""
        versions = employee.version_ids.filtered('contract_date_start')
        if not versions:
            raise UserError(self.env._(
                'El empleado %(employee)s no tiene ninguna versión con '
                'fecha de inicio de contrato.',
                employee=employee.display_name))
        contracts = {}
        for version in versions:
            start = version.contract_date_start
            end = contracts.get(start, version.contract_date_end)
            contracts[start] = end and version.contract_date_end \
                and max(end, version.contract_date_end)
        starts = sorted(contracts)
        current = [start for start in starts
                   if not on_date or start <= on_date] or starts[:1]
        index = starts.index(current[-1])
        while index > 0:
            previous_end = contracts[starts[index - 1]]
            if not previous_end \
                    or previous_end + relativedelta(days=1) < starts[index]:
                break
            index -= 1
        first = starts[index]
        return min(versions.filtered(
            lambda version: version.contract_date_start == first),
            key=lambda version: version.date_version or first)

    @api.model
    def _count_months(self, records):
        """Meses calendario distintos de las boletas (o líneas de boleta)
        de ``records``: la regla de las 3 apariciones y el divisor del
        promedio cuentan MESES, no líneas ni boletas (dos boletas del
        mismo mes —cambio de versión, dos lotes— son un solo mes)."""
        slips = records.slip_id if records._name == 'hr.payslip.line' \
            else records
        return len({(slip.date_to.year, slip.date_to.month)
                    for slip in slips if slip.date_to})

    @api.model
    def _l10n_pe_lots_by_month(self, lots):
        """Lotes agrupados por mes calendario de ``date_end``.

        Un mes cuenta una sola vez aunque tenga varios lotes con boletas
        del trabajador (CTS o gratificación en lote aparte, segundo lote,
        liquidación): contados por lote, ese mes sumaba dos meses (una
        gratificación de 7/6)."""
        by_month = {}
        for lot in lots.sorted(lambda lot: (lot.date_end, lot.id)):
            key = (lot.date_end.year, lot.date_end.month)
            by_month[key] = by_month.get(key, lots.browse()) | lot
        return list(by_month.values())

    def _l10n_pe_family_allowance_amount(self, on_date):
        """Asignación familiar vigente a ``on_date``: 10 % de la RMV de la
        tabla «RMV» (Ley 25129), como la boleta. ``family_allowance`` del
        parámetro (RMV fija) solo es el respaldo si la tabla no cubre la
        fecha: con él, la CTS y la gratificación no cuadraban con la
        boleta al cambiar la RMV."""
        rmv = self.env['hr.rule.parameter']._l10n_pe_get_rmv(on_date)
        if rmv:
            return round(rmv * 0.10, 2)
        return self[:1].family_allowance

    @api.model
    def _l10n_pe_bonus_rate(self, version, on_date):
        """% de la bonificación extraordinaria (Ley 30334, art. 3): lo
        que el empleador aportaría al seguro social sobre la
        gratificación.

        Con seguro en la versión, su porcentaje (EsSalud 9 % o EPS
        6,75 %). Sin seguro, la boleta igual cobra EsSalud con la tasa
        del parámetro de reglas ``l10n_pe_essalud_rate`` (regla ESSALUD):
        la bonificación usa esa misma tasa en lugar de quedar en 0.
        """
        if version.social_insurance_id:
            return version.social_insurance_id.percent or 0.0
        return float(self.env['hr.rule.parameter'].sudo()
                     ._get_parameter_from_code(
                         'l10n_pe_essalud_rate', on_date,
                         raise_if_not_found=False) or 0.0)

    @api.model
    def _l10n_pe_truncated_window(self, cessation_date):
        """Ventana de los promedios de variables en las truncas: los 6
        meses previos al cese; el mes de cese solo cuenta si el cese cae
        a fin de mes (si no, la ventana termina el mes anterior).

        Criterio único para la gratificación, la CTS y las vacaciones
        truncas (antes cada una promediaba su propio semestre y daban
        promedios distintos para el mismo trabajador)."""
        last_day = calendar.monthrange(
            cessation_date.year, cessation_date.month)[1]
        if cessation_date.day == last_day:
            date_to = cessation_date
        else:
            date_to = date(cessation_date.year, cessation_date.month, 1) \
                - relativedelta(days=1)
        start = date_to - relativedelta(months=5)
        return date(start.year, start.month, 1), date_to

    def _l10n_pe_average_variables(self, slips, admission_date, date_from,
                                   principal_commission=False):
        """Promedios ``{'commission', 'bonus', 'extra_hours'}`` de las
        boletas ``slips`` (las canceladas no cuentan) con
        ``calculate_bonus``; ``months`` son los meses con boleta.

        ``principal_commission``: la comisión es la remuneración
        principal del trabajador (``l10n_pe_commission_principal`` de la
        versión) y se promedia sin la regla de las 3 apariciones (D.S.
        001-97-TR art. 17, remuneración principal imprecisa).
        """
        self.ensure_one()
        param = self
        slips = slips.filtered(lambda slip: slip.state != 'cancel')
        months = self._count_months(slips)
        lines = slips.line_ids.filtered(lambda line: line.total > 0)
        commissions = lines.filtered(
            lambda line: line.salary_rule_id in param.commission_sr_ids)
        bonus_lines = lines.filtered(
            lambda line: line.salary_rule_id in param.bonus_sr_ids)
        extra_hours_lines = lines.filtered(
            lambda line: line.salary_rule_id == param.extra_hours_sr_id)
        return {
            'commission': self.calculate_bonus(
                admission_date, date_from, months, commissions,
                principal=principal_commission),
            'bonus': self.calculate_bonus(
                admission_date, date_from, months, bonus_lines),
            'extra_hours': self.calculate_bonus(
                admission_date, date_from, months, extra_hours_lines),
            'months': months,
        }

    def _l10n_pe_truncated_variables(self, employee, cessation_date,
                                     admission_date, version=None):
        """Promedios de variables de las truncas de un cese (gratificación,
        CTS y vacaciones): boletas de los lotes de la compañía en
        ``_l10n_pe_truncated_window``, divididas entre 6 o entre los meses
        laborados si son menos (ingreso dentro de la ventana).

        Devuelve el dict de ``_l10n_pe_average_variables`` más
        ``date_from``/``date_to`` de la ventana."""
        self.ensure_one()
        date_from, date_to = self._l10n_pe_truncated_window(cessation_date)
        admission_month = date(admission_date.year, admission_date.month, 1)
        slips = self.env['hr.payslip.run'].search([
            ('date_end', '>=', date_from),
            ('date_end', '<=', date_to),
            ('company_id', '=', self.company_id.id),
        ]).slip_ids.filtered(
            lambda slip: slip.employee_id == employee
            and slip.date_to >= admission_month)
        result = self._l10n_pe_average_variables(
            slips, admission_date, date_from,
            principal_commission=bool(
                version and version.l10n_pe_commission_principal))
        result.update(date_from=date_from, date_to=date_to)
        return result

    @api.model
    def calculate_bonus(self, admission_date, date_from, months, lines,
                        principal=False):
        """Promedio de variables (regla peruana de las 3 apariciones).

        Cada código de regla cobrado en >= 3 meses distintos del semestre
        (y con >= 3 meses laborados) promedia ÷6, o ÷meses trabajados si
        el empleado ingresó después del inicio del semestre.

        ``principal``: remuneración principal imprecisa (comisionista):
        se promedia con el mismo divisor sin exigir las 3 apariciones.
        """
        total = 0.0
        for code_lines in lines.grouped('code').values():
            appearances = self._count_months(code_lines)
            if (principal and months) or (months >= 3 and appearances >= 3):
                amount = sum(code_lines.mapped('total'))
                if admission_date > date_from:
                    amount = custom_round(amount / months, 2)
                else:
                    amount = custom_round(amount / 6, 2)
                total += amount
        return total

    def _l10n_pe_month_computable_days(self, worked_days):
        """(días computables, faltas, descanso médico) de un mes.

        Las faltas (DLAB + DOM + FAL + … = días del mes) y el descanso
        médico también son días del mes: cuentan para decidir si el mes
        está completo y la falta se descuenta UNA sola vez (vía
        ``amount_per_lack``). El descanso médico computa como laborado:
        en la gratificación sin tope (Ley 27735 art. 7 y D.S. 005-2002-TR
        art. 3, días subsidiados) y en la CTS hasta 60 días al año
        (D.S. 001-97-TR art. 8; el exceso se descuenta aparte).
        """
        medical_types = self.medical_rest_wd_ids
        working_types = self.working_wd_ids - medical_types

        def total(types):
            return sum(worked_days.filtered(
                lambda line: line.work_entry_type_id in types
            ).mapped('number_of_days'))

        lacks = total(self.lack_wd_ids)
        medical = total(medical_types)
        return total(working_types) + lacks + medical, lacks, medical

    @api.model
    def calculate_excess_medical_rest(self, employee, company, date_from,
                                      date_to, slips=None):
        """(días de descanso médico del periodo, exceso sobre 60).

        El descanso médico computa para CTS hasta 60 días por año CTS
        (noviembre–octubre, D.S. 001-97-TR art. 8). El exceso del
        periodo [date_from, date_to] es lo que supera el tope contando
        lo ya consumido desde el 1 de noviembre anterior, así que el
        segundo semestre no vuelve a abonar ni a descontar los días del
        primero.
        """
        param = self.get_main_parameter(company)
        year_start = date_from if date_from.month == 11 \
            else date(date_from.year - 1, 11, 1)
        if slips is None:
            slips = self.env['hr.payslip'].search([
                ('employee_id', '=', employee.id),
                ('company_id', '=', company.id),
                ('payslip_run_id', '!=', False),
                ('state', '!=', 'cancel'),
                ('date_to', '>=', year_start),
                ('date_to', '<=', date_to),
            ])

        def medical_days(start, stop):
            return sum(slips.filtered(
                lambda slip: slip.employee_id == employee
                and start <= slip.date_to <= stop
            ).worked_days_line_ids.filtered(
                lambda line: line.work_entry_type_id
                in param.medical_rest_wd_ids
            ).mapped('number_of_days'))

        before = medical_days(year_start, date_from - relativedelta(days=1)) \
            if year_start < date_from else 0.0
        current = medical_days(date_from, date_to)
        excess = max(0.0, before + current - 60) - max(0.0, before - 60)
        return current, excess

    @api.model
    def _l10n_pe_history_window(self, date_calculate):
        """Ventana del histórico: los 6 meses completos previos al mes de
        cálculo."""
        start_ref = date_calculate - relativedelta(months=6)
        end_ref = date_calculate - relativedelta(months=1)
        return (date(start_ref.year, start_ref.month, 1),
                date(end_ref.year, end_ref.month,
                     calendar.monthrange(end_ref.year, end_ref.month)[1]))

    @api.model
    def _l10n_pe_history_employee_ids(self, company, date_calculate, employees):
        """Ids de los empleados con boletas BASE en la ventana del
        histórico (una sola consulta para todo el grupo)."""
        if not employees:
            return set()
        date_from, date_to = self._l10n_pe_history_window(date_calculate)
        groups = self.env['hr.payslip']._read_group([
            ('employee_id', 'in', employees.ids),
            ('company_id', '=', company.id),
            ('struct_id', '=', self.env.ref('al_hr_pe.base_structure').id),
            ('state', '!=', 'cancel'),
            ('date_to', '>=', date_from),
            ('date_to', '<=', date_to),
        ], ['employee_id'])
        return {employee.id for (employee,) in groups}

    @api.model
    def get_salary_history(self, employee, company, date_calculate):
        """Histórico de nómina (estructura BASE) de los 6 meses previos.

        Devuelve ``{periodo(hr.period): {bucket: importe}}`` con los
        importes agrupados por concepto según las reglas configuradas.
        Sustituye al SQL con ``.format()`` del v18 por ORM puro (regla
        de migración: sin SQL formateado).
        """
        param = self.get_main_parameter(company)
        base_struct = self.env.ref('al_hr_pe.base_structure')
        date_from, date_to = self._l10n_pe_history_window(date_calculate)
        slips = self.env['hr.payslip'].search([
            ('employee_id', '=', employee.id),
            ('company_id', '=', company.id),
            ('struct_id', '=', base_struct.id),
            # Una boleta anulada (reintegro cancelado) no es remuneración.
            ('state', '!=', 'cancel'),
            ('date_to', '>=', date_from),
            ('date_to', '<=', date_to),
        ])
        history = {}
        for slip in slips:
            bucket = history.setdefault(slip.periodo_id, {
                'wage': 0.0, 'household_allowance': 0.0, 'commission': 0.0,
                'extra_hours': 0.0, 'others_income': 0.0,
            })
            for line in slip.line_ids:
                if not line.total:
                    continue
                rule = line.salary_rule_id
                if rule == param.basic_sr_id:
                    bucket['wage'] += line.total
                elif rule == param.household_allowance_sr_id:
                    bucket['household_allowance'] += line.total
                elif rule in param.commission_sr_ids:
                    bucket['commission'] += line.total
                elif rule == param.extra_hours_sr_id:
                    bucket['extra_hours'] += line.total
                elif rule in param.bonus_sr_ids:
                    bucket['others_income'] += line.total
        return history

    # ------------------------------------------------------------------
    # Motor principal
    # ------------------------------------------------------------------
    def compute_benefits(self, record, record_type, liquidation=False):
        """Genera las líneas de CTS ('11'/'05') o gratificación
        ('07'/'12') del lote ``record``. Paridad con el v18; toda
        búsqueda filtra por la compañía del lote."""
        company = record.company_id
        year = record.year
        param = self.get_main_parameter(company)
        if record_type in ('07', '12'):
            param.check_gratification_values()
        else:
            param.check_cts_values()
        payslip_month = False
        if liquidation:
            param.check_liquidation_values()
            payslip_month = record.payslip_run_id.date_end.month

        required_gratification = {}
        if record_type == '07':
            date_from, date_to = date(year, 1, 1), date(year, 6, 30)
            month_date_from, month_date_to = \
                date(year, 6, 1), date(year, 6, 30)
        elif record_type == '12':
            if liquidation:
                date_from, date_to = date(year, 7, 1), date(year, 12, 31)
            else:
                date_from, date_to = date(year, 6, 1), date(year, 11, 30)
            month_date_from, month_date_to = \
                date(year, 12, 1), date(year, 12, 31)
        elif record_type == '11':
            date_from, date_to = date(year, 5, 1), date(year, 10, 31)
            month_date_from, month_date_to = \
                date(year, 10, 1), date(year, 10, 31)
            required_gratification = {'year': year, 'type': '07'}
        else:  # '05'
            if liquidation and payslip_month in (11, 12):
                date_from, date_to = \
                    date(year, 11, 1), date(year + 1, 4, 30)
            else:
                date_from, date_to = \
                    date(year - 1, 11, 1), date(year, 4, 30)
            month_date_from, month_date_to = \
                date(year, 4, 1), date(year, 4, 30)
            required_gratification = {'year': year - 1, 'type': '12'}

        if liquidation:
            month_lot = record.payslip_run_id
            filtered_slips = month_lot.slip_ids.filtered(
                lambda slip: slip.state != 'cancel')
            if record_type in ('05', '11'):
                filtered_slips = filtered_slips.filtered(
                    lambda slip: not slip.version_id.l10n_pe_less_than_four)
            employees = filtered_slips.filtered(
                lambda slip:
                slip.version_id.l10n_pe_labor_regime in ('general', 'small')
                and slip.version_id.situation_code == '0'
                and slip.version_id.contract_date_end
                and slip.date_from <= slip.version_id.contract_date_end
                and slip.date_to >= slip.version_id.contract_date_end
            ).employee_id
        else:
            periodo = self.env['hr.period'].search([
                ('date_start', '>=', month_date_from),
                ('date_end', '<=', month_date_to),
                ('company_id', '=', company.id),
            ], limit=1)
            if not periodo:
                raise UserError(self.env._(
                    'No existe el periodo de nómina de cierre '
                    '(%(month)s/%(year)s) para la compañía %(company)s.',
                    month=month_date_from.month, year=month_date_from.year,
                    company=company.display_name))
            month_lot = self.env['hr.payslip.run'].search([
                ('periodo_id', '=', periodo.id),
                ('company_id', '=', company.id),
            ])
            filtered_slips = month_lot.slip_ids.filtered(
                lambda slip: slip.state != 'cancel')
            if record_type in ('05', '11'):
                filtered_slips = filtered_slips.filtered(
                    lambda slip: not slip.version_id.l10n_pe_less_than_four)
            employees = filtered_slips.filtered(
                lambda slip:
                slip.version_id.l10n_pe_labor_regime in ('general', 'small')
                and slip.version_id.situation_code != '0'
            ).employee_id

        lots = self.env['hr.payslip.run'].search([
            ('date_end', '>=', date_from),
            ('date_end', '<=', date_to),
            ('company_id', '=', company.id),
        ])
        # Navidad: los días laborados se cuentan sobre jul-dic, aunque los
        # promedios de variables usan jun-nov (v18).
        lots_wd = lots
        if record_type == '12':
            lots_wd = self.env['hr.payslip.run'].search([
                ('date_end', '>=', date(year, 7, 1)),
                ('date_end', '<=', date(year, 12, 31)),
                ('company_id', '=', company.id),
            ])
        # Precarga única (evita recorrer las boletas de cada lote por
        # empleado): boletas de los lotes agrupadas por trabajador. Una
        # boleta anulada no es remuneración ni tiempo laborado.
        Payslip = self.env['hr.payslip']
        slips_by_employee = (lots | lots_wd).slip_ids.filtered(
            lambda slip: slip.employee_id in employees
            and slip.state != 'cancel'
        ).grouped('employee_id')
        # Gratificación sin días sueltos (Ley 27735: solo meses calendario
        # completos): el mes incompleto no cuenta y sus faltas tampoco se
        # descuentan.
        whole_months_only = record_type in ('07', '12') \
            and not record.months_and_days

        remaining_by_employee = {}
        if record_type in ('05', '11'):
            if record_type == '11':
                last_date = {'year': year, 'type': '05'}
            elif liquidation and payslip_month in (11, 12):
                last_date = {'year': year, 'type': '11'}
            else:
                last_date = {'year': year - 1, 'type': '11'}
            # Saldo reservado del semestre anterior (trabajador con menos
            # de un mes: su CTS pasa al depósito siguiente).
            for line in self.env['hr.cts.line'].search([
                    ('employee_id', 'in', employees.ids),
                    ('cts_id.year', '=', last_date['year']),
                    ('cts_id.type', '=', last_date['type']),
                    ('cts_id.company_id', '=', company.id),
                    ('less_than_one_month', '=', True)]):
                remaining_by_employee[line.employee_id] = \
                    remaining_by_employee.get(line.employee_id, 0.0) \
                    + line.total_cts
            # Descanso médico del año CTS (1-nov anterior → fin del
            # periodo) en una sola búsqueda.
            medical_start = date_from if date_from.month == 11 \
                else date(date_from.year - 1, 11, 1)
            medical_slips = Payslip.search([
                ('employee_id', 'in', employees.ids),
                ('company_id', '=', company.id),
                ('payslip_run_id', '!=', False),
                ('state', '!=', 'cancel'),
                ('date_to', '>=', medical_start),
                ('date_to', '<=', date_to),
            ])

        for employee in employees:
            months = days = lacks = 0
            month_slip = filtered_slips.filtered(
                lambda slip: slip.employee_id == employee)
            if len(month_slip) > 1:
                # Desambiguación v18 (contrato vigente) → versión vigente;
                # si ninguna boleta es de la versión actual (recálculo de
                # un semestre pasado), la más reciente del lote.
                current = month_slip.filtered(
                    lambda slip: slip.version_id == employee.version_id)
                month_slip = (current or month_slip).sorted('date_to')[-1:]
            version = month_slip.version_id
            admission_date = self.get_first_version(
                employee, month_slip.date_to).contract_date_start
            remaining_wage = remaining_by_employee.get(employee, 0.0)

            # Fecha de la remuneración computable: la CTS toma la de
            # octubre/abril (D.S. 001-97-TR art. 9, boleta del mes de
            # cierre) y la liquidación la del cese; la gratificación, la
            # vigente al pagarla (Ley 27735 art. 2, «en la oportunidad en
            # que corresponde otorgar el beneficio»): un aumento desde el
            # 1 de julio entra en la de Fiestas Patrias.
            remuneration_date = month_slip.date_to
            if record_type in ('07', '12') and not liquidation \
                    and record.deposit_date:
                remuneration_date = record.deposit_date
                deposit_version = employee._get_version(record.deposit_date)
                if deposit_version.contract_date_start \
                        == version.contract_date_start:
                    version = deposit_version
            wage = version.wage
            # Asignación familiar con el mismo criterio que la boleta
            # (derechohabientes por edad, Ley 25129), no el campo manual
            # ``children``, y con la RMV vigente a esa fecha (no la fija
            # del parámetro).
            household_allowance = \
                param._l10n_pe_family_allowance_amount(remuneration_date) \
                if month_slip.l10n_pe_family_allowance_ok else 0.0
            employee_all_slips = slips_by_employee.get(employee, Payslip)
            admission_payslip_date = \
                date(admission_date.year, admission_date.month, 1)
            month_limit = month_slip.date_to

            def lot_slips(lot):
                return employee_all_slips.filtered(
                    lambda slip: slip.payslip_run_id == lot
                    and admission_payslip_date <= slip.date_to <= month_limit)


            for month_lots in self._l10n_pe_lots_by_month(lots_wd):
                # Del mes vale el lote con más días computables.
                counted, lot_lacks, lot = max(
                    (param._l10n_pe_month_computable_days(
                        lot_slips(lot).worked_days_line_ids)[:2] + (lot,)
                     for lot in month_lots),
                    key=lambda item: item[0])
                complete = \
                    counted >= (lot.date_end - lot.date_start).days + 1
                if complete:
                    months += 1
                else:
                    days += counted
                if complete or not whole_months_only:
                    lacks += lot_lacks

            if record_type in ('07', '12'):
                # Sin días sueltos (Ley 27735: solo meses calendario
                # completos) se descartan ANTES de normalizar: si no, cada
                # 30 días sueltos se convertían en un mes.
                if not record.months_and_days:
                    days = 0
                if days >= 30:
                    days, months = param.get_months_of_30_days(days, months)

            # Promedios de variables: el semestre en el cálculo regular; en
            # las truncas, criterio único de los 6 meses previos al cese
            # (``_l10n_pe_truncated_variables``, el mismo de las
            # vacaciones truncas).
            if liquidation:
                averages = param._l10n_pe_truncated_variables(
                    employee, version.contract_date_end, admission_date,
                    version=version)
            else:
                averages = param._l10n_pe_average_variables(
                    employee_all_slips.filtered(
                        lambda slip: slip.payslip_run_id in lots
                        and admission_payslip_date <= slip.date_to
                        <= month_limit),
                    admission_date, date_from,
                    principal_commission=version.l10n_pe_commission_principal)
            commission = averages['commission']
            bonus = averages['bonus']
            extra_hours = averages['extra_hours']
            computable_remuneration = (wage + household_allowance
                                       + commission + bonus + extra_hours)
            divider = 6 if record_type in ('07', '12') else 12

            sixth_of_gratification = 0.0
            if record_type in ('05', '11'):
                if liquidation:
                    cessation_date = version.contract_date_end
                    grati_lines = self.env['hr.gratification.line'].search([
                        ('employee_id', '=', employee.id),
                        ('gratification_id.year', '=', year),
                        ('gratification_id.company_id', '=', company.id),
                    ]).sorted(
                        lambda line: line.gratification_id.deposit_date)
                    if len(grati_lines) == 0:
                        required_gratification = \
                            {'year': year - 1, 'type': '12'}
                    elif len(grati_lines) == 1:
                        if grati_lines.gratification_id.deposit_date \
                                <= cessation_date:
                            required_gratification = \
                                {'year': year, 'type': '07'}
                        else:
                            required_gratification = \
                                {'year': year - 1, 'type': '12'}
                    else:
                        if grati_lines[0].gratification_id.deposit_date \
                                <= cessation_date \
                                < grati_lines[1].gratification_id.deposit_date:
                            required_gratification = \
                                {'year': year, 'type': '07'}
                        if cessation_date >= \
                                grati_lines[1].gratification_id.deposit_date:
                            required_gratification = \
                                {'year': year, 'type': '12'}
                gratification_line = \
                    self.env['hr.gratification.line'].search([
                        ('employee_id', '=', employee.id),
                        ('gratification_id.year', '=',
                         required_gratification['year']),
                        ('gratification_id.type', '=',
                         required_gratification['type']),
                        ('gratification_id.company_id', '=', company.id),
                    ])
                if gratification_line:
                    sixth_of_gratification = custom_round(
                        sum(gratification_line.mapped('total_grat')) / 6, 2)
                computable_remuneration += sixth_of_gratification

            if version.l10n_pe_labor_regime == 'general':
                amount_per_month = computable_remuneration / divider
            else:
                amount_per_month = computable_remuneration / (divider * 2)
            amount_per_day = amount_per_month / 30
            vals = {
                'employee_id': employee.id,
                'version_id': version.id,
                'admission_date': admission_date,
                'months': months,
                'days': days,
                'lacks': lacks,
                'wage': wage,
                'household_allowance': household_allowance,
                'commission': commission,
                'bonus': bonus,
                'extra_hours': extra_hours,
                'computable_remuneration': computable_remuneration,
                'amount_per_month': custom_round(amount_per_month, 2),
                'amount_per_day': custom_round(amount_per_day, 2),
            }
            # TODO(fase3-revisar): distribution_id (distribución analítica
            # del contrato v18) sin equivalente en hr.version v19.

            if record_type in ('07', '12'):
                if admission_date > month_slip.date_from:
                    continue
                if liquidation:
                    vals['compute_date'] = max(admission_date, date_from)
                    vals['cessation_date'] = version.contract_date_end
                    vals['liquidation_id'] = record.id
                else:
                    vals['gratification_id'] = record.id
                # Faltas: 1/30 del sexto (1/180 de la remuneración) por
                # día. La Ley 27735 no lo regula de forma expresa; se
                # descuenta por analogía con la CTS, práctica usual
                # (decisión aprobada), solo en los meses que sí cuentan.
                amount_per_lack = amount_per_day * lacks
                grat_per_month = custom_round(amount_per_month * months, 2)
                grat_per_day = custom_round(amount_per_day * days, 2)
                total_grat = custom_round(
                    (grat_per_month + grat_per_day) - amount_per_lack, 2)
                percent = param._l10n_pe_bonus_rate(
                    version, remuneration_date) if record.with_bonus else 0.0
                bonus_essalud = custom_round(total_grat * percent * 0.01, 2)
                vals.update({
                    'amount_per_lack': custom_round(amount_per_lack, 2),
                    'grat_per_month': grat_per_month,
                    'grat_per_day': grat_per_day,
                    'total_grat': total_grat,
                    'bonus_essalud': bonus_essalud,
                    'total': custom_round(total_grat + bonus_essalud, 2),
                })
                # Trunca de cese: no se paga si el semestre ya se abonó en
                # una gratificación regular (sea cual sea su lote).
                if liquidation and self.env['hr.gratification.line'] \
                        .search_count([
                            ('employee_id', '=', employee.id),
                            ('gratification_id.year', '=', year),
                            ('gratification_id.type', '=', record_type),
                            ('gratification_id.company_id', '=',
                             company.id),
                        ], limit=1):
                    continue
                self.env['hr.gratification.line'].create(vals)
            else:
                if liquidation:
                    vals['compute_date'] = max(admission_date, date_from)
                    vals['cessation_date'] = version.contract_date_end
                    vals['liquidation_id'] = record.id
                else:
                    vals['cts_id'] = record.id
                # Los días de descanso médico ya cuentan como computables
                # mes a mes; aquí solo se descuenta lo que exceda los 60
                # días del año CTS dentro de ESTE periodo.
                _medical_days, excess_medical_rest = \
                    self.calculate_excess_medical_rest(
                        employee, company, date_from,
                        min(date_to, month_limit), slips=medical_slips)
                if days >= 30:
                    days, months = param.get_months_of_30_days(days, months)
                amount_per_lack = \
                    amount_per_day * (lacks + excess_medical_rest)
                cts_per_month = custom_round(amount_per_month * months, 2)
                cts_per_day = custom_round(amount_per_day * days, 2)
                total_cts = custom_round(
                    cts_per_month + cts_per_day - amount_per_lack
                    + remaining_wage, 2)
                exchange = record.exchange_type or 1.0
                vals.update({
                    'months': months,
                    'days': days,
                    'less_than_one_month': bool(months == 0 and days > 0),
                    'exchange_type': record.exchange_type,
                    'excess_medical_rest': excess_medical_rest,
                    'remaining_wage': remaining_wage,
                    'sixth_of_gratification': sixth_of_gratification,
                    'amount_per_lack': custom_round(amount_per_lack, 2),
                    'cts_per_month': cts_per_month,
                    'cts_per_day': cts_per_day,
                    'total_cts': total_cts,
                    'cts_soles': total_cts,
                    'cts_dollars': custom_round(total_cts / exchange, 2),
                })
                if liquidation:
                    if admission_date > month_slip.date_from:
                        continue
                    # La CTS exige al menos un mes de servicios (D.S.
                    # 001-97-TR art. 4): ingreso el 25/08 y cese el 05/09
                    # no generan CTS trunca, aunque crucen dos meses.
                    if admission_date + relativedelta(months=1) > \
                            version.contract_date_end + relativedelta(days=1):
                        continue
                    cts = self.env['hr.cts'].search([
                        ('payslip_run_id', '=',
                         liquidation.payslip_run_id.id),
                        ('year', '=', liquidation.year),
                        ('type', '=', record_type),
                        ('company_id', '=', liquidation.company_id.id),
                    ])
                    if cts and cts.line_ids.filtered(
                            lambda line: line.employee_id == employee):
                        continue
                    # Trunca de cese: no se paga si el semestre ya se
                    # depositó en una CTS regular (mismo criterio que la
                    # gratificación).
                    # En nov-dic la '05' es la del depósito de mayo
                    # siguiente.
                    deposit_year = year + 1 if record_type == '05' \
                        and payslip_month in (11, 12) else year
                    if self.env['hr.cts.line'].search_count([
                            ('employee_id', '=', employee.id),
                            ('cts_id.year', '=', deposit_year),
                            ('cts_id.type', '=', record_type),
                            ('cts_id.company_id', '=', company.id),
                    ], limit=1):
                        continue
                self.env['hr.cts.line'].create(vals)
