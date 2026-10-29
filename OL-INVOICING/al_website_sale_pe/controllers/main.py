# -*- coding: utf-8 -*-
from odoo.http import request, route

from odoo.addons.l10n_pe.controllers.portal import L10nPEPortalAccount

# Consultas de RUC/DNI permitidas por sesión: la ruta es pública y las API de
# consulta pueden cobrar por consulta.
MAX_LOOKUPS_PER_SESSION = 10
SESSION_KEY = 'al_website_sale_pe_lookups'


class WebsiteSalePeAddress(L10nPEPortalAccount):

    def _prepare_address_form_values(self, partner_sudo, *args, **kwargs):
        rendering_values = super()._prepare_address_form_values(partner_sudo, *args, **kwargs)
        country = rendering_values.get('country')
        if not self._is_peru_company() or not country or country.code != 'PE':
            return rendering_values
        # Odoo 20: factura → RUC en «vat»; boleta → DNI (identificador PE_DNI).
        partner = partner_sudo or rendering_values['current_partner']
        rendering_values['l10n_pe_receipt'] = 'factura' if partner.vat else 'boleta'
        return rendering_values

    @route('/shop/l10n_pe/document_lookup', type='jsonrpc', auth='public', website=True,
           methods=['POST'], sitemap=False)
    def l10n_pe_document_lookup(self, number, sunat_code):
        """Datos de un RUC o DNI para llenar la dirección del checkout.

        :param str number: número de documento.
        :param str sunat_code: tipo de documento (catálogo 06): ``'6'`` RUC,
            ``'1'`` DNI.
        :return: ``{'found': bool, 'values': {...}, 'message': str}``
        """
        if not self._is_peru_company() or sunat_code not in ('1', '6'):
            return {'found': False, 'message': ''}
        lookups = request.session.get(SESSION_KEY, 0)
        if lookups >= MAX_LOOKUPS_PER_SESSION:
            return {'found': False, 'message': request.env._(
                'Alcanzó el límite de consultas. Complete sus datos a mano.')}
        request.session[SESSION_KEY] = lookups + 1

        # sudo(): el visitante es público y las conexiones de consulta (y su
        # token) no son legibles para él. Solo se devuelven el nombre y la
        # dirección del documento que el propio visitante escribió, y las
        # consultas por sesión están limitadas.
        partner_model_sudo = request.env['res.partner'].sudo().with_company(request.website.company_id)
        values = partner_model_sudo._l10n_pe_lookup_document(number, sunat_code)
        if not values:
            return {'found': False, 'message': request.env._(
                'No se encontraron datos de ese documento. Complete sus datos a mano.')}
        return {'found': True, 'values': values, 'message': ''}
