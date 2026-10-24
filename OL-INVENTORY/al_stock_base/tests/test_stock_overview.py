# -*- coding: utf-8 -*-
from lxml import etree

from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestStockOverview(TransactionCase):
    """Resumen de inventario: sin gráficos y con las etiquetas en español."""

    def _kanban(self, lang):
        views = self.env['stock.picking.type'].with_context(lang=lang).get_views([(False, 'kanban')])
        return views['views']['kanban']['arch']

    def test_no_graph(self):
        root = etree.fromstring(self._kanban('en_US'))
        self.assertFalse(root.xpath("//templates//field[@name='kanban_dashboard_graph']"))
        self.assertFalse(root.xpath("//field[@widget='picking_type_dashboard_graph']"))
        # El renderer de stock lo necesita cargado.
        self.assertTrue(root.xpath("./field[@name='kanban_dashboard_graph']"))

    def test_spanish_labels(self):
        self.env['res.lang']._activate_lang('es_419')
        root = etree.fromstring(self._kanban('es_419'))
        texts = {t.strip() for node in root.iter() for t in (node.text, node.tail) if t and t.strip()}
        self.assertFalse(texts & {'Late', 'Waiting', 'Back Orders', 'Operations'}, texts)
        self.assertIn('Con demora', texts)

    # Paquete 1.11, M111-19 A: estilo de la compañía y del usuario.
    def test_overview_options(self):
        company = self.env.company
        root = etree.fromstring(self._kanban('en_US'))
        self.assertIn('o_al_overview_compact', root.get('class'))
        self.assertIn('o_al_overview_w_medium', root.get('class'))
        company.al_stock_overview_width = 'narrow'
        root = etree.fromstring(self._kanban('en_US'))
        self.assertIn('o_al_overview_w_narrow', root.get('class'))
        company.al_stock_overview_graph = True
        company.al_stock_overview_width = 'wide'
        root = etree.fromstring(self._kanban('en_US'))
        self.assertTrue(root.xpath("//templates//field[@name='kanban_dashboard_graph']"))
        self.assertIn('o_al_overview_w_wide', root.get('class'))
        company.al_stock_overview_graph = False
        # Un usuario elige las tarjetas de Odoo; otro sigue con las compactas.
        user = new_test_user(self.env, 'overview_std', groups='stock.group_stock_user')
        user.al_stock_overview_style = 'standard'
        arch = self.env['stock.picking.type'].with_user(user).get_views(
            [(False, 'kanban')])['views']['kanban']['arch']
        root = etree.fromstring(arch)
        self.assertNotIn('o_al_overview_compact', root.get('class') or '')
        self.assertTrue(root.xpath("//templates//field[@name='kanban_dashboard_graph']"))
        root = etree.fromstring(self._kanban('en_US'))
        self.assertIn('o_al_overview_compact', root.get('class'))
        # Cada usuario puede cambiar su preferencia.
        user.with_user(user).al_stock_overview_style = 'compact'
        self.assertEqual(user.al_stock_overview_style, 'compact')
        company.al_stock_overview_style = 'standard'
        user.al_stock_overview_style = 'company'
        self.assertEqual(user._al_stock_overview_options()[0], 'standard')
