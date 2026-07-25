# -*- coding: utf-8 -*-
"""Liquidación semestral de CTS (Compensación por Tiempo de Servicios).

D.S. 001-97-TR (TUO Ley CTS): el empleador deposita un sueldo al año en
una cuenta intangible del trabajador, en dos semestres:

* **Tipo '11' (depósito de noviembre)**: cubre mayo a octubre.
* **Tipo '05' (depósito de mayo)**: cubre noviembre a abril.

El cálculo es proporcional: cada mes completo computa 1/12 (1/24 en
pequeña empresa) de la remuneración computable; los meses incompletos
se prorratean por días (mes comercial de 30 días). Las líneas con
``less_than_one_month=True`` se excluyen y su importe se reserva para
el semestre siguiente.

Portado de ``hr_social_benefits/models/hr_cts.py`` (v18). Cambios v19:
``hr.contract`` → ``hr.version``; ``account.fiscal.year`` (eliminado)
→ campo entero ``year``; certificados PDF/Excel y envío por correo
quedan para la Fase 7.
"""
import calendar
from datetime import date

from odoo import api, fields, models

from odoo.addons.al_hr_pe.tools import custom_round
from .hr_benefits_engine import notify_success


class HrCts(models.Model):
    _name = 'hr.cts'
    _description = 'CTS (depósito semestral)'
    _order = 'deposit_date desc'
    _check_company_auto = True

    name = fields.Char(string='Nombre')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    year = fields.Integer(
        string='Año', required=True,
        default=lambda self: fields.Date.context_today(self).year,
        help='Año del depósito (sustituye al año fiscal contable v18).')
    exchange_type = fields.Float(string='Tipo de cambio', default=1.0)
    type = fields.Selection(
        selection=[('11', 'CTS Mayo - Octubre'),
                   ('05', 'CTS Noviembre - Abril')],
        string='Tipo CTS', required=True)
    payslip_run_id = fields.Many2one(
        'hr.payslip.run', string='Lote de nómina', required=True,
        check_company=True)
    deposit_date = fields.Date(string='Fecha de depósito', required=True)
    line_ids = fields.One2many(
        'hr.cts.line', 'cts_id', string='Cálculo de CTS')
    state = fields.Selection(
        selection=[('draft', 'Borrador'), ('exported', 'Exportado')],
        string='Estado', default='draft')
    cts_count = fields.Integer(compute='_compute_cts_count')

    _unique_semester = models.Constraint(
        'UNIQUE(company_id, year, type)',
        'Ya existe un depósito CTS de ese semestre y año para la '
        'compañía.')

    @api.depends('line_ids', 'line_ids.less_than_one_month')
    def _compute_cts_count(self):
        """Cuenta líneas elegibles (excluye trabajadores con < 1 mes)."""
        for cts in self:
            cts.cts_count = len(cts.line_ids.filtered(
                lambda line: not line.less_than_one_month))

    @api.onchange('year', 'type')
    def _get_period(self):
        """Nombra el lote y enlaza el hr.payslip.run del mes de depósito."""
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

    def action_open_cts(self):
        """Abre las líneas del lote que califican al depósito."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.cts.line',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('id', 'in', self.line_ids.filtered(
                lambda line: not line.less_than_one_month).ids)],
            'name': self.env._('Certificados CTS'),
        }

    def turn_draft(self):
        """Reabre el lote a borrador para permitir recálculo."""
        self.write({'state': 'draft'})

    def get_cts(self):
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

    def compute_cts_line_all(self):
        """Recalcula todas las líneas del lote en una pasada."""
        self.line_ids.compute_cts_line()
        return notify_success(self.env._('Se recalculó exitosamente.'))

    def set_amounts(self, line_ids, lot, param):
        """Vuelca el ``total_cts`` de cada línea al input del payslip.

        Escribe el monto en el input configurado en
        ``hr.main.parameter.cts_input_id``; crea la línea de input si
        el payslip no la tiene. Omite las líneas con menos de un mes.
        """
        input_cts = param.cts_input_id
        for line in line_ids.filtered(
                lambda line: not line.less_than_one_month):
            slip = lot.slip_ids.filtered(
                lambda slip: slip.employee_id == line.employee_id)
            if not slip:
                continue
            cts_input_line = slip.input_line_ids.filtered(
                lambda inp: inp.input_type_id == input_cts)
            if cts_input_line:
                cts_input_line.amount = line.total_cts
            else:
                slip[:1].write({'input_line_ids': [(0, 0, {
                    'input_type_id': input_cts.id,
                    'amount': line.total_cts,
                })]})

    def export_cts(self):
        """Exporta los montos al lote de nómina y cierra el registro."""
        self.ensure_one()
        param = self.env['hr.main.parameter'].get_main_parameter(
            self.company_id)
        param.check_cts_values()
        self.set_amounts(self.line_ids, self.payslip_run_id, param)
        self.state = 'exported'
        return notify_success(self.env._('Se exportó exitosamente.'))


class HrCtsLine(models.Model):
    _name = 'hr.cts.line'
    _description = 'Línea de CTS'
    _order = 'employee_id'
    _check_company_auto = True

    cts_id = fields.Many2one(
        'hr.cts', string='Depósito CTS', ondelete='cascade', index=True)
    liquidation_id = fields.Many2one(
        'hr.liquidation', string='Liquidación', ondelete='cascade',
        index=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', store=True, index=True,
        compute='_compute_company_id')

    @api.depends('cts_id.company_id', 'liquidation_id.company_id')
    def _compute_company_id(self):
        for line in self:
            line.company_id = (line.cts_id.company_id
                               or line.liquidation_id.company_id)
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', check_company=True)
    version_id = fields.Many2one(
        'hr.version', string='Contrato (versión)', check_company=True)
    less_than_one_month = fields.Boolean(
        string='Menos de un mes', default=False)
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
    cts_account = fields.Many2one(
        related='employee_id.cts_bank_account_id', string='Cuenta CTS')
    cts_bank = fields.Many2one(
        related='cts_account.bank_id', string='Banco')
    exchange_type = fields.Float(string='Tipo de cambio')
    distribution_id = fields.Char(string='Distribución analítica')
    months = fields.Integer(string='Meses')
    days = fields.Integer(string='Días')
    lacks = fields.Integer(string='Faltas')
    excess_medical_rest = fields.Integer(string='Exceso descanso médico')
    wage = fields.Float(string='Sueldo')
    household_allowance = fields.Float(string='Asignación familiar')
    sixth_of_gratification = fields.Float(string='1/6 gratificación')
    commission = fields.Float(string='Prom. comisión')
    bonus = fields.Float(string='Prom. bonificación')
    extra_hours = fields.Float(string='Prom. horas extras')
    computable_remuneration = fields.Float(string='Remuneración computable')
    amount_per_month = fields.Float(string='Monto por mes')
    amount_per_day = fields.Float(string='Monto por día')
    amount_per_lack = fields.Float(string='(-) Monto por faltas')
    cts_per_month = fields.Float(string='CTS por meses')
    cts_per_day = fields.Float(string='CTS por días')
    cts_interest = fields.Float(string='(+) Interés CTS')
    other_discounts = fields.Float(string='(-) Otros descuentos')
    total_cts = fields.Float(string='Total CTS')
    cts_soles = fields.Float(string='CTS a pagar soles')
    cts_dollars = fields.Float(string='CTS a pagar dólares')
    preserve_record = fields.Boolean(string='No recalcular')
    cts_line_ids = fields.One2many(
        'hr.cts.line.detalle', 'cts_line_id', string='Detalle histórico')

    def compute_cts_line(self):
        """Recalcula la línea a partir de sus componentes editables."""
        for record in self:
            record.computable_remuneration = (
                record.wage + record.household_allowance
                + record.sixth_of_gratification + record.commission
                + record.bonus + record.extra_hours)
            if record.version_id.l10n_pe_labor_regime == 'general':
                record.amount_per_month = record.computable_remuneration / 12
            else:
                record.amount_per_month = record.computable_remuneration / 24
            record.amount_per_day = record.amount_per_month / 30
            record.amount_per_lack = record.amount_per_day * record.lacks
            record.cts_per_month = custom_round(
                record.amount_per_month * record.months, 2)
            record.cts_per_day = custom_round(
                record.amount_per_day * record.days, 2)
            record.total_cts = (
                record.cts_per_month + record.cts_per_day
                - record.amount_per_lack + record.cts_interest
                - record.other_discounts)
            record.cts_soles = custom_round(record.total_cts, 2)
            exchange = record.exchange_type or 1.0
            record.cts_dollars = custom_round(
                record.total_cts / exchange, 2)

    def view_detail_cts(self):
        """Detalle histórico de planillas de los 6 meses computados."""
        self.ensure_one()
        self.cts_line_ids.unlink()
        history = self.env['hr.main.parameter'].get_salary_history(
            self.employee_id, self.company_id, self.cts_id.deposit_date)
        Detalle = self.env['hr.cts.line.detalle']
        for periodo, amounts in history.items():
            Detalle.create({
                'cts_line_id': self.id,
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
            'res_model': 'hr.cts.line.detalle',
            'domain': [('cts_line_id', '=', self.id)],
            'view_mode': 'list',
            'views': [(False, 'list')],
            'target': 'new',
        }


class HrCtsLineDetalle(models.Model):
    _name = 'hr.cts.line.detalle'
    _description = 'Detalle de línea de CTS'
    _order = 'periodo_id desc'

    cts_line_id = fields.Many2one(
        'hr.cts.line', string='Línea de CTS', ondelete='cascade',
        required=True, index=True)
    company_id = fields.Many2one(
        related='cts_line_id.company_id', string='Compañía', store=True,
        index=True)
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
