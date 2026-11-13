# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AlUserRoleAddUsersWizard(models.TransientModel):
    """Asigna un rol a varios usuarios a la vez (omite a quienes ya lo tienen)."""
    _name = 'al.user.role.add.users.wizard'
    _description = 'Agregar usuarios a un rol'
    _check_company_auto = True

    role_id = fields.Many2one('al.user.role', string='Rol', required=True, ondelete='cascade')
    user_ids = fields.Many2many(
        'res.users', string='Usuarios', required=True,
        domain=[('share', '=', False)],
    )
    date_from = fields.Date(string='Desde')
    date_to = fields.Date(string='Hasta')
    company_id = fields.Many2one(
        'res.company', string='Compañía',
        help='Opcional: el rol solo aplica cuando esta compañía está activa.',
    )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise ValidationError(self.env._('La fecha Desde es posterior a Hasta.'))

    def action_add_users(self):
        self.ensure_one()
        existing = self.role_id.line_ids.filtered(
            lambda line: line.company_id == self.company_id
        ).user_id
        new_users = self.user_ids - existing
        if self.company_id:
            missing = new_users.filtered(lambda user: self.company_id not in user.company_ids)
            if missing:
                raise ValidationError(self.env._(
                    'Sin acceso a la compañía %(company)s: %(users)s',
                    company=self.company_id.name, users=', '.join(missing.mapped('name')),
                ))
        self.env['al.user.role.line'].create([{
            'role_id': self.role_id.id,
            'user_id': user.id,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'company_id': self.company_id.id,
        } for user in new_users])
        return {'type': 'ir.actions.act_window_close'}
