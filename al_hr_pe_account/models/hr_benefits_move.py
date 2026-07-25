# -*- coding: utf-8 -*-
"""Asientos contables de beneficios sociales (CTS, gratificación,
liquidación de cese y provisión mensual).

Portado de ``hr_social_benefits_move`` + ``hr_social_benefits_move_analytic``
(v18, wizards byte-idénticos y SQL crudo con ``.format()``) y de
``hr_payslip_run_move_analytic/models/hr_provisions.py``. Cambios v19:

* Todo por ORM: las líneas se construyen leyendo los registros de BBSS
  de ``al_hr_pe_benefits`` y el asiento se crea con
  ``account.move.create`` (el SQL v18 queda prohibido).
* Las cuentas ya no se localizan por código de regla salarial
  (``CTS``, ``ADE_CTS``, ``GRA_TRU``…): se configuran por compañía en
  ``hr.main.parameter`` (ver ``hr_main_parameter_accounts.py``).
* Los dos módulos v18 (con y sin analítica) se unifican en un solo
  comportamiento condicional: cuando el flag por compañía
  ``detail_analytic`` está activo, las líneas de gasto llevan el
  ``analytic_distribution`` JSON nativo de ``hr.version`` (el
  prorrateo por porcentaje que v18 hacía desdoblando líneas por
  ``hr.analytic.distribution.line`` lo resuelve el JSON en una sola
  línea).

Estructura de cada asiento (misma que v18):

* **CTS / gratificación** (1 asiento por lote): debe = reversión de la
  provisión acumulada (por trabajador, con tercero) + gasto por la
  diferencia no provisionada; haber = beneficio por pagar (por
  trabajador, con tercero).
* **Liquidación de cese** (1 asiento por cesado, ``hr.liquidation.move``):
  debe = reversión de provisiones CTS/grati/vacaciones + gasto de los
  truncos netos; haber = liquidaciones por pagar (incluye conceptos
  extra) + retenciones AFP/ONP (cuenta de la afiliación) + descuentos
  extra.
* **Provisión mensual** (1 asiento por lote): debe = gasto de cada
  concepto (CTS, gratificación, bono Ley 29351, vacaciones); haber =
  pasivo provisional por concepto, detallado por trabajador si
  ``detallar_provision`` está activo.
"""
import json
from datetime import date

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_hr_pe.tools import custom_round
from odoo.addons.al_hr_pe_benefits.models.hr_benefits_engine import \
    notify_success


def _round(amount):
    """Redondeo contable a 2 decimales (``custom_round`` del núcleo)."""
    return custom_round(amount or 0.0, 2)


def _dist_key(distribution):
    """Clave hashable para agrupar líneas por distribución analítica."""
    if not distribution:
        return False
    return json.dumps(distribution, sort_keys=True)


