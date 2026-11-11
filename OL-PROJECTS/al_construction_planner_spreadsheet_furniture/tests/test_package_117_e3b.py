# -*- coding: utf-8 -*-
"""Paquete 1.17, entrega 3, bloque b. M117-16 a M117-20: la hoja de venta."""
import json

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import HttpCase, TransactionCase, tagged

from ..models.sale_sheet import (
    OBRA_ROW, SALE_COLUMNS, SALE_SHEET_ORDER, letter_of,
)
from .test_package_116_stage4b import _book


class SaleSheetCommon:

    @classmethod
    def _setup_quote(cls):
        env = cls.env
        cls.company = env.company
        cls.furniture = env['construction.vertical.profile'].create({
            'name': 'Mobiliario hoja de venta (test)', 'code': 'sale_sheet_test',
            'level_template_id': env['construction.level.template'].create(
                {'name': 'Plantilla hoja de venta (test)'}).id,
            'construction_spreadsheet_kind': 'furniture'})
        cls.company.construction_profile_id = cls.furniture
        cls.company.account_sale_tax_id = env['account.tax'].create(
            {'name': 'IGV 18 (test 1.17)', 'amount': 18.0, 'type_tax_use': 'sale'})
        cls.partner_company = env['res.partner'].create(
            {'name': 'Inmobiliaria 1.17 (test)', 'is_company': True})
        cls.contact = env['res.partner'].create(
            {'name': 'Contacto 1.17 (test)', 'parent_id': cls.partner_company.id})
        cls.service = env['product.product'].create(
            {'name': 'Mobiliario (test 1.17)', 'type': 'service'})
        cls.order = env['sale.order'].create({
            'partner_id': cls.contact.id, 'client_order_ref': 'Edificio 1.17',
            'order_line': [Command.create({'product_id': cls.service.id})]})


