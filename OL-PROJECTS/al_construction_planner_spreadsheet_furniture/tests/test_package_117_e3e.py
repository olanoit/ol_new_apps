# -*- coding: utf-8 -*-
"""Paquete 1.17, entrega 3, bloque e. M117-22: traer la venta a la planificación."""
import json

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import HttpCase, TransactionCase, tagged

from .test_package_117_e3b import SaleSheetCommon, _summary


def _full_summary(**values):
    typology = {
        'code': 'C01', 'name': 'Cocina dpto 201', 'partida': 'Cocina', 'ml_low': 4.33,
        'ml_high': 4.24, 'price': 5725.65, 'spaces': 16, 'lines': [],
        'departments': '201 al 1701 (posición 01)'}
    rough = {'code': 'C02', 'name': 'Cocina gruesa', 'partida': 'Cocina', 'ml_low': 0,
             'ml_high': 0, 'price': 7776.0, 'spaces': 16, 'lines': []}
    summary = _summary(
        obra={'Cliente': 'Inmobiliaria', 'Adelanto %': 30, 'Fondo de garantía %': 5,
              'Inicio': '2026-12-01', 'Fin': '2027-06-30'},
        typologies=[typology, rough],
        building=[
            {'group': '', 'from': 2, 'to': 17, 'position': 1, 'duplex': '',
             'unit_type': 'Departamento', 'space': 'Cocina', 'typology': 'C01'},
            {'group': '', 'from': 17, 'to': 17, 'position': 2, 'duplex': 2,
             'unit_type': 'Departamento', 'space': 'Closet adicional', 'typology': 'CL05'},
            {'group': '', 'from': 'Azotea', 'to': 'Azotea', 'position': 1, 'duplex': '',
             'unit_type': 'Departamento', 'space': 'Baño', 'typology': 'C01'},
        ],
        finishes=[{'code': 'R02', 'description': 'Frentes', 'kind': 'Color RH', 'material': 'Rovere'}],
        sold=[{'typology': 'C01', 'partida': 'Cocina', 'group': 'Mueble alto', 'ml': 4.24,
               'structure': 'R04', 'fronts': 'R02', 'price': 5725.65, 'spaces': 16,
               'departments': '201 al 1701'}],
        dpto_factor=100, pisos_nombre='Azotea=AZ;Sótano=SO')
    summary.update(values)
    return summary


class BringCommon(SaleSheetCommon):

    @classmethod
    def _setup_bring(cls):
        cls._setup_quote()
        env = cls.env
        cls.order.order_line.unlink()
        env.company.construction_sale_partida_product_id = env['product.product'].create(
            {'name': 'Mobiliario por partida (test)', 'type': 'service'})
        env.company.construction_sale_milestone_template = 'Hitos 80/15/5'
        cls.order.action_construction_open_spreadsheet()
        cls.order.construction_sale_pass(_full_summary())
        cls.order.action_confirm()
        cls.site = env['project.project'].create({
            'name': 'Obra vendida (test 1.17)', 'is_construction_site': True,
            'construction_profile_id': cls.furniture.id,
            'construction_sale_order_id': cls.order.id, 'construction_spreadsheet_rows': 30})
        cls.site.action_construction_open_spreadsheet()
        cls.document = env['documents.document'].search(
            [('construction_project_id', '=', cls.site.id)])