class HrBenefitsMoveMixin(models.AbstractModel):
    """Comportamiento común de los registros de BBSS contabilizables.

    Cada modelo concreto implementa ``_get_move_lines()`` (lista de
    dicts con ``account_id``, ``name``, ``debit``, ``credit``,
    ``partner_id`` y ``analytic_distribution``) y este mixin aporta la
    apertura del wizard, la vista del asiento y los hooks que el wizard
    usa para fechar, referenciar y colgar el ``account.move``.
    """
    _name = 'hr.benefits.move.mixin'
    _description = 'Mixin de asiento contable de BBSS'

    # Sin check_company: el mixin abstracto no tiene company_id (los
    # modelos concretos sí); la coherencia la garantiza el diario.
    account_move_id = fields.Many2one(
        'account.move', string='Asiento contable', readonly=True,
        copy=False)

    def action_open_asiento(self):
        """Abre el ``account.move`` generado para este registro."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('id', '=', self.account_move_id.id)],
            'name': self.env._('Asiento contable de BBSS'),
        }

    def _get_move_lines(self):
        raise NotImplementedError

    def _benefits_move_date_ref(self):
        """(fecha, referencia) del asiento; implementa cada modelo."""
        raise NotImplementedError

    def _register_benefits_move(self, move):
        """Cuelga el asiento recién contabilizado del registro."""
        self.ensure_one()
        self.account_move_id = move.id

    @api.model
    def _benefits_period_code(self, run):
        """Código de periodo para la glosa/ref (v18: ``periodo_id.code``
        sin guiones)."""
        if run.periodo_id.code:
            return run.periodo_id.code.replace('-', '')
        return (run.name or '').replace('-', '')

    def get_move_wizard(self):
        """Abre el wizard de generación del asiento con los totales
        precalculados (mismo flujo que los 4 wizards v18)."""
        if len(self.ids) > 1:
            raise UserError(self.env._(
                'No se puede seleccionar más de un registro para este '
                'proceso.'))
        if self.account_move_id:
            raise UserError(self.env._(
                'Elimine el asiento actual para generar uno nuevo.'))
        move_lines = self._get_move_lines()
        if not move_lines:
            raise UserError(self.env._(
                'No hay importes que contabilizar: procese el registro '
                'y obtenga las provisiones antes de generar el '
                'asiento.'))
        total_debit = sum(line['debit'] for line in move_lines)
        total_credit = sum(line['credit'] for line in move_lines)
        view = self.env.ref(
            'al_hr_pe_account.hr_benefits_move_wizard_view_form')
        return {
            'name': self.env._('Generar asiento contable'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.benefits.move.wizard',
            'views': [(view.id, 'form')],
            'context': {
                'default_debit': _round(total_debit),
                'default_credit': _round(total_credit),
                'benefits_model': self._name,
                'benefits_id': self.id,
                'move_lines': move_lines,
            },
            'target': 'new',
        }

    # ------------------------------------------------------------------
    # Helpers de construcción de líneas
    # ------------------------------------------------------------------
    @api.model
    def _employee_partner(self, employee):
        """Tercero del trabajador (v18 ``user_partner_id`` →
        v19 ``work_contact_id``)."""
        return employee.work_contact_id.id or False

    @api.model
    def _make_line(self, account, name, debit=0.0, credit=0.0,
                   partner_id=False, distribution=False):
        return {
            'account_id': account.id,
            'name': name,
            'debit': _round(debit),
            'credit': _round(credit),
            'partner_id': partner_id,
            'analytic_distribution': distribution or False,
        }

    @api.model
    def _append_expense_lines(self, move_lines, groups, account, name):
        """Vuelca los grupos de gasto acumulados por distribución
        analítica; el signo decide debe/haber (v18: ``CASE WHEN
        sum > 0 THEN debit ELSE credit``)."""
        for group in groups.values():
            amount = _round(group['amount'])
            if not amount:
                continue
            move_lines.append(self._make_line(
                account, name,
                debit=amount if amount > 0 else 0.0,
                credit=-amount if amount < 0 else 0.0,
                distribution=group['dist'],
            ))

    @api.model
    def _accumulate(self, groups, dist, amount):
        entry = groups.setdefault(
            _dist_key(dist), {'dist': dist, 'amount': 0.0})
        entry['amount'] += amount


class HrCts(models.Model):
    """Asiento contable del depósito semestral de CTS.

    Debe: reversión de la provisión acumulada del semestre (por
    trabajador) + gasto por la diferencia ``total_cts - provisión``
    (con distribución analítica si aplica). Haber: CTS por pagar
    (``cts_soles``, por trabajador).

    Nota v19: en v18 el haber incluía además «Descuento por Adelantos»
    y «Descuento por Préstamos» (campos ``advance_amount`` /
    ``loan_amount`` de la línea); esos campos no existen en el modelo
    v19 (los adelantos/préstamos se descuentan vía nómina), por lo que
    esas líneas no se portan.
    """
    _name = 'hr.cts'
    _inherit = ['hr.cts', 'hr.benefits.move.mixin']

    def _cts_semester_range(self):
        """Rango de provisiones del semestre del depósito (v18:
        may-oct para tipo '11', nov-abr para tipo '05')."""
        self.ensure_one()
        if self.type == '11':
            return date(self.year, 5, 1), date(self.year, 10, 31)
        return date(self.year - 1, 11, 1), date(self.year, 4, 30)

    def compute_provision_cts(self):
        """Trae a ``prov_acumulado`` lo provisionado en el semestre
        desde ``hr.provisiones`` (ORM; v18 lo hacía con SQL)."""
        self.ensure_one()
        date_from, date_to = self._cts_semester_range()
        totals = {
            employee.id: total
            for employee, total in self.env['hr.provisiones.cts.line']
            ._read_group([
                ('provision_id.company_id', '=', self.company_id.id),
                ('provision_id.payslip_run_id.date_end', '>=', date_from),
                ('provision_id.payslip_run_id.date_end', '<=', date_to),
            ], ['employee_id'], ['provisiones_cts:sum'])
        }
        for line in self.line_ids:
            line.prov_acumulado = totals.get(line.employee_id.id, 0.0)
        return notify_success(self.env._(
            'Se obtuvo el acumulado de provisiones exitosamente.'))

    def _get_move_lines(self):
        self.ensure_one()
        param = self.env['hr.main.parameter'].get_main_parameter(
            self.company_id)
        param.check_benefits_account_values([
            'cts_debe_account_id', 'cts_haber_account_id',
            'cts_payable_account_id'])
        move_lines = []
        expense = {}
        # TODO(fase5-revisar): v18 no filtraba less_than_one_month en el
        # asiento; aquí se excluyen igual que en export_cts (esas líneas
        # no se depositan este semestre).
        lines = self.line_ids.filtered(
            lambda line: not line.less_than_one_month)
        for line in lines:
            partner_id = self._employee_partner(line.employee_id)
            # 1) Reversión de la provisión acumulada (debe).
            prov = _round(line.prov_acumulado)
            if prov:
                move_lines.append(self._make_line(
                    param.cts_haber_account_id,
                    self.env._('Provisión de CTS'),
                    debit=prov, partner_id=partner_id))
            # 2) Gasto por la diferencia no provisionada.
            self._accumulate(
                expense,
                param._benefits_analytic_distribution(line.version_id),
                line.total_cts - (line.prov_acumulado or 0.0))
            # 3) CTS por pagar (haber).
            payable = _round(line.cts_soles)
            if payable:
                move_lines.append(self._make_line(
                    param.cts_payable_account_id,
                    self.env._('CTS por pagar'),
                    credit=payable, partner_id=partner_id))
        self._append_expense_lines(
            move_lines, expense, param.cts_debe_account_id,
            self.env._('Gasto de CTS'))
        return move_lines

    def _benefits_move_date_ref(self):
        self.ensure_one()
        return self.deposit_date, \
            'CTS%s' % self._benefits_period_code(self.payslip_run_id)


class HrCtsLine(models.Model):
    _inherit = 'hr.cts.line'

    prov_acumulado = fields.Float(
        string='Prov. acumulada',
        help='Provisión de CTS acumulada del periodo computado, traída '
             'de hr.provisiones para conciliar contra lo pagado.')


class HrGratification(models.Model):
    """Asiento contable del pago semestral de gratificación.

    Misma estructura que la CTS; el gasto cubre gratificación + Bono
    Extraordinario Ley 29351 (v18 usaba la regla GRA para ambos en el
    asiento de pago) y el haber abona ``total`` (grati + bono).
    """
    _name = 'hr.gratification'
    _inherit = ['hr.gratification', 'hr.benefits.move.mixin']

    def _grati_semester_range(self):
        """Semestre legal: ene-jun (tipo '07') o jul-dic (tipo '12')."""
        self.ensure_one()
        if self.type == '07':
            return date(self.year, 1, 1), date(self.year, 6, 30)
        return date(self.year, 7, 1), date(self.year, 12, 31)

    def compute_provision_grati(self):
        """``prov_acumulado`` = provisión + bono provisionados en el
        semestre (ORM sobre ``hr.provisiones.grati.line``)."""
        self.ensure_one()
        date_from, date_to = self._grati_semester_range()
        totals = {}
        for employee, prov, boni in \
                self.env['hr.provisiones.grati.line']._read_group([
                    ('provision_id.company_id', '=', self.company_id.id),
                    ('provision_id.payslip_run_id.date_end', '>=',
                     date_from),
                    ('provision_id.payslip_run_id.date_end', '<=',
                     date_to),
                ], ['employee_id'],
                    ['provisiones_grati:sum', 'boni_grati:sum']):
            totals[employee.id] = (prov or 0.0) + (boni or 0.0)
        for line in self.line_ids:
            line.prov_acumulado = totals.get(line.employee_id.id, 0.0)
        return notify_success(self.env._(
            'Se obtuvo el acumulado de provisiones exitosamente.'))

    def _get_move_lines(self):
        self.ensure_one()
        param = self.env['hr.main.parameter'].get_main_parameter(
            self.company_id)
        param.check_benefits_account_values([
            'grati_debe_account_id', 'grati_haber_account_id',
            'grati_payable_account_id'])
        move_lines = []
        expense = {}
        for line in self.line_ids:
            partner_id = self._employee_partner(line.employee_id)
            prov = _round(line.prov_acumulado)
            if prov:
                move_lines.append(self._make_line(
                    param.grati_haber_account_id,
                    self.env._('Provisión de gratificación'),
                    debit=prov, partner_id=partner_id))
            self._accumulate(
                expense,
                param._benefits_analytic_distribution(line.version_id),
                line.total_grat + line.bonus_essalud
                - (line.prov_acumulado or 0.0))
            payable = _round(line.total)
            if payable:
                move_lines.append(self._make_line(
                    param.grati_payable_account_id,
                    self.env._('Gratificación por pagar'),
                    credit=payable, partner_id=partner_id))
        self._append_expense_lines(
            move_lines, expense, param.grati_debe_account_id,
            self.env._('Gasto de gratificación'))
        return move_lines

    def _benefits_move_date_ref(self):
        self.ensure_one()
        return self.deposit_date, \
            'GRA%s' % self._benefits_period_code(self.payslip_run_id)


class HrGratificationLine(models.Model):
    _inherit = 'hr.gratification.line'

    prov_acumulado = fields.Float(
        string='Prov. acumulada',
        help='Provisión de gratificación + bono acumulada del periodo '
             'computado, traída de hr.provisiones.')


class HrLiquidationVacationLine(models.Model):
    _inherit = 'hr.liquidation.vacation.line'

    prov_acumulado = fields.Float(
        string='Prov. acumulada',
        help='Provisión de vacaciones acumulada del periodo computado, '
             'traída de hr.provisiones.')


class HrLiquidation(models.Model):
    """A diferencia de CTS/gratificación (1 asiento por lote), la
    liquidación de cese genera **un asiento por cesado** (cada cese
    tiene su fecha, importe y tercero): las filas se materializan en
    ``hr.liquidation.move`` y ``preserve_record`` protege las ajustadas
    a mano del recálculo (semántica v18)."""
    _inherit = 'hr.liquidation'

    liq_move_ids = fields.One2many(
        'hr.liquidation.move', 'liquidation_id',
        string='Asientos contables')
    move_count = fields.Integer(compute='_compute_move_count')

    @api.depends('liq_move_ids.account_move_id')
    def _compute_move_count(self):
        """Smart button: asientos ya generados."""
        for record in self:
            record.move_count = len(
                record.liq_move_ids.account_move_id)

    def action_open_asiento(self):
        """Abre la lista de asientos generados por los cesados."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('id', 'in',
                        self.liq_move_ids.account_move_id.ids)],
            'name': self.env._('Asientos de liquidación'),
        }

    def get_liq_move_lines(self):
        """Crea una fila ``hr.liquidation.move`` por cesado del lote.

        Mismos criterios de selección que el resto de la liquidación
        (``_get_cessation_slips``). v18 divergía entre variantes: la
        no-analítica excluía jornadas < 4 horas y la analítica no; se
        mantiene la exclusión (coherente con las vacaciones truncas).
        """
        self.ensure_one()
        Move = self.env['hr.liquidation.move']
        for slip in self._get_cessation_slips(
                include_less_than_four=False):
            version = slip.version_id
            admission_date = self.env['hr.main.parameter'] \
                .get_first_version(slip.employee_id).contract_date_start
            Move.create({
                'liquidation_id': self.id,
                'employee_id': slip.employee_id.id,
                'version_id': version.id,
                'admission_date': admission_date,
                'cessation_date': version.contract_date_end,
            })

    def get_liquidation(self):
        """Override: tras recalcular los truncos, regenera las filas de
        asiento respetando ``preserve_record`` (v18)."""
        res = super().get_liquidation()
        self.liq_move_ids.filtered(
            lambda move: not move.preserve_record).unlink()
        self.get_liq_move_lines()
        preserved_employees = \
            self.liq_move_ids.filtered('preserve_record').employee_id
        self.liq_move_ids.filtered(
            lambda move: not move.preserve_record
            and move.employee_id in preserved_employees).unlink()
        return res

    def compute_provision_liqui(self):
        """Acumulado provisionado por cesado y concepto (ORM).

        Rango v18: desde ``compute_date`` hasta ``cessation_date`` de
        cada línea, sobre los lotes de ``hr.provisiones``.
        """
        self.ensure_one()

        def provision_total(model, line, sums):
            if not (line.compute_date and line.cessation_date):
                return 0.0
            groups = self.env[model]._read_group([
                ('provision_id.company_id', '=', self.company_id.id),
                ('employee_id', '=', line.employee_id.id),
                ('provision_id.payslip_run_id.date_end', '>=',
                 line.compute_date),
                ('provision_id.payslip_run_id.date_end', '<=',
                 line.cessation_date),
            ], [], sums)
            return sum((amount or 0.0) for amount in groups[0])

        for line in self.cts_line_ids:
            line.prov_acumulado = provision_total(
                'hr.provisiones.cts.line', line, ['provisiones_cts:sum'])
        for line in self.gratification_line_ids:
            line.prov_acumulado = provision_total(
                'hr.provisiones.grati.line', line,
                ['provisiones_grati:sum', 'boni_grati:sum'])
        for line in self.vacation_line_ids:
            line.prov_acumulado = provision_total(
                'hr.provisiones.vaca.line', line,
                ['provisiones_vaca:sum'])
        return notify_success(self.env._(
            'Se obtuvo el acumulado de provisiones exitosamente.'))


