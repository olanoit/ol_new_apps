# -*- coding: utf-8 -*-
import os

from odoo import api, fields, models, tools

# Marca que ``docs/validacion/fichas_modulos.py`` deja en las fichas que
# prepara: distingue una ficha completa de la descripción genérica que
# traen muchos módulos de Odoo.
FICHA_MARKER = b'al-ficha-link'
FICHA_PATH = 'static/description/index.html'


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    al_ficha_url = fields.Char(
        string='Ficha completa del módulo',
        compute='_compute_al_ficha_url',
        help='Dirección de la ficha completa del módulo, si la tiene.')

    @api.depends('name')
    def _compute_al_ficha_url(self):
        for module in self:
            module.al_ficha_url = (
                self._al_ficha_url(module.name) if module.name else False)

    @api.model
    @tools.ormcache('name')
    def _al_ficha_url(self, name):
        """URL de la ficha, o False. En caché: el kanban la pide por cada
        tarjeta y la ficha solo cambia con el código del módulo."""
        try:
            with tools.file_open(os.path.join(name, FICHA_PATH), 'rb') as ficha:
                if FICHA_MARKER in ficha.read():
                    return '/%s/%s' % (name, FICHA_PATH)
        except (OSError, ValueError):
            # sin ficha, o módulo fuera del addons_path
            pass
        return False
