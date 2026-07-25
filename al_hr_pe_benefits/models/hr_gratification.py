# -*- coding: utf-8 -*-
"""Liquidación semestral de gratificación legal (Ley 27735).

El empleador paga dos gratificaciones al año equivalentes a un sueldo
cada una (medio sueldo en pequeña empresa):

* **Tipo '07' (Fiestas Patrias, julio)**: cubre enero-junio.
* **Tipo '12' (Navidad, diciembre)**: cubre julio-diciembre.

El monto se prorratea por meses laborados en el semestre. Con
``with_bonus=True`` se añade el Bono Extraordinario Ley 29351: el % del
seguro social de la versión (9 % EsSalud / 6.75 % EPS) sobre la
gratificación, no afecto a aportes.

Portado de ``hr_social_benefits/models/hr_gratification.py`` (v18).
Cambios v19: ``hr.contract`` → ``hr.version``; ``account.fiscal.year``
(eliminado) → campo entero ``year``; boletas PDF/Excel y envío por
correo quedan para la Fase 7.
"""
import calendar
from datetime import date

from odoo import api, fields, models

from odoo.addons.al_hr_pe.tools import custom_round
from .hr_benefits_engine import notify_success


class HrGratification(models.Model):
    _name = 'hr.gratification'
    _description = 'Gratificación legal'
    _order = 'deposit_date desc'
    _check_company_auto = True

    name = fields.Char(string='Nombre')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    year = fields.Integer(
        string='Año', required=True,
        default=lambda self: fields.Date.context_today(self).year,
        help='Año del pago (sustituye al año fiscal contable v18).')
    with_bonus = fields.Boolean(
        string='Bono extraordinario', default=False,
        help='Añade el Bono Extraordinario Ley 29351 (% del seguro '
             'social sobre la gratificación).')
    months_and_days = fields.Boolean(
        string='Calcular días grati.', default=False,
        help='Incluye los días sueltos (además de los meses completos) '
             'en el prorrateo.')
    type = fields.Selection(
        selection=[('07', 'Gratificación Fiestas Patrias'),
                   ('12', 'Gratificación Navidad')],
        string='Tipo gratificación', required=True)
    payslip_run_id = fields.Many2one(
        'hr.payslip.run', string='Lote de nómina', required=True,
        check_company=True)
    deposit_date = fields.Date(string='Fecha de pago', required=True)
    line_ids = fields.One2many(
        'hr.gratification.line', 'gratification_id',
        string='Cálculo de gratificación')
    state = fields.Selection(
        selection=[('draft', 'Borrador'), ('exported', 'Exportado')],
        string='Estado', default='draft')
    grati_count = fields.Integer(compute='_compute_grati_count')

    _unique_semester = models.Constraint(
        'UNIQUE(company_id, year, type)',
        'Ya existe una gratificación de ese tipo y año para la compañía.')

    @api.depends('line_ids')
    def _compute_grati_count(self):
        for grati in self:
            grati.grati_count = len(grati.line_ids)

    @api.onchange('year', 'type')
    def _get_period(self):
        """Nombra el lote y enlaza el hr.payslip.run del mes de pago."""
        for record in self:
            if not (record.type and record.year):
                continue
            type_label = dict(
                self._fields['type'].selection).get(record.type)
            record.name = '%s %d' % (type_label, record.year)
            month = int(record.type)
            last_day = calendar.monthrange(record.year, month)[1]
            periodo = self.env['hr.period'].search([
                ('date_start', '>=', date(record.year, month, 1)),
                ('date_end', '<=', date(record.year, month, last_day)),
                ('company_id', '=', record.company_id.id),
            ], limit=1)
            run = self.env['hr.payslip.run'].search([
                ('periodo_id', '=', periodo.id),
                ('company_id', '=', record.company_id.id),
            ], limit=1)
            if run:
                record.payslip_run_id = run.id

    def action_open_grati(self):
        """Abre las líneas de gratificación del lote."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.gratification.line',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('id', 'in', self.line_ids.ids)],
            'name': self.env._('Boletas de gratificación'),
        }

    def turn_draft(self):
        """Reabre el lote a borrador para permitir recálculo."""
        self.write({'state': 'draft'})

    def get_gratification(self):
        """Genera/recalcula las líneas del semestre.

        Borra las líneas no preservadas, delega el cálculo al motor de
        `hr.main.parameter` y descarta los duplicados de los empleados
        con overrides manuales (``preserve_record``).
        """
        self.ensure_one()
        self.line_ids.filtered(lambda line: not line.preserve_record).unlink()
        self.env['hr.main.parameter'].compute_benefits(self, self.type)
        preserved_employees = \
            self.line_ids.filtered('preserve_record').employee_id
        self.line_ids.filtered(
            lambda line: not line.preserve_record
            and line.employee_id in preserved_employees).unlink()
        return notify_success(self.env._('Se calculó exitosamente.'))

    def compute_grati_line_all(self):
        """Recalcula todas las líneas del lote en una pasada."""
        self.line_ids.compute_grati_line()
        return notify_success(self.env._('Se recalculó exitosamente.'))

    def set_amounts(self, line_ids, lot, param):
        """Vuelca gratificación + bono EsSalud al payslip del empleado.

        Escribe la gratificación en el input ``gratification_input_id``
        y el bono extraordinario en ``bonus_nine_input_id``; crea las
        líneas de input si el payslip no las tiene.
        """
        for line in line_ids:
            slip = lot.slip_ids.filtered(
                lambda slip: slip.employee_id == line.employee_id)
            if not slip:
                continue
            slip = slip[:1]
            for input_type, amount in (
                    (param.gratification_input_id, line.total_grat),
                    (param.bonus_nine_input_id, line.bonus_essalud)):
                input_line = slip.input_line_ids.filtered(
                    lambda inp: inp.input_type_id == input_type)
                if input_line:
                    input_line.amount = amount
                else:
                    slip.write({'input_line_ids': [(0, 0, {
                        'input_type_id': input_type.id,
                        'amount': amount,
                    })]})

    def export_gratification(self):
        """Exporta los montos al lote de nómina y cierra el registro."""
        self.ensure_one()
        param = self.env['hr.main.parameter'].get_main_parameter(
            self.company_id)
        param.check_gratification_values()
        self.set_amounts(self.line_ids, self.payslip_run_id, param)
        self.state = 'exported'
        return notify_success(self.env._('Se exportó exitosamente.'))


class HrGratificationLine(models.Model):
    _name = 'hr.gratification.line'
    _description = 'Línea de gratificación'
    _order = 'employee_id'
    _check_company_auto = True

    gratification_id = fields.Many2one(
        'hr.gratification', string='Gratificación', ondelete='cascade',
        index=True)
    liquidation_id = fields.Many2one(
        'hr.liquidation', string='Liquidación', ondelete='cascade',
        index=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', store=True, index=True,
        compute='_compute_company_id')

    @api.depends('gratification_id.company_id', 'liquidation_id.company_id')
    def _compute_company_id(self):
        for line in self:
            line.company_id = (line.gratification_id.company_id
                               or line.liquidation_id.company_id)
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
    labor_regime = fields.Selection(
        related='version_id.l10n_pe_labor_regime',
        string='Régimen laboral')
    social_insurance_id = fields.Many2one(
        related='version_id.social_insurance_id', string='Seguro social')
    distribution_id = fields.Char(string='Distribución analítica')
    months = fields.Integer(string='Meses')
    days = fields.Integer(string='Días')
    lacks = fields.Integer(string='Faltas')
    wage = fields.Float(string='Sueldo')
    household_allowance = fields.Float(string='Asignación familiar')
    commission = fields.Float(string='Prom. comisión')
    bonus = fields.Float(string='Prom. bonificación')
    extra_hours = fields.Float(string='Prom. horas extras')
    computable_remuneration = fields.Float(string='Remuneración computable')
    amount_per_month = fields.Float(string='Monto por mes')
    amount_per_day = fields.Float(string='Monto por día')
    amount_per_lack = fields.Float(string='(-) Monto por faltas')
    grat_per_month = fields.Float(string='Grat. por meses')
    grat_per_day = fields.Float(string='Grat. por días')
    total_grat = fields.Float(string='Total gratificación')
    bonus_essalud = fields.Float(string='(+) Bono extraordinario')
    total = fields.Float(string='Total a pagar')
    preserve_record = fields.Boolean(string='No recalcular')
    gratification_line_ids = fields.One2many(
        'hr.gratification.line.detalle', 'gratification_line_id',
        string='Detalle histórico')

    def compute_grati_line(self):
        """Recalcula la línea a partir de sus componentes editables."""
        for record in self:
            record.computable_remuneration = (
                record.wage + record.household_allowance + record.commission
                + record.bonus + record.extra_hours)
            if record.version_id.l10n_pe_labor_regime == 'general':
                record.amount_per_month = record.computable_remuneration / 6
            else:
                record.amount_per_month = record.computable_remuneration / 12
            record.amount_per_day = record.amount_per_month / 30
            record.amount_per_lack = record.amount_per_day * record.lacks
            record.grat_per_month = custom_round(
                record.amount_per_month * record.months, 2)
            record.grat_per_day = custom_round(
                record.amount_per_day * record.days, 2)
            record.total_grat = custom_round(
                (record.grat_per_month + record.grat_per_day)
                - record.amount_per_lack, 2)
            percent = 0.0
            header = record.gratification_id or record.liquidation_id
            if header and header.with_bonus:
                percent = record.social_insurance_id.percent or 0.0
            record.bonus_essalud = custom_round(
                record.total_grat * percent * 0.01, 2)
            record.total = custom_round(
                record.total_grat + record.bonus_essalud, 2)

    def view_detail_grat(self):
        """Detalle histórico de planillas de los 6 meses computados."""
        self.ensure_one()
        self.gratification_line_ids.unlink()
        history = self.env['hr.main.parameter'].get_salary_history(
            self.employee_id, self.company_id,
            self.gratification_id.deposit_date)
        Detalle = self.env['hr.gratification.line.detalle']
        for periodo, amounts in history.items():
            Detalle.create({
                'gratification_line_id': self.id,
                'periodo_id': periodo.id,
                'wage': amounts['wage'],
                'household_allowance': amounts['household_allowance'],
                'commission': amounts['commission'],
                'extra_hours': amounts['extra_hours'],
                'others_income': amounts['others_income'],
            })
        return {
            'name': self.env._('Detalle histórico de planillas'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.gratification.line.detalle',
            'domain': [('gratification_line_id', '=', self.id)],
            'view_mode': 'list',
            'views': [(False, 'list')],
            'target': 'new',
        }


class HrGratificationLineDetalle(models.Model):
    _name = 'hr.gratification.line.detalle'
    _description = 'Detalle de línea de gratificación'
    _order = 'periodo_id desc'

    gratification_line_id = fields.Many2one(
        'hr.gratification.line', string='Línea de gratificación',
        ondelete='cascade', required=True, index=True)
    company_id = fields.Many2one(
        related='gratification_line_id.company_id', string='Compañía',
        store=True, index=True)
    periodo_id = fields.Many2one('hr.period', string='Periodo')
    wage = fields.Float(string='Básico')
    household_allowance = fields.Float(string='Asignación familiar')
    commission = fields.Float(string='Comisiones')
    extra_hours = fields.Float(string='Horas extras')
    others_income = fields.Float(string='Bonificaciones')
    total = fields.Float(
        string='Base imponible', digits=(12, 2), compute='_compute_total',
        store=True)

    @api.depends('wage', 'household_allowance', 'commission',
                 'extra_hours', 'others_income')
    def _compute_total(self):
        for line in self:
            line.total = (line.wage + line.household_allowance
                          + line.commission + line.extra_hours
                          + line.others_income)
