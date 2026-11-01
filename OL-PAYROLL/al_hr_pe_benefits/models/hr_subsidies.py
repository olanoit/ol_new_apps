# -*- coding: utf-8 -*-
"""Subsidios EsSalud (maternidad y enfermedad).

Portado de ``hr_subsidies`` (v18). El subsidio se calcula sobre el
promedio de las remuneraciones de los 12 meses previos a la
contingencia (la remuneración afecta a EsSalud de cada mes: regla
AESSALUD en BASE, TREM en construcción civil) dividido entre 30 × nº de
meses con boleta. La enfermedad descuenta los primeros 20 días del año
calendario a cargo del empleador (días naturales de las suspensiones
T21 «20» y «21» del año anteriores al tramo); la maternidad se
subsidia completa. El total se reparte por periodo
(`hr.subsidies.periodo`) con estados ``not payed``/``paid out`` y se
importa a la boleta mensual vía ``import_subsidies``.

Cambios v19:

* ``hr.contract`` → ``hr.version`` (situación de baja =
  ``situation_code == '0'`` de la versión vigente).
* Fuente de contingencias: v18 leía ``hr.leave.work_suspension_id``;
  ese override no existe aún, así que el lote se alimenta de las
  suspensiones ``hr.work.suspension`` (``al_hr_pe``) con código T21
  '21' (enfermedad) o '22' (maternidad) que inician en el periodo.
  # TODO(fase4-revisar): al integrar hr_payroll_holidays, alimentar
  # desde hr.leave validados (fechas completas de la contingencia).
* Sin SQL ``.format()``: histórico salarial y acumulado DMED por ORM.
* El corte v18 del histórico conservaba el día del mes (excluía la
  boleta del mes anterior si la contingencia iniciaba a mitad de mes);
  aquí se normaliza a meses completos: 12 meses cerrados previos.
* Los campos de configuración (``vacation_sr_id``, ``otros_sr_ids``,
  ``lack_sr_ids``, ``maternidad_input_id``, ``enfermedad_input_id``)
  los añade ``hr_benefits_engine`` a `hr.main.parameter`; aquí se leen
  con ``getattr`` con guard.
* Reportes PDF/Excel de subsidios quedan para la Fase 7.
"""
import calendar
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.addons.al_hr_pe.models.display_name import pe_join, pe_range
from odoo.exceptions import UserError

from odoo.addons.al_hr_pe.tools import custom_round
from .hr_benefits_engine import notify_success
from .hr_benefits_engine import compute_locked
from .hr_benefits_engine import ensure_slips_draft, ensure_state

EMPLOYER_SUSPENSION_CODE = '20'   # T21-20: primeros 20 días (empleador)
ILLNESS_SUSPENSION_CODE = '21'    # T21-21: enfermedad
MATERNITY_SUSPENSION_CODE = '22'  # T21-22: maternidad
EMPLOYER_ILLNESS_DAYS = 20        # primeros 20 días a cargo del empleador


def _check_param_config(param, requirements):
    """Valida configuración leída con ``getattr`` (los campos los añade
    ``hr_benefits_engine``; mientras no existan también cuentan como
    faltantes)."""
    missing = [label for field_name, label in requirements
               if not getattr(param, field_name, False)]
    if missing:
        raise UserError(param.env._(
            'Faltan configuraciones de subsidios en los Parámetros '
            'Principales de Nómina: %(fields)s.',
            fields=', '.join(missing)))


