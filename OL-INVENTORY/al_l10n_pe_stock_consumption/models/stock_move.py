# -*- coding: utf-8 -*-
"""Asiento de consumo a costo por movimiento.

Odoo ya crea el asiento de la salida a una ubicación con cuenta de valorización
(``stock_account``). Este módulo solo cambia, en las ubicaciones de consumo, la
cuenta del cargo y añade el centro de costo. El importe sigue siendo el valor
del movimiento.
"""
import json

from odoo import api, fields, models


class StockMove(models.Model):
    _name = 'stock.move'
    _inherit = ['stock.move', 'analytic.mixin']

    l10n_pe_is_consumption = fields.Boolean(
        string='Es consumo', compute='_compute_l10n_pe_is_consumption')

    # El JSON no sirve de clave para agrupar: la fusión compara este texto.
    l10n_pe_distribution_key = fields.Char(compute='_compute_l10n_pe_distribution_key')

    @api.depends('analytic_distribution')
    def _compute_l10n_pe_distribution_key(self):
        for move in self:
            move.l10n_pe_distribution_key = json.dumps(move.analytic_distribution or {}, sort_keys=True)

    @api.depends('location_id.l10n_pe_is_consumption', 'location_dest_id.l10n_pe_is_consumption')
    def _compute_l10n_pe_is_consumption(self):
        for move in self:
            move.l10n_pe_is_consumption = bool(move._l10n_pe_consumption_location())

    def _prepare_merge_moves_distinct_fields(self):
        # Dos líneas del mismo producto con distinto centro no se fusionan.
        return super()._prepare_merge_moves_distinct_fields() + ['l10n_pe_distribution_key']

    def _l10n_pe_consumption_location(self):
        """Ubicación de consumo del movimiento: el destino en la salida, el
        origen en la devolución."""
        self.ensure_one()
        if self.location_dest_id.l10n_pe_is_consumption:
            return self.location_dest_id
        if self.location_id.l10n_pe_is_consumption:
            return self.location_id
        return self.env['stock.location']

    def _l10n_pe_consumption_account(self, location):
        self.ensure_one()
        category = self.product_id.categ_id.with_company(self.company_id)
        return category.l10n_pe_consumption_account_id or location.valuation_account_id

    def _l10n_pe_consumption_distribution(self, location):
        """Centro de costo del asiento: el de la línea o el de la ubicación.

        Si otro módulo ya da distribución al movimiento (proyecto, obra), Odoo
        crea el apunte analítico desde el movimiento: repetirla en el asiento
        cargaría dos veces el centro de costo.
        """
        self.ensure_one()
        if self._get_analytic_distribution():
            return False
        return self.analytic_distribution or location.analytic_distribution or False

    def _get_account_move_line_vals(self):
        vals_list = super()._get_account_move_line_vals()
        location = self._l10n_pe_consumption_location()
        if not location:
            return vals_list
        account = self._l10n_pe_consumption_account(location)
        distribution = self._l10n_pe_consumption_distribution(location)
        for vals in vals_list:
            if vals['account_id'] == location.valuation_account_id.id:
                vals['account_id'] = account.id
                if distribution and not vals.get('analytic_distribution'):
                    vals['analytic_distribution'] = distribution
        return vals_list
