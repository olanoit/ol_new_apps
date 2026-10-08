# -*- coding: utf-8 -*-
"""Provisión mensual de beneficios sociales (CTS, gratificación, vacaciones).

Devengo mensual (NIIF/PCGE) de los beneficios sociales antes de su pago
efectivo, calculado por lote de nómina (``payslip_run_id``):

* **CTS** (D.S. 001-97-TR): remuneración computable (básico +
  asignación familiar + promedios + 1/6 de gratificación + otros
  adicionales) / 12; ÷2 en pequeña empresa.
* **Gratificación** (Ley 27735): computable / 6 (÷2 pequeña empresa)
  + Bono Extraordinario EsSalud (Ley 29351) según la ``tasa`` del
  seguro social del trabajador.
* **Vacaciones**: computable / 12 (÷2 pequeña y microempresa).

Los ingresos del mes se prorratean por días (mes comercial de 30) y
``compute_acumulado`` totaliza lo provisionado del semestre/año
corriente por empleado.

Portado de ``hr_provisions/models/hr_provisions.py`` (v18). Cambios
v19: ``hr.contract`` → ``hr.version``; SQL con ``.format()`` → ORM;
los «conceptos adicionales» cuelgan directo de cada línea (sin modelos
wizard). Esta fase solo CALCULA: el asiento contable de provisión
(cuentas debe/haber, ``account.move``) llega en la Fase 5 y el Excel
en la Fase 7.
"""
import calendar
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.addons.al_hr_pe.models.display_name import pe_join
from odoo.exceptions import UserError

from odoo.addons.al_hr_pe.tools import custom_round
from .hr_benefits_engine import notify_success


