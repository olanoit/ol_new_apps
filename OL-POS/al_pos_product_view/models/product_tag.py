# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductTag(models.Model):
    _inherit = "product.tag"

    show_in_pos_filter = fields.Boolean(
        string="Mostrar en la barra de filtros del TPV",
        default=True,
        help=(
            "Mostrar esta etiqueta como chip en la barra de filtros del TPV. "
            "Desmarcarla solo oculta el chip (útil para mantener la barra "
            "corta cuando hay muchas etiquetas); NO afecta a la lógica de "
            "filtrado ni a las etiquetas mostradas en los productos."
        ),
    )

    @api.model
    def _load_pos_data_fields(self, config):
        # `sequence` no está en la carga estándar del TPV: el orden de los
        # chips respeta el del backend. `show_in_pos_filter`: los registros
        # cacheados por un dispositivo antes de existir el campo lo cargan
        # como `undefined` y el selector trata cualquier valor distinto de
        # `false` explícito como visible (el default del campo).
        return super()._load_pos_data_fields(config) + [
            "show_in_pos_filter", "sequence",
        ]
