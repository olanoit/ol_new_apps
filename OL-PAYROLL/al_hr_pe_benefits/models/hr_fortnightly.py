# -*- coding: utf-8 -*-
"""Adelanto quincenal (lote de boletas de la 1.ª quincena).

Portado de ``hr_fortnightly`` (v18). Permite procesar un lote de
boletas de «adelanto quincenal» antes del cierre del mes: el neto
quincenal de cada boleta (regla ``net_fortnightly_sr_id``) se vuelca
como input ``fortnightly_input_id`` de la boleta mensual definitiva
(:meth:`HrFortnightly.set_amounts`), junto con los adelantos/préstamos
específicos de quincena (``quin_advance_id`` / ``quin_loan_id``).

Estados del lote: ``draft`` → ``verify`` (boletas generadas) →
``exported`` (volcado al lote mensual).

Cambios v19:

* ``hr.contract`` → ``hr.version``: la selección de empleados para
  generar boletas usa las versiones con contrato vigente en la
  quincena (sustituye al wizard ``hr.payslip.employees.fortnightly``).
* Sin SQL ``.format()`` en ``import_advance_quin`` /
  ``import_loan_quin`` (ORM).
* Los campos de configuración (``fortnightly_input_id``,
  ``net_fortnightly_sr_id``, ``quin_advance_id``, ``quin_loan_id``)
  los añade ``hr_benefits_engine`` a `hr.main.parameter`; aquí se leen
  con ``getattr`` con guard.
* Las boletas quincenales llevan ``fortnightly_id``: todos los
  históricos de beneficios (5ta, utilidades, subsidios) las excluyen
  para no contar dos veces lo que la mensual ya declara.
* Estructura propia «Adelanto quincenal» (ADE_QUINCENAL, reglas *_AQ):
  adelanta un porcentaje del sueldo o los días trabajados, más la
  asignación familiar si se pide; los aportes y la 5ta van en la boleta
  mensual (solo se descuentan AFP/ONP a cuenta si la compañía lo pidió).
  Antes las boletas quincenales usaban BASE y calculaban EsSalud, AFP y
  5ta de medio mes que el mes volvía a calcular.
* La planilla tabular y el wizard de novedades de empleados quedan
  para la Fase 7.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_hr_pe.tools import custom_round

from .hr_benefits_engine import notify_success


class HrFortnightly(models.Model):
    _name = 'hr.fortnightly'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Adelanto quincenal'
    _order = 'date_end desc'
    _check_company_auto = True

    name = fields.Char(string='Nombre', required=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    slip_ids = fields.One2many(
        'hr.payslip', 'fortnightly_id', string='Nóminas')
    state = fields.Selection(
        selection=[('draft', 'Nuevo'), ('verify', 'Confirmado'),
                   ('exported', 'Exportado')],
        string='Estado', index=True, readonly=True, copy=False,
        default='draft')
    date_start = fields.Date(
        string='Desde', required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_end = fields.Date(
        string='Hasta', required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=15))
    payslip_count = fields.Integer(compute='_compute_payslip_count')
    payslip_run_id = fields.Many2one(
        'hr.payslip.run', string='Lote de nómina mensual', required=True,
        check_company=True,
        help='Lote mensual definitivo al que se exporta el neto '
             'quincenal.')

    @api.depends('slip_ids')
    def _compute_payslip_count(self):
        for record in self:
            record.payslip_count = len(record.slip_ids)

    @api.ondelete(at_uninstall=False)
    def _unlink_if_draft(self):
        if any(record.state != 'draft' for record in self):
            raise UserError(self.env._(
                'No puede eliminar un lote de quincena que no esté en '
                'borrador.'))
        if any(slip.state not in ('draft', 'cancel')
               for slip in self.slip_ids):
            raise UserError(self.env._(
                'No puede borrar una nómina que no esté en borrador o '
                'cancelada.'))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _check_configuration(self, param):
        """Port de ``check_quincena_values`` v18 (los campos los añade
        ``hr_benefits_engine``; mientras no existan cuentan como
        faltantes)."""
        missing = [label for field_name, label in [
            ('fortnightly_input_id', 'Input quincena'),
            ('net_fortnightly_sr_id', 'R.S. neto quincenal'),
        ] if not getattr(param, field_name, False)]
        if missing:
            raise UserError(self.env._(
                'Faltan configuraciones de adelanto quincenal en los '
                'Parámetros Principales de Nómina: %(fields)s.',
                fields=', '.join(missing)))

    def _get_quincena_structure(self):
        return self.env.ref('al_hr_pe_benefits.fortnightly_structure',
                            raise_if_not_found=False) \
            or self.env.ref('al_hr_pe.base_structure')

    # Botones, en el mismo orden que en la vista
    # ------------------------------------------------------------------
    # Generación de boletas quincenales
    # ------------------------------------------------------------------
    def generate_payslips(self):
        """Genera las boletas quincenales del lote (sustituye al wizard
        ``hr.payslip.employees.fortnightly`` v18): una por empleado con
        versión de contrato vigente en la quincena, omitiendo los que
        ya tienen boleta en el lote."""
        self.ensure_one()
        structure = self._get_quincena_structure()
        versions = self.env['hr.version'].search([
            ('company_id', '=', self.company_id.id),
            ('contract_date_start', '!=', False),
            ('contract_date_start', '<=', self.date_end),
            '|', ('contract_date_end', '=', False),
            ('contract_date_end', '>=', self.date_start),
        ])
        employees = versions.employee_id - self.slip_ids.employee_id
        if not employees:
            raise UserError(self.env._(
                'No hay empleados con contrato vigente pendientes de '
                'generar en esta quincena.'))
        slips = self.env['hr.payslip'].create([{
            'name': 'Quincena - %s - %s' % (employee.display_name,
                                            self.name),
            'employee_id': employee.id,
            'company_id': self.company_id.id,
            'date_from': self.date_start,
            'date_to': self.date_end,
            'struct_id': structure.id,
            'fortnightly_id': self.id,
        } for employee in employees])
        slips.compute_sheet()
        self.state = 'verify'
        return notify_success(self.env._('Se generaron %(count)d boletas '
                                         'quincenales.', count=len(slips)))

    def recompute_payslips(self):
        """Recalcula todas las boletas del lote."""
        self.slip_ids.compute_sheet()
        return notify_success(self.env._('Se recalculó exitosamente.'))

    # ------------------------------------------------------------------
    # Adelantos/préstamos de quincena
    # ------------------------------------------------------------------
    def import_advances_ade_quin(self):
        return self.slip_ids.import_advance_quin()

    def import_loans_ade_quin(self):
        return self.slip_ids.import_loan_quin()

    def export_quincena(self):
        """Cierra el lote quincenal volcando los montos al mensual; las
        boletas quincenales pasan a validadas."""
        self.ensure_one()
        param = self.env['hr.main.parameter'].get_main_parameter(
            self.company_id)
        self._check_configuration(param)
        self.set_amounts(self.slip_ids, self.payslip_run_id, param)
        self.state = 'exported'
        self.slip_ids.filtered(
            lambda slip: slip.state == 'draft').action_payslip_done()
        return notify_success(self.env._('Se exportó exitosamente.'))

    def set_draft(self):
        """Vuelve el lote a borrador eliminando sus boletas."""
        self.slip_ids.action_payslip_cancel()
        self.slip_ids.unlink()
        self.write({'state': 'draft'})

    def reopen_payroll(self):
        """Reabre el lote exportado para corregir y re-exportar."""
        self.write({'state': 'verify'})
        self.slip_ids.filtered(
            lambda slip: slip.state != 'draft').action_payslip_draft()

    def action_open_payslips(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('id', 'in', self.slip_ids.ids)],
            'context': {'default_fortnightly_id': self.id},
            'name': self.env._('Boletas quincenales'),
        }

    # ------------------------------------------------------------------
    # Exportación al lote mensual
    # ------------------------------------------------------------------
    def set_amounts(self, slips, lot, param):
        """Vuelca al lote mensual, por cada boleta quincenal:

        1. El neto de la regla ``net_fortnightly_sr_id`` al input
           ``fortnightly_input_id`` de la boleta mensual del empleado.
        2. Los adelantos pagados de tipo ``quin_advance_id`` del rango.
        3. Las cuotas de préstamo pagadas de tipo ``quin_loan_id``.
        """
        net_rule = getattr(param, 'net_fortnightly_sr_id')
        input_quincena = getattr(param, 'fortnightly_input_id')
        quin_advance = getattr(param, 'quin_advance_id', False)
        quin_loan = getattr(param, 'quin_loan_id', False)
        for line in slips:
            monthly_slip = lot.slip_ids.filtered(
                lambda slip: slip.employee_id == line.employee_id)[:1]
            if not monthly_slip:
                continue
            net_lines = line.line_ids.filtered(
                lambda rule_line: rule_line.salary_rule_id == net_rule)
            if not net_lines:
                # La regla configurada es de otra estructura (p. ej. el NETO
                # de BASE, de cuando la quincena se calculaba con BASE).
                net_lines = line.line_ids.filtered(
                    lambda rule_line: rule_line.code == 'NETO_AQ')
            net_amount = sum(net_lines.mapped('total'))
            monthly_slip._set_pe_input_amount(input_quincena, net_amount)

            if quin_loan and quin_loan.input_id:
                loan_lines = self.env['hr.loan.line'].search([
                    ('date', '>=', line.date_from),
                    ('date', '<=', line.date_to),
                    ('employee_id', '=', line.employee_id.id),
                    ('company_id', '=', line.company_id.id),
                    ('validation', '=', 'paid out'),
                    ('loan_type_id', '=', quin_loan.id),
                ])
                if loan_lines:
                    monthly_slip._set_pe_input_amount(
                        quin_loan.input_id,
                        sum(loan_lines.mapped('amount')))

            if quin_advance and quin_advance.input_id:
                advances = self.env['hr.advance'].search([
                    ('discount_date', '>=', line.date_from),
                    ('discount_date', '<=', line.date_to),
                    ('employee_id', '=', line.employee_id.id),
                    ('company_id', '=', line.company_id.id),
                    ('state', '=', 'paid out'),
                    ('advance_type_id', '=', quin_advance.id),
                ])
                if advances:
                    monthly_slip._set_pe_input_amount(
                        quin_advance.input_id,
                        sum(advances.mapped('amount')))


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    fortnightly_id = fields.Many2one(
        'hr.fortnightly', string='Lote quincenal', readonly=True,
        copy=False, ondelete='cascade', index=True, check_company=True)

    # ------------------------------------------------------------------
    # Reglas de la estructura «Adelanto quincenal» (*_AQ)
    # ------------------------------------------------------------------
    PAID_DAY_CODES = ('DLAB', 'DOM', 'FER', 'DVAC', 'DMED', 'DPAT', 'LCGH')

    def _l10n_pe_fortnightly_param(self):
        return self.env['hr.main.parameter'].search(
            [('company_id', '=', self.company_id.id)], limit=1)

    def _l10n_pe_fortnightly_share(self):
        """Fracción del mes que se adelanta: la tasa configurada o los
        días pagados de la quincena ÷ 30."""
        self.ensure_one()
        param = self._l10n_pe_fortnightly_param()
        if param.fortnightly_type == 'days':
            days = sum(self.worked_days_line_ids.filtered(
                lambda wd: wd.code in self.PAID_DAY_CODES
            ).mapped('number_of_days'))
            return min(days, 15.0) / 30.0
        return param.tasa if param else 0.5

    def _l10n_pe_fortnightly_basic(self):
        self.ensure_one()
        return custom_round(
            (self.version_id.wage or 0.0) * self._l10n_pe_fortnightly_share())

    def _l10n_pe_fortnightly_family_allowance(self):
        self.ensure_one()
        param = self._l10n_pe_fortnightly_param()
        if not param.compute_af or not self.l10n_pe_family_allowance_ok \
                or self.version_id.l10n_pe_labor_regime == 'practicante':
            return 0.0
        return custom_round(
            (self.family_allowance or 0.0) * self._l10n_pe_fortnightly_share())

    def _l10n_pe_fortnightly_pension(self, base):
        """AFP/ONP a cuenta, solo si la compañía lo pidió: reducen el
        adelanto; el aporte que se declara es el de la boleta mensual."""
        self.ensure_one()
        param = self._l10n_pe_fortnightly_param()
        membership = self.membership_id
        if not param.compute_afiliacion or not membership or not base:
            return 0.0
        rate = self.l10n_pe_retirement_fund or 0.0
        if membership.is_afp:
            rate += (self.l10n_pe_commission or 0.0) \
                + (0.0 if self.l10n_pe_is_older
                   else self.l10n_pe_prima_insurance or 0.0)
        return custom_round(base * rate / 100.0)

    def _l10n_pe_fortnightly_discounts(self):
        """Adelantos y préstamos de quincena importados a la boleta."""
        self.ensure_one()
        param = self._l10n_pe_fortnightly_param()
        input_types = (param.quin_advance_id.input_id
                       | param.quin_loan_id.input_id)
        return sum(self.input_line_ids.filtered(
            lambda line: line.input_type_id in input_types
        ).mapped('amount'))

    def import_advance_quin(self):
        """Vuelca a la boleta quincenal los adelantos ``not payed`` de
        tipo quincena del rango y los marca ``paid out``."""
        log = ''
        for slip in self:
            param = self.env['hr.main.parameter'].get_main_parameter(
                slip.company_id)
            quin_advance = getattr(param, 'quin_advance_id', False)
            if not quin_advance:
                raise UserError(self.env._(
                    'No se ha configurado el tipo de adelanto de '
                    'quincena en los Parámetros Principales de Nómina.'))
            pending = self.env['hr.advance'].search([
                ('discount_date', '>=', slip.date_from),
                ('discount_date', '<=', slip.date_to),
                ('employee_id', '=', slip.employee_id.id),
                ('company_id', '=', slip.company_id.id),
                ('state', '=', 'not payed'),
                ('advance_type_id', '=', quin_advance.id),
            ])
            # Sin input en el tipo no se descuenta nada: no marcar como
            # pagado lo que nunca llegó a la boleta.
            if not pending or not quin_advance.input_id:
                continue
            slip._set_pe_input_amount(
                quin_advance.input_id, sum(pending.mapped('amount')))
            pending.turn_paid_out()
            log += '%s\n' % slip.employee_id.display_name
        if log:
            return notify_success(self.env._(
                'Se importaron adelantos a los siguientes empleados:\n'
                '%(log)s', log=log))
        return notify_success(self.env._('No se importó ningún adelanto.'))

    def import_loan_quin(self):
        """Vuelca a la boleta quincenal las cuotas ``not payed`` de
        préstamos de tipo quincena del rango y las marca ``paid out``."""
        log = ''
        for slip in self:
            param = self.env['hr.main.parameter'].get_main_parameter(
                slip.company_id)
            quin_loan = getattr(param, 'quin_loan_id', False)
            if not quin_loan:
                raise UserError(self.env._(
                    'No se ha configurado el tipo de préstamo de '
                    'quincena en los Parámetros Principales de Nómina.'))
            pending = self.env['hr.loan.line'].search([
                ('date', '>=', slip.date_from),
                ('date', '<=', slip.date_to),
                ('employee_id', '=', slip.employee_id.id),
                ('company_id', '=', slip.company_id.id),
                ('validation', '=', 'not payed'),
                ('loan_type_id', '=', quin_loan.id),
            ])
            # Sin input en el tipo no se descuenta nada: no marcar como
            # pagado lo que nunca llegó a la boleta.
            if not pending or not quin_loan.input_id:
                continue
            slip._set_pe_input_amount(
                quin_loan.input_id, sum(pending.mapped('amount')))
            pending.turn_paid_out()
            log += '%s\n' % slip.employee_id.display_name
        if log:
            return notify_success(self.env._(
                'Se importaron préstamos a los siguientes empleados:\n'
                '%(log)s', log=log))
        return notify_success(self.env._('No se importó ningún préstamo.'))