@tagged('post_install', '-at_install')
class TestPackage117Bring(BringCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_bring()

    def _tab(self, name):
        tab = self.document.construction_sale_bring()['tabs'][name]
        return [dict(zip(tab['keys'], row)) for row in tab['rows']]

    def test_tree_expands_the_ranges(self):
        rows = self._tab('ARBOL')
        c01 = [row for row in rows if row['typology'] == 'C01' and row['floor'].startswith('Piso')]
        self.assertEqual(len(c01), 16)
        self.assertEqual((c01[0]['floor'], c01[0]['apartment']), ('Piso 02', 'Dpto 201'))
        self.assertEqual((c01[-1]['floor'], c01[-1]['apartment']), ('Piso 17', 'Dpto 1701'))
        duplex = next(row for row in rows if row['typology'] == 'CL05')
        self.assertEqual((duplex['floor'], duplex['apartment'], duplex['unit_type']),
                         ('Piso 18', 'Dpto 1702', 'Nivel de dúplex'))
        roof = next(row for row in rows if row['floor'] == 'Azotea')
        self.assertEqual(roof['apartment'], 'Dpto AZ01')

    def test_typologies_price_and_contract(self):
        typologies = {row['code']: row for row in self._tab('TIPOLOGIAS')}
        self.assertEqual((typologies['C01']['ml_low'], typologies['C01']['ml_high']),
                         ('4.33', '4.24'))
        self.assertEqual(typologies['C02']['ml_low'], '', 'la gruesa pasa sin ML')
        prices = {row['typology']: row['price'] for row in self._tab('VENTA')}
        self.assertEqual(prices, {'C01': '5725.65', 'C02': '7776.0'})
        contract = self._tab('CONTRATOS')[0]
        self.assertEqual((contract['advance'], contract['guarantee'], contract['discount_factor']),
                         ('30', '5', '1.000000'))
        self.assertEqual(contract['milestone_template'], 'Hitos 80/15/5')

    def test_discount_goes_in_the_factor_and_not_in_the_price(self):
        self.order.construction_sale_summary = json.dumps(_full_summary(discount=10000))
        contract = self._tab('CONTRATOS')[0]
        self.assertEqual(contract['discount_factor'], '%.6f' % (1 - 10000 / 245818.40))
        self.assertEqual({row['price'] for row in self._tab('VENTA')}, {'5725.65', '7776.0'})

    def test_prices_with_tax_are_divided(self):
        self.order.construction_sale_summary = json.dumps(_full_summary(prices_without_tax=False))
        prices = {row['typology']: float(row['price']) for row in self._tab('VENTA')}
        self.assertAlmostEqual(prices['C01'], 5725.65 / 1.18, places=4)

    def test_warns_what_is_not_ready(self):
        self.assertIn('CL05 sin metrado', self.document.construction_sale_bring()['warnings'])

    def test_metadata_asks_to_bring_once(self):
        metadata = self.document._get_spreadsheet_metadata()
        self.assertTrue(metadata['construction_sale_bring_pending'])
        self.document.construction_sale_bring_done('N1')
        metadata = self.document._get_spreadsheet_metadata()
        self.assertFalse(metadata['construction_sale_bring_pending'])
        self.assertTrue(metadata['construction_sale_available'])

    def test_no_awarded_sale_has_nothing_to_bring(self):
        site = self.env['project.project'].create(
            {'name': 'Obra sin venta (test)', 'is_construction_site': True})
        site.action_construction_open_spreadsheet()
        document = self.env['documents.document'].search([('construction_project_id', '=', site.id)])
        self.assertFalse(document._get_spreadsheet_metadata()['construction_sale_bring_pending'])
        with self.assertRaises(UserError):
            document.construction_sale_bring()

    def test_template_has_the_new_tabs(self):
        data = self.site._construction_spreadsheet_data(10)
        names = [sheet['name'] for sheet in data['sheets']]
        self.assertLess(names.index('ACABADOS DE OBRA'), names.index('TIPOLOGIAS'))
        self.assertLess(names.index('VENDIDO'), names.index('FICHA'))
        hidden = next(sheet for sheet in data['sheets'] if sheet['name'] == '_HUELLA')
        self.assertFalse(hidden['isVisible'])
        obra = next(sheet for sheet in data['sheets'] if sheet['name'] == 'OBRA')['cells']
        self.assertEqual(obra['A9'], 'Venta traída el')
        self.assertEqual(obra['A13'], 'Departamentos vendidos')

    def test_price_different_from_sold_warns(self):
        issues = self.document._construction_sold_issues({
            'VENDIDO': [['Tipología'] + [''] * 6, ['C01', '', '', '', '', '', 5725.65]],
            'VENTA': [['Contrato', 'Tipología', 'Precio'], ['V', 'C01', 5000]]})
        self.assertEqual(issues[0][4], 'warning')
        self.assertIn('precio distinto del vendido', issues[0][3])

    def test_activity_when_awarded(self):
        self.order.write({'state': 'draft'})
        self.order.action_confirm()
        self.assertIn('Obra adjudicada: crear la hoja de planificación',
                      self.site.activity_ids.mapped('summary'))

    def test_send_keeps_advance_of_an_existing_contract(self):
        contract = self.env['construction.contract'].create({
            'name': 'Venta A', 'project_id': self.site.id, 'partner_id': self.partner_company.id,
            'advance_pct': 30.0, 'guarantee_pct': 5.0})
        wizard = self.env['construction.master.import.wizard'].create(
            {'project_id': self.site.id, 'filename': 'x.xlsx'})
        wizard._apply_contracts({'contracts': [{
            'name': 'Venta A', 'partner': self.partner_company.name, 'advance': '',
            'guarantee': None, 'discount_factor': '0.959319'}], 'prices': [], 'milestones': []})
        self.assertEqual((contract.advance_pct, contract.guarantee_pct), (30.0, 5.0))
        self.assertEqual(contract.discount_factor, 0.959319)


    def test_pieces_without_board_are_listed(self):
        issues = self.document._construction_sold_issues({
            'VENDIDO': [['Tipología'] + [''] * 6, ['C01', '', '', '', '', '', 5725.65]],
            'PIEZAS': [['typology', 'product_name'], ['C01', ''], ['C01', 'Tablero']]})
        self.assertEqual([(issue[0], issue[1]) for issue in issues], [('PIEZAS', 2)])
        many = {'VENDIDO': [['T'] + [''] * 6, ['C01', '', '', '', '', '', 1]],
                'PIEZAS': [['typology', 'product_name']] + [['C01', '']] * 205}
        issues = self.document._construction_sold_issues(many)
        self.assertEqual(len(issues), 201)
        self.assertIn('y 5 más', issues[-1][3])

    def test_bring_writes_the_control_figures(self):
        self.order.construction_sale_summary = json.dumps(_full_summary(departments_total=16))
        rows = dict(tuple(row) for row in self.document.construction_sale_bring()['tabs']['OBRA']['rows'])
        self.assertEqual(rows['Departamentos vendidos'], '16')
        self.assertEqual(rows['Subtotal de la cotización'], '245818.4')
        self.assertEqual(rows['Inicio de la venta'], '2026-12-01')

    def test_control_and_card_have_the_sold_figures(self):
        data = self.site._construction_spreadsheet_data(10)
        sheets = {sheet['name']: sheet['cells'] for sheet in data['sheets']}
        self.assertIn('Subtotal de la cotización', sheets['CONTROL']['Z3'])
        self.assertIn('Departamentos vendidos', sheets['CONTROL']['Z5'])
        self.assertEqual(sheets['FICHA']['A23'], 'ML vendidos')
        self.assertIn('Traer la venta', sheets['INICIO']['A12'])
        self.assertIn('Validar y enviar', sheets['INICIO']['A19'])
        self.assertIn('parter' if False else 'res.partner',
                      {item['model'] for item in data['lists'].values()})

    def test_marks_of_contracts_sale_and_obra(self):
        layout = self.site._construction_sheet_layout()
        parts = self.site._construction_row_parts(layout, 2, 5)
        self.assertTrue(any('empty' in cf['id'] for cf in parts['CONTRATOS']['conditional']))
        self.assertTrue(any('sold' in cf['id'] for cf in parts['VENTA']['conditional']))
        self.assertTrue(any('dates' in cf['id'] for cf in parts['OBRA']['conditional']))

    def test_duplicated_quote_offers_to_copy_the_sheet(self):
        origin_sheet = self.order._construction_sale_sheet()
        copy = self.order.copy()
        self.assertEqual(copy.construction_copied_from_id, self.order)
        self.assertFalse(copy.construction_sale_summary)
        action = copy.action_construction_open_spreadsheet()
        self.assertEqual(action['res_model'], 'construction.sale.sheet.copy.wizard')
        wizard = self.env[action['res_model']].browse(action['res_id'])
        opened = wizard.action_copy()
        document = self.env['documents.document'].browse(opened['params']['spreadsheet_id'])
        self.assertNotEqual(document, origin_sheet)
        self.assertEqual(document.construction_sale_order_id, copy)
        self.assertEqual(document.construction_sale_phase, 'in_progress')
        self.assertEqual(copy._construction_sale_sheet(), document)

    def test_duplicated_quote_can_start_a_new_sheet(self):
        copy = self.order.copy()
        action = copy.action_construction_open_spreadsheet()
        opened = self.env[action['res_model']].browse(action['res_id']).action_new()
        document = self.env['documents.document'].browse(opened['params']['spreadsheet_id'])
        self.assertEqual(document.construction_sale_order_id, copy)

    def test_add_rows_keeps_the_data(self):
        document = self.order._construction_sale_sheet().sudo(False)
        self.assertEqual(document.construction_sheet_rows, 300)
        document.construction_sale_add_rows({'master': {}, 'other': {
            'METRADO': {'cells': {'A2': 'C01', 'E2': '=1.27+1.27'}}}})
        self.assertEqual(document.construction_sheet_rows, 600)
        data = json.loads(document.with_context(bin_size=False).spreadsheet_data)
        cells = next(sheet for sheet in data['sheets'] if sheet['name'] == 'METRADO')['cells']
        self.assertEqual(cells['E2'], '=1.27+1.27')
        self.assertIn('N601', cells)


@tagged('post_install', '-at_install')
class TestPackage117BringTour(BringCommon, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_bring()

    def setUp(self):
        super().setUp()
        # Los datos del test son de la compañía del entorno; la base puede
        # tener al administrador en otra (y el navegador abriría sus datos).
        self.env.ref('base.user_admin').write({
            'company_ids': [Command.link(self.env.company.id)],
            'company_id': self.env.company.id})

    def test_sheet_is_born_with_the_sale(self):
        self.start_tour('/odoo', 'al_construction_bring_sale', login='admin')
        self.assertEqual(self.document.construction_sale_brought, 'N1')


@tagged('post_install', '-at_install')
class TestPackage117SaleReopenTour(SaleSheetCommon, HttpCase):

    def test_version_and_changed_quote_on_open(self):
        self._setup_quote()
        self.order.order_line.unlink()
        self.env.company.construction_sale_partida_product_id = self.env['product.product'].create(
            {'name': 'Mobiliario por partida (test)', 'type': 'service'})
        action = self.order.action_construction_open_spreadsheet()
        document = self.env['documents.document'].browse(action['params']['spreadsheet_id'])
        self.order.construction_sale_pass(_full_summary())
        self.order.action_quotation_sent()
        document.construction_sale_new_version()
        self.order.client_order_ref = 'Proyecto cambiado'
        self.start_tour('/odoo', 'al_construction_sale_reopen', login='admin')
        self.assertFalse(document.construction_sale_pending)
