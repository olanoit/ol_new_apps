# -*- coding: utf-8 -*-
import base64

from odoo import SUPERUSER_ID, api
from odoo.tools.misc import file_open


def migrate(cr, version):
    """Ícono nuevo al estilo de Odoo (los datos del proveedor son noupdate)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    with file_open('al_payment_izipay/static/description/icon.png', 'rb') as icon:
        image = base64.b64encode(icon.read())
    env['payment.provider'].with_context(active_test=False).search([('code', '=', 'izipay')]).image_128 = image
