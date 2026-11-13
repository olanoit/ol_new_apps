# -*- coding: utf-8 -*-
from functools import reduce

from odoo import api, fields, models, tools


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    # Inverso de al.user.role.hidden_menu_ids (pantalla Menús ocultos por rol).
    al_hiding_role_ids = fields.Many2many(
        'al.user.role', 'al_user_role_hidden_menu_rel', 'menu_id', 'role_id',
        string='Roles que lo ocultan',
        help='El menú se oculta a un usuario solo si todos sus roles lo ocultan.',
    )

    def _filter_visible_menus(self):
        """Quita los menús que ocultan los roles del usuario.

        Ocultar un menú es solo visual: no cambia los permisos del usuario
        sobre los modelos (eso lo dan los grupos del rol).
        """
        menus = super()._filter_visible_menus()
        hidden_ids = self._al_role_hidden_menu_ids()
        if not hidden_ids:
            return menus
        return menus.filtered(lambda menu: menu.id not in hidden_ids)

    @api.model
    @tools.ormcache('frozenset(self.env.user._get_group_ids())')
    def _al_role_hidden_menu_ids(self):
        """Ids de los menús ocultos para los grupos del usuario actual.

        Los roles habilitados son los que el usuario tiene como grupo: los
        grupos ya siguen la vigencia y la compañía activa (_al_apply_roles).
        Un menú se oculta si *todos* sus roles lo ocultan, porque los roles
        suman acceso igual que los grupos. Ocultar un menú oculta también
        sus submenús. La caché depende solo de los grupos y se limpia al
        cambiar los grupos del usuario o los menús ocultos de un rol.
        """
        user = self.env.user
        if user._is_system():
            return frozenset()
        # sudo: un usuario interno no tiene acceso de lectura a los roles.
        roles_sudo = self.env['al.user.role'].sudo().search([
            ('group_id', 'in', list(user._get_group_ids())),
        ])
        if not roles_sudo or not all(role.hidden_menu_ids for role in roles_sudo):
            return frozenset()
        menus_sudo = self.sudo().with_context(active_test=False)
        hidden_by_role = [
            set(menus_sudo.search([('id', 'child_of', role.hidden_menu_ids.ids)]).ids)
            for role in roles_sudo
        ]
        return frozenset(reduce(set.intersection, hidden_by_role))
