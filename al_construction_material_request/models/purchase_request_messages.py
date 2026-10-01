# -*- coding: utf-8 -*-
"""Mensajes del chatter de ``purchase_request`` (OCA) rehechos con plantillas.

En Odoo 19 ``env._()`` devuelve ``Markup`` cuando la traducción lleva HTML;
OCA suma a esa traducción HTML armado como texto plano (``f"<h3>…"``) y
``Markup`` lo escapa: el chatter muestra ``<h3>``, ``<ul>``… como texto. Se
corrige para todos los requerimientos de compra, no solo los de obra.
"""
from odoo import api, fields, models
from odoo.tools import format_date, formatLang


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _purchase_request_confirm_message_content(self, request, request_dict=None):
        self.ensure_one()
        lines = []
        for data in (request_dict or {}).values():
            planned = data.get('date_planned')
            if isinstance(planned, str):
                planned = fields.Datetime.to_datetime(planned)
            local = planned and fields.Datetime.context_timestamp(self, planned).date()
            lines.append({
                'name': data['name'],
                'qty': f"{formatLang(self.env, data['product_qty'], digits=2)} {data['product_uom']}",
                'date': local and format_date(self.env, local),
            })
        return self.env['ir.qweb']._render(
            'al_construction_material_request.message_purchase_request_po_confirmed',
            {'order': self, 'lines': lines})


class PurchaseRequestAllocation(models.Model):
    _inherit = 'purchase.request.allocation'

    @api.model
    def _purchase_request_confirm_done_message_content(self, message_data):
        qty = formatLang(self.env, message_data['product_qty'], digits=2)
        return self.env['ir.qweb']._render(
            'al_construction_material_request.message_purchase_request_received',
            {'product': message_data['product_name'],
             'qty': f"{qty} {message_data['product_uom']}"})
