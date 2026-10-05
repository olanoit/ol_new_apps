# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # --- Filtro por etiquetas ----------------------------------------------
    pos_iface_filter_products_by_tag = fields.Boolean(
        related="pos_config_id.iface_filter_products_by_tag",
        readonly=False,
    )

    # --- Conmutador cuadrícula/lista ---------------------------------------
    pos_default_product_view = fields.Selection(
        related="pos_config_id.default_product_view",
        readonly=False,
    )
