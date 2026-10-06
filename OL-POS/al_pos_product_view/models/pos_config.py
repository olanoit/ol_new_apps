# -*- coding: utf-8 -*-
from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    # `pos.config` hereda `pos.load.mixin` y se carga con TODOS los campos
    # por defecto, así que ambos flags están disponibles en el frontend como
    # `pos.config.<campo>`.

    # --- Filtro por etiquetas ----------------------------------------------
    iface_filter_products_by_tag = fields.Boolean(
        string="Filtrar productos por etiqueta",
        # Activado por defecto: la fila de chips es la funcionalidad por la
        # que existe este módulo; cada TPV puede desactivarla.
        default=True,
        help=(
            "Muestra una fila de chips de etiquetas de producto sobre el "
            "catálogo del TPV. Seleccionar una o varias etiquetas acota el "
            "catálogo a los productos que llevan alguna de ellas."
        ),
    )

    # --- Conmutador cuadrícula/lista ---------------------------------------
    default_product_view = fields.Selection(
        selection=[
            ("grid", "Cuadrícula (tarjetas)"),
            ("list", "Lista (filas compactas)"),
        ],
        string="Vista de productos por defecto",
        default="grid",
        required=True,
        help=(
            "Disposición por defecto del catálogo de productos en el TPV. "
            "El cajero puede cambiar de vista en cualquier momento."
        ),
    )
