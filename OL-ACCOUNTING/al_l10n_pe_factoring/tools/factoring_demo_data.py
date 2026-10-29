# -*- coding: utf-8 -*-
"""Datos de factoring para las capturas de la ficha (se ejecuta con ``odoo shell``).

Crea un factor, un cliente, un diario de ventas sin documentos electrónicos
(para que ningún cron envíe las facturas al OSE) y tres operaciones:

* FAC sin recurso con dos facturas, cedida y desembolsada;
* FAC con recurso con una factura, desembolsada y con intereses devengados;
* FAC en borrador con una factura.

Es idempotente: si el factor demo existe, no hace nada.
"""
from datetime import timedelta

from odoo import fields


def ruc(base10):
    """RUC con su dígito verificador (módulo 11 de SUNAT)."""
    total = sum(int(d) * w for d, w in zip(base10, (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)))
    return base10 + str((11 - total % 11) % 10)

company = env.company
Partner = env['res.partner']
if Partner.search([('name', '=', 'Factor Capital S.A.')], limit=1):
    print('Los datos de factoring ya existen.')
else:
    factor = Partner.create({'name': 'Factor Capital S.A.', 'vat': ruc('2060123456'), 'is_company': True,
                             'country_id': env.ref('base.pe').id})
    customer = Partner.create({'name': 'Inmobiliaria del Sur S.A.C.', 'vat': ruc('2060987654'),
                               'is_company': True, 'country_id': env.ref('base.pe').id})
    Journal = env['account.journal'].with_company(company)
    sale = Journal.create({'name': 'Ventas factoring', 'code': 'DFAC', 'type': 'sale',
                           'company_id': company.id, 'l10n_latam_use_documents': False})
    misc = Journal.search([('type', '=', 'general'), ('company_id', '=', company.id)], limit=1)
    bank = Journal.search([('type', '=', 'bank'), ('company_id', '=', company.id)], limit=1)
    income = env['account.account'].with_company(company).search([('account_type', '=', 'income')], limit=1)
    today = fields.Date.context_today(env.user)

    def invoice(amount, days_ago):
        move = env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': customer.id, 'journal_id': sale.id,
            'invoice_date': today - timedelta(days=days_ago),
            'invoice_date_due': today + timedelta(days=60 - days_ago),
            'invoice_line_ids': [(0, 0, {'name': 'Avance de obra', 'quantity': 1, 'price_unit': amount,
                                         'account_id': income.id, 'tax_ids': [(6, 0, [])]})]})
        move.action_post()
        return move

    def operation(invoices, modality, percent, contract):
        return env['l10n_pe.factoring'].create({
            'factor_id': factor.id, 'modality': modality, 'journal_id': misc.id,
            'currency_id': company.currency_id.id, 'default_advance_percent': percent,
            'contract_ref': contract,
            'line_ids': [(0, 0, {'move_id': inv.id, 'advance_percent': percent,
                                 'cavali_number': 'CAV-%s' % inv.id, 'cavali_date': today,
                                 'conformity_state': 'presumed',
                                 'conformity_date': inv.invoice_date + timedelta(days=8)})
                         for inv in invoices]})

    def wizard(op, kind, **vals):
        wiz = env['l10n_pe.factoring.wizard'].create(dict({
            'factoring_id': op.id, 'operation': kind, 'date': today, 'bank_journal_id': bank.id}, **vals))
        wiz.action_apply()

    op1 = operation(invoice(12000.0, 10) + invoice(8500.0, 5), 'without_recourse', 90.0, 'CT-2026-015')
    op1.action_assign()
    wizard(op1, 'disburse', interest_amount=245.0, fee_amount=120.0, expense_amount=35.0)

    op2 = operation(invoice(15000.0, 3), 'with_recourse', 85.0, 'CT-2026-016')
    op2.action_assign()
    wizard(op2, 'disburse', interest_amount=310.0, fee_amount=90.0)
    wizard(op2, 'accrue', amount=155.0)

    operation(invoice(6400.0, 1), 'without_recourse', 90.0, 'CT-2026-017')
    env.cr.commit()
    print('Factoring:', env['l10n_pe.factoring'].search([('factor_id', '=', factor.id)]).mapped(
        lambda o: (o.name, o.modality, o.state, o.net_amount)))

# Versión 8: contrato del factor con su cuenta, simulación de la operación en
# borrador y factura negociable con sus eventos. Idempotente.
factor = Partner.search([('name', '=', 'Factor Capital S.A.')], limit=1)
Contract = env['l10n_pe.factoring.contract']
if factor and not Contract.search([('factor_id', '=', factor.id)], limit=1):
    bank = env['l10n_pe.bank'].search([('name', 'ilike', 'Crédito')], limit=1) or env['l10n_pe.bank'].create(
        {'name': 'Banco de Crédito del Perú'})
    account = env['res.partner.bank'].create({
        'partner_id': factor.id, 'account_number': '193-2456789-0-12', 'l10n_pe_bank_id': bank.id,
        'currency_id': company.currency_id.id})
    contract = Contract.create({
        'name': 'Línea de factoring 2026', 'factor_id': factor.id, 'factor_bank_id': account.id,
        'modality': 'without_recourse', 'currency_id': company.currency_id.id,
        'date_start': fields.Date.context_today(env.user) - timedelta(days=60), 'advance_percent': 90.0,
        'annual_rate': 14.5, 'fee_percent': 0.4, 'fee_min': 60.0, 'expense_fixed': 15.0,
        'credit_limit': 100000.0, 'debtor_limit': 50000.0})
    operations = env['l10n_pe.factoring'].search([('factor_id', '=', factor.id)])
    operations.filtered(lambda o: o.modality == 'without_recourse').write({'contract_id': contract.id})
    draft = operations.filtered(lambda o: o.state == 'draft')[:1]
    if draft:
        draft.action_simulate()
    for move in operations.line_ids.move_id:
        if not move.l10n_pe_negotiable_event_ids:
            env['l10n_pe.negotiable.event'].create([
                {'move_id': move.id, 'event_type': 'presumed', 'date': move.l10n_pe_conformity_date
                 or move.invoice_date, 'source': 'cron'},
                {'move_id': move.id, 'event_type': 'registered', 'date': move.l10n_pe_cavali_date
                 or move.invoice_date, 'reference': move.l10n_pe_cavali_number, 'source': 'manual'},
            ])
    env.cr.commit()
    print('Factoring v8: contrato', contract.name, 'disponible', contract.available_amount)
