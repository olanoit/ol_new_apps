# -*- coding: utf-8 -*-
import logging
from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models, tools

_logger = logging.getLogger(__name__)

# Hora local a la que corre el cron diario, y zona por defecto (Perú).
CRON_TIME = time(0, 5)
DEFAULT_TZ = 'America/Lima'

# Opciones de al.user.role.restriction: booleanas (aplican si todos los roles
# las tienen) y conjuntos (se oculta lo que ocultan todos los roles).
RESTRICTION_FLAGS = (
    'is_readonly', 'hide_create', 'hide_delete', 'hide_duplicate', 'hide_archive', 'hide_export',
)
RESTRICTION_SETS = {
    # clave: (campo, atributo del registro relacionado que se guarda)
    'hidden_fields': ('hidden_field_ids', 'name'),
    'readonly_fields': ('readonly_field_ids', 'name'),
    'required_fields': ('required_field_ids', 'name'),
    'no_open_fields': ('no_open_field_ids', 'name'),
    'buttons': ('hidden_button_ids', 'name'),
    'pages': ('hidden_page_ids', 'name'),
    'filters': ('hidden_filter_ids', 'name'),
    'reports': ('hidden_report_ids', 'id'),
    'server_actions': ('hidden_server_action_ids', 'id'),
}
# Opciones generales del rol.
ROLE_FLAGS = ('block_debug', 'hide_chatter', 'hide_send_message', 'readonly_all')
# Modelos que un usuario con "Todo en solo lectura" sigue pudiendo escribir:
# su sesión, preferencias, notas del chatter, adjuntos y filtros favoritos.
READONLY_ALL_EXEMPT_MODELS = frozenset({
    'bus.presence', 'discuss.channel', 'discuss.channel.member', 'ir.attachment',
    'ir.filters', 'mail.followers', 'mail.guest', 'mail.link.preview', 'mail.message',
    'mail.message.reaction', 'mail.notification', 'mail.presence', 'mail.tracking.value',
    'res.device', 'res.device.log', 'res.users', 'res.users.apikeys', 'res.users.log',
    'res.users.settings', 'res.users.settings.volumes',
})


