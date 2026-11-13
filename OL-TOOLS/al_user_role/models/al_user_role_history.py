# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AlUserRoleHistory(models.Model):
    """Historial de altas, cambios y bajas de roles por usuario (solo lectura).

    Quién y cuándo: create_uid / create_date. El nombre del rol se guarda
    aparte para que el registro se lea aunque el rol se borre después.
    """
    _name = 'al.user.role.history'
    _description = 'Historial de roles de usuario'
    _order = 'id desc'

    action = fields.Selection(
        [('add', 'Alta'), ('edit', 'Cambio'), ('unlink', 'Baja')],
        string='Acción', required=True, readonly=True,
    )
    user_id = fields.Many2one(
        'res.users', string='Usuario', ondelete='cascade', index=True, readonly=True,
    )
    old_role_id = fields.Many2one('al.user.role', string='Rol anterior', ondelete='set null', readonly=True)
    new_role_id = fields.Many2one('al.user.role', string='Rol nuevo', ondelete='set null', readonly=True)
    old_role_name = fields.Char(string='Nombre rol anterior', readonly=True)
    new_role_name = fields.Char(string='Nombre rol nuevo', readonly=True)
    old_date_from = fields.Date(string='Desde (anterior)', readonly=True)
    new_date_from = fields.Date(string='Desde (nuevo)', readonly=True)
    old_date_to = fields.Date(string='Hasta (anterior)', readonly=True)
    new_date_to = fields.Date(string='Hasta (nuevo)', readonly=True)
    old_is_enabled = fields.Boolean(string='Habilitado (anterior)', readonly=True)
    new_is_enabled = fields.Boolean(string='Habilitado (nuevo)', readonly=True)
    old_company_id = fields.Many2one('res.company', string='Compañía (anterior)', ondelete='set null', readonly=True)
    new_company_id = fields.Many2one('res.company', string='Compañía (nueva)', ondelete='set null', readonly=True)

    @api.depends('action', 'new_role_name', 'old_role_name', 'user_id.name')
    def _compute_display_name(self):
        actions = dict(self._fields['action']._description_selection(self.env))
        for record in self:
            role = record.new_role_name or record.old_role_name or ''
            record.display_name = (
                f'{actions.get(record.action, "")}: {role} → {record.user_id.name or ""}'
            )
