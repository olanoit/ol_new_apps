# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    construction_site_name = fields.Char(
        string='Nombre de la obra',
        help='Con la referencia del cliente como código de obra, la obra que crea esta venta '
             'se llama «<código> <nombre de la obra>» (p. ej. «ROOFG-04-25 ROOF GARDEN»).')

    def _construction_is_site_order(self):
        """Venta de una obra: su proyecto es una obra o creó una."""
        self.ensure_one()
        # sudo: quien factura no siempre lee los proyectos; solo se pregunta
        # si la venta es de una obra.
        order_sudo = self.sudo()
        return bool(order_sudo.project_id.is_construction_site) or bool(
            self.env['project.project'].sudo().search_count(
                [('construction_sale_order_id', '=', self.id)], limit=1))
