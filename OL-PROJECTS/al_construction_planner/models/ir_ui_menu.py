# -*- coding: utf-8 -*-
from odoo import models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _load_menus_blacklist(self):
        """Con el planificador instalado, la aplicación «Gantt» se oculta: su
        diagrama, los colores por estado y el cronograma de la obra están en
        «Planificación de obra ▸ Obras ▸ Cronograma» y «Configuración». Se oculta
        desde el código (no se archiva el menú): al desinstalar el
        planificador, el Gantt vuelve a aparecer solo."""
        res = super()._load_menus_blacklist()
        gantt_root = self.env.ref('al_project_gantt_backend.menu_gantt_root', raise_if_not_found=False)
        if gantt_root:
            res.append(gantt_root.id)
        return res
