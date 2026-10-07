# -*- coding: utf-8 -*-
from odoo import api, fields, models
from .display_name import pe_join, pe_range
from odoo.exceptions import ValidationError


class HrWorkSuspension(models.Model):
    """Suspensión de la relación laboral (TABLA 21) por periodo.

    Alimenta el exportador PLAME .snl. En v18 colgaba de hr.contract; en
    v19 referencia al empleado y su versión vigente. Las crean los flujos
    de ausencias (Fase 3, prorrateo mensual desde hr.leave) o se
    registran a mano.
    """
    _name = 'hr.work.suspension'
    _description = 'Suspensión de labores (T21)'
    _order = 'periodo_id desc, employee_id'
    _check_company_auto = True

    employee_id = fields.Many2one(
        'hr.employee', string='Trabajador', required=True, index=True,
        check_company=True)
    version_id = fields.Many2one(
        'hr.version', string='Versión/contrato', check_company=True,
        domain="[('employee_id', '=', employee_id)]")
    periodo_id = fields.Many2one(
        'hr.period', string='Periodo', required=True, index=True,
        check_company=True)
    suspension_type_id = fields.Many2one(
        'hr.suspension.type', string='Tipo de suspensión (T21)',
        required=True)
    date_from = fields.Date(string='Desde')
    date_to = fields.Date(string='Hasta')
    days = fields.Integer(string='Días', required=True)
    # Nota Fase 3: al integrar hr_payroll_holidays se añadirá leave_id
    # (M2O hr.leave) para rastrear la ausencia origen.
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)

    @api.constrains('days')
    def _check_days(self):
        for suspension in self:
            if suspension.days <= 0:
                raise ValidationError(self.env._(
                    'Los días de suspensión deben ser positivos.'))

    @api.depends('employee_id', 'suspension_type_id', 'date_from', 'date_to')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = pe_join(rec.employee_id.name, rec.suspension_type_id.display_name, pe_range(rec.env, rec.date_from, rec.date_to))
