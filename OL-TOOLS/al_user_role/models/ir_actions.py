# -*- coding: utf-8 -*-
from odoo import models


class IrActionsActions(models.Model):
    _inherit = 'ir.actions.actions'

    def get_bindings(self, model_name):
        """Quita de Imprimir / Acciones lo que ocultan los roles del usuario.

        ``_get_bindings`` está en caché por modelo e idioma; este filtro corre
        después, por usuario (igual que el filtro por grupos de Odoo).
        """
        result = super().get_bindings(model_name)
        if self.env.su:
            return result
        restrictions = self.env['al.user.role']._al_ui_restrictions()
        spec = restrictions.get('models', {}).get(model_name) if restrictions else None
        if not spec or not (spec['reports'] or spec['server_actions']):
            return result
        # Los ids de acciones son únicos entre todos los tipos (heredan de
        # ir.actions.actions); los bindings no traen el tipo de acción.
        hidden = spec['reports'] | spec['server_actions']
        result = {
            key: [action for action in actions if action['id'] not in hidden]
            for key, actions in result.items()
        }
        return {key: actions for key, actions in result.items() if actions}

