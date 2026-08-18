# -*- coding: utf-8 -*-
"""Actualización del tipo de cambio SUNAT (compra/venta) para USD/PEN.

Cuatro fuentes, todas devolviendo compra y venta:

* **SUNAT** — TXT oficial, gratuito y sin token, pero solo del día publicado.
  Es la fuente del cron diario.
* **BCRP** — series históricas del sistema bancario SBS, gratuitas y sin
  token; devuelve un rango completo en una sola llamada.
* **Decolecta** — tipo de cambio de SUNAT con fecha histórica; requiere token.
* **apis.net.pe** — alternativa histórica; requiere token.

La tasa nativa ``rate`` se guarda como ``1 / venta`` (la venta es la tasa
oficial para la conversión contable en Perú), y se conservan compra/venta en
los campos ``rate_purchase`` / ``rate_sale``.
"""
import logging

from odoo import _, api, fields, models

from ..services import bcrp_rate, decolecta_rate, sunat_rate

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

    # ------------------------------------------------------------------ #
    # Conversión con el tipo de cambio peruano                            #
    # ------------------------------------------------------------------ #

    def _get_conversion_rate(self, from_currency, to_currency, company=None,
                             date=None):
        """Respeta el tipo de cambio compra/venta indicado en el contexto.

        Odoo convierte con una única tasa por día. Cuando quien llama sabe qué
        tipo de cambio corresponde —una factura, un pago— lo indica con
        ``with_context(l10n_pe_exchange_rate_type=…)`` y aquí se aplica.

        Solo interviene entre la moneda de la compañía y otra, en el sentido
        que sea, y únicamente si hay compra/venta registradas para la fecha;
        en cualquier otro caso se mantiene el comportamiento nativo.
        """
        rate_type = self.env.context.get('l10n_pe_exchange_rate_type')
        if rate_type in ('purchase', 'sale') and from_currency != to_currency:
            company = company or self.env.company
            value = self._l10n_pe_rate_value(
                from_currency, to_currency, company, date, rate_type)
            if value:
                return value
        return super()._get_conversion_rate(from_currency, to_currency,
                                            company=company, date=date)

    @api.model
    def _l10n_pe_rate_value(self, from_currency, to_currency, company, date,
                            rate_type):
        """Factor de conversión según el tipo de cambio peruano, o ``None``.

        El tipo de cambio se guarda como «moneda de la compañía por una unidad
        de la extranjera» (soles por dólar), de modo que convertir *hacia* la
        moneda de la compañía multiplica y convertir *desde* ella divide.
        """
        company_currency = company.currency_id
        if to_currency == company_currency:
            foreign, invert = from_currency, False
        elif from_currency == company_currency:
            foreign, invert = to_currency, True
        else:
            # Entre dos monedas extranjeras no hay tipo de cambio SUNAT.
            return None

        rate = self.env['res.currency.rate'].search([
            ('currency_id', '=', foreign.id),
            ('company_id', '=', company.root_id.id),
            ('name', '<=', date or fields.Date.context_today(self)),
        ], order='name desc', limit=1)
        value = rate.rate_purchase if rate_type == 'purchase' else rate.rate_sale
        if not value:
            return None
        return (1.0 / value) if invert else value

    @api.model
    def _l10n_pe_connection_token(self, name, company=None):
        """Token de una conexión configurada en ``l10n_pe_vat_sunat``.

        Dependencia suave: quien consulta RUC/DNI con un proveedor ya tiene
        allí su token, y varios de esos proveedores publican también el tipo
        de cambio. Si el módulo no está instalado, devuelve ''.
        """
        if 'l10n_pe.api.connection' not in self.env:
            return ''
        company = company or self.env.company
        connection = self.env['l10n_pe.api.connection'].sudo().search([
            ('name', 'ilike', name),
            ('company_id', '=', company.id),
        ], limit=1)
        return connection.token or ''

    @api.model
    def _l10n_pe_apis_net_token(self, company=None):
        return self._l10n_pe_connection_token('apis.net.pe', company=company)

    @api.model
    def _l10n_pe_decolecta_token(self, company=None):
        return self._l10n_pe_connection_token('decolecta', company=company)

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

    def l10n_pe_update_range_bcrp(self, date_from, date_to):
        """Tipos de cambio de un rango desde el BCRP (USD).

        Es la vía recomendada para cargar históricos: el BCRP publica la serie
        del sistema bancario SBS —la que SUNAT toma para efectos
        tributarios— de forma gratuita y sin token, y en una sola llamada
        devuelve todo el rango. Los días sin publicación (fines de semana y
        feriados) simplemente no vienen en la respuesta.

        Devuelve el número de fechas cargadas.
        """
        usd = self._l10n_pe_get_usd()
        if not usd:
            return 0
        rates = bcrp_rate.fetch_bcrp(date_from, date_to)
        for data in rates:
            usd._l10n_pe_upsert_rate(
                data['date'], data['compra'], data['venta'], 'bcrp')
        _logger.info('TC BCRP %s..%s: %d fecha(s) cargadas',
                     date_from, date_to, len(rates))
        return len(rates)

    def l10n_pe_update_date_decolecta(self, rate_date=None, token=''):
        """Tipo de cambio de una fecha desde Decolecta (USD).

        Decolecta publica el tipo de cambio de SUNAT con compra y venta y
        admite fecha histórica. Si no se pasa token, se reutiliza el de la
        conexión Decolecta configurada para consultar RUC/DNI.
        """
        usd = self._l10n_pe_get_usd()
        token = token or self._l10n_pe_decolecta_token()
        data = decolecta_rate.fetch_decolecta(token, date=rate_date)
        if usd and data:
            usd._l10n_pe_upsert_rate(
                data['date'], data['compra'], data['venta'], 'decolecta')
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
