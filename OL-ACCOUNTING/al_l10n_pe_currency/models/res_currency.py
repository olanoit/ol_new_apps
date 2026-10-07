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
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from ..services import bcrp_rate, decolecta_rate, sunat_rate

_logger = logging.getLogger(__name__)


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    def _l10n_pe_upsert_rate(self, rate_date, compra, venta, origin='sunat',
                             keep_manual=False):
        """Crea o actualiza el tipo de cambio del día para esta moneda,
        respetando la unicidad nativa (una tasa por día).

        - Si la tasa ya tiene esos valores no se reescribe (el cron corre
          cada hora).
        - ``keep_manual``: no pisa una tasa registrada a mano (el cron);
          el asistente, que lo pide el usuario, sí la reemplaza.

        Solo en las compañías **raíz** cuya moneda es el sol: el núcleo
        prohíbe tasas en las sucursales (``_check_company_id``, heredan las de
        su matriz) y en una compañía con otra moneda base «1 / venta» no
        significaría nada.
        """
        self.ensure_one()
        if not (venta and venta > 0):
            return
        pen = self.env.ref('base.PEN', raise_if_not_found=False)
        # sudo: la tasa es de toda la base (la usan todas las compañías en
        # soles), no solo de las que el usuario tiene activas.
        companies_sudo = self.env['res.company'].sudo().search([
            ('parent_id', '=', False),
            ('currency_id', '=', pen.id if pen else False),
        ]).filtered(lambda company: company.currency_id != self)
        if not companies_sudo:
            return
        # sudo: la escritura de tasas está reservada al administrador
        # contable; quien llega aquí ya pasó _l10n_pe_check_rate_access (o es
        # el cron), y la tasa se replica en compañías que el usuario puede no
        # tener activas.
        rates_sudo = self.env['res.currency.rate'].sudo()
        date_str = fields.Date.to_string(rate_date)
        # Una sola búsqueda para todas las compañías (antes, una por compañía).
        existing_by_company = {
            rate.company_id: rate
            for rate in rates_sudo.search([
                ('currency_id', '=', self.id),
                ('company_id', 'in', companies_sudo.ids),
                ('name', '=', date_str),
            ])
        }
        to_create = []
        for company in companies_sudo:
            vals = {
                'name': date_str,
                'currency_id': self.id,
                'company_id': company.id,
                'rate': 1.0 / venta,
                'rate_sale': venta,
                'rate_purchase': compra,
                'ref_origin': origin,
            }
            existing = existing_by_company.get(company)
            if existing:
                if keep_manual and existing.ref_origin == 'manual':
                    continue
                if (existing.rate_sale, existing.rate_purchase) == (
                        round(venta, 3), round(compra or venta, 3)):
                    continue
                existing.write(vals)
            else:
                to_create.append(vals)
        if to_create:
            rates_sudo.create(to_create)

    def _l10n_pe_check_rate_access(self):
        """Solo contables pueden cargar tipos de cambio.

        Los métodos de actualización son públicos (los usan los botones, el
        asistente y el cierre de tipo de cambio) y escriben con ``sudo()``;
        sin esta comprobación cualquier usuario interno podría, por RPC,
        pisar la tasa del día o lanzar consultas a servicios externos.
        """
        if self.env.su:
            return
        user = self.env.user
        if not (user.has_group('account.group_account_user')
                or user.has_group('account.group_account_manager')):
            raise AccessError(_(
                'Solo los usuarios de contabilidad pueden actualizar el tipo '
                'de cambio.'))

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
        value = rate._l10n_pe_purchase_value() if rate_type == 'purchase' else None
        if not value:
            # Venta, o compra sin valor propio: la tasa nativa ya es 1 / venta
            # y sin el redondeo a 3 decimales de ``rate_sale``, que falsearía
            # las monedas de poco valor (yen, peso chileno…).
            return None
        return (1.0 / value) if invert else value

    @api.model
    def _l10n_pe_connection_token(self, host, company=None):
        """Token de una conexión configurada en ``l10n_pe_vat_sunat``.

        Dependencia suave: quien consulta RUC/DNI con un proveedor ya tiene
        allí su token, y varios de esos proveedores publican también el tipo
        de cambio. La conexión se identifica por el dominio del proveedor en
        su URL base (más estable que el nombre, que el usuario puede cambiar).
        Si el módulo no está instalado, devuelve ''.
        """
        if 'l10n_pe.api.connection' not in self.env:
            return ''
        company = company or self.env.company
        # sudo: el token es una credencial reservada al administrador
        # (``groups`` en el campo); aquí se lee en el servidor solo para
        # llamar al proveedor y nunca se devuelve al cliente.
        connection_sudo = self.env['l10n_pe.api.connection'].sudo().search([
            '|', ('base_url', 'ilike', host), ('name', 'ilike', host),
            ('company_id', '=', company.id),
        ], limit=1)
        return connection_sudo.token or ''

    @api.model
    def _l10n_pe_apis_net_token(self, company=None):
        return self._l10n_pe_connection_token('apis.net.pe', company=company)

    @api.model
    def _l10n_pe_decolecta_token(self, company=None):
        return self._l10n_pe_connection_token('decolecta.com', company=company)

    def l10n_pe_update_today_sunat(self, keep_manual=False):
        """Tipo de cambio de hoy desde el TXT oficial de SUNAT (USD).

        Devuelve los datos cargados, o ``None`` si SUNAT no respondió."""
        self._l10n_pe_check_rate_access()
        usd = self._l10n_pe_get_usd()
        data = sunat_rate.fetch_sunat_txt()
        if usd and data:
            usd._l10n_pe_upsert_rate(
                data['date'], data['compra'], data['venta'], 'sunat',
                keep_manual=keep_manual)
            _logger.info('TC SUNAT %s: compra=%s venta=%s',
                         data['date'], data['compra'], data['venta'])
        return data if usd else None

    def l10n_pe_update_date_apis(self, rate_date, token=''):
        """Tipo de cambio de una fecha desde apis.net.pe (USD).

        Si no se pasa token, reutiliza el de l10n_pe_vat_sunat."""
        self._l10n_pe_check_rate_access()
        usd = self._l10n_pe_get_usd()
        token = token or self._l10n_pe_apis_net_token()
        data = sunat_rate.fetch_apis_net(date=rate_date, token=token)
        if usd and data:
            usd._l10n_pe_upsert_rate(
                data['date'], data['compra'], data['venta'], 'apis_net')
        return bool(data)

    def l10n_pe_update_range_bcrp(self, date_from, date_to, keep_manual=False):
        """Tipos de cambio de un rango desde el BCRP (USD).

        Es la vía recomendada para cargar históricos: el BCRP publica la serie
        del sistema bancario SBS —la que SUNAT toma para efectos
        tributarios— de forma gratuita y sin token, y en una sola llamada
        devuelve todo el rango.

        El cierre SBS de un día es el T.C. SUNAT del día siguiente (y de los
        días sin publicación que siguen): se piden unos días antes del rango y
        cada fecha toma el cierre anterior (``bcrp_rate.to_sunat_dates``).
        Nunca se cargan fechas futuras.

        Devuelve el número de fechas cargadas.
        """
        self._l10n_pe_check_rate_access()
        usd = self._l10n_pe_get_usd()
        if not usd:
            return 0
        date_to = min(date_to, fields.Date.context_today(
            self.with_context(tz='America/Lima')))
        if date_to < date_from:
            return 0
        closes = bcrp_rate.fetch_bcrp(
            date_from - timedelta(days=bcrp_rate.LOOKBACK_DAYS),
            date_to - timedelta(days=1))
        rates = bcrp_rate.to_sunat_dates(closes, date_from, date_to)
        for data in rates:
            usd._l10n_pe_upsert_rate(
                data['date'], data['compra'], data['venta'], 'bcrp',
                keep_manual=keep_manual)
        _logger.info('TC BCRP %s..%s: %d fecha(s) cargadas',
                     date_from, date_to, len(rates))
        return len(rates)

    def l10n_pe_update_date_decolecta(self, rate_date=None, token=''):
        """Tipo de cambio de una fecha desde Decolecta (USD).

        Decolecta publica el tipo de cambio de SUNAT con compra y venta y
        admite fecha histórica. Si no se pasa token, se reutiliza el de la
        conexión Decolecta configurada para consultar RUC/DNI.
        """
        self._l10n_pe_check_rate_access()
        usd = self._l10n_pe_get_usd()
        token = token or self._l10n_pe_decolecta_token()
        data = decolecta_rate.fetch_decolecta(token, date=rate_date)
        if usd and data:
            usd._l10n_pe_upsert_rate(
                data['date'], data['compra'], data['venta'], 'decolecta')
        return bool(data)

    @api.model
    def _cron_update_sunat_rate(self):
        """Cron horario: actualiza el TC de hoy desde SUNAT.

        Cada hora y no una vez al día: si la única corrida caía antes de que
        SUNAT publicara, el día entero se facturaba con la tasa anterior. Una
        tasa registrada a mano no se pisa."""
        self.l10n_pe_update_today_sunat(keep_manual=True)

    # ------------------------------------------------------------------ #
    # Acciones de UI                                                      #
    # ------------------------------------------------------------------ #

    def action_update_today_sunat(self):
        data = self.l10n_pe_update_today_sunat()
        if data:
            message = _('Tipo de cambio del %(date)s cargado: compra %(buy)s, '
                        'venta %(sell)s.', date=data['date'],
                        buy=data['compra'], sell=data['venta'])
            kind = 'success'
        else:
            message = _('SUNAT no devolvió el tipo de cambio de hoy. Inténtelo '
                        'más tarde o use «Actualizar por fecha/mes».')
            kind = 'warning'
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': _('Tipo de cambio'), 'message': message,
                       'type': kind, 'sticky': False},
        }

    def action_open_rate_wizard(self):
        return {
            'name': _('Actualizar tipo de cambio'),
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_pe.exchange.rate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_currency_id': (self._l10n_pe_get_usd() or self).id},
        }
