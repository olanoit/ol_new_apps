# -*- coding: utf-8 -*-
from odoo import Command, fields, models
from odoo.exceptions import UserError


class AlUserRoleFromUserWizard(models.TransientModel):
    """Crea un rol con los grupos actuales de un usuario."""
    _name = 'al.user.role.from.user.wizard'
    _description = 'Crear rol desde un usuario'

    name = fields.Char(string='Nombre del rol', required=True)
    user_id = fields.Many2one(
        'res.users', string='Usuario', required=True,
        default=lambda self: self._default_user_id(),
    )
    assign_to_user = fields.Boolean(
        string='Asignar el rol al usuario', default=True,
        help='El usuario pasa a tener sus permisos administrados por este rol.',
    )

    def _default_user_id(self):
        if self.env.context.get('active_model') == 'res.users':
            return self.env.context.get('active_id')
        return False

    def action_create_role(self):
        self.ensure_one()
        if self.user_id.share:
            raise UserError(self.env._('Solo se crean roles desde usuarios internos.'))
        role = self.env['al.user.role'].create({
            'name': self.name,
            'implied_ids': [Command.set(self.user_id.group_ids.ids)],
        })
        if self.assign_to_user:
            self.env['al.user.role.line'].create({
                'role_id': role.id, 'user_id': self.user_id.id,
            })
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Rol de usuario'),
            'res_model': 'al.user.role',
            'view_mode': 'form',
            'res_id': role.id,
            'target': 'current',
        }
