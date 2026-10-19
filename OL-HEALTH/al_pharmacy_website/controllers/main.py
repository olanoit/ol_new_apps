# -*- coding: utf-8 -*-
"""Receta en el checkout de la tienda en línea.

La receta se sube en un paso propio antes del pago: el carrito de la sesión
(``request.cart``) o, desde el portal, un pedido con su ``access_token``.
Nadie puede subir ni ver la receta de un pedido ajeno."""
import base64

from werkzeug.exceptions import NotFound

from odoo import _
from odoo.exceptions import AccessError, MissingError
from odoo.http import request, route
from odoo.tools.mimetypes import guess_mimetype

from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.website_sale.controllers.main import WebsiteSale

ALLOWED_MIMETYPES = ('image/jpeg', 'image/png', 'application/pdf')
MAX_SIZE = 5 * 1024 * 1024  # 5 MB


def _read_prescription(upload):
    """Contenido en base64 de la receta subida, o el mensaje de error."""
    if not upload or not getattr(upload, 'filename', None):
        return None, _('Elija la foto o el PDF de la receta.')
    data = upload.read(MAX_SIZE + 1)
    if len(data) > MAX_SIZE:
        return None, _('La receta pesa más de 5 MB: tome una foto más liviana.')
    if guess_mimetype(data) not in ALLOWED_MIMETYPES:
        return None, _('La receta debe ser una foto (JPG o PNG) o un PDF.')
    return base64.b64encode(data), None


class WebsiteSalePharmacy(WebsiteSale):

    @route()
    def shop_payment(self, **post):
        order_sudo = request.cart
        if (order_sudo and order_sudo.pharmacy_prescription_required
                and not order_sudo.pharmacy_prescription_uploaded):
            return request.redirect('/shop/pharmacy/prescription')
        return super().shop_payment(**post)

    @route('/shop/pharmacy/prescription', type='http', auth='public', website=True,
           sitemap=False, methods=['GET', 'POST'])
    def shop_pharmacy_prescription(self, prescription=None, **post):
        order_sudo = request.cart
        if not order_sudo or not order_sudo.pharmacy_prescription_required:
            return request.redirect('/shop/cart')
        error = None
        if request.httprequest.method == 'POST':
            content, error = _read_prescription(prescription)
            if content:
                order_sudo._pharmacy_save_prescription(content, prescription.filename)
                return request.redirect('/shop/payment')
        return request.render('al_pharmacy_website.prescription_upload', {
            'order': order_sudo,
            'error': error,
            'action_url': '/shop/pharmacy/prescription',
            'products': order_sudo.order_line.product_id.filtered(
                lambda p: p.pharmacy_sale_condition == 'prescription'),
        })


class PharmacyPortal(CustomerPortal):

    @route('/my/orders/<int:order_id>/prescription', type='http', auth='public', website=True,
           sitemap=False, methods=['GET', 'POST'])
    def portal_order_prescription(self, order_id, access_token=None, prescription=None, **post):
        """Subir otra receta a un pedido ya pagado (por ejemplo, tras un
        rechazo), solo con acceso al pedido."""
        try:
            order_sudo = self._document_check_access('sale.order', order_id, access_token=access_token)
        except (AccessError, MissingError):
            raise NotFound()
        if (not order_sudo.pharmacy_prescription_required
                or order_sudo.pharmacy_review_state == 'approved'):
            return request.redirect(order_sudo.get_portal_url())
        error = None
        if request.httprequest.method == 'POST':
            content, error = _read_prescription(prescription)
            if content:
                order_sudo._pharmacy_save_prescription(content, prescription.filename)
                return request.redirect(order_sudo.get_portal_url())
        action_url = '/my/orders/%s/prescription' % order_sudo.id
        if access_token:
            action_url += '?access_token=%s' % access_token
        return request.render('al_pharmacy_website.prescription_upload', {
            'order': order_sudo,
            'error': error,
            'action_url': action_url,
            'products': order_sudo.order_line.product_id.filtered(
                lambda p: p.pharmacy_sale_condition == 'prescription'),
        })
