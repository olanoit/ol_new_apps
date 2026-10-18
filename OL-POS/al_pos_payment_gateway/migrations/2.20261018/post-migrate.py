# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Los métodos en línea creados antes de esta versión toman el logo de su pasarela."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['pos.payment.method'].with_context(active_test=False).search(
        [('is_online_payment', '=', True)])._al_set_provider_logo()
