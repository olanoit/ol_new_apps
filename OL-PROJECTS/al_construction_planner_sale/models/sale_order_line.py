# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    construction_valuation_line_ids = fields.One2many(
        'construction.valuation.line', 'sale_line_id', string='Valorizaciones',
        readonly=True)

    def _construction_price(self, day=None):
        """Precio de la partida (subtotal sin impuestos de la línea) en la
        moneda de la compañía de la obra."""
        self.ensure_one()
        order = self.order_id
        company = order.company_id
        return order.currency_id._convert(
            self.price_subtotal, company.currency_id, company,
            day or fields.Date.context_today(self))

    def _timesheet_create_project_prepare_values(self):
        """Servicio que crea una obra: el proyecto nace marcado como obra y
        con esta venta como orden de venta del contrato."""
        values = super()._timesheet_create_project_prepare_values()
        if self.product_id.construction_creates_site:
            values.update(is_construction_site=True,
                          construction_sale_order_id=self.order_id.id)
            code = (self.order_id.client_order_ref or '').strip()
            if code:
                values['construction_code'] = code
        return values

    def _timesheet_create_project(self):
        """Con la referencia del cliente como código de obra, la obra se llama
        «<código> <nombre de la obra>» (Odoo le agrega el producto o la
        plantilla al nombre)."""
        project = super()._timesheet_create_project()
        order = self.order_id
        code = (order.client_order_ref or '').strip()
        if self.product_id.construction_creates_site and code:
            site_name = (order.construction_site_name or '').strip() or code
            project.name = '%s %s' % (code, site_name)
        return project
