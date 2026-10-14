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
        if not self._is_peru_company() or not rendering_values.get('is_latam_country'):
            return rendering_values
        identification_type = rendering_values['identification_type']
        rendering_values.update({
            'l10n_pe_ruc_type': request.env.ref('l10n_pe.it_RUC'),
            'l10n_pe_dni_type': request.env.ref('l10n_pe.it_DNI'),
            'l10n_pe_receipt': 'factura' if identification_type.l10n_pe_vat_code == '6' else 'boleta',
        })
        return rendering_values

    @route('/shop/l10n_pe/document_lookup', type='jsonrpc', auth='public', website=True,
           methods=['POST'], sitemap=False)
    def l10n_pe_document_lookup(self, number, identification_type_id):
        """Datos de un RUC o DNI para llenar la dirección del checkout.

        :param str number: número de documento.
        :param int identification_type_id: tipo de documento elegido.
        :return: ``{'found': bool, 'values': {...}, 'message': str}``
        """
        if not self._is_peru_company():
            return {'found': False, 'message': ''}
        identification_type = request.env['l10n_latam.identification.type'].sudo().browse(
            int(identification_type_id or 0)).exists()
        if identification_type.l10n_pe_vat_code not in ('1', '6'):
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
        values = partner_model_sudo._l10n_pe_lookup_document(number, identification_type)
        if not values:
            return {'found': False, 'message': request.env._(
                'No se encontraron datos de ese documento. Complete sus datos a mano.')}
        return {'found': True, 'values': values, 'message': ''}
