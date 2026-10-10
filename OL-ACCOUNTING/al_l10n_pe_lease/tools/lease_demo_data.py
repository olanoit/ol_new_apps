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

# ----------------------------------------------------------------------
# Versión 2: moneda extranjera, subcuentas del pasivo y remedición.
# ----------------------------------------------------------------------
lessor2_name = '%s Centro Comercial del Sur S.A.' % PREFIX
if Partner.search([('name', '=', lessor2_name)], limit=1):
    print('Los datos DEMO NIIF16 (v2) ya existen.')
else:
    from dateutil.relativedelta import relativedelta
    it_ruc = env.ref('l10n_pe.it_RUC', raise_if_not_found=False)
    lessor2 = Partner.create({'name': lessor2_name, 'vat': ruc('2061234598'), 'is_company': True,
                              'country_id': env.ref('base.pe').id,
                              'l10n_latam_identification_type_id': it_ruc.id if it_ruc else False})
    Lease = env['l10n_pe.lease']
    usd = env.ref('base.USD')
    usd.active = True
    shop = Lease.create({
        'partner_id': lessor2.id, 'property_description': 'Local comercial Av. Larco 1020 (en dólares)',
        'contract_ref': 'ARR-2026-04', 'currency_id': usd.id, 'date_start': date(2026, 1, 1),
        'term_months': 36, 'payment_amount': 2000.0, 'payment_timing': 'advance', 'annual_rate': 8.0})
    shop.action_create_liability_accounts()
    shop.action_confirm()
    shop._exchange_difference(date(2026, 9, 30))

    depot = Lease.create({
        'partner_id': lessor2.id, 'property_description': 'Depósito Ate (reajuste anual)',
        'contract_ref': 'ARR-2026-05', 'date_start': date(2026, 1, 1), 'term_months': 36,
        'payment_amount': 3000.0, 'payment_timing': 'advance', 'annual_rate': 12.0})
    depot.action_create_liability_accounts()
    depot.action_confirm()
    env['l10n_pe.lease.remeasure'].with_context(default_lease_id=depot.id).create({
        'date': date(2026, 10, 1), 'payment_amount': 3300.0, 'remaining_months': 27,
        'annual_rate': 12.0, 'reason': 'Reajuste anual de la renta (10 %)'}).action_apply()
    env.cr.commit()
    print('DEMO NIIF16 v2:', [(l.name, l.state, l.currency_id.name, l.liability_amount) for l in shop | depot])


# Facturas del arrendador del depósito, enero a octubre, publicadas en un diario
# de compras sin documentos electrónicos (ningún cron las envía).
depot = env['l10n_pe.lease'].search([('contract_ref', '=', 'ARR-2026-05')], limit=1)
if depot and not depot._vendor_bills().filtered(lambda m: m.state == 'posted'):
    company = depot.company_id
    journal = env['account.journal'].search([('code', '=', 'DNIF'), ('company_id', '=', company.id)], limit=1) \
        or env['account.journal'].create({'name': '%s Compras' % PREFIX, 'code': 'DNIF', 'type': 'purchase',
                                          'company_id': company.id, 'l10n_latam_use_documents': False})
    for _i in range(10):
        bill = env['account.move'].browse(depot.action_register_installment()['res_id'])
        bill.journal_id = journal
        bill.action_post()
    env.cr.commit()
    print('DEMO NIIF16: 10 facturas del depósito publicadas')
