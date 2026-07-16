# -*- coding: utf-8 -*-
"""Actualización del tipo de cambio SUNAT (compra/venta) para USD/PEN.

Refactor sobre Odoo 19: se elimina el scraping frágil de SBS/Selenium/Yahoo y
se usa como fuente principal el TXT oficial de SUNAT (gratuito, con compra y
venta). apis.net.pe queda como fuente para fechas históricas.

La tasa nativa ``rate`` se guarda como ``1 / venta`` (la venta es la tasa
oficial para la conversión contable en Perú), y se conservan compra/venta en
los campos ``rate_purchase`` / ``rate_sale``.
"""
import logging

from odoo import _, api, fields, models

from ..services import sunat_rate

_logger = logging.getLogger(__name__)


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    def _l10n_pe_upsert_rate(self, rate_date, compra, venta, origin='sunat'):
        """Crea o actualiza el tipo de cambio del día para esta moneda en todas
        las compañías, respetando la unicidad nativa (una tasa por día)."""
        self.ensure_one()
        if not (venta and venta > 0):
            return
        Rate = self.env['res.currency.rate'].sudo()
        date_str = fields.Date.to_string(rate_date)
        for company in self.env['res.company'].search([]):
            vals = {
                'name': date_str,
                'currency_id': self.id,
                'company_id': company.id,
                'rate': 1.0 / venta,
                'rate_sale': venta,
                'rate_purchase': compra,
                'ref_origin': origin,
            }
            existing = Rate.search([
                ('currency_id', '=', self.id),
                ('company_id', '=', company.id),
                ('name', '=', date_str),
            ], limit=1)
            if existing:
                existing.write(vals)
            else:
                Rate.create(vals)

    # ------------------------------------------------------------------ #
    # Fuentes                                                             #
    # ------------------------------------------------------------------ #

    @api.model
    def _l10n_pe_get_usd(self):
        return self.env.ref('base.USD', raise_if_not_found=False)

    @api.model
    def _l10n_pe_apis_net_token(self, company=None):
        """Reutiliza el token de apis.net.pe configurado en el módulo
        l10n_pe_vat_sunat (si está instalado). Dependencia suave: si el modelo
        no existe, devuelve ''."""
        if 'l10n_pe.api.connection' not in self.env:
            return ''
        company = company or self.env.company
        conn = self.env['l10n_pe.api.connection'].sudo().search([
            ('name', '=', 'apis.net.pe'),
            ('company_id', '=', company.id),
        ], limit=1)
        return conn.token or ''

    def l10n_pe_update_today_sunat(self):
        """Tipo de cambio de hoy desde el TXT oficial de SUNAT (USD)."""
        usd = self._l10n_pe_get_usd()
        data = sunat_rate.fetch_sunat_txt()
        if usd and data:
            usd._l10n_pe_upsert_rate(
                data['date'], data['compra'], data['venta'], 'sunat')
            _logger.info('TC SUNAT %s: compra=%s venta=%s',
                         data['date'], data['compra'], data['venta'])
        return True

    def l10n_pe_update_date_apis(self, rate_date, token=''):
        """Tipo de cambio de una fecha desde apis.net.pe (USD).

        Si no se pasa token, reutiliza el de l10n_pe_vat_sunat."""
        usd = self._l10n_pe_get_usd()
        token = token or self._l10n_pe_apis_net_token()
        data = sunat_rate.fetch_apis_net(date=rate_date, token=token)
        if usd and data:
            usd._l10n_pe_upsert_rate(
                data['date'], data['compra'], data['venta'], 'apis_net')
        return bool(data)

    @api.model
    def _cron_update_sunat_rate(self):
        """Cron diario: actualiza el TC de hoy desde SUNAT."""
        self.l10n_pe_update_today_sunat()

    # ------------------------------------------------------------------ #
    # Acciones de UI                                                      #
    # ------------------------------------------------------------------ #

    def action_update_today_sunat(self):
        self.l10n_pe_update_today_sunat()

    def action_open_rate_wizard(self):
        return {
            'name': _('Actualizar tipo de cambio'),
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_pe.exchange.rate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_currency_id': (self._l10n_pe_get_usd() or self).id},
        }
