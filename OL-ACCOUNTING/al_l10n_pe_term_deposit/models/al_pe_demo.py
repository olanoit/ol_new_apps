# -*- coding: utf-8 -*-
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class AlPeDemo(models.AbstractModel):
    _inherit = 'al.pe.demo'

    @api.model
    def _load_demo_term_deposit(self):
        """Un depósito a plazo vigente con intereses devengados, otro por
        vencer, el fondo en garantía de una carta fianza y el depósito en
        garantía de un alquiler liberado en parte."""
        company = self._demo_company()
        if not company or self._demo_ref('al_l10n_pe_term_deposit.demo_deposit_4'):
            return
        env = self._demo_env(company)
        Journal = env['account.journal']
        bank_journal = self._demo_bank_journal(env)
        misc = Journal.search([*Journal._check_company_domain(company), ('type', '=', 'general')], limit=1)
        if not bank_journal or not misc:
            return
        bank = self._demo_partner(env, 'al_l10n_pe_term_deposit.demo_bank', 'Banco Andino S.A.',
                                  self._demo_ruc('2061112223'))
        landlord = self._demo_partner(env, 'al_l10n_pe_term_deposit.demo_landlord',
                                      'Inmuebles Lurín S.A.C.', self._demo_ruc('2061445556'))
        entity = self._demo_partner(env, 'al_l10n_pe_term_deposit.demo_entity', 'Proyecto Especial Vial',
                                    self._demo_ruc('2061778889'))
        today = fields.Date.context_today(self)
        Deposit = env['l10n_pe.term.deposit']
        base = {'journal_id': bank_journal.id, 'misc_journal_id': misc.id, 'day_basis': '360'}

        def deposit(key, **vals):
            return self._demo_record('al_l10n_pe_term_deposit.demo_deposit_%s' % key, Deposit, dict(base, **vals))

        d1 = deposit('1', partner_id=bank.id, reference='CDP-001245', amount=250000.0, rate=5.75,
                     date_start=today - relativedelta(months=2, days=5), term_days=360, capitalize_interest=True)
        d1.action_open()
        d1._l10n_pe_accrue(today.replace(day=1) - timedelta(days=1))
        d2 = deposit('2', partner_id=bank.id, reference='CDP-001198', amount=80000.0, rate=5.2,
                     date_start=today - timedelta(days=85), term_days=90, auto_renew=True)
        d2.action_open()
        d2._l10n_pe_accrue(today)
        d3 = deposit('3', deposit_type='guarantee_fund', partner_id=bank.id,
                     reference='Carta fianza CF-%s-031' % today.year, amount=45000.0, rate=1.5,
                     date_start=today - relativedelta(months=1), term_days=365, guarantee_purpose='bond',
                     guarantee_beneficiary_id=entity.id,
                     guarantee_reference='Licitación LP-014-%s (fiel cumplimiento)' % today.year,
                     guarantee_date_end=today + relativedelta(months=11))
        d3.action_open()
        d4 = deposit('4', deposit_type='guarantee_given', partner_id=landlord.id,
                     reference='Contrato de alquiler almacén Lurín', amount=18000.0, rate=0.0,
                     date_start=today - relativedelta(months=8), term_days=0, guarantee_purpose='lease',
                     guarantee_beneficiary_id=landlord.id,
                     guarantee_reference='Contrato de arrendamiento ALQ-%s-003' % today.year,
                     guarantee_date_end=today + relativedelta(months=16))
        d4.action_open()
        d4._l10n_pe_release(today - relativedelta(months=1), 6000.0)
        (d1 | d2 | d3 | d4)._cron_l10n_pe_term_deposits()
