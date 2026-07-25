# -*- coding: utf-8 -*-
from odoo import fields, models


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    # Código del concepto en la planilla electrónica (PLAME): lo consumen
    # los exportadores .rem. Sin company_id: las reglas son globales y sus
    # cuentas contables ya son company_dependent en v19 (hr_payroll_account).
    sunat_code = fields.Char(
        string='Código SUNAT (PLAME)',
        help='Código del concepto remunerativo en la tabla 22 de la '
             'planilla electrónica.')
