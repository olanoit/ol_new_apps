# -*- coding: utf-8 -*-
from lxml import etree

from odoo.tests import TransactionCase, tagged


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
