# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import Command, api, fields, models


class AlPeDemo(models.AbstractModel):
    _inherit = 'al.pe.demo'

    @api.model
    def _load_demo_fourth_category(self):
        """Dos prestadores y tres recibos por honorarios pagados: uno con
        retención (S/ 2 000), uno bajo el tope (S/ 1 200) y uno sin retención
        por la constancia de suspensión del prestador (S/ 5 000)."""
        company = self._demo_company()
        if not company or self._demo_ref('al_l10n_pe_fourth_category.demo_receipt_3'):
            return
        env = self._demo_env(company)
        Journal = env['account.journal']
        journal = Journal.search([*Journal._check_company_domain(company), ('type', '=', 'purchase'),
                                  ('l10n_latam_use_documents', '=', True)], limit=1)
        bank = self._demo_bank_journal(env)
        if not journal or not bank:
            return
        company.l10n_pe_fourth_category_agent = True
        today = fields.Date.context_today(self)
        day, paid_on = today - timedelta(days=7), today - timedelta(days=2)
        quispe = self._demo_partner(env, 'al_l10n_pe_fourth_category.demo_provider_quispe',
                                    'DEMO 4TA Quispe Rojas Ana', self._demo_ruc('1047382956'), is_company=False)
        torres = self._demo_partner(env, 'al_l10n_pe_fourth_category.demo_provider_torres',
                                    'DEMO 4TA Torres Paz Luis', self._demo_ruc('1041122334'), is_company=False)
        self._demo_record('al_l10n_pe_fourth_category.demo_suspension', env['l10n_pe.fourth.category.suspension'], {
            'partner_id': torres.id, 'number': '1609-%s-000184' % str(today.year)[2:],
            'date_issued': today.replace(month=1, day=15),
            'note': 'Constancia entregada por el prestador (demostración).'})
        for key, partner, number, amount, concept in (
                ('1', quispe, 'E001-58', 2000.0, 'Asesoría contable del mes'),
                ('2', quispe, 'E001-59', 1200.0, 'Capacitación al personal'),
                ('3', torres, 'E001-12', 5000.0, 'Diseño de la campaña publicitaria')):
            move = self._demo_record('al_l10n_pe_fourth_category.demo_receipt_%s' % key, env['account.move'], {
                'move_type': 'in_invoice', 'partner_id': partner.id, 'journal_id': journal.id,
                'invoice_date': day, 'date': day,
                'l10n_latam_document_type_id': env.ref('l10n_pe.document_type03').id,
                'l10n_latam_document_number': number,
                'invoice_line_ids': [Command.create({'name': concept, 'quantity': 1, 'price_unit': amount,
                                                     'tax_ids': [Command.clear()]})],
            })
            if move.state == 'draft':
                move.action_post()
            if move.payment_state == 'not_paid':
                env['account.payment.register'].with_context(
                    active_model='account.move', active_ids=move.ids).create({
                        'payment_date': paid_on, 'journal_id': bank.id})._create_payments()
