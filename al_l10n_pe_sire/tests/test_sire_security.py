"""Seguridad del SIRE: credenciales, permisos de envío y multicompañía."""
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase

CREDENTIAL_FIELDS = (
    'l10n_pe_sire_sol_user', 'l10n_pe_sire_sol_password',
    'l10n_pe_sire_client_id', 'l10n_pe_sire_client_secret',
    'l10n_pe_sire_token', 'l10n_pe_sire_token_expiry',
)


@tagged('post_install', '-at_install')
class TestSireSecurity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.accountant = new_test_user(
            cls.env, login='sire_accountant', groups='account.group_account_user',
            company_id=cls.company.id)
        cls.auditor = new_test_user(
            cls.env, login='sire_auditor', groups='account.group_account_readonly',
            company_id=cls.company.id)
        # Periodo en un mes sin datos para no chocar con la unicidad.
        cls.rvie = cls.env['l10n_pe.sire.rvie'].create({
            'year': 2001, 'month': '01', 'company_id': cls.company.id})

    def test_credentials_are_admin_only(self):
        for name in CREDENTIAL_FIELDS:
            with self.subTest(field=name):
                self.assertEqual(
                    self.env['res.company']._fields[name].groups, 'base.group_system')
        with self.assertRaises(AccessError):
            self.company.with_user(self.accountant).read(['l10n_pe_sire_sol_password'])
        with self.assertRaises(AccessError):
            self.company.with_user(self.accountant).read(['l10n_pe_sire_token'])

    def test_readonly_user_cannot_talk_to_sunat(self):
        """El auditor puede ver el periodo, pero no aceptar ni enviar nada."""
        record = self.rvie.with_user(self.auditor)
        self.assertTrue(record.name, 'el auditor lee el periodo')
        with patch.object(type(self.rvie), '_sire_get_token', return_value='tok') as token, \
                patch.object(type(self.rvie), '_sire_accept_proposal', return_value='T') as accept:
            for method in ('action_accept_proposal', 'action_send_replacement',
                           'action_register_preliminary', 'action_request_proposal',
                           'action_check_ticket', 'action_download_proposal',
                           'action_check_submission'):
                with self.subTest(method=method), self.assertRaises(AccessError):
                    getattr(record, method)()
        token.assert_not_called()
        accept.assert_not_called()

    def test_periods_are_isolated_by_company(self):
        other = self.env['res.company'].create({'name': 'Otra compañía SIRE'})
        foreign = self.env['l10n_pe.sire.rvie'].create({
            'year': 2001, 'month': '01', 'company_id': other.id})
        visible = self.env['l10n_pe.sire.rvie'].with_user(self.accountant).search(
            [('id', 'in', (self.rvie | foreign).ids)])
        self.assertEqual(visible, self.rvie)
