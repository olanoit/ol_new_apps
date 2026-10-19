# -*- coding: utf-8 -*-
"""Ficha del producto en la tienda en línea: alternativas genéricas primero
(DS 020-2024-SA, art. 49, también en los canales virtuales)."""
from odoo import models
from odoo.fields import Domain
from odoo.http import request

GENERIC_FIRST = {'generic_dci': 0, 'generic_brand': 1, 'innovator': 2}


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _pharmacy_website_alternatives(self):
        """Equivalentes publicados del producto: genéricos en DCI primero,
        luego genéricos de marca e innovadores, y en cada grupo del más barato
        al más caro."""
        self.ensure_one()
        key = self.pharmacy_equivalence_key
        if not key:
            return self.browse()
        domain = Domain([
            ('pharmacy_equivalence_key', '=', key), ('id', '!=', self.id),
            ('is_published', '=', True), ('sale_ok', '=', True),
        ])
        website = request and getattr(request, 'website', None)
        if website:
            domain &= Domain(website.website_domain())
        alternatives = self.search(domain)
        return alternatives.sorted(lambda t: (
            GENERIC_FIRST.get(t.pharmacy_product_type, 3), t.list_price, t.name))

    def _pharmacy_online_restriction(self):
        """'controlled' si no se vende en línea, 'prescription' si pide la
        receta antes de pagar; False si se vende libremente."""
        self.ensure_one()
        condition = self.pharmacy_sale_condition
        if condition in ('controlled', 'prescription'):
            return condition
        return False
