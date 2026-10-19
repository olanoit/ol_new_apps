# -*- coding: utf-8 -*-
from . import models


def _post_init_hook(env):
    """Los programas que ya existían toman la exclusión por defecto: sus
    descuentos sobre el pedido pasan a aplicarse solo a los productos de venta
    libre."""
    env['loyalty.reward'].with_context(active_test=False).search([])._pharmacy_restrict_order_discount()
