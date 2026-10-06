from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Campos relacionados a la caja seleccionada en Ajustes PdV: la marca se
    # configura por caja (TPV 1, TPV 2...) sin tocar código.
    pos_al_theme_brand_name = fields.Char(related="pos_config_id.al_theme_brand_name", readonly=False)
    pos_al_theme_logo = fields.Image(related="pos_config_id.al_theme_logo", readonly=False)
    pos_al_theme_favicon = fields.Image(related="pos_config_id.al_theme_favicon", readonly=False)
    pos_al_theme_color_primary = fields.Char(related="pos_config_id.al_theme_color_primary", readonly=False)
    pos_al_theme_color_secondary = fields.Char(related="pos_config_id.al_theme_color_secondary", readonly=False)
    pos_al_theme_color_accent = fields.Char(related="pos_config_id.al_theme_color_accent", readonly=False)
    pos_al_theme_color_background = fields.Char(related="pos_config_id.al_theme_color_background", readonly=False)
