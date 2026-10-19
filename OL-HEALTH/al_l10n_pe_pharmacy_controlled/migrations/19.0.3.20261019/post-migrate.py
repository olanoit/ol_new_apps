# -*- coding: utf-8 -*-
"""Las recetas que ya estaban retenidas toman como fecha de retención la de
su última dispensación (o su última modificación): desde ahí corren los dos
años de archivo."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    prescriptions = env['pharmacy.prescription'].with_context(active_test=False).search(
        [('retained', '=', True), ('retention_date', '=', False)])
    for prescription in prescriptions:
        dates = prescription.dispensation_ids.mapped('date')
        prescription.retention_date = (max(dates) if dates else prescription.write_date).date()
