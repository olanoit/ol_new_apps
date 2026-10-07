# -*- coding: utf-8 -*-
"""Códigos T-Registro de los regímenes pensionario (T11) y de salud (T32).

Los datos son ``noupdate``: en bases ya instaladas los códigos quedaban
vacíos y la estructura 11 salía sin régimen. Solo se llenan los vacíos.
"""
from odoo import SUPERUSER_ID, api

CODES = {
    'al_hr_pe.membership_AFP_HABIAT': '25',
    'al_hr_pe.membership_AFP_INTEGRA': '21',
    'al_hr_pe.membership_AFP_PRIMA': '24',
    'al_hr_pe.membership_AFP_PROFUTURO': '23',
    'al_hr_pe.membership_ONP': '02',
    'al_hr_pe.insurance_ESSALUD': '00',
    'al_hr_pe.insurance_EPS': '01',
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, code in CODES.items():
        record = env.ref(xmlid, raise_if_not_found=False)
        if record and not record.l10n_pe_tregistro_code:
            record.l10n_pe_tregistro_code = code
