# -*- coding: utf-8 -*-
from odoo import Command, api, fields, models

# Escrituras de res.users que pueden dejar los grupos fuera de lo que dicen
# los roles: se reaplican los roles después (y no en cualquier write, como
# login_date en cada inicio de sesión).
ROLE_SENSITIVE_FIELDS = {
    'al_role_line_ids', 'group_ids', 'role', 'company_id', 'company_ids', 'active',
}


class ResUsers(models.Model):
    _inherit = 'res.users'

    # active_test=False: la asignación es archivable (active = user_id.active)
    # y en un usuario nuevo, aún sin guardar, se filtraría. El formulario
    # perdería los roles por defecto.
    al_role_line_ids = fields.One2many(
        'al.user.role.line', 'user_id', string='Roles',
        default=lambda self: self._al_default_role_lines(),
        context={'active_test': False},
        groups='base.group_erp_manager',
    )
    al_role_ids = fields.Many2many(
        'al.user.role', string='Roles asignados',
        compute='_compute_al_role_ids', search='_search_al_role_ids',
        compute_sudo=True, groups='base.group_erp_manager',
    )
    al_role_count = fields.Integer(
        string='N.º de roles', compute='_compute_al_role_ids', compute_sudo=True,
        groups='base.group_erp_manager',
    )
    al_role_granted_group_ids = fields.Many2many(
        'res.groups', 'al_res_users_role_granted_group_rel', 'user_id', 'group_id',
        string='Grupos otorgados por roles', readonly=True, copy=False,
        groups='base.group_erp_manager',
        help='Grupos que el usuario tiene solo por sus roles (no por su configuración '
             'propia). Son los que se le quitan cuando el rol se quita o vence.',
    )
    # Aviso azul: un rol vigente reemplaza los permisos del usuario.
    al_show_role_alert = fields.Boolean(
        compute='_compute_al_show_role_alert', groups='base.group_erp_manager',
    )
    # Aviso gris: roles vigentes que solo agregan grupos.
    al_show_role_info = fields.Boolean(
        compute='_compute_al_show_role_alert', groups='base.group_erp_manager',
    )
    al_role_last_change = fields.Datetime(
        string='Último cambio de roles', compute='_compute_al_role_last_change',
        groups='base.group_erp_manager',
    )

    @api.model
    def _al_default_role_lines(self):
        roles = self.env['al.user.role'].search([('is_default', '=', True)])
        return [Command.create({'role_id': role.id}) for role in roles]

    @api.depends('al_role_line_ids.role_id')
    def _compute_al_role_ids(self):
        for user in self:
            user.al_role_ids = user.al_role_line_ids.role_id
            user.al_role_count = len(user.al_role_ids)

    def _search_al_role_ids(self, operator, value):
        return [('al_role_line_ids.role_id', operator, value)]

    @api.depends('al_role_line_ids.is_enabled', 'al_role_line_ids.role_id.exclusive_permissions')
    def _compute_al_show_role_alert(self):
        for user in self:
            roles = user.al_role_line_ids.filtered('is_enabled').role_id
            exclusive = any(roles.mapped('exclusive_permissions'))
            user.al_show_role_alert = exclusive
            user.al_show_role_info = bool(roles) and not exclusive

    def _compute_al_role_last_change(self):
        History = self.env['al.user.role.history']
        for user in self:
            last = History.search([('user_id', '=', user.id)], limit=1, order='id desc')
            user.al_role_last_change = last.create_date

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users._al_apply_roles()
        return users

    def write(self, vals):
        res = super().write(vals)
        if ROLE_SENSITIVE_FIELDS.intersection(vals):
            # sudo: los grupos los fijan los roles, no quien edita el usuario.
            users_sudo = self.sudo()
            users_sudo._al_apply_roles()
        return res

    def authenticate(self, *args, **kwargs):
        auth_info = super().authenticate(*args, **kwargs)
        # Al iniciar sesión aplican los roles de la compañía por defecto.
        uid = auth_info.get('uid') if isinstance(auth_info, dict) else None
        if uid:
            # sudo: el usuario que inicia sesión no puede escribir sus propios grupos.
            user_sudo = self.env['res.users'].sudo().browse(uid)
            if user_sudo.al_role_line_ids:
                user_sudo._al_apply_roles()
        return auth_info

    # ------------------------------------------------------------------
    # Roles -> grupos
    # ------------------------------------------------------------------
    def _al_get_enabled_role_lines(self):
        """Asignaciones vigentes del usuario para las compañías activas.

        Sin compañía, la asignación aplica siempre. Con compañía, aplica solo
        si esa compañía está activa y el usuario tiene el mismo rol en *todas*
        las compañías activas (si no, al trabajar en varias compañías a la vez
        tendría permisos de una compañía sobre los datos de otra).
        """
        self.ensure_one()
        lines = self.al_role_line_ids.filtered('is_enabled')
        company_ids = self.env.context.get('al_active_company_ids') or self.company_id.ids
        enabled = self.env['al.user.role.line']
        for line in lines:
            if not line.company_id:
                enabled |= line
            elif line.company_id.id in company_ids:
                role_companies = lines.filtered(
                    lambda l, role=line.role_id: l.role_id == role and l.company_id
                ).company_id
                if set(company_ids) <= set(role_companies.ids):
                    enabled |= line
        return enabled

    @api.model
    def _al_get_self_writable_groups(self):
        """Grupos que el usuario elige él mismo: los roles no los quitan ni dan."""
        groups = self.env.ref('base.group_multi_company')
        inbox = self.env.ref('mail.group_mail_notification_type_inbox', raise_if_not_found=False)
        return groups | inbox if inbox else groups

    def _al_apply_roles(self, force=False):
        """Sincroniza los grupos de cada usuario con sus roles habilitados.

        - Si algún rol vigente tiene *Reemplazar permisos del usuario*, los
          grupos quedan exactamente iguales a los de sus roles.
        - Si no, los roles *agregan* sus grupos a la configuración propia del
          usuario (sus grupos menos los que le dieron los roles la vez
          anterior, ``al_role_granted_group_ids``). Al quitarse o vencer un
          rol solo se quitan los grupos que daba y que el usuario no tenía
          por su cuenta.

        Un usuario sin roles queda intacto, salvo con ``force`` (se le quitó su
        último rol). Nunca se quita el grupo Administrador al último
        administrador del sistema.
        """
        self_writable_ids = set(self._al_get_self_writable_groups().ids)
        admin_group = self.env.ref('base.group_system')
        group_user = self.env.ref('base.group_user')
        for user in self:
            if not user.al_role_line_ids and not force:
                continue
            current_ids = set(user.group_ids.ids) - self_writable_ids
            roles = user._al_get_enabled_role_lines().role_id
            role_group_ids = set(roles.group_id.all_implied_ids.ids) - self_writable_ids
            previous_granted_ids = set(user.al_role_granted_group_ids.ids)
            if any(roles.mapped('exclusive_permissions')):
                target_ids = set(role_group_ids)
                granted_ids = set(role_group_ids)
            else:
                # Un grupo quitado a mano que da un rol vigente vuelve: el rol
                # garantiza sus grupos mientras esté vigente.
                own_ids = current_ids - previous_granted_ids
                target_ids = own_ids | role_group_ids
                granted_ids = role_group_ids - own_ids
            if admin_group.id in current_ids and admin_group.id not in target_ids:
                # sudo: contar a los demás administradores aunque quien edita
                # no pueda leer todos los usuarios (multicompañía).
                users_sudo = self.sudo()
                other_admins = users_sudo.search_count([
                    ('id', '!=', user.id), ('group_ids', 'in', admin_group.id),
                ])
                if not other_admins:
                    target_ids.add(admin_group.id)
            to_add, to_remove = target_ids - current_ids, current_ids - target_ids
            vals = {}
            if granted_ids != previous_granted_ids:
                vals['al_role_granted_group_ids'] = [Command.set(list(granted_ids))]
            if to_add or to_remove:
                vals['group_ids'] = ([Command.unlink(gid) for gid in to_remove]
                                     + [Command.link(gid) for gid in to_add])
            if not vals:
                continue
            # Sin usuario interno no puede tener notificaciones en Odoo (inbox).
            if (group_user.id in to_remove and 'notification_type' in user._fields
                    and user.notification_type == 'inbox'):
                vals['notification_type'] = 'email'
            # super(): el write propio volvería a aplicar los roles.
            super(ResUsers, user).write(vals)
        return True

    def action_al_view_roles(self):
        """Roles del usuario: el formulario si tiene uno, la lista si tiene varios."""
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('al_user_role.action_al_user_role')
        action['context'] = {}
        roles = self.al_role_ids
        if len(roles) == 1:
            action.update(views=[(False, 'form')], view_mode='form', res_id=roles.id)
        else:
            action['domain'] = [('id', 'in', roles.ids)]
        return action

    def action_al_role_history(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'al_user_role.action_al_user_role_history'
        )
        action['domain'] = [('user_id', '=', self.id)]
        action['context'] = {}
        return action
