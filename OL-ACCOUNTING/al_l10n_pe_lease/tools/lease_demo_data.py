# -*- coding: utf-8 -*-
"""Datos «DEMO NIIF16» para las capturas de la ficha (se ejecuta con ``odoo shell``).

* Oficina a 36 meses, cuota adelantada de S/ 4 500, tasa 12 %, costos directos
  de S/ 1 200: confirmada, con sus dos primeras facturas del arrendador.
* Almacén a 12 meses: exento (corto plazo), con su primera cuota a gasto.
* Montacargas a 24 meses, cuota vencida: en borrador con su tabla calculada.

Es idempotente: si el arrendador demo existe, no hace nada.
"""
from datetime import date

PREFIX = 'DEMO NIIF16'


def ruc(base10):
    """RUC con su dígito verificador (módulo 11 de SUNAT)."""
    total = sum(int(d) * w for d, w in zip(base10, (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)))
    return base10 + str((11 - total % 11) % 10)


Partner = env['res.partner']
if Partner.search([('name', '=', '%s Inmobiliaria San Isidro S.A.C.' % PREFIX)], limit=1):
    print('Los datos DEMO NIIF16 ya existen.')
else:
    it_ruc = env.ref('l10n_pe.it_RUC', raise_if_not_found=False)
    lessor = Partner.create({'name': '%s Inmobiliaria San Isidro S.A.C.' % PREFIX, 'vat': ruc('2061234567'),
                             'is_company': True, 'country_id': env.ref('base.pe').id,
                             'l10n_latam_identification_type_id': it_ruc.id if it_ruc else False})
    Lease = env['l10n_pe.lease']
    office = Lease.create({
        'partner_id': lessor.id, 'property_description': 'Oficina Av. Javier Prado 450, piso 8',
        'contract_ref': 'ARR-2026-01', 'date_start': date(2026, 7, 1), 'term_months': 36,
        'payment_amount': 4500.0, 'payment_timing': 'advance', 'annual_rate': 12.0,
        'initial_direct_costs': 1200.0, 'guarantee_amount': 9000.0})
    office.action_confirm()
    office.action_register_installment()
    office.action_register_installment()

    warehouse = Lease.create({
        'partner_id': lessor.id, 'property_description': 'Almacén temporal Lurín',
        'contract_ref': 'ARR-2026-02', 'date_start': date(2026, 8, 1), 'term_months': 12,
        'payment_amount': 2800.0, 'payment_timing': 'advance'})
    warehouse.action_confirm()
    warehouse.action_register_installment()

    forklift = Lease.create({
        'partner_id': lessor.id, 'property_description': 'Montacargas eléctrico 2,5 t',
        'contract_ref': 'ARR-2026-03', 'date_start': date(2026, 11, 1), 'term_months': 24,
        'payment_amount': 1350.0, 'payment_timing': 'arrears', 'annual_rate': 10.5})
    forklift.action_compute()
    env.cr.commit()
    print('DEMO NIIF16:', [(l.name, l.state, l.liability_amount, l.rou_amount) for l in office | warehouse | forklift])