class HrLiquidationMove(models.Model):
    """Fila de asiento de liquidación por trabajador cesado."""
    _name = 'hr.liquidation.move'
    _description = 'Asiento contable de liquidación por cesado'
    _inherit = ['hr.benefits.move.mixin']
    _order = 'employee_id'
    _check_company_auto = True

    liquidation_id = fields.Many2one(
        'hr.liquidation', string='Liquidación', ondelete='cascade',
        required=True, index=True)
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
    preserve_record = fields.Boolean(string='No recalcular')

    def _get_move_lines(self):
        self.ensure_one()
        liquidation = self.liquidation_id
        employee = self.employee_id
        param = self.env['hr.main.parameter'].get_main_parameter(
            liquidation.company_id)
        param.check_benefits_account_values([
            'cts_debe_account_id', 'cts_haber_account_id',
            'grati_debe_account_id', 'grati_haber_account_id',
            'vaca_debe_account_id', 'vaca_haber_account_id',
            'liquidation_payable_account_id'])
        partner_id = self._employee_partner(employee)
        move_lines = []

        def employee_lines(lines):
            return lines.filtered(
                lambda line: line.employee_id == employee)

        cts_lines = employee_lines(liquidation.cts_line_ids)
        grati_lines = employee_lines(liquidation.gratification_line_ids)
        vaca_lines = employee_lines(liquidation.vacation_line_ids)
        extra_lines = employee_lines(liquidation.liq_ext_concept_ids)

        # 1) Reversión de provisiones acumuladas (debe, con tercero).
        for lines, account, name in (
                (cts_lines, param.cts_haber_account_id,
                 self.env._('Provisión de CTS')),
                (grati_lines, param.grati_haber_account_id,
                 self.env._('Provisión de gratificación')),
                (vaca_lines, param.vaca_haber_account_id,
                 self.env._('Provisión de vacaciones'))):
            prov = _round(sum(lines.mapped('prov_acumulado')))
            if prov:
                move_lines.append(self._make_line(
                    account, name, debit=prov, partner_id=partner_id))

        # 2) Gasto de los truncos netos de provisión (signo decide
        #    debe/haber, con distribución analítica de la versión).
        # TODO(fase5-revisar): v18 permitía cuentas de gasto distintas
        # para los truncos (reglas GRA_TRU/CTS_TRU/VATRU); v19 reutiliza
        # las cuentas de gasto por concepto de hr.main.parameter.
        distribution = param._benefits_analytic_distribution(
            self.version_id)
        for amount, account, name in (
                (sum(grati_lines.mapped('total'))
                 - sum(grati_lines.mapped('prov_acumulado')),
                 param.grati_debe_account_id,
                 self.env._('Gratificación trunca')),
                (sum(cts_lines.mapped('total_cts'))
                 - sum(cts_lines.mapped('prov_acumulado')),
                 param.cts_debe_account_id,
                 self.env._('CTS trunca')),
                (sum(vaca_lines.mapped('total_vacation'))
                 - sum(vaca_lines.mapped('prov_acumulado')),
                 param.vaca_debe_account_id,
                 self.env._('Vacaciones truncas'))):
            amount = _round(amount)
            if amount:
                move_lines.append(self._make_line(
                    account, name,
                    debit=amount if amount > 0 else 0.0,
                    credit=-amount if amount < 0 else 0.0,
                    distribution=distribution))

        # 3) Liquidaciones por pagar (haber): truncos brutos (neto AFP
        #    en vacaciones) + conceptos extra (ingresos - descuentos).
        payable = (
            sum(grati_lines.mapped('total_grat'))
            + sum(grati_lines.mapped('bonus_essalud'))
            + sum(cts_lines.mapped('total_cts'))
            + sum(vaca_lines.mapped('total'))
            + sum(extra_lines.mapped('income'))
            - sum(extra_lines.mapped('expenses')))
        payable = _round(payable)
        if payable:
            move_lines.append(self._make_line(
                param.liquidation_payable_account_id,
                self.env._('Liquidaciones por pagar'),
                credit=payable, partner_id=partner_id))

        # 4) Retenciones previsionales de las vacaciones truncas
        #    (haber, cuenta de la afiliación AFP/ONP).
        pension = _round(sum(
            line.onp + line.afp_jub + line.afp_si + line.afp_mixed_com
            + line.afp_fixed_com for line in vaca_lines))
        if pension:
            membership = self.version_id.membership_id
            account = membership.with_company(
                liquidation.company_id).account_id
            if not account:
                raise UserError(self.env._(
                    'La afiliación %(membership)s no tiene cuenta '
                    'contable configurada para la compañía.',
                    membership=membership.display_name))
            move_lines.append(self._make_line(
                account, membership.name, credit=pension,
                partner_id=partner_id))

        # 5) Conceptos extra: «ingreso» al debe (con analítica) y
        #    «descuento» al haber.
        # TODO(fase5-revisar): v18 resolvía la cuenta por concepto vía la
        # regla salarial homónima al input (una cuenta por concepto); v19
        # unifica en el par liq_concept_in/out_account_id de los
        # Parámetros Principales. Si se necesita cuenta por concepto,
        # añadir cuentas company_dependent a hr.payslip.input.type.
        concept_lines = extra_lines.conceptos_lines.filtered('amount')
        if concept_lines:
            param.check_benefits_account_values([
                'liq_concept_in_account_id',
                'liq_concept_out_account_id'])
        for concept in concept_lines:
            name = concept.name_input_id.display_name
            if concept.type == 'in':
                move_lines.append(self._make_line(
                    param.liq_concept_in_account_id, name,
                    debit=concept.amount, partner_id=partner_id,
                    distribution=distribution))
            else:
                move_lines.append(self._make_line(
                    param.liq_concept_out_account_id, name,
                    credit=concept.amount, partner_id=partner_id))
        return move_lines

    def get_liquidation_move_wizard(self):
        """Alias v18 del botón por fila (delegado al mixin)."""
        return self.get_move_wizard()

    def _benefits_move_date_ref(self):
        self.ensure_one()
        return self.cessation_date, 'LIQUI%s' % self._benefits_period_code(
            self.liquidation_id.payslip_run_id)

    def _register_benefits_move(self, move):
        super()._register_benefits_move(move)
        self.preserve_record = True


