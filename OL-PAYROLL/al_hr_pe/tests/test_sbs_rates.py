# -*- coding: utf-8 -*-
"""Tasas del SPP desde la tabla de la SBS (sin red: página guardada)."""
from pathlib import Path
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.al_hr_pe.services import sbs_spp

PAGE = (Path(__file__).parent / 'data'
        / 'sbs_comision_prima_202610.html').read_text(encoding='utf-8')


@tagged('post_install', '-at_install', 'al_hr_pe')
class TestSbsRates(TransactionCase):

    def test_parse_official_table(self):
        data = sbs_spp.parse_sbs_spp(PAGE)
        self.assertEqual(data['period'], '2026-10')
        self.assertEqual(set(data['afp']), set(sbs_spp.AFP_NAMES))
        self.assertEqual(data['afp']['PROFUTURO']['flow_commission'], 1.69)
        self.assertEqual(data['afp']['PRIMA']['prima_insurance'], 1.37)
        self.assertEqual(data['afp']['HABITAT']['insurable_remuneration'],
                         12732.70)

    def test_challenge_or_incomplete_page_is_rejected(self):
        stub = ('<html><head><script src="/_Incapsula_Resource?x=1">'
                '</script></head></html>')
        self.assertIsNone(sbs_spp.parse_sbs_spp(stub))
        # Una AFP menos: no se aplica nada a medias.
        broken = PAGE.replace('PROFUTURO', 'OTRA', 1)
        self.assertIsNone(sbs_spp.parse_sbs_spp(broken))

    def test_apply_updates_global_afps_only(self):
        Membership = self.env['hr.membership']
        prima = self.env.ref('al_hr_pe.membership_AFP_PRIMA')
        override = prima.copy({'company_id': self.env.company.id,
                               'fixed_commision': 9.0})
        jub = self.env.ref('al_hr_pe.membership_JUB_PROFUT_TRANSITO')
        jub_rate = jub.fixed_commision
        Membership._l10n_pe_apply_sbs_rates(sbs_spp.parse_sbs_spp(PAGE))
        self.assertEqual(prima.fixed_commision, 1.60)
        self.assertEqual(prima.insurable_remuneration, 12732.70)
        self.assertEqual(prima.l10n_pe_sbs_period, '2026-10')
        self.assertEqual(override.fixed_commision, 9.0,
                         'el override de la compañía no se toca')
        self.assertEqual(jub.fixed_commision, jub_rate)

    def test_cron_without_data_changes_nothing(self):
        prima = self.env.ref('al_hr_pe.membership_AFP_PRIMA')
        before = prima.insurable_remuneration
        with patch.object(sbs_spp, 'fetch_sbs_spp', return_value=None):
            self.env['hr.membership']._cron_l10n_pe_update_sbs_rates()
        self.assertEqual(prima.insurable_remuneration, before)
