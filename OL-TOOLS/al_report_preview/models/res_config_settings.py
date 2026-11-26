# -*- coding: utf-8 -*-
from odoo import fields, models

from .ir_actions_report import PREVIEW_SCOPE_DEFAULT, PREVIEW_SCOPE_PARAM


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    al_report_preview_scope = fields.Selection(
        selection=[
            ('all', 'Todos los reportes'),
            ('selected', 'Solo los reportes elegidos'),
        ],
        string='Abrir en el navegador',
        config_parameter=PREVIEW_SCOPE_PARAM,
        default=PREVIEW_SCOPE_DEFAULT, required=True,
        help="Todos los reportes: cada PDF se abre en una pestaña, salvo los "
             "reportes marcados como «Descargar».\n"
             "Solo los reportes elegidos: se descargan, salvo los reportes "
             "marcados como «Abrir en el navegador».")