class HrProvisiones(models.Model):
    """Asiento de la provisión mensual de BBSS.

    Debe: gasto por concepto (CTS, gratificación, bono Ley 29351,
    vacaciones), con distribución analítica de cada versión si el flag
    está activo. Haber: pasivo provisional por concepto; con
    ``detallar_provision`` activo se genera una línea por trabajador
    con su tercero (v18 ``hr_provisions`` + variante analítica).
    """
    _name = 'hr.provisiones'
    _inherit = ['hr.provisiones', 'hr.benefits.move.mixin']

    def _get_move_lines(self):
        self.ensure_one()
        param = self.env['hr.main.parameter'].get_main_parameter(
            self.company_id)
        param.check_benefits_account_values([
            'cts_debe_account_id', 'cts_haber_account_id',
            'grati_debe_account_id', 'grati_haber_account_id',
            'boni_debe_account_id', 'boni_haber_account_id',
            'vaca_debe_account_id', 'vaca_haber_account_id'])
        move_lines = []
        concepts = (
            (self.cts_lines, 'provisiones_cts',
             param.cts_debe_account_id, param.cts_haber_account_id,
             self.env._('Provisión de CTS'),
             self.env._('Provisión de CTS por pagar')),
            (self.grati_lines, 'provisiones_grati',
             param.grati_debe_account_id, param.grati_haber_account_id,
             self.env._('Provisión de gratificación'),
             self.env._('Provisión de gratificación por pagar')),
            (self.grati_lines, 'boni_grati',
             param.boni_debe_account_id, param.boni_haber_account_id,
             self.env._('Provisión del bono extraordinario'),
             self.env._('Provisión del bono extraordinario por pagar')),
            (self.vaca_lines, 'provisiones_vaca',
             param.vaca_debe_account_id, param.vaca_haber_account_id,
             self.env._('Provisión de vacaciones'),
             self.env._('Provisión de vacaciones por pagar')),
        )
        for lines, field_name, debit_account, credit_account, \
                debit_name, credit_name in concepts:
            expense = {}
            credit_total = 0.0
            for line in lines:
                amount = line[field_name]
                if not amount:
                    continue
                self._accumulate(
                    expense,
                    param._benefits_analytic_distribution(
                        line.version_id),
                    amount)
                # Haber: detallado por trabajador o agrupado.
                if param.detallar_provision:
                    move_lines.append(self._make_line(
                        credit_account, credit_name,
                        credit=amount,
                        partner_id=self._employee_partner(
                            line.employee_id)))
                else:
                    credit_total += amount
            self._append_expense_lines(
                move_lines, expense, debit_account, debit_name)
            if not param.detallar_provision and _round(credit_total):
                move_lines.append(self._make_line(
                    credit_account, credit_name,
                    credit=credit_total))
        return move_lines

    def _benefits_move_date_ref(self):
        self.ensure_one()
        return self.payslip_run_id.date_end, \
            'PROVISION%s' % self._benefits_period_code(
                self.payslip_run_id)

    def _register_benefits_move(self, move):
        """v18: contabilizar la provisión la cierra (``done``)."""
        super()._register_benefits_move(move)
        self.state = 'done'
