# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.api import SUPERUSER_ID
from odoo.exceptions import ValidationError

# Campos de una asignación que se guardan en el historial (anterior / nuevo).
HISTORY_FIELDS = ('role_id', 'date_from', 'date_to', 'is_enabled', 'company_id')


class AlUserRoleLine(models.Model):
    """Asignación de un rol a un usuario, con vigencia y compañía opcionales."""
    _name = 'al.user.role.line'
    _description = 'Asignación de rol de usuario'
    _order = 'role_id, id'

    role_id = fields.Many2one(
        'al.user.role', string='Rol', required=True, ondelete='cascade', index=True,
        help='Rol que se asigna al usuario.',
    )
    user_id = fields.Many2one(
        'res.users', string='Usuario', required=True, ondelete='cascade', index=True,
        domain=[('id', '!=', SUPERUSER_ID)],
        help='Usuario que recibe los grupos del rol.',
    )
    active = fields.Boolean(related='user_id.active')
    date_from = fields.Date(
        string='Desde', help='Primer día en que aplica el rol. Vacío: desde siempre.',
    )
    date_to = fields.Date(
        string='Hasta', help='Último día en que aplica el rol. Vacío: sin vencimiento.',
    )
    is_enabled = fields.Boolean(
        string='Habilitado', compute='_compute_is_enabled',
        help='El rol está dentro de su vigencia (desde / hasta).',
    )
    allowed_company_ids = fields.Many2many(related='user_id.company_ids')
    company_id = fields.Many2one(
        'res.company', string='Compañía',
        domain="[('id', 'in', allowed_company_ids)]",
        help='Si se indica, el rol solo aplica cuando esta compañía está activa. '
             'Vacío: aplica en todas las compañías.',
    )

    # Un mismo rol una sola vez por usuario y compañía; sin compañía cuenta
    # como "0" (en un UNIQUE normal, dos NULL no chocan).
    _user_role_company_uniq = models.UniqueIndex(
        '(user_id, role_id, COALESCE(company_id, 0))',
        'Un usuario solo puede tener el mismo rol una vez por compañía.',
    )

    @api.depends('role_id.name', 'user_id.name', 'company_id.name')
    def _compute_display_name(self):
        for line in self:
            name = f'{line.role_id.name or ""} → {line.user_id.name or ""}'
            if line.company_id:
                name += f' ({line.company_id.name})'
            line.display_name = name

    @api.depends('date_from', 'date_to')
    def _compute_is_enabled(self):
        today = fields.Date.context_today(self)
        for line in self:
            line.is_enabled = (
                (not line.date_from or line.date_from <= today)
                and (not line.date_to or line.date_to >= today)
            )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for line in self:
            if line.date_from and line.date_to and line.date_from > line.date_to:
                raise ValidationError(self.env._(
                    'Rol "%(role)s" de "%(user)s": la fecha Desde es posterior a Hasta.',
                    role=line.role_id.name, user=line.user_id.name,
                ))

    # No se llama _check_company: pisaría el método de BaseModel que usa
    # _check_company_auto.
    @api.constrains('user_id', 'company_id')
    def _check_user_company(self):
        for line in self:
            if line.company_id and line.company_id not in line.user_id.company_ids:
                raise ValidationError(self.env._(
                    'El usuario "%(user)s" no tiene acceso a la compañía "%(company)s".',
                    user=line.user_id.name, company=line.company_id.name,
                ))

    # ------------------------------------------------------------------
    # Historial y sincronización de grupos
    # ------------------------------------------------------------------
    def _history_values(self, prefix):
        self.ensure_one()
        vals = {}
        for name in HISTORY_FIELDS:
            value = self[name]
            vals[f'{prefix}_{name}'] = value.id if isinstance(value, models.BaseModel) else value
        if prefix == 'old':
            vals['old_role_name'] = self.role_id.name
        else:
            vals['new_role_name'] = self.role_id.name
        return vals

    def _create_history(self, history_vals):
        if history_vals:
            # sudo: el historial es de solo lectura incluso para el
            # Administrador de permisos; solo este método lo escribe.
            history_sudo = self.env['al.user.role.history'].sudo()
            history_sudo.create(history_vals)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        self._create_history([
            {'action': 'add', 'user_id': line.user_id.id, **line._history_values('new')}
            for line in lines
        ])
        lines.user_id._al_apply_roles()
        return lines

    def write(self, vals):
        old = {line.id: line._history_values('old') for line in self}
        old_users = self.user_id
        res = super().write(vals)
        history_vals = []
        for line in self:
            new = line._history_values('new')
            changed = any(
                old[line.id][f'old_{name}'] != new[f'new_{name}'] for name in HISTORY_FIELDS
            )
            if changed:
                history_vals.append({
                    'action': 'edit', 'user_id': line.user_id.id, **old[line.id], **new,
                })
        self._create_history(history_vals)
        (old_users | self.user_id)._al_apply_roles(force=True)
        return res

    def unlink(self):
        users = self.user_id
        self._create_history([
            {'action': 'unlink', 'user_id': line.user_id.id, **line._history_values('old')}
            for line in self
        ])
        res = super().unlink()
        users.exists()._al_apply_roles(force=True)
        return res
