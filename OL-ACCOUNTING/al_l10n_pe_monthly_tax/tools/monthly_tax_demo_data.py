# -*- coding: utf-8 -*-
"""Datos de la ficha y la documentación (idempotente): régimen general desde
el 01/01/2026, coeficientes de ejemplo y los periodos 09/2026 y 10/2026
calculados con los movimientos reales de la base.

    odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http < \\
        myodoo/ol_new_apps/OL-ACCOUNTING/al_l10n_pe_monthly_tax/tools/monthly_tax_demo_data.py
"""
from datetime import date

company = env.company
root = company.root_id
Regime = env['l10n_pe.tax.regime']
if not Regime.search([('company_id', '=', root.id), ('date_from', '=', date(2026, 1, 1))]):
    Regime.create({'company_id': root.id, 'regime': 'general', 'date_from': date(2026, 1, 1),
                   'note': 'Régimen General (demostración)'})
root.write({'l10n_pe_income_coefficient': 0.0185, 'l10n_pe_income_coefficient_jan_feb': 0.0150})
Tax = env['l10n_pe.monthly.tax']
for month in (9, 10):
    record = Tax.search([('company_id', '=', company.id), ('year', '=', 2026), ('month', '=', str(month))])
    if record.state == 'declared':
        record.state = 'calculated'
    record = record or Tax.create({'year': 2026, 'month': str(month)})
    record.state = 'draft'
    record.action_compute()
    print('621', record.name, 'IGV', record.igv_to_pay, 'renta', record.income_tax_to_pay)
env.cr.commit()
