# -*- coding: utf-8 -*-
from odoo import fields, models


class ResGroups(models.Model):
    _inherit = 'res.groups'

    # Inverso de al.user.role.group_id: el rol que *es* este grupo (0 o 1).
    al_role_id = fields.One2many('al.user.role', 'group_id', string='Rol asociado')
    al_role_ids = fields.Many2many(
        'al.user.role', string='Roles que lo otorgan', compute='_compute_al_role_ids',
        help='Roles que dan este grupo, directa o transitivamente.',
    )
    al_role_count = fields.Integer(string='N.º de roles', compute='_compute_al_role_ids')

    def _compute_al_role_ids(self):
        Role = self.env['al.user.role']
        for group in self:
            # all_implied_by_ids es reflexivo: incluye al propio grupo.
            group.al_role_ids = Role.search([('group_id', 'in', group.all_implied_by_ids.ids)])
            group.al_role_count = len(group.al_role_ids)

    def action_al_view_roles(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('al_user_role.action_al_user_role')
        action['context'] = {}
        if len(self.al_role_ids) == 1:
            action.update(views=[(False, 'form')], view_mode='form', res_id=self.al_role_ids.id)
        else:
            action['domain'] = [('id', 'in', self.al_role_ids.ids)]
        return action