class HrProvisiones(models.Model):
    _name = 'hr.provisiones'
    _description = 'Provisión mensual de beneficios sociales'
    _rec_name = 'payslip_run_id'
    _order = 'id desc'
    _check_company_auto = True

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    payslip_run_id = fields.Many2one(
        'hr.payslip.run', string='Lote de nómina', required=True,
        check_company=True)
    gratificacion_id = fields.Many2one(
        'hr.gratification', string='Gratificación', check_company=True,
        help='Gratificación semestral de la que se toma el 1/6 para la '
             'remuneración computable de la CTS.')
    cts_lines = fields.One2many(
        'hr.provisiones.cts.line', 'provision_id', string='Líneas CTS')
    grati_lines = fields.One2many(
        'hr.provisiones.grati.line', 'provision_id',
        string='Líneas gratificación')
    vaca_lines = fields.One2many(
        'hr.provisiones.vaca.line', 'provision_id',
        string='Líneas vacaciones')
    state = fields.Selection(
        selection=[('draft', 'Borrador'), ('done', 'Hecho')],
        string='Estado', default='draft')

    _unique_run = models.Constraint(
        'UNIQUE(company_id, payslip_run_id)',
        'Ya existe una provisión de beneficios sociales para ese lote '
        'de nómina en la compañía (el acumulado la contaría doble).')

    @api.ondelete(at_uninstall=False)
    def _unlink_except_done(self):
        """Bloquea el borrado de provisiones cerradas (``done``):
        primero hay que volverlas a borrador."""
        if any(record.state == 'done' for record in self):
            raise UserError(self.env._(
                'No puedes eliminar una provisión ya cerrada. '
                'Primero debes volverla a borrador.'))

    # Botones, en el mismo orden que en la vista
    def action_process(self):
        """Genera las líneas de provisión del lote.

        Por cada trabajador con boleta y básico en el lote (regímenes
        general/pequeña/micro, sin cesados del mes):

        * microempresa → solo línea de vacaciones;
        * general/pequeña → CTS + vacaciones, y gratificación si el
          contrato empezó antes del inicio del lote;
        * ``l10n_pe_less_than_four`` → sin CTS (D.Leg. 650, igual que el
          motor de CTS) ni vacaciones (D.Leg. 713 exige 4 horas diarias);
          la gratificación sí se provisiona (antes se saltaba todo).
        """
        self.ensure_one()
        param = self.env['hr.main.parameter'].get_main_parameter(
            self.company_id)
        lot = self.payslip_run_id
        (self.cts_lines).unlink()
        (self.grati_lines).unlink()
        (self.vaca_lines).unlink()

        CtsLine = self.env['hr.provisiones.cts.line']
        GratiLine = self.env['hr.provisiones.grati.line']
        VacaLine = self.env['hr.provisiones.vaca.line']
        seen = self.env['hr.employee']
        for slip in lot.slip_ids:
            employee = slip.employee_id
            version = slip.version_id
            if employee in seen:
                continue
            if version.l10n_pe_labor_regime not in (
                    'general', 'small', 'micro'):
                continue
            if not slip.line_ids.filtered(
                    lambda line: line.salary_rule_id == param.basic_sr_id):
                continue
            seen |= employee
            # Cesado dentro del mes: se liquida, no se provisiona.
            if version.situation_code == '0' \
                    and version.contract_date_end \
                    and lot.date_start <= version.contract_date_end \
                    <= lot.date_end:
                continue
            less_than_four = version.l10n_pe_less_than_four
            averages = self._get_variable_averages(param, employee)
            common_vals = {
                'provision_id': self.id,
                'employee_id': employee.id,
                'version_id': version.id,
                'fecha_ingreso': version.contract_date_start,
                'basico': version.wage,
                # Mismo criterio que la regla AF de la boleta
                # (derechohabientes por edad, Ley 25129).
                'asignacion': param.family_allowance
                if slip.l10n_pe_family_allowance_ok else 0.0,
                'commission': averages['commission'],
                'bonus': averages['bonus'],
                'extra_hours': averages['extra_hours'],
            }
            # TODO(fase4-revisar): distribution_id (distribución
            # analítica del contrato v18) sin equivalente en hr.version.
            if version.l10n_pe_labor_regime == 'micro':
                if not less_than_four:
                    VacaLine.create(common_vals)
                continue
            if not less_than_four:
                grati_line = self.gratificacion_id.line_ids.filtered(
                    lambda line: line.employee_id == employee)[:1]
                CtsLine.create(dict(
                    common_vals,
                    un_sexto_grati=custom_round(grati_line.total_grat / 6, 2)
                    if grati_line else 0.0,
                ))
                VacaLine.create(common_vals)
            if version.contract_date_start \
                    and version.contract_date_start <= lot.date_start:
                GratiLine.create(dict(
                    common_vals,
                    tasa=version.social_insurance_id.percent or 0.0,
                ))
        return notify_success(self.env._('Se actualizó exitosamente.'))

    def action_compute_accumulated(self):
        """Acumulado provisionado por empleado (ORM, sin SQL).

        * CTS: desde el inicio del semestre CTS en curso (may-oct /
          nov-abr) hasta el fin del lote.
        * Gratificación: desde el inicio del semestre (ene-jun /
          jul-dic), sumando provisión + bono.
        * Vacaciones: desde el último aniversario de ingreso.
        """
        self.ensure_one()
        lot = self.payslip_run_id
        year = lot.date_end.year
        month = lot.date_end.month

        def base_domain(date_from):
            return [
                ('provision_id.company_id', '=', self.company_id.id),
                ('provision_id.payslip_run_id.date_end', '>=', date_from),
                ('provision_id.payslip_run_id.date_end', '<=',
                 lot.date_end),
            ]

        # CTS: semestre de depósito en curso.
        if month in (5, 6, 7, 8, 9, 10):
            date_from_cts = date(year, 5, 1)
        elif month in (11, 12):
            date_from_cts = date(year, 11, 1)
        else:
            date_from_cts = date(year - 1, 11, 1)
        cts_totals = {
            employee.id: total
            for employee, total in self.env['hr.provisiones.cts.line']
            ._read_group(base_domain(date_from_cts), ['employee_id'],
                         ['provisiones_cts:sum'])
        }
        for record in self.cts_lines:
            record.prov_acumulado = cts_totals.get(
                record.employee_id.id, 0.0)

        # Gratificación: semestre legal en curso (provisión + bono).
        date_from_grat = date(year, 1, 1) if month <= 6 else date(year, 7, 1)
        grat_totals = {}
        for employee, prov, boni in self.env['hr.provisiones.grati.line'] \
                ._read_group(base_domain(date_from_grat), ['employee_id'],
                             ['provisiones_grati:sum', 'boni_grati:sum']):
            grat_totals[employee.id] = (prov or 0.0) + (boni or 0.0)
        for record in self.grati_lines:
            record.prov_acumulado = grat_totals.get(
                record.employee_id.id, 0.0)

        # Vacaciones: desde el último aniversario de ingreso.
        VacaLine = self.env['hr.provisiones.vaca.line']
        Param = self.env['hr.main.parameter']
        for record in self.vaca_lines:
            admission_date = Param.get_first_version(
                record.employee_id).contract_date_start
            # Último aniversario de ingreso <= fin del lote: el de este
            # año si ya pasó, si no el del año anterior (v18 tomaba
            # siempre el anterior y acumulaba hasta 21 meses).
            date_from_vac = self._anniversary(admission_date, year)
            if date_from_vac > lot.date_end:
                date_from_vac = self._anniversary(admission_date, year - 1)
            lines = VacaLine.search(
                base_domain(date_from_vac)
                + [('employee_id', '=', record.employee_id.id)])
            record.prov_acumulado = sum(lines.mapped('provisiones_vaca'))
        return notify_success(self.env._(
            'Se obtuvo el acumulado de provisiones exitosamente.'))

    def action_close(self):
        """Cierra la provisión y bloquea el recálculo."""
        self.write({'state': 'done'})

    def action_draft(self):
        """Reabre la provisión a borrador para permitir recálculo."""
        self.write({'state': 'draft'})

    def _get_variable_averages(self, param, employee):
        """(comisión, bonificación, horas extras) promedios /6.

        Regla v18: se suman las líneas de los 6 meses (lote actual y 5
        previos, solo boletas con lote) y cada concepto promedia ÷6
        únicamente si se percibió en al menos 3 MESES distintos; si no,
        vale 0. Se cuentan meses, no líneas: dos reglas del mismo
        concepto o dos boletas en un mes son un solo mes.
        """
        lot = self.payslip_run_id
        date_from = lot.date_start - relativedelta(months=5)
        slips = self.env['hr.payslip'].search([
            ('employee_id', '=', employee.id),
            ('company_id', '=', self.company_id.id),
            ('date_from', '>=', date_from),
            ('date_to', '<=', lot.date_end),
            ('payslip_run_id', '!=', False),
            ('state', 'in', ('validated', 'paid')),
        ])
        totals = {'commission': 0.0, 'bonus': 0.0, 'extra_hours': 0.0}
        months = {'commission': set(), 'bonus': set(), 'extra_hours': set()}
        for line in slips.line_ids:
            if line.salary_rule_id in param.commission_sr_ids:
                bucket = 'commission'
            elif line.salary_rule_id in param.bonus_sr_ids:
                bucket = 'bonus'
            elif line.salary_rule_id == param.extra_hours_sr_id:
                bucket = 'extra_hours'
            else:
                continue
            totals[bucket] += line.total
            if line.total:
                months[bucket].add(
                    (line.slip_id.date_to.year, line.slip_id.date_to.month))
        return {
            bucket: custom_round(totals[bucket] / 6, 2)
            if len(months[bucket]) >= 3 else 0.0
            for bucket in totals
        }

    @staticmethod
    def _anniversary(admission_date, year):
        """Aniversario de ingreso en ``year`` (29/02 → 28/02)."""
        day = min(admission_date.day,
                  calendar.monthrange(year, admission_date.month)[1])
        return date(year, admission_date.month, day)


    @api.depends('payslip_run_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = pe_join('Provisiones', rec.payslip_run_id.display_name)


class HrProvisionesLineMixin(models.AbstractModel):
    """Campos y comportamiento comunes de las 3 líneas de provisión."""
    _name = 'hr.provisiones.line.mixin'
    _description = 'Base de línea de provisión'
    _order = 'employee_id'
    _check_company_auto = True

    provision_id = fields.Many2one(
        'hr.provisiones', string='Provisión', ondelete='cascade',
        required=True, index=True, check_company=True)
    company_id = fields.Many2one(
        related='provision_id.company_id', string='Compañía', store=True,
        index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', check_company=True)
    version_id = fields.Many2one(
        'hr.version', string='Contrato (versión)', check_company=True)
    nro_doc = fields.Char(
        related='employee_id.identification_id', string='Nro. documento')
    fecha_ingreso = fields.Date(string='Fecha de ingreso')
    distribution_id = fields.Char(string='Distribución analítica')
    basico = fields.Float(string='Rem. básica')
    asignacion = fields.Float(string='Asignación familiar')
    commission = fields.Float(string='Prom. comisión')
    bonus = fields.Float(string='Prom. bonificación')
    extra_hours = fields.Float(string='Prom. horas extras')
    prov_acumulado = fields.Float(string='Acumulado')

    def _prorate_by_admission(self, amount):
        """Prorratea el mes de ingreso: días laborados / mes de 30."""
        self.ensure_one()
        lot = self.provision_id.payslip_run_id
        if self.fecha_ingreso and lot.date_start \
                and lot.date_start < self.fecha_ingreso <= lot.date_end:
            dias = 30 - self.fecha_ingreso.day + 1
            amount = amount / 30 * dias
        return amount

    def action_open_concepts(self):
        """Popup con los conceptos adicionales de la línea."""
        self.ensure_one()
        view = self.env.ref(
            'al_hr_pe_benefits.%s_concepts_view_form'
            % self._table)
        return {
            'name': self.env._('Conceptos adicionales'),
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(view.id, 'form')],
            'target': 'new',
        }

    @api.depends('provision_id', 'employee_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = pe_join(rec.provision_id.display_name, rec.employee_id.name)


class HrProvisionesCtsLine(models.Model):
    _name = 'hr.provisiones.cts.line'
    _inherit = 'hr.provisiones.line.mixin'
    _description = 'Línea de provisión CTS'

    un_sexto_grati = fields.Float(string='1/6 gratificación')
    concepto_ids = fields.One2many(
        'hr.provisiones.concepto', 'cts_line_id', string='Otros conceptos')
    total_cts = fields.Float(
        string='Otros adicionales', compute='_compute_total_cts',
        store=True)
    provisiones_cts = fields.Float(
        string='Provisión CTS', compute='_compute_provisiones_cts',
        store=True)

    @api.depends('concepto_ids.monto')
    def _compute_total_cts(self):
        for record in self:
            record.total_cts = sum(record.concepto_ids.mapped('monto'))

    @api.depends('basico', 'asignacion', 'commission', 'bonus',
                 'extra_hours', 'un_sexto_grati', 'total_cts',
                 'fecha_ingreso', 'version_id.l10n_pe_labor_regime',
                 'provision_id.payslip_run_id')
    def _compute_provisiones_cts(self):
        for record in self:
            amount = (record.basico + record.asignacion + record.commission
                      + record.bonus + record.extra_hours
                      + record.un_sexto_grati + record.total_cts) / 12
            divider = 2 if record.version_id.l10n_pe_labor_regime \
                == 'small' else 1
            amount = record._prorate_by_admission(amount)
            record.provisiones_cts = custom_round(amount / divider, 2)


class HrProvisionesGratiLine(models.Model):
    _name = 'hr.provisiones.grati.line'
    _inherit = 'hr.provisiones.line.mixin'
    _description = 'Línea de provisión gratificación'

    tasa = fields.Float(
        string='Tasa %',
        help='Porcentaje del seguro social (EsSalud/EPS) para el Bono '
             'Extraordinario Ley 29351.')
    concepto_ids = fields.One2many(
        'hr.provisiones.concepto', 'grati_line_id',
        string='Otros conceptos')
    total_grati = fields.Float(
        string='Otros adicionales', compute='_compute_total_grati',
        store=True)
    provisiones_grati = fields.Float(
        string='Provisión gratificación',
        compute='_compute_provisiones_grati', store=True)
    boni_grati = fields.Float(
        string='Provisión bono', compute='_compute_boni_grati', store=True)
    total = fields.Float(string='Total', compute='_compute_total')

    @api.depends('concepto_ids.monto')
    def _compute_total_grati(self):
        for record in self:
            record.total_grati = sum(record.concepto_ids.mapped('monto'))

    @api.depends('basico', 'asignacion', 'commission', 'bonus',
                 'extra_hours', 'total_grati',
                 'version_id.l10n_pe_labor_regime')
    def _compute_provisiones_grati(self):
        for record in self:
            amount = (record.basico + record.asignacion + record.commission
                      + record.bonus + record.extra_hours
                      + record.total_grati) / 6
            divider = 2 if record.version_id.l10n_pe_labor_regime \
                == 'small' else 1
            record.provisiones_grati = custom_round(amount / divider, 2)

    @api.depends('provisiones_grati', 'tasa')
    def _compute_boni_grati(self):
        for record in self:
            record.boni_grati = custom_round(
                record.provisiones_grati * record.tasa / 100, 2)

    @api.depends('provisiones_grati', 'boni_grati')
    def _compute_total(self):
        for record in self:
            record.total = record.provisiones_grati + record.boni_grati


class HrProvisionesVacaLine(models.Model):
    _name = 'hr.provisiones.vaca.line'
    _inherit = 'hr.provisiones.line.mixin'
    _description = 'Línea de provisión vacaciones'

    concepto_ids = fields.One2many(
        'hr.provisiones.concepto', 'vaca_line_id', string='Otros conceptos')
    total_vaca = fields.Float(
        string='Otros adicionales', compute='_compute_total_vaca',
        store=True)
    provisiones_vaca = fields.Float(
        string='Provisión vacaciones', compute='_compute_provisiones_vaca',
        store=True)

    @api.depends('concepto_ids.monto')
    def _compute_total_vaca(self):
        for record in self:
            record.total_vaca = sum(record.concepto_ids.mapped('monto'))

    @api.depends('basico', 'asignacion', 'commission', 'bonus',
                 'extra_hours', 'total_vaca', 'fecha_ingreso',
                 'version_id.l10n_pe_labor_regime',
                 'provision_id.payslip_run_id')
    def _compute_provisiones_vaca(self):
        for record in self:
            amount = (record.basico + record.asignacion + record.commission
                      + record.bonus + record.extra_hours
                      + record.total_vaca) / 12
            divider = 2 if record.version_id.l10n_pe_labor_regime \
                in ('small', 'micro') else 1
            amount = record._prorate_by_admission(amount)
            record.provisiones_vaca = custom_round(amount / divider, 2)


class HrProvisionesConcepto(models.Model):
    """Concepto adicional de una línea de provisión.

    En v18 vivía en 3 modelos wizard (``cts/grati/vaca.line.wizard`` +
    ``*.conceptos``); aquí un solo modelo cuelga de la línea que
    corresponda (exactamente uno de los 3 M2O está lleno).
    """
    _name = 'hr.provisiones.concepto'
    _description = 'Concepto adicional de provisión'
    _check_company_auto = True

    cts_line_id = fields.Many2one(
        'hr.provisiones.cts.line', string='Línea CTS', ondelete='cascade',
        index=True,
        check_company=True)
    grati_line_id = fields.Many2one(
        'hr.provisiones.grati.line', string='Línea gratificación',
        ondelete='cascade', index=True,
        check_company=True)
    vaca_line_id = fields.Many2one(
        'hr.provisiones.vaca.line', string='Línea vacaciones',
        ondelete='cascade', index=True,
        check_company=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', store=True, index=True,
        compute='_compute_company_id')
    concepto = fields.Many2one('hr.salary.rule', string='Concepto')
    monto = fields.Float(string='Monto')

    @api.depends('cts_line_id.company_id', 'grati_line_id.company_id',
                 'vaca_line_id.company_id')
    def _compute_company_id(self):
        for record in self:
            record.company_id = (record.cts_line_id.company_id
                                 or record.grati_line_id.company_id
                                 or record.vaca_line_id.company_id)

    @api.depends('concepto')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.concepto.display_name or ''
