# -*- coding: utf-8 -*-
from odoo import Command, fields, models


class AlUserRoleFromGroupsWizard(models.TransientModel):
    """Crea un rol con los grupos seleccionados en la lista de grupos."""
    _name = 'al.user.role.from.groups.wizard'
    _description = 'Crear rol desde grupos'

    name = fields.Char(
        string='Nombre del rol', required=True, help='Nombre del rol que se va a crear.',
    )
    group_ids = fields.Many2many(
        'res.groups', string='Grupos', required=True,
        default=lambda self: self._default_group_ids(),
        help='Grupos que otorgará el rol. Vienen los seleccionados en la lista de grupos.',
    )

    def _default_group_ids(self):
        if self.env.context.get('active_model') == 'res.groups':
            return [Command.set(self.env.context.get('active_ids') or [])]
        return False

    def action_create_role(self):
        self.ensure_one()
        role = self.env['al.user.role'].create({
            'name': self.name,
            'implied_ids': [Command.set(self.group_ids.ids)],
        })
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Rol de usuario'),
            'res_model': 'al.user.role',
            'view_mode': 'form',
            'res_id': role.id,
            'target': 'current',
        }
