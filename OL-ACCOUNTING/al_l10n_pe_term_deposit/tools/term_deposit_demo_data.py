# -*- coding: utf-8 -*-
"""Datos «DEMO DEP» para las capturas de la ficha (se ejecuta con ``odoo shell``).

Crea un banco y un arrendador y cuatro registros:

* depósito a plazo vigente con dos meses de intereses devengados;
* depósito a plazo por vencer (dentro del aviso);
* fondo en garantía de una carta fianza;
* depósito en garantía del alquiler de un almacén, liberado en parte.

Es idempotente: si el banco demo existe, no hace nada.
"""
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import fields

PREFIX = 'DEMO DEP'


def ruc(base10):
    """RUC con su dígito verificador (módulo 11 de SUNAT)."""
    total = sum(int(d) * w for d, w in zip(base10, (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)))
    return base10 + str((11 - total % 11) % 10)


company = env.company
Partner = env['res.partner']
if Partner.search([('name', '=', '%s Banco Andino S.A.' % PREFIX)], limit=1):
    print('Los datos DEMO DEP ya existen.')
else:
    it_ruc = env.ref('l10n_pe.it_RUC', raise_if_not_found=False)
    common = {'is_company': True, 'country_id': env.ref('base.pe').id,
              'l10n_latam_identification_type_id': it_ruc.id if it_ruc else False}
    bank = Partner.create(dict(common, name='%s Banco Andino S.A.' % PREFIX, vat=ruc('2061112223')))
    landlord = Partner.create(dict(common, name='%s Inmuebles Lurín S.A.C.' % PREFIX, vat=ruc('2061445556')))
    Journal = env['account.journal'].with_company(company)
    bank_journal = Journal.search([('type', '=', 'bank'), ('company_id', '=', company.id)], limit=1)
    misc = Journal.search([('type', '=', 'general'), ('company_id', '=', company.id)], limit=1)
    today = fields.Date.context_today(env.user)
    Deposit = env['l10n_pe.term.deposit']
    base = {'journal_id': bank_journal.id, 'misc_journal_id': misc.id, 'day_basis': '360'}

    d1 = Deposit.create(dict(base, partner_id=bank.id, reference='CDP-001245', amount=250000.0, rate=5.75,
                             date_start=today - relativedelta(months=2, days=5), term_days=360,
                             capitalize_interest=True))
    d1.action_open()
    d1._l10n_pe_accrue(today.replace(day=1) - timedelta(days=1))

    d2 = Deposit.create(dict(base, partner_id=bank.id, reference='CDP-001198', amount=80000.0, rate=5.2,
                             date_start=today - timedelta(days=85), term_days=90, auto_renew=True))
    d2.action_open()
    d2._l10n_pe_accrue(today)

    d3 = Deposit.create(dict(base, deposit_type='guarantee_fund', partner_id=bank.id,
                             reference='Carta fianza CF-2026-031', amount=45000.0, rate=1.5,
                             date_start=today - relativedelta(months=1), term_days=365))
    d3.action_open()

    d4 = Deposit.create(dict(base, deposit_type='guarantee_given', partner_id=landlord.id,
                             reference='Contrato de alquiler almacén Lurín', amount=18000.0, rate=0.0,
                             date_start=today - relativedelta(months=8), term_days=0))
    d4.action_open()
    d4._l10n_pe_release(today - relativedelta(months=1), 6000.0)

    Deposit.search([('partner_id', 'in', (bank | landlord).ids)])._cron_l10n_pe_term_deposits()
    env.cr.commit()
    print('DEMO DEP:', Deposit.search([('partner_id', 'in', (bank | landlord).ids)]).mapped(
        lambda d: (d.id, d.name, d.deposit_type, d.state, d.remaining_amount, d.interest_accrued)))
