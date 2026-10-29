# -*- coding: utf-8 -*-
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    # Preferencia de cada usuario (paquete 1.11, M111-19 A).
    al_stock_overview_style = fields.Selection(
        [('company', 'Según la compañía'), ('standard', 'Estándar de Odoo'),
         ('compact', 'Compacta')],
        string='Tarjetas del resumen de Inventario', default='company', required=True,
        user_writeable=True)

    def _al_stock_overview_options(self):
        """(estilo, gráfico, ancho) efectivos del resumen de Inventario: el
        estilo del usuario o, «Según la compañía», el de la compañía activa."""
        self.ensure_one()
        company = self.env.company
        style = self.al_stock_overview_style
        if style == 'company':
            style = company.al_stock_overview_style or 'compact'
        return style, company.al_stock_overview_graph, company.al_stock_overview_width or 'medium'
