# -*- coding: utf-8 -*-
"""Configuración principal de planillas: una por compañía, creada sola y
editable desde Ajustes ▸ Nómina ▸ Perú."""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMainParameterSettings(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Param = cls.env['hr.main.parameter']
        cls.company_a = cls.env.company
        cls.company_b = cls.env['res.company'].create({
            'name': 'Planillas B', 'country_id': cls.env.ref('base.pe').id})
        cls.env.user.company_ids |= cls.company_b

    def test_created_once_per_company(self):
        """Ya no se corta un flujo por «no se han creado los parámetros»:
        la primera lectura la crea y las siguientes devuelven la misma."""
        self.assertFalse(self.Param.search([('company_id', '=', self.company_b.id)]))
        param = self.Param.get_main_parameter(self.company_b)
        self.assertEqual(param.company_id, self.company_b)
        self.assertEqual(self.Param.get_main_parameter(self.company_b), param)
        self.assertEqual(self.company_b.l10n_pe_main_parameter_id, param)

    def test_settings_write_their_company(self):
        """Ajustes guarda en la configuración de la compañía activa y no
        toca la de otra."""
        partner = self.env['res.partner'].create({'name': 'Representante B'})
        param_a = self.Param.get_main_parameter(self.company_a)
        before_a = param_a.reprentante_legal_id
        settings = self.env['res.config.settings'].with_company(self.company_b).create({})
        settings.l10n_pe_payroll_legal_representative_id = partner
        settings.execute()
        self.assertEqual(self.Param.get_main_parameter(self.company_b).reprentante_legal_id, partner)
        self.assertEqual(param_a.reprentante_legal_id, before_a)

    def test_menu_opens_active_company_form(self):
        action = self.Param.with_company(self.company_b).action_open_main_parameter()
        self.assertEqual(action['view_mode'], 'form')
        self.assertEqual(self.Param.browse(action['res_id']).company_id, self.company_b)

    def test_settings_without_payroll_rights(self):
        """Los ajustes se abren también desde otras apps (inventario los crea
        al dar de alta un almacén): sin permisos de planillas no deben
        fallar por la configuración principal."""
        from odoo.tests import new_test_user
        user = new_test_user(self.env, login='ajustes_sin_nomina',
                             groups='base.group_system,base.group_user')
        self.assertFalse(self.env['hr.main.parameter'].with_user(user).has_access('read'))
        self.env['res.config.settings'].with_user(user).default_get([])
        self.env.company.with_user(user).l10n_pe_main_parameter_id