@tagged('post_install', '-at_install')
class TestPackage117SaleSheet(SaleSheetCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_quote()

    def _document(self, order=None):
        order = order or self.order
        action = order.action_construction_open_spreadsheet()
        return self.env['documents.document'].browse(action['params']['spreadsheet_id'])

    def _data(self, document):
        return json.loads(document.with_context(bin_size=False).spreadsheet_data)

    def _sheet(self, data, name):
        return next(sheet for sheet in data['sheets'] if sheet['name'] == name)

    def test_quote_with_furniture_profile_creates_the_sale_sheet(self):
        document = self._document()
        self.assertEqual(document.construction_sheet_kind, 'sale')
        self.assertFalse(document.construction_project_id, 'no necesita obra')
        self.assertEqual(document.construction_sale_phase, 'in_progress')
        self.assertEqual(document.construction_sale_order_id, self.order)
        self.assertEqual(self._document(), document, 'la segunda vez la abre')
        names = [sheet['name'] for sheet in self._data(document)['sheets']]
        self.assertEqual(names, list(SALE_SHEET_ORDER))

    def test_other_profile_keeps_the_budget_sheet(self):
        self.furniture.construction_spreadsheet_kind = 'budget'
        document = self._document()
        self.assertEqual(document.construction_sheet_kind, 'budget')

    def test_obra_comes_from_the_quote(self):
        cells = self._sheet(self._data(self._document()), 'OBRA')['cells']
        value = lambda name: cells.get('B%s' % OBRA_ROW[name])
        self.assertEqual(value('Proyecto'), 'Edificio 1.17')
        self.assertEqual(value('Código de cotización'), self.order.name)
        self.assertEqual(value('Cliente'), 'Inmobiliaria 1.17 (test)')
        self.assertEqual(value('Solicitante'), 'Contacto 1.17 (test)')
        self.assertEqual(value('Versión de la cotización'), 'N1')

    def test_parameters_of_the_sale_sheet(self):
        data = self._data(self._document())
        cells = self._sheet(data, 'PARAMETROS')['cells']
        keys = {value: ref[1:] for ref, value in cells.items()
                if ref.startswith('G') and ref != 'G1'}
        self.assertEqual(cells['C%s' % keys['moneda']], self.order.currency_id.name)
        self.assertEqual(cells['C%s' % keys['redondeo_multiplo']], '5')
        self.assertEqual(cells['C%s' % keys['rec_color_rh']], '0.4')
        self.assertNotIn('cond_generales', keys, 'los textos no van en la pestaña')
        text = json.dumps(self._sheet(data, 'PRECIOS')['cells'])
        for number in ('0.18', '1.8'):
            self.assertNotIn(number, text)
        self.assertIn('redondeo_multiplo', text)

    def test_design_of_the_tabs(self):
        data = self._data(self._document())
        prices = self._sheet(data, 'PRECIOS')
        self.assertEqual(prices['panes']['xSplit'], 3)
        self.assertEqual(prices['color'], '#FFDC00')
        self.assertTrue(prices['tables'][0]['config']['hasFilters'])
        self.assertFalse(self._sheet(data, 'METRADO')['tables'][0]['config']['hasFilters'])
        self.assertFalse(self._sheet(data, 'EDIFICIO')['tables'][0]['config']['hasFilters'])
        self.assertTrue(prices['cols'][str(len(SALE_COLUMNS['PRECIOS']) - 1)]['isHidden'])
        self.assertEqual(letter_of('METRADO', 'subtotal'), 'N')
        self.assertEqual(letter_of('PRECIOS', 'final'), 'Q')

    def test_phase_follows_the_quote(self):
        document = self._document()
        self.order.action_quotation_sent()
        self.assertEqual(document.construction_sale_phase, 'sent')
        self.assertTrue(document._get_spreadsheet_metadata()['isReadonly'])
        self.order._action_cancel()
        self.assertEqual(document.construction_sale_phase, 'lost')
        self.order.action_draft()
        self.assertEqual(document.construction_sale_phase, 'in_progress')
        self.order.action_confirm()
        self.assertEqual(document.construction_sale_phase, 'awarded')

    def _validate(self, document, **sheets):
        rows = {'OBRA': [['Dato', 'Valor'], ['Proyecto', 'X'], ['Cliente', 'Y'],
                         ['Código de cotización', 'Z']]}
        rows.update(sheets)
        return document._construction_validate_sale(rows)

    def test_validate_sale(self):
        document = self._document()
        self.assertEqual(self._validate(document), [])
        issues = document._construction_validate_sale({'OBRA': [['Dato', 'Valor']]})
        self.assertEqual({issue[4] for issue in issues}, {'error'})
        self.assertEqual(len(issues), 3)
        columns = [column[0] for column in SALE_COLUMNS['EDIFICIO']]
        building = [row := [''] * len(columns)]
        row[columns.index('warning')] = 'Tipología sin metrado'
        issues = self._validate(document, EDIFICIO=[columns] + building)
        self.assertEqual(issues[0][4], 'error')
        row[columns.index('warning')] = 'Ambiente fuera de la lista'
        issues = self._validate(document, EDIFICIO=[columns] + building)
        self.assertEqual(issues[0][4], 'warning')

    def test_factor_is_required_only_when_used(self):
        document = self._document()
        cells = self._sheet(self._data(document), 'PARAMETROS')['cells']
        row = next(ref[1:] for ref, value in cells.items() if value == 'factor_costo')
        parameter_rows = [[''] * 10 for _i in range(int(row))]
        parameter_rows[int(row) - 1][6] = 'factor_costo'
        self.assertEqual(self._validate(document, PARAMETROS=parameter_rows), [])
        prices = [column[0] for column in SALE_COLUMNS['PRECIOS']]
        line = [''] * len(prices)
        line[prices.index('cost')] = 900
        issues = self._validate(document, PARAMETROS=parameter_rows, PRECIOS=[prices, line])
        self.assertEqual([issue[4] for issue in issues], ['error'])


@tagged('post_install', '-at_install')
class TestPackage117SaleSheetTour(SaleSheetCommon, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_quote()

    def setUp(self):
        super().setUp()
        # Los datos del test son de la compañía del entorno; la base puede
        # tener al administrador en otra (y el navegador abriría sus datos).
        self.env.ref('base.user_admin').write({
            'company_ids': [Command.link(self.env.company.id)],
            'company_id': self.env.company.id})

    def test_values_of_the_recording(self):
        self.order.action_construction_open_spreadsheet()
        self.env['construction.sale.rate'].create({
            'partida': 'Cocina', 'item': 'Panel del catálogo', 'uom': 'UND', 'price': 500,
            'currency_id': self.order.currency_id.id, 'group': 'Accesorio'})
        self.env.company.construction_sale_partida_product_id = self.env['product.product'].create(
            {'name': 'Mobiliario por partida (test)', 'type': 'service'})
        self.start_tour('/odoo', 'al_construction_sale_sheet', login='admin')
        self.assertEqual(self.order.order_line.filtered('construction_partida').mapped(
            'construction_partida'), ['Cocina'])
        self.assertTrue(self.order.construction_sale_summary)


@tagged('post_install', '-at_install')
class TestPackage117SaleRates(SaleSheetCommon, TransactionCase):
    """M117-19: tarifario de venta. M117-16: importar y actualizar la hoja."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_quote()
        cls.Rate = cls.env['construction.sale.rate']
        cls.currency = cls.order.currency_id

    def _rate(self, **values):
        return self.Rate.create(dict({
            'partida': 'Cocina', 'item': 'Mueble bajo', 'uom': 'ML', 'price': 345,
            'currency_id': self.currency.id, 'group': 'Mueble bajo'}, **values))

    def _lines(self, partner=None, date='2026-11-01'):
        return self.Rate._construction_rates_for(
            self.env.company, self.currency, partner or self.partner_company,
            fields.Date.to_date(date))

    def test_price_with_date_closes_the_previous_one(self):
        old = self._rate(date_from='2026-01-01')
        new = self._rate(date_from='2026-06-01', price=400)
        self.assertEqual(old.date_to, fields.Date.to_date('2026-05-31'))
        self.assertEqual(self._lines(), [new])
        self.assertEqual(self._lines(date='2026-03-01'), [old])

    def test_two_lines_in_force_are_rejected(self):
        self._rate()
        with self.assertRaises(ValidationError):
            self._rate(price=500)

    def test_agreement_completes_with_the_general_list(self):
        self._rate()
        low = self._rate(item='Mueble alto', price=320)
        special = self._rate(partner_id=self.partner_company.id, price=300)
        lines = self._lines()
        self.assertIn(special, lines)
        self.assertIn(low, lines)
        self.assertEqual(len(lines), 2)
        other = self.env['res.partner'].create({'name': 'Sin convenio (test)'})
        self.assertNotIn(special, self._lines(partner=other))

    def test_expired_line_does_not_arrive(self):
        self._rate(date_from='2025-01-01', date_to='2025-12-31')
        self.assertEqual(self._lines(), [])

    def _document(self):
        action = self.order.action_construction_open_spreadsheet()
        return self.env['documents.document'].browse(action['params']['spreadsheet_id'])

    def test_new_sheet_brings_the_rates(self):
        rate = self._rate()
        data = json.loads(self._document().with_context(bin_size=False).spreadsheet_data)
        cells = next(s for s in data['sheets'] if s['name'] == 'TARIFARIO')['cells']
        self.assertEqual((cells['A2'], cells['B2'], cells['F2'], cells['L2']),
                         ('Cocina', 'Mueble bajo', '345.0', str(rate.id)))

    def test_import_reads_its_own_tabs(self):
        document = self._document()
        wizard = self.env['construction.spreadsheet.import.wizard'].create({
            'document_id': document.id, 'filename': 'venta.xlsx',
            'file': _book({
                'OBRA': [['Dato', 'Valor'], ['Proyecto', 'No se toca'], ['Inicio', '2026-12-01']],
                'EDIFICIO': [['Piso desde', 'Piso hasta', 'Ambiente', 'Dptos (calc.)'],
                             [2, 17, 'Cocina', 99]],
                'TIPOLOGIAS': [['Código'], ['C01']],
                'RESUMEN VENTA': [['Subtotal']],
                'PARAMETROS': [['Parámetro', 'Valor', 'Clave', 'Motivo del cambio'],
                               ['Redondeo', 10, 'redondeo_multiplo', 'Convenio']],
            })})
        self.assertIn('Ignorada: es de la hoja de planificación', wizard.review_html)
        self.assertIn('Ignorada: es de la plantilla', wizard.review_html)
        payload = wizard.action_import()['infos']['construction_sheet_import']
        self.assertEqual(payload['obra'], {'Inicio': '2026-12-01'})
        self.assertEqual(payload['parameters'], {'redondeo_multiplo': ['10', 'Convenio']})
        self.assertEqual(payload['sheets']['EDIFICIO']['keys'],
                         ['floor_from', 'floor_to', 'space'])
        self.assertFalse(payload['expand_rows'])

    def test_upgrade_keeps_written_cells(self):
        document = self._document()
        document.construction_sheet_upgrade({'master': {}, 'other': {
            'METRADO': {'cells': {'A2': 'C01', 'E2': '=1.27+1.27', 'K2': 'pisada'}},
            'EDIFICIO': {'cells': {'B2': '2', 'J2': 'pisada'}},
            'ACABADOS': {'cells': {'A3': 'R02', 'I2': 'Cocina', 'J2': 'R04'}},
            'OBRA': {'cells': {'B10': '2026-12-01', 'F2': 'Cliente', 'H2': 'Cambió la cocina'}},
        }})
        data = json.loads(document.with_context(bin_size=False).spreadsheet_data)
        sheets = {sheet['name']: sheet['cells'] for sheet in data['sheets']}
        self.assertEqual(sheets['METRADO']['E2'], '=1.27+1.27')
        self.assertNotEqual(sheets['METRADO']['K2'], 'pisada')
        self.assertNotEqual(sheets['EDIFICIO']['J2'], 'pisada')
        self.assertEqual(sheets['ACABADOS']['J2'], 'R04')
        self.assertEqual(sheets['OBRA']['H2'], 'Cambió la cocina')
        self.assertEqual(self.env['documents.document'].search_count(
            [('construction_source_id', '=', document.id)]), 1)

    def test_propose_rates_creates_an_activity(self):
        document = self._document()
        document.construction_sale_propose_rates([['Cocina', 'Panel TV', 500]])
        activity = self.order.activity_ids
        self.assertIn('Panel TV', activity.note)


def _summary(**values):
    """Los datos de la maqueta del requerimiento."""
    summary = {
        'version': 'N1', 'igv': 0.18, 'prices_without_tax': True, 'discount': 0,
        'partidas': [{'name': 'Cocina', 'spaces': 32, 'subtotal': 216026.40},
                     {'name': 'Closet', 'spaces': 16, 'subtotal': 8192.00},
                     {'name': 'Lavandería', 'spaces': 16, 'subtotal': 21600.00}],
        'typologies': [{'code': 'C01', 'partida': 'Cocina', 'lines': []},
                       {'code': 'C02', 'partida': 'Cocina', 'lines': []}],
        'order_subtotal': 245818.40, 'subtotal': 245818.40, 'tax': 44247.31, 'total': 290065.71,
    }
    summary.update(values)
    return summary


@tagged('post_install', '-at_install')
class TestPackage117SalePass(SaleSheetCommon, TransactionCase):
    """M117-21: el resumen pasa a la cotización, una línea por partida."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_quote()
        cls.order.order_line.unlink()
        cls.partida_product = cls.env['product.product'].create(
            {'name': 'Mobiliario por partida (test)', 'type': 'service', 'list_price': 1})
        cls.env.company.construction_sale_partida_product_id = cls.partida_product
        action = cls.order.action_construction_open_spreadsheet()
        cls.document = cls.env['documents.document'].browse(action['params']['spreadsheet_id'])

    def _prices(self):
        return {line.construction_partida: line.price_unit for line in self.order.order_line}

    def test_one_line_per_partida(self):
        self.order.construction_sale_pass(_summary())
        self.assertEqual(self._prices(), {'Cocina': 216026.40, 'Closet': 8192.00,
                                          'Lavandería': 21600.00})
        self.assertEqual(self.order.amount_untaxed, 245818.40)
        self.assertEqual(set(self.order.order_line.mapped('product_uom_qty')), {1})
        self.assertEqual(self.order.order_line[0].name, 'Cocina · C01, C02 · 32 ambientes')

    def test_discount_is_spread_and_adds_up_exactly(self):
        self.order.construction_sale_pass(_summary(discount=10000, order_subtotal=235818.40))
        self.assertEqual(self.order.amount_untaxed, 235818.40)
        self.assertLess(self._prices()['Closet'], 8192.00)

    def test_repeating_does_not_duplicate(self):
        self.order.construction_sale_pass(_summary())
        self.order.construction_sale_pass(_summary())
        self.assertEqual(len(self.order.order_line), 3)
        preview = self.order.construction_sale_pass_preview(_summary())
        self.assertEqual({line['kind'] for line in preview['lines']}, {'same'})
        self.assertFalse(preview['warnings'])

    def test_prices_with_tax_are_written_without_it(self):
        summary = _summary(prices_without_tax=False, partidas=[
            {'name': 'Cocina', 'spaces': 1, 'subtotal': 118.0}],
            typologies=[], order_subtotal=100.0)
        self.order.construction_sale_pass(summary)
        self.assertEqual(self._prices(), {'Cocina': 100.0})

    def test_product_is_required(self):
        self.env.company.construction_sale_partida_product_id = False
        with self.assertRaises(UserError):
            self.order.construction_sale_pass(_summary())

    def test_additional_adds_lines_and_leaves_confirmed_ones(self):
        self.order.construction_sale_pass(_summary())
        self.order.action_confirm()
        self.assertEqual(self.document.construction_sale_phase, 'awarded')
        self.document.construction_sale_new_version()
        self.assertEqual(self.document.construction_sale_phase, 'additional')
        self.assertEqual(self.document.construction_sale_version, 2)
        self.assertIn('N2', self.document.construction_sale_pending)
        summary = _summary(version='N2', partidas=[
            {'name': 'Cocina', 'spaces': 32, 'subtotal': 216526.40},
            {'name': 'Closet', 'spaces': 16, 'subtotal': 8092.00},
            {'name': 'Lavandería', 'spaces': 16, 'subtotal': 21600.00}])
        self.order.construction_sale_pass(summary)
        self.assertEqual(self.document.construction_sale_phase, 'awarded')
        lines = self.order.order_line.sorted('id')
        self.assertEqual(lines[:3].mapped('price_unit'), [216026.40, 8192.00, 21600.00])
        self.assertEqual(lines[3:].mapped('name'), ['Adicional N2 · Cocina', 'Adicional N2 · Closet'])
        self.assertEqual(lines[3:].mapped('price_unit'), [500.0, -100.0])

    def test_new_version_from_sent_goes_back_to_in_progress(self):
        self.order.construction_sale_pass(_summary())
        self.order.action_quotation_sent()
        self.document.construction_sale_new_version()
        self.assertEqual(self.document.construction_sale_phase, 'in_progress')
        copy = self.env['documents.document'].search(
            [('construction_source_id', '=', self.document.id)])
        self.assertEqual(copy.construction_version_reason, 'Versión N1 de la cotización')
        self.assertTrue(self.env['ir.attachment'].search_count([
            ('res_model', '=', 'documents.document'), ('res_id', '=', copy.id),
            ('name', '=', 'Cotizacion_%s_N1.pdf' % self.order.name)]))
        # Enviar otra vez, con la cotización ya en «Enviada», pasa de fase.
        self.order.with_context(mark_so_as_sent=True).message_post(body='Envío')
        self.assertEqual(self.document.construction_sale_phase, 'sent')

    def test_confirm_warns_when_totals_differ(self):
        self.order.construction_sale_pass(_summary())
        self.order.order_line[0].price_unit = 1
        result = self.order.action_confirm()
        self.assertEqual(result['tag'], 'display_notification')
        self.assertIn('hoja de venta', result['params']['message'])

    def test_mail_uses_the_sheet_report(self):
        self.assertNotEqual(
            self.order._find_mail_template().name, 'Cotización de mobiliario')
        self.order.construction_sale_pass(_summary())
        template = self.order._find_mail_template()
        self.assertEqual(template.report_template_ids.report_name,
                         'al_construction_planner_spreadsheet_furniture.report_sale_sheet_quotation')
        self.assertEqual(self.order._construction_sale_version_label(), 'N1')

    def test_report_renders_without_fabrication_modules(self):
        summary = _summary(typologies=[{
            'code': 'C01', 'partida': 'Cocina', 'name': 'Cocina dpto 201', 'price': 5725.65,
            'footer': 'C01 · Cocina dpto 201 · DPTO: 201 al 1701 (posición 01) · 16 ×',
            'lines': [{'description': 'Mueble bajo: estructura R04 (melamina)', 'qty': 4.33,
                       'uom': 'ML', 'price': 625, 'subtotal': 2706.25}]}],
            obra={'Cliente': 'Inmobiliaria'}, considerations=['No incluye pintado'])
        self.order.construction_sale_pass(summary)
        html, _kind = self.env['ir.actions.report']._render_qweb_html(
            'al_construction_planner_spreadsheet_furniture.report_sale_sheet_quotation',
            self.order.ids)
        text = html.decode()
        for expected in ('DPTO: 201 al 1701', 'No incluye pintado', 'Inmobiliaria', 'Mueble bajo'):
            self.assertIn(expected, text)