class AlUserRole(models.Model):
    """Rol (perfil) de usuario.

    Cada rol *es* un grupo (``_inherits res.groups``): sus permisos son los
    grupos que implica (``implied_ids``) y los usuarios con el rol habilitado
    reciben todos esos grupos, también los implicados de forma transitiva.
    """
    _name = 'al.user.role'
    _inherits = {'res.groups': 'group_id'}
    _description = 'Rol de usuario'
    _order = 'sequence, name, id'

    group_id = fields.Many2one(
        'res.groups', string='Grupo asociado', required=True, readonly=True,
        ondelete='cascade', index=True,
        help='Grupo de seguridad que se crea con el rol y lo representa. Se crea y se '
             'borra junto con el rol; los usuarios con el rol lo reciben.',
    )
    sequence = fields.Integer(
        string='Secuencia', default=10, help='Orden del rol en las listas.',
    )
    line_ids = fields.One2many(
        'al.user.role.line', 'role_id', string='Asignaciones',
        help='Usuarios que tienen el rol, con su vigencia y compañía.',
    )
    # No se llama user_ids: ese nombre es el campo de usuarios del grupo heredado.
    role_user_ids = fields.Many2many(
        'res.users', string='Usuarios del rol',
        compute='_compute_role_user_ids', search='_search_role_user_ids',
        help='Usuarios con alguna asignación de este rol, vigente o no.',
    )
    role_user_count = fields.Integer(string='N.º de usuarios', compute='_compute_role_user_ids')
    effective_group_ids = fields.Many2many(
        'res.groups', string='Grupos efectivos', compute='_compute_effective_group_ids',
        help='Todos los grupos que recibe el usuario: los de Grupos más los que estos '
             'incluyen.',
    )
    model_access_ids = fields.Many2many(
        'ir.model.access', string='Permisos de acceso', compute='_compute_model_access_ids',
        help='Permisos sobre modelos (leer, escribir, crear, borrar) de los grupos efectivos.',
    )
    model_access_count = fields.Integer(string='N.º de permisos', compute='_compute_model_access_ids')
    rule_ids = fields.Many2many(
        'ir.rule', string='Reglas de registro', compute='_compute_rule_ids',
        help='Reglas que limitan qué registros ve o edita el usuario, según los grupos '
             'efectivos.',
    )
    rule_count = fields.Integer(string='N.º de reglas', compute='_compute_rule_ids')
    hidden_menu_ids = fields.Many2many(
        'ir.ui.menu', 'al_user_role_hidden_menu_rel', 'role_id', 'menu_id',
        string='Menús ocultos',
        help='Menús (y sus submenús) que no ven los usuarios con este rol. Un menú se '
             'oculta solo si todos los roles del usuario lo ocultan. Es solo visual: '
             'los permisos los dan los grupos.',
    )
    exclusive_permissions = fields.Boolean(
        string='Reemplazar permisos del usuario',
        help='Marcado: los grupos del usuario quedan exactamente iguales a los de sus '
             'roles y se pierde su configuración propia (si un rol vigente del usuario lo '
             'tiene marcado, manda). Sin marcar: el rol agrega sus grupos y conserva la '
             'configuración propia del usuario.',
    )
    is_default = fields.Boolean(
        string='Por defecto en usuarios nuevos',
        help='Se asigna automáticamente a cada usuario nuevo. No cambia a los usuarios '
             'que ya existen.',
    )
    restriction_ids = fields.One2many(
        'al.user.role.restriction', 'role_id', string='Restricciones por modelo', copy=True,
        help='Qué ocultar o bloquear en cada modelo. Con varios roles, una restricción '
             'aplica solo si todos los roles del usuario la tienen.',
    )
    block_debug = fields.Boolean(
        string='Bloquear modo desarrollador',
        help='El usuario no puede activar el modo desarrollador (?debug=1).',
    )
    hide_chatter = fields.Boolean(
        string='Ocultar chatter',
        help='No se muestran los mensajes, actividades ni seguidores en los formularios.',
    )
    hide_send_message = fields.Boolean(
        string='Ocultar Enviar mensaje',
        help='En el chatter no se puede enviar mensajes (llegan a los seguidores, p. ej. '
             'al cliente). Registrar nota, que es interna, sigue disponible.',
    )
    readonly_all = fields.Boolean(
        string='Todo en solo lectura',
        help='No se puede crear, editar, borrar ni archivar en ningún modelo, tampoco por '
             'otros caminos (botones, importación, API). Sí se puede usar el chatter, '
             'adjuntar archivos, guardar filtros y cambiar las preferencias propias.',
    )

    @api.depends('line_ids.user_id')
    def _compute_role_user_ids(self):
        for role in self:
            role.role_user_ids = role.line_ids.user_id
            role.role_user_count = len(role.role_user_ids)

    def _search_role_user_ids(self, operator, value):
        return [('line_ids.user_id', operator, value)]

    @api.depends('implied_ids.all_implied_ids')
    def _compute_effective_group_ids(self):
        for role in self:
            role.effective_group_ids = role.implied_ids.all_implied_ids

    @api.depends('implied_ids.all_implied_ids.model_access')
    def _compute_model_access_ids(self):
        for role in self:
            role.model_access_ids = role.implied_ids.all_implied_ids.model_access
            role.model_access_count = len(role.model_access_ids)

    @api.depends('implied_ids.all_implied_ids.rule_groups')
    def _compute_rule_ids(self):
        for role in self:
            role.rule_ids = role.implied_ids.all_implied_ids.rule_groups
            role.rule_count = len(role.rule_ids)

    @api.model_create_multi
    def create(self, vals_list):
        roles = super().create(vals_list)
        roles._update_users()
        return roles

    def write(self, vals):
        # Los campos del grupo se escriben aparte, en res.groups: el write de
        # grupos limpia cachés y, mezclado con los campos del rol, puede perder
        # valores (mismo resguardo que base_user_role).
        group_vals = {
            name: vals.pop(name) for name in list(vals)
            if name in self._fields and self._fields[name].inherited
        }
        if group_vals:
            self.group_id.write(group_vals)
        res = super().write(vals) if vals else True
        if {'hidden_menu_ids', 'restriction_ids', *ROLE_FLAGS} & vals.keys():
            # Menús visibles y restricciones se guardan en caché por grupos
            # (ir.ui.menu.load_menus, _al_ui_restrictions).
            self.env.registry.clear_cache()
        self._update_users()
        return res

    def unlink(self):
        users = self.role_user_ids
        groups = self.group_id
        # Las asignaciones se borran por ORM para que queden en el historial.
        self.line_ids.unlink()
        res = super().unlink()
        # _inherits no borra el registro padre: sin esto el grupo queda huérfano.
        groups.unlink()
        users._al_apply_roles(force=True)
        self.env.registry.clear_cache()
        return res

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        if 'name' not in (default or {}):
            for role, vals in zip(self, vals_list):
                vals['name'] = self.env._('%s (copia)', role.name)
        return vals_list

    def _update_users(self):
        """Reaplica los grupos de los usuarios con estos roles."""
        self.role_user_ids._al_apply_roles()

    @api.model
    def _al_role_tz(self):
        """Zona horaria de las vigencias en el cron: la de la compañía, o Lima."""
        return self.env.company.partner_id.tz or DEFAULT_TZ

    @api.model
    def _cron_update_users(self):
        _logger.info('Roles de usuario: actualizando grupos por vigencia')
        # El cron corre como __system__ (sin zona horaria, "hoy" sería UTC):
        # Desde / Hasta se evalúan en la zona de la compañía.
        self = self.with_context(tz=self._al_role_tz())
        batch, offset = 2000, 0
        while roles := self.search([], offset=offset, limit=batch):
            roles._update_users()
            offset += batch

    @api.model
    def _al_reset_cron_schedule(self):
        """Deja el cron diario y activo, con próxima ejecución a las 00:05.

        La hora es la de ``_al_role_tz`` (compañía, o Lima): las vigencias
        Desde / Hasta cambian a medianoche en esa zona.
        """
        cron = self.env.ref(
            'al_user_role.ir_cron_al_user_role_update_users', raise_if_not_found=False,
        )
        if not cron:
            return
        tz = pytz.timezone(self._al_role_tz())
        now_local = datetime.now(tz)
        next_local = tz.localize(datetime.combine(now_local.date(), CRON_TIME))
        if next_local <= now_local:
            next_local = tz.localize(
                datetime.combine(now_local.date() + timedelta(days=1), CRON_TIME)
            )
        cron.write({
            'interval_number': 1,
            'interval_type': 'days',
            'nextcall': next_local.astimezone(pytz.utc).replace(tzinfo=None),
            'active': True,
        })

    @api.model
    @tools.ormcache('frozenset(self.env.user._get_group_ids())')
    def _al_ui_restrictions(self):
        """Restricciones de interfaz y de registros del usuario actual.

        Los roles vigentes son los que el usuario tiene como grupo (los grupos
        ya siguen la vigencia y la compañía activa). Una restricción aplica
        solo si *todos* esos roles la tienen, igual que los menús ocultos: los
        roles suman acceso. El Administrador del sistema no tiene restricciones.

        :return: dict de solo lectura (está en caché, no modificar)::

            {'block_debug': bool, 'hide_chatter': bool, 'readonly_all': bool,
             'models': {modelo: {opción: bool, conjunto: frozenset}},
             'domains': {modelo: (dominio_texto, ...)}}

            o ``{}`` si no hay ninguna restricción.
        """
        user = self.env.user
        if not user or user._is_system():
            return {}
        # sudo: un usuario interno no tiene acceso de lectura a los roles.
        roles_sudo = self.sudo().search([('group_id', 'in', list(user._get_group_ids()))])
        if not roles_sudo:
            return {}
        result = {name: all(roles_sudo.mapped(name)) for name in ROLE_FLAGS}
        # Modelos con una línea en cada rol: si un rol no restringe el modelo,
        # el usuario no tiene restricciones en él.
        lines_by_role = [role.restriction_ids for role in roles_sudo]
        common_models = set.intersection(*(set(lines.mapped('model')) for lines in lines_by_role))
        models_res, domains = {}, {}
        for model in common_models:
            lines = [lines.filtered(lambda l: l.model == model) for lines in lines_by_role]
            spec = {flag: all(line[flag] for line in lines) for flag in RESTRICTION_FLAGS}
            for key, (fname, attr) in RESTRICTION_SETS.items():
                spec[key] = frozenset.intersection(
                    *(frozenset(line[fname].mapped(attr)) for line in lines))
            if any(spec.values()):
                models_res[model] = spec
            if all(line.domain and line.domain.strip() not in ('[]', '') for line in lines):
                domains[model] = tuple(line.domain for line in lines)
        result['models'] = models_res
        result['domains'] = domains
        if not (any(result[name] for name in ROLE_FLAGS) or models_res or domains):
            return {}
        return result

    @api.model
    def _al_is_readonly_model(self, model_name):
        """Si los roles del usuario dejan ``model_name`` en solo lectura real.

        Por modelo (``is_readonly``) o en general (``readonly_all``, salvo los
        modelos exentos y los asistentes). Sin roles o como Administrador del
        sistema, nunca.
        """
        restrictions = self._al_ui_restrictions()
        if not restrictions:
            return False
        if restrictions['models'].get(model_name, {}).get('is_readonly'):
            return True
        if not restrictions['readonly_all'] or model_name in READONLY_ALL_EXEMPT_MODELS:
            return False
        model = self.env.get(model_name)
        return model is not None and not model._transient and not model._abstract

    def action_view_model_access(self):
        action = self.env['ir.actions.actions']._for_xml_id('base.ir_access_act')
        action['domain'] = [('id', 'in', self.model_access_ids.ids)]
        return action

    def action_view_rules(self):
        action = self.env['ir.actions.actions']._for_xml_id('base.action_rule')
        action['domain'] = [('id', 'in', self.rule_ids.ids)]
        return action

    def action_view_users(self):
        action = self.env['ir.actions.actions']._for_xml_id('base.action_res_users')
        action['domain'] = [('id', 'in', self.role_user_ids.ids)]
        action['context'] = {}
        return action
