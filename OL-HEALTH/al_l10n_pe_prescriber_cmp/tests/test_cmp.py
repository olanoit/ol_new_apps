# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.al_l10n_pe_prescriber_cmp.models import cmp_client

SEARCH_PAGE = """<html><body><table border="1">
<tr><th></th><th>CMP</th><th>Ap. paterno</th><th>Ap. materno</th><th>Nombres</th></tr>
<tr><td><a href="datos-colegiado-detallado.php?id=AbC123">Ver</a></td><td>045678</td>
<td>SALAZAR</td><td>PEREZ</td><td>JORGE LUIS</td></tr>
</table></body></html>"""

DETAIL_PAGE = """<html><body>
<table border="1"><tr><td>045678</td><td>SALAZAR PEREZ</td><td>JORGE LUIS</td></tr></table>
<table border="1"><tr><td>HÁBIL</td></tr></table>
<table border="1"><tr><td></td><td></td><td></td><td><img src="fotos/045678.jpg"/></td>
<td>jsalazar@correo.pe</td><td>CONSEJO REGIONAL III - LIMA</td></tr></table>
<table border="1"><tr><th>Especialidad</th><th>Tipo</th><th>Código</th><th>Fecha</th></tr>
<tr><td>PEDIATRÍA</td><td>RNE</td><td>12345</td><td>01/01/2010</td></tr></table>
</body></html>"""


def _session(search=SEARCH_PAGE, detail=DETAIL_PAGE):
    session = MagicMock()
    session.post.return_value = MagicMock(text=search, raise_for_status=lambda: None)
    session.get.return_value = MagicMock(text=detail, raise_for_status=lambda: None)
    return session


@tagged('post_install', '-at_install')
class TestCmp(TransactionCase):

    def test_status_parsing_inhabil_is_not_habil(self):
        self.assertEqual(cmp_client.parse_status('HÁBIL'), 'enabled')
        self.assertEqual(cmp_client.parse_status('INHÁBIL'), 'disabled')
        self.assertEqual(cmp_client.parse_status('inhabil por deuda'), 'disabled')
        self.assertFalse(cmp_client.parse_status(''))

    def test_fetch_parses_search_and_detail(self):
        data = cmp_client.fetch('045678', session=_session())
        self.assertEqual(data['code'], '045678')
        self.assertEqual(data['first_name'], 'JORGE LUIS')
        self.assertEqual(data['last_name'], 'SALAZAR PEREZ')
        self.assertEqual(data['status'], 'enabled')
        self.assertEqual(data['specialties'], ['PEDIATRÍA'])
        self.assertIn('LIMA', data['council'])

    def test_fetch_without_results(self):
        self.assertIsNone(cmp_client.fetch('999999', session=_session(search='<html></html>')))

    def test_partner_button_updates_prescriber(self):
        partner = self.env['res.partner'].create({
            'name': 'Médico', 'pharmacy_is_prescriber': True, 'pharmacy_profession': 'physician',
            'pharmacy_prescriber_license': '045678'})
        with patch.object(cmp_client.requests, 'Session', return_value=_session()):
            partner.action_pharmacy_check_cmp()
        self.assertEqual(partner.name, 'Jorge Luis Salazar Perez')
        self.assertEqual(partner.pharmacy_prescriber_status, 'enabled')
        self.assertEqual(partner.pharmacy_specialty, 'PEDIATRÍA')
        self.assertTrue(partner.pharmacy_prescriber_checked)

    def test_connection_error_is_user_error(self):
        partner = self.env['res.partner'].create({
            'name': 'Médico', 'pharmacy_is_prescriber': True,
            'pharmacy_prescriber_license': '045678'})
        session = MagicMock()
        session.get.side_effect = cmp_client.requests.ConnectionError('sin red')
        with patch.object(cmp_client.requests, 'Session', return_value=session), \
                self.assertRaises(UserError):
            partner.action_pharmacy_check_cmp()
