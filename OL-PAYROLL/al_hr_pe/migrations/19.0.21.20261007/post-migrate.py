# -*- coding: utf-8 -*-
"""La regla INDEM se declaraba en el PLAME con el código 0904, que en la
tabla 22 es la CTS. La indemnización genérica pasa a 0501 (despido); la
vacacional tiene ahora su propia regla, INDVAC (0504).

Solo se corrige si conserva el 0904 de los datos (regla ``noupdate``).
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    rule = env.ref('al_hr_pe.salary_rule_INDEM', raise_if_not_found=False)
    if rule and rule.sunat_code == '0904':
        rule.sunat_code = '0501'