class HrSubsidiesLot(models.Model):
    """Lote mensual de subsidios EsSalud (maternidad / enfermedad)."""
    _name = 'hr.subsidies.lot'
    _description = 'Lote de subsidios'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'periodo_id'
    _order = 'periodo_id desc'
    _check_company_auto = True

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    periodo_id = fields.Many2one(
        'hr.period', string='Periodo', required=True, check_company=True, tracking=True)
    line_ids = fields.One2many(
        'hr.subsidies', 'subsidies_lot_id', string='Subsidios')
    state = fields.Selection(
        selection=[('draft', 'Borrador'), ('done', 'Hecho')],
        string='Estado', default='draft', tracking=True)
    subsidies_count = fields.Integer(
        compute='_compute_subsidies_count', string='N.º de subsidios')

    _unique_period = models.Constraint(
        'UNIQUE(company_id, periodo_id)',
        'Ya existe un lote de subsidios para ese periodo y compañía.')

    @api.depends('line_ids')
    def _compute_subsidies_count(self):
        for lot in self:
            lot.subsidies_count = len(lot.line_ids)

    # Botones, en el mismo orden que en la vista
    def action_process(self):
        """Genera los subsidios del periodo desde las suspensiones.

        Crea un `hr.subsidies` por cada `hr.work.suspension` de tipo
        '21' (enfermedad) o '22' (maternidad) que inicie dentro del
        periodo. Excluye empleados de baja (``situation_code == '0'``).
        Las líneas con ``preserve_record`` se mantienen entre corridas
        y sus duplicados recalculados se descartan (paridad v18).
        """
        self.ensure_one()
        ensure_state(self, 'draft')
        self.line_ids.filtered(lambda sub: not sub.preserve_record).unlink()
        suspensions = self.env['hr.work.suspension'].search([
            ('company_id', '=', self.company_id.id),
            ('suspension_type_id.code', 'in',
             (ILLNESS_SUSPENSION_CODE, MATERNITY_SUSPENSION_CODE)),
            ('date_from', '>=', self.periodo_id.date_start),
            ('date_from', '<=', self.periodo_id.date_end),
        ])
        for suspension in suspensions:
            version = suspension.version_id \
                or suspension.employee_id.version_id
            if version.situation_code == '0':
                continue
            is_maternity = \
                suspension.suspension_type_id.code == \
                MATERNITY_SUSPENSION_CODE
            self.env['hr.subsidies'].create({
                'subsidies_lot_id': self.id,
                'type': 'maternity' if is_maternity else 'illness',
                'suspension_id': suspension.id,
                'employee_id': suspension.employee_id.id,
                'date_start': suspension.date_from,
                'date_end': suspension.date_to,
            })
        preserved_employees = \
            self.line_ids.filtered('preserve_record').employee_id
        self.line_ids.filtered(
            lambda sub: not sub.preserve_record
            and sub.employee_id in preserved_employees).unlink()
        return notify_success(self.env._('Se calculó exitosamente.'))

    def action_close(self):
        """Cierra el lote: no se permite recalcular hasta reabrirlo."""
        self.write({'state': 'done'})
        return notify_success(self.env._('Se cerró exitosamente.'))

    def action_draft(self):
        """Reabre el lote a borrador para permitir recalcular."""
        self.write({'state': 'draft'})

    def action_open_subsidies(self):
        """Abre la lista de subsidios del lote."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.subsidies',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('id', 'in', self.line_ids.ids)],
            'name': self.env._('Subsidios'),
        }

    @api.depends('periodo_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = pe_join('Subsidios', rec.periodo_id.display_name)


class HrSubsidies(models.Model):
    """Subsidio individual (maternidad o enfermedad) de un empleado."""
    _name = 'hr.subsidies'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Subsidio'
    _rec_name = 'employee_id'
    _order = 'date_start desc'
    _check_company_auto = True

    subsidies_lot_id = fields.Many2one(
        'hr.subsidies.lot', string='Lote de subsidios',
        ondelete='cascade', index=True,
        check_company=True)
    company_id = fields.Many2one(
        related='subsidies_lot_id.company_id', string='Compañía',
        store=True, index=True)
    type = fields.Selection(
        selection=[('maternity', 'Subsidio por maternidad'),
                   ('illness', 'Subsidio por enfermedad')],
        string='Tipo de subsidio', required=True, default='maternity')
    # v18: leave_id (hr.leave). En v19 la contingencia viene de la
    # suspensión T21 (ver docstring del módulo).
    suspension_id = fields.Many2one(
        'hr.work.suspension', string='Suspensión (T-Registro)',
        check_company=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Trabajador', check_company=True)
    date_start = fields.Date(string='Inicio de la contingencia')
    date_end = fields.Date(string='Fin de la contingencia')
    subsidies_line_ids = fields.One2many(
        'hr.subsidies.line', 'subsidies_id',
        string='Últimos 12 meses')
    subsidies_total_ids = fields.One2many(
        'hr.subsidies.total', 'subsidies_id', string='Subsidio total')
    subsidies_periodo_ids = fields.One2many(
        'hr.subsidies.periodo', 'subsidies_id',
        string='Subsidio por periodos')
    state = fields.Selection(
        selection=[('draft', 'Borrador'), ('close', 'Hecho')],
        string='Estado', index=True, readonly=True, copy=False,
        default='draft')
    is_compute_20_days = fields.Boolean(
        string='Primeros 20 días ya cubiertos', default=False,
        help='Marcar si los primeros 20 días a cargo del empleador ya '
             'fueron cubiertos en un descanso médico anterior del año.')
    preserve_record = fields.Boolean(
        string='No recalcular',
        help='Al procesar de nuevo, la línea se conserva tal cual, con sus '
             'ajustes manuales.')

    # Botones, en el mismo orden que en la vista
    # ------------------------------------------------------------------
    # Cálculo
    # ------------------------------------------------------------------
    def action_load_information(self):
        """Trae el histórico de remuneraciones de los 12 meses previos.

        Enfermedad: si los días de incapacidad del año (suspensiones
        «20»/«21» previas + días del tramo) no superan los 20 a cargo del
        empleador y no se marcó ``is_compute_20_days``, no genera líneas
        y lo informa (paridad v18).
        """
        self.ensure_one()
        if not (self.date_start and self.date_end):
            raise UserError(self.env._(
                'Debe indicar las fechas de contingencia.'))
        param = self.env['hr.main.parameter'].get_main_parameter(
            self.company_id)
        self._check_configuration(param)
        if self.type == 'illness' and not self.is_compute_20_days:
            contingency_days = (self.date_end - self.date_start).days + 1
            history = self._l10n_pe_prior_incapacity()
            total_days = contingency_days + sum(
                days for _suspension, days in history)
            if total_days <= EMPLOYER_ILLNESS_DAYS:
                log = ''.join(
                    '%d días de %s\n'
                    % (days, suspension.display_name)
                    for suspension, days in history)
                log += '%d días de contingencia\n' % contingency_days
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'type': 'warning',
                        'sticky': True,
                        'message': self.env._(
                            'Este trabajador aún no superó los primeros '
                            '%(limit)d días para el cálculo del '
                            'subsidio:\n\n%(log)s\nTotal días = %(total)d',
                            limit=EMPLOYER_ILLNESS_DAYS, log=log,
                            total=int(total_days)),
                    },
                }
        Line = self.env['hr.subsidies.line']
        for periodo, amounts in self._get_salary_history(param).items():
            Line.create(dict(amounts, subsidies_id=self.id,
                             periodo_id=periodo.id))
        self.state = 'close'
        return notify_success(self.env._('Generación exitosa.'))

    def action_compute(self):
        """Calcula el subsidio total y su reparto por periodos.

        * Base diaria = total de remuneraciones ÷ (30 × meses con
          boleta).
        * Maternidad: se subsidian todos los días de la contingencia.
        * Enfermedad: se descuentan los primeros 20 días del año
          calendario a cargo del empleador, en días naturales: los que
          aún queden tras las suspensiones «20»/«21» del año previas al
          tramo (D.S. 009-97-SA, art. 15), salvo ``is_compute_20_days``.
        """
        self.ensure_one()
        if any(line.validation == 'paid out'
               for line in self.subsidies_periodo_ids):
            raise UserError(self.env._(
                'No puede recalcular: ya fue importado desde la planilla '
                'mensual. Primero cambie a "No pagado" los subsidios por '
                'periodo.'))
        self.subsidies_total_ids.unlink()
        self.subsidies_periodo_ids.unlink()

        amount = sum(self.subsidies_line_ids.mapped('total'))
        months_count = len(self.subsidies_line_ids)
        divider_days = 30 * months_count if months_count else 1
        total_days = (self.date_end - self.date_start).days + 1
        if self.type == 'maternity':
            subsidized_days = total_days
            date_start = self.date_start
        else:
            contingency_days = total_days
            if not self.is_compute_20_days:
                # Días de incapacidad del año antes de este tramo: los
                # tramos previos de la misma contingencia y otros
                # descansos médicos, también los del mismo mes.
                previous_days = sum(
                    days for _suspension, days
                    in self._l10n_pe_prior_incapacity())
                employer_days = max(
                    EMPLOYER_ILLNESS_DAYS - previous_days, 0)
                subsidized_days = contingency_days - employer_days
                total_days = contingency_days + previous_days
            else:
                subsidized_days = contingency_days
                total_days = contingency_days + EMPLOYER_ILLNESS_DAYS
            if subsidized_days <= 0:
                raise UserError(self.env._(
                    'El trabajador aún no supera los primeros %(limit)d '
                    'días a cargo del empleador: no hay días '
                    'subsidiados.', limit=EMPLOYER_ILLNESS_DAYS))
            date_start = self.date_end \
                - relativedelta(days=subsidized_days - 1)

        daily_amount = amount / divider_days
        self.env['hr.subsidies.total'].create({
            'subsidies_id': self.id,
            'total_rem': amount,
            'sub_dia': daily_amount,
            'days_total': total_days,
            'days': subsidized_days,
            'total_sub': custom_round(daily_amount, 2) * subsidized_days,
        })

        # Reparto mensual (paridad v18, incluidos los casos borde de
        # primer/último mes).
        if date_start.year == self.date_end.year:
            months = (self.date_end.month - date_start.month) + 1
        else:
            months = (13 - date_start.month) + self.date_end.month
        current = date_start
        Periodo = self.env['hr.subsidies.periodo']
        for count in range(1, months + 1):
            last_day = calendar.monthrange(current.year, current.month)[1]
            if count == 1 and count != months:
                period_days = last_day - date_start.day + 1
            elif count == months:
                current = self.date_end
                if count == 1:
                    # Contingencia dentro de un solo mes (enfermedad o
                    # maternidad): días entre ambas fechas, no desde el 1.
                    period_days = self.date_end.day - date_start.day + 1
                else:
                    period_days = self.date_end.day
            else:
                period_days = last_day
            # Periodo mensual: con semanas de construcción civil el mes y
            # su semana contienen la misma fecha.
            periodo = self.env['hr.period'].search([
                ('date_start', '<=', current),
                ('date_end', '>=', current),
                ('company_id', '=', self.company_id.id),
                ('period_type', '=', 'monthly'),
            ], limit=1)
            Periodo.create({
                'subsidies_id': self.id,
                'periodo_id': periodo.id,
                'days': period_days,
                'sub_dia': daily_amount,
                'total_sub': custom_round(daily_amount, 2) * period_days,
            })
            current = current + relativedelta(months=1)
        return notify_success(self.env._('Se calculó correctamente.'))

    def action_draft(self):
        """Reabre el subsidio eliminando todas las líneas calculadas."""
        self.subsidies_line_ids.unlink()
        self.subsidies_total_ids.unlink()
        self.subsidies_periodo_ids.unlink()
        self.write({'state': 'draft'})

    @api.ondelete(at_uninstall=False)
    def _unlink_if_draft(self):
        """Borrar un subsidio cerrado rompería la trazabilidad del
        descuento aplicado a la boleta y del reporte a EsSalud."""
        if any(subsidy.state != 'draft' for subsidy in self):
            raise UserError(self.env._(
                'No puede eliminar este subsidio: no está en estado '
                'borrador.'))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _check_configuration(self, param):
        """Port de ``check_maternidad_values`` v18."""
        _check_param_config(param, [
            ('basic_sr_id', 'R.S. básico'),
            ('vacation_sr_id', 'R.S. vacaciones'),
            ('household_allowance_sr_id', 'R.S. asignación familiar'),
            ('commission_sr_ids', 'R.S. comisiones'),
            ('extra_hours_sr_id', 'R.S. sobretiempo'),
            ('otros_sr_ids', 'R.S. otros ingresos'),
            ('lack_sr_ids', 'R.S. descuentos por inasistencias'),
            ('maternidad_input_id', 'Input maternidad'),
            ('enfermedad_input_id', 'Input enfermedad'),
        ])

    def _l10n_pe_contingency_start(self):
        """Inicio de la contingencia (no del tramo).

        La ausencia se parte en una suspensión por mes y cada una genera
        su subsidio, pero la base (12 meses previos) y los 20 días del
        empleador se cuentan desde el mes en que se INICIA la contingencia
        (Ley 26790, D.S. 009-97-SA): desde el tramo, el de marzo promediaba
        enero y febrero ya subsidiados. Sale de la ausencia de la
        suspensión o, si se cargó a mano, de las suspensiones contiguas
        del mismo tipo."""
        self.ensure_one()
        suspension = self.suspension_id
        if suspension.leave_id.request_date_from:
            return min(suspension.leave_id.request_date_from,
                       self.date_start)
        start = self.date_start
        Suspension = self.env['hr.work.suspension']
        seen = suspension
        while suspension and suspension.date_from:
            suspension = Suspension.search([
                ('employee_id', '=', suspension.employee_id.id),
                ('suspension_type_id', '=',
                 suspension.suspension_type_id.id),
                ('date_to', '=', suspension.date_from - relativedelta(days=1)),
                ('id', 'not in', seen.ids),
            ], limit=1)
            seen |= suspension
            if suspension.date_from:
                start = min(start, suspension.date_from)
        return start

    def _l10n_pe_prior_incapacity(self):
        """Días naturales de incapacidad del año anteriores a este tramo:
        ``[(suspensión, días)]``.

        Los 20 primeros días de incapacidad de cada año calendario los
        paga el empleador (Ley 26790, art. 12; D.S. 009-97-SA, art. 15).
        Se acumulan las suspensiones T21 «20» (descanso médico) y «21»
        (tramos previos de esta u otra contingencia) del año en que se
        inicia la contingencia, hasta el día anterior al tramo, incluidas
        las del mismo mes. Antes se sumaban los días DMED de las boletas
        cerradas de meses anteriores: eran días laborables y se perdía el
        descanso médico del mismo mes, así que un subsidio que empezaba
        tras 20 días de descanso médico en marzo salía en cero. Un día
        cubierto por dos suspensiones cuenta una vez."""
        self.ensure_one()
        year_start = date(self._l10n_pe_contingency_start().year, 1, 1)
        limit = self.date_start - relativedelta(days=1)
        suspensions = self.env['hr.work.suspension'].search([
            ('employee_id', '=', self.employee_id.id),
            ('suspension_type_id.code', 'in',
             (EMPLOYER_SUSPENSION_CODE, ILLNESS_SUSPENSION_CODE)),
            ('date_from', '<=', limit),
            ('date_to', '>=', year_start),
            ('id', '!=', self.suspension_id.id),
        ], order='date_from')
        seen = set()
        history = []
        for suspension in suspensions:
            day = max(suspension.date_from, year_start)
            days = 0
            while day <= min(suspension.date_to, limit):
                if day not in seen:
                    seen.add(day)
                    days += 1
                day += relativedelta(days=1)
            if days:
                history.append((suspension, days))
        return history

    @api.model
    def _l10n_pe_subsidy_structures(self):
        """Estructuras cuyas boletas forman la base del subsidio, con la
        regla que da la remuneración afecta a EsSalud del periodo.

        La base del subsidio es la remuneración sobre la que se aportó a
        EsSalud (Ley 26790, art. 12; D.S. 009-97-SA, art. 16): la regla
        AESSALUD ya suma lo pagado como descanso médico, licencia con goce
        y paternidad (BAS_M), que el desglose por conceptos dejaba fuera.
        ``al_hr_pe_construction`` añade la suya (TREM)."""
        return {self.env.ref('al_hr_pe.base_structure'): 'AESSALUD'}

    def _l10n_pe_subsidy_bucket(self, line, param):
        """Columna del histórico en la que se muestra una línea de boleta
        (solo informativo: el total del mes es la base afecta)."""
        rule = line.salary_rule_id
        if rule == param.basic_sr_id:
            return 'wage'
        if rule == param.vacation_sr_id:
            return 'vacation'
        if rule == param.household_allowance_sr_id:
            return 'household_allowance'
        if rule in param.commission_sr_ids:
            return 'commission'
        if rule == param.extra_hours_sr_id:
            return 'extra_hours'
        if rule in param.otros_sr_ids:
            return 'others_income'
        if rule in param.lack_sr_ids:
            return 'lacks'
        return False

    def _get_salary_history(self, param):
        """Histórico de los 12 meses cerrados previos al mes en que se
        inicia la contingencia, agrupado por periodo mensual (sustituye al
        SQL ``_get_sql_salary`` v18).

        Cada mes suma la regla afecta a EsSalud de sus boletas (ver
        ``_l10n_pe_subsidy_structures``); lo que no cae en ninguna columna
        del desglose va a «Otros afectos a EsSalud», de modo que el total
        del mes es esa base. Las boletas semanales (construcción civil) se
        agrupan en el mes en que terminan."""
        self.ensure_one()
        structures = self._l10n_pe_subsidy_structures()
        contingency_start = self._l10n_pe_contingency_start()
        start_ref = contingency_start - relativedelta(months=12)
        date_from = date(start_ref.year, start_ref.month, 1)
        end_ref = contingency_start - relativedelta(months=1)
        date_to = date(end_ref.year, end_ref.month, calendar.monthrange(
            end_ref.year, end_ref.month)[1])
        slips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('company_id', '=', self.company_id.id),
            ('struct_id', 'in', [struct.id for struct in structures]),
            ('date_to', '>=', date_from),
            ('date_to', '<=', date_to),
            # Boletas cerradas y sin quincenales (misma estructura BASE):
            # canceladas o quincenas inflarían el promedio diario.
            ('state', 'in', ('validated', 'paid')),
            ('fortnightly_id', '=', False),
        ], order='date_to')
        Period = self.env['hr.period']
        months = {}
        history = {}
        for slip in slips:
            month = (slip.date_to.year, slip.date_to.month)
            if month not in months:
                months[month] = Period.search([
                    ('company_id', '=', slip.company_id.id),
                    ('period_type', '=', 'monthly'),
                    ('date_start', '<=', slip.date_to),
                    ('date_end', '>=', slip.date_to),
                ], limit=1)
            bucket = history.setdefault(months[month], {
                'wage': 0.0, 'vacation': 0.0, 'household_allowance': 0.0,
                'commission': 0.0, 'extra_hours': 0.0,
                'others_income': 0.0, 'lacks': 0.0, 'other_affected': 0.0,
            })
            base_code = structures[slip.struct_id]
            detail = 0.0
            for line in slip.line_ids:
                if not line.total:
                    continue
                if line.code == base_code:
                    bucket['other_affected'] += line.total
                    continue
                field_name = self._l10n_pe_subsidy_bucket(line, param)
                if field_name:
                    bucket[field_name] += line.total
                    detail += -line.total if field_name == 'lacks' \
                        else line.total
            # «Otros afectos» = base afecta − lo ya desglosado.
            bucket['other_affected'] -= detail
        return history

    @api.depends('employee_id', 'type', 'date_start', 'date_end')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = pe_join(rec.employee_id.name, dict(rec._fields['type']._description_selection(rec.env)).get(rec.type), pe_range(rec.env, rec.date_start, rec.date_end))


class HrSubsidiesLine(models.Model):
    _name = 'hr.subsidies.line'
    _description = 'Línea de subsidio'
    _check_company_auto = True
    _order = 'periodo_id'

    # La cabecera (lote o liquidación) ya no está en un estado editable: la
    # vista deja la línea de solo lectura.
    l10n_pe_locked = fields.Boolean(
        string='Bloqueada', compute='_compute_l10n_pe_locked')

    @api.depends('subsidies_id.state')
    def _compute_l10n_pe_locked(self):
        compute_locked(self, {'subsidies_id': ('draft',)})

    subsidies_id = fields.Many2one(
        'hr.subsidies', string='Subsidio', ondelete='cascade',
        required=True, index=True,
        check_company=True)
    company_id = fields.Many2one(
        related='subsidies_id.company_id', string='Compañía', store=True,
        index=True)
    periodo_id = fields.Many2one('hr.period', string='Periodo', check_company=True)
    wage = fields.Float(string='Básico')
    vacation = fields.Float(string='Vacaciones')
    household_allowance = fields.Float(string='Asignación familiar')
    commission = fields.Float(string='Comisiones')
    extra_hours = fields.Float(string='Horas extras')
    others_income = fields.Float(string='Otros ingresos')
    lacks = fields.Float(string='Descuento por inasistencias')
    other_affected = fields.Float(
        string='Otros afectos a EsSalud',
        help='Resto de la remuneración afecta a EsSalud del mes que no '
             'cae en las columnas anteriores: descanso médico, licencia '
             'con goce, paternidad, feriados, jornal y bonificaciones de '
             'construcción civil… Con él, la base del mes es la '
             'remuneración sobre la que se aportó a EsSalud.')
    total = fields.Float(
        string='Base imponible', compute='_compute_total', store=True)

    @api.depends('wage', 'vacation', 'household_allowance', 'commission',
                 'extra_hours', 'others_income', 'lacks', 'other_affected')
    def _compute_total(self):
        for line in self:
            line.total = (line.wage + line.vacation
                          + line.household_allowance + line.commission
                          + line.extra_hours + line.others_income
                          - line.lacks + line.other_affected)

    @api.depends('subsidies_id', 'periodo_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = pe_join(rec.subsidies_id.display_name, rec.periodo_id.display_name)


class HrSubsidiesTotal(models.Model):
    _name = 'hr.subsidies.total'
    _description = 'Total de subsidio'
    _check_company_auto = True

    subsidies_id = fields.Many2one(
        'hr.subsidies', string='Subsidio', ondelete='cascade',
        required=True, index=True,
        check_company=True)
    company_id = fields.Many2one(
        related='subsidies_id.company_id', string='Compañía', store=True,
        index=True)
    total_rem = fields.Float(
        string='Rem. 12 meses',
        help='Suma de las bases imponibles de los 12 meses previos a la '
             'contingencia.')
    sub_dia = fields.Float(
        string='Subsidio diario',
        help='Remuneraciones ÷ (30 × meses con boleta).')
    days_total = fields.Integer(string='Días de la contingencia')
    days = fields.Integer(
        string='Días subsidiados',
        help='En enfermedad se restan los primeros 20 días del año, que '
             'paga el empleador.')
    total_sub = fields.Float(
        string='Total subsidio', help='Subsidio diario × días subsidiados.')

    @api.depends('subsidies_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = pe_join(rec.subsidies_id.display_name, 'Total')


class HrSubsidiesPeriodo(models.Model):
    _name = 'hr.subsidies.periodo'
    _description = 'Subsidio por periodo'
    _check_company_auto = True
    _order = 'periodo_id'

    subsidies_id = fields.Many2one(
        'hr.subsidies', string='Subsidio', ondelete='cascade',
        required=True, index=True,
        check_company=True)
    company_id = fields.Many2one(
        related='subsidies_id.company_id', string='Compañía', store=True,
        index=True)
    employee_id = fields.Many2one(
        related='subsidies_id.employee_id', string='Trabajador', store=True)
    periodo_id = fields.Many2one('hr.period', string='Periodo', check_company=True)
    days = fields.Integer(string='Días subsidiados')
    sub_dia = fields.Float(string='Subsidio diario')
    total_sub = fields.Float(string='Subsidio del periodo')
    validation = fields.Selection(
        selection=[('not payed', 'No pagado'), ('paid out', 'Pagado')],
        string='Pago', default='not payed')

    def turn_paid_out(self):
        self.write({'validation': 'paid out'})

    def action_set_unpaid(self):
        self.write({'validation': 'not payed'})

    @api.depends('subsidies_id', 'periodo_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = pe_join(rec.subsidies_id.display_name, rec.periodo_id.display_name)


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _set_pe_input_amount(self, input_type, amount):
        """Fija el importe de un input en la boleta, creándolo si falta
        (en v19 las líneas de input no se autogeneran como en v18).
        Helper compartido por subsidios, adelantos/préstamos y quincena.
        """
        self.ensure_one()
        line = self.input_line_ids.filtered(
            lambda inp: inp.salary_rule_id == input_type)
        if line:
            line[:1].amount = amount
        else:
            self.write({'input_line_ids': [(0, 0, {
                'salary_rule_id': input_type.id,
                'amount': amount,
            })]})

    def import_subsidies(self):
        """Vuelca los subsidios ``not payed`` del periodo de la boleta a
        los inputs de maternidad/enfermedad y los marca ``paid out``
        (solo boletas en borrador: en una cerrada no llegarían a sus
        líneas).

        Una boleta semanal (construcción civil) busca los subsidios de su
        mes y los lleva a la regla de su estructura con el mismo código
        (SMAR/SENF): el subsidio del mes se paga en la semana en que se
        importa."""
        ensure_slips_draft(self)
        log = ''
        for slip in self:
            param = self.env['hr.main.parameter'].get_main_parameter(
                slip.company_id)
            _check_param_config(param, [
                ('maternidad_input_id', 'Input maternidad'),
                ('enfermedad_input_id', 'Input enfermedad'),
            ])
            periodo = slip.payslip_run_id.periodo_id or slip.periodo_id
            if periodo:
                periodo = periodo._l10n_pe_plame_period()
            pending = self.env['hr.subsidies.periodo'].search([
                ('periodo_id', '=', periodo.id),
                ('employee_id', '=', slip.employee_id.id),
                ('company_id', '=', slip.company_id.id),
                ('validation', '=', 'not payed'),
            ])
            if not pending:
                continue
            for subsidy_type, input_field in (
                    ('maternity', 'maternidad_input_id'),
                    ('illness', 'enfermedad_input_id')):
                lines = pending.filtered(
                    lambda p: p.subsidies_id.type == subsidy_type)
                if lines:
                    input_type = getattr(param, input_field)
                    slip._set_pe_input_amount(
                        slip.struct_id.rule_ids.filtered(
                            lambda rule: rule.code == input_type.code
                            and rule.input_usage_payslip)[:1] or input_type,
                        sum(lines.mapped('total_sub')))
            pending.turn_paid_out()
            log += '%s\n' % slip.employee_id.display_name
        if log:
            return notify_success(self.env._(
                'Se importaron los subsidios de los siguientes '
                'empleados:\n%(log)s', log=log))
        return notify_success(self.env._('No se importó ningún subsidio.'))


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    def action_import_subsidies(self):
        return self.slip_ids.import_subsidies()
