# -*- coding: utf-8 -*-
"""Personal del portal de obra, ingreso y sesiones (requerimiento CREVAL v1.0,
4.11).

* Miembro del portal: el capataz o maestro de obra, la contrata y la oficina
  técnica asignados a una obra, cada uno con su usuario (de portal o
  interno), su papel y, para el ingreso por QR, un PIN de 4 dígitos que le
  asigna el residente. Tres PIN errados bloquean su ingreso por QR.
* Código de la obra: va en el QR del cartel de la obra y se puede regenerar.
* Token del portal: el que guarda el celular después de ingresar (con usuario
  y clave o con el QR y el PIN). Vale solo para los servicios del portal, no
  para el escritorio ni el RPC de Odoo, y vence a los días que fije la
  compañía (90 por defecto). Se guarda solo su huella."""
import hashlib
import secrets
from datetime import timedelta
from urllib.parse import quote

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

PORTAL_ROLES = [
    ('foreman', 'Capataz o maestro de obra'),
    ('contractor', 'Contrata'),
    ('office', 'Oficina técnica'),
]
MAX_PIN_FAILURES = 3


def _hash(value):
    return hashlib.sha256((value or '').encode()).hexdigest()


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_portal_session_days = fields.Integer(
        string='Duración de la sesión del portal (días)', default=90)
    construction_portal_progress_days = fields.Integer(
        string='Días hacia atrás del avance', default=3,
        help='El avance no puede tener fecha futura ni más antigua que estos días.')
    construction_portal_photo_max_px = fields.Integer(
        string='Lado mayor de las fotos (px)', default=1600,
        help='El celular comprime las fotos a este tamaño antes de guardarlas.')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_portal_session_days = fields.Integer(
        related='company_id.construction_portal_session_days', readonly=False)
    construction_portal_progress_days = fields.Integer(
        related='company_id.construction_portal_progress_days', readonly=False)
    construction_portal_photo_max_px = fields.Integer(
        related='company_id.construction_portal_photo_max_px', readonly=False)


class ProjectProject(models.Model):
    _inherit = 'project.project'

    construction_portal_member_ids = fields.One2many(
        'construction.portal.member', 'project_id', string='Personal del portal')
    construction_portal_password_login = fields.Boolean(
        string='Ingreso con usuario y clave', default=True)
    construction_portal_qr_login = fields.Boolean(
        string='Ingreso con el QR de la obra',
        help='El cartel de la obra lleva un QR con el código de la obra: la persona elige su '
             'nombre y escribe su PIN.')
    construction_portal_code = fields.Char(
        string='Código del QR', copy=False, readonly=True,
        groups='al_construction_planner.group_planner_user')
    construction_portal_overhead_area_id = fields.Many2one(
        'account.analytic.account', string='Analítica de gastos generales de la obra',
        check_company=True,
        help='Área de los requerimientos internos del portal (EPP, útiles y aseo de la obra).')
    construction_portal_url = fields.Char(
        string='Enlace del QR', compute='_compute_construction_portal_url',
        groups='al_construction_planner.group_planner_user')

    construction_portal_qr_html = fields.Html(
        string='QR del cartel', compute='_compute_construction_portal_url', sanitize=False,
        groups='al_construction_planner.group_planner_user')

    def _compute_construction_portal_url(self):
        base = self.get_base_url()
        for project in self:
            url = '%s/obra/app/#qr=%s' % (base, project.construction_portal_code) \
                if project.construction_portal_code else False
            project.construction_portal_url = url
            project.construction_portal_qr_html = Markup(
                '<img alt="QR del portal de obra" style="width:180px;height:180px" '
                'src="/report/barcode/?barcode_type=QR&amp;width=360&amp;height=360&amp;value=%s"/>'
            ) % quote(url, safe='') if url else False

    def action_construction_portal_new_code(self):
        """Nuevo código del QR: el cartel anterior deja de servir."""
        for project in self:
            project.construction_portal_code = secrets.token_urlsafe(9)
            project.message_post(body=self.env._('Nuevo código del QR del portal de obra.'))

    @api.model
    def _construction_portal_by_code(self, code):
        if not code:
            return self.browse()
        # sudo: el código del QR es la llave pública de la obra; solo se
        # busca la obra que lo tiene.
        return self.sudo().search([('construction_portal_code', '=', code),
                                   ('construction_portal_qr_login', '=', True)], limit=1)


class ConstructionPortalMember(models.Model):
    _name = 'construction.portal.member'
    _description = 'Personal del portal de obra'
    _order = 'project_id, role, name'
    _check_company_auto = True

    project_id = fields.Many2one('project.project', string='Obra', required=True,
                                 ondelete='cascade', index=True, check_company=True,
                                 domain=[('is_construction_site', '=', True)])
    company_id = fields.Many2one(related='project_id.company_id', store=True, index=True)
    user_id = fields.Many2one(
        'res.users', string='Usuario', required=True, ondelete='cascade', index=True,
        help='Usuario de portal (contrata, capataz u oficina técnica sin licencia) o interno.')
    name = fields.Char(related='user_id.name', string='Nombre', store=True)
    role = fields.Selection(PORTAL_ROLES, string='Papel', required=True, default='foreman')
    partner_id = fields.Many2one(
        'res.partner', string='Contrata', index=True,
        help='La empresa de la contrata: ve solo sus partidas y sus valorizaciones.')
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', index='btree_not_null',
        help='Capataz o maestro de obra de la planilla: su cuadrilla y su tareo.')
    pin_hash = fields.Char(string='Huella del PIN', copy=False, readonly=True,
                           groups='base.group_system')
    has_pin = fields.Boolean(string='Tiene PIN', compute='_compute_has_pin')
    pin_failures = fields.Integer(string='PIN errados', copy=False, readonly=True)
    pin_locked = fields.Boolean(string='Ingreso por QR bloqueado', copy=False, readonly=True)
    active = fields.Boolean(default=True)

    _project_user_unique = models.UniqueIndex(
        '(project_id, user_id)', 'La persona ya está en el portal de esta obra.')

    def _compute_has_pin(self):
        for member, pin_hash in zip(self, self.sudo().mapped('pin_hash')):
            member.has_pin = bool(pin_hash)

    @api.constrains('role', 'partner_id')
    def _check_contractor(self):
        for member in self:
            if member.role == 'contractor' and not member.partner_id:
                raise ValidationError(self.env._(
                    '%s es de una contrata: indique la empresa.', member.name))

    @api.onchange('user_id', 'role')
    def _onchange_user_id(self):
        if self.role == 'contractor' and self.user_id and not self.partner_id:
            self.partner_id = self.user_id.partner_id.commercial_partner_id

    def action_set_pin(self, pin):
        """Asigna el PIN de 4 dígitos (y desbloquea el ingreso por QR)."""
        pin = (pin or '').strip()
        if len(pin) != 4 or not pin.isdigit():
            raise UserError(self.env._('El PIN es de 4 dígitos.'))
        for member in self:
            # sudo: la huella del PIN solo la escribe el sistema.
            member.sudo().write({'pin_hash': _hash('%s:%s' % (member.id, pin)),
                                 'pin_failures': 0, 'pin_locked': False})
        return True

    def action_open_pin_wizard(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': self.env._('PIN del portal'),
                'res_model': 'construction.portal.pin.wizard', 'view_mode': 'form',
                'target': 'new', 'context': {'default_member_id': self.id}}

    def action_unlock(self):
        self.sudo().write({'pin_failures': 0, 'pin_locked': False})

    def _check_pin(self, pin):
        """True si el PIN es el de la persona; tres errados bloquean."""
        self.ensure_one()
        member_sudo = self.sudo()
        if member_sudo.pin_locked or not member_sudo.pin_hash:
            return False
        if member_sudo.pin_hash == _hash('%s:%s' % (self.id, (pin or '').strip())):
            member_sudo.pin_failures = 0
            return True
        member_sudo.pin_failures += 1
        if member_sudo.pin_failures >= MAX_PIN_FAILURES:
            member_sudo.pin_locked = True
        return False


class ConstructionPortalToken(models.Model):
    _name = 'construction.portal.token'
    _description = 'Sesión del portal de obra'
    _order = 'create_date desc'

    user_id = fields.Many2one('res.users', string='Usuario', required=True, ondelete='cascade',
                              index=True)
    token_hash = fields.Char(required=True, index=True, copy=False)
    device = fields.Char(string='Equipo')
    method = fields.Selection([('password', 'Usuario y clave'), ('qr', 'QR y PIN')],
                              string='Ingreso', required=True)
    expiration = fields.Datetime(string='Vence', required=True)
    last_used = fields.Datetime(string='Último uso', readonly=True)

    @api.model
    def _hash_token(self, token):
        return _hash(token)

    @api.model
    def _issue(self, user, method, device=None):
        """Token nuevo de ``user``: el texto solo se devuelve aquí."""
        token = secrets.token_urlsafe(32)
        company = user.company_id
        days = company.construction_portal_session_days or 90
        # sudo: los tokens del portal los crea el sistema al ingresar.
        record = self.sudo().create({
            'user_id': user.id, 'token_hash': _hash(token), 'method': method,
            'device': (device or '')[:120], 'expiration': fields.Datetime.now() + timedelta(
                days=days)})
        return token, record.expiration

    @api.model
    def _check(self, token):
        """Usuario del token vigente; vacío si no lo es."""
        if not token:
            return self.env['res.users']
        # sudo: se busca la sesión por la huella del token del encabezado.
        record = self.sudo().search([('token_hash', '=', _hash(token)),
                                     ('expiration', '>', fields.Datetime.now())], limit=1)
        if not record or not record.user_id.active:
            return self.env['res.users']
        now = fields.Datetime.now()
        if not record.last_used or (now - record.last_used).total_seconds() > 300:
            record.last_used = now
        return record.user_id

    @api.autovacuum
    def _gc_expired(self):
        self.sudo().search([('expiration', '<', fields.Datetime.now())]).unlink()


class ConstructionPortalSubmission(models.Model):
    """Envío del celular: el identificador único de cada registro hecho sin
    señal impide crearlo dos veces si el envío se repite."""
    _name = 'construction.portal.submission'
    _description = 'Envío del portal de obra'
    _order = 'create_date desc'

    uuid = fields.Char(required=True, index=True, readonly=True)
    user_id = fields.Many2one('res.users', string='Usuario', required=True, readonly=True,
                              ondelete='cascade')
    kind = fields.Char(string='Tipo', required=True, readonly=True)
    res_model = fields.Char(string='Modelo', readonly=True)
    res_ids = fields.Char(string='Registros', readonly=True)
    state = fields.Selection([('done', 'Registrado'), ('rejected', 'Rechazado')],
                             string='Estado', required=True, readonly=True)
    message = fields.Text(string='Motivo', readonly=True)

    _uuid_unique = models.UniqueIndex("(uuid, user_id) WHERE state = 'done'",
                                      'Ese envío ya se registró.')


class ConstructionPortalPinWizard(models.TransientModel):
    _name = 'construction.portal.pin.wizard'
    _description = 'PIN del portal de obra'

    member_id = fields.Many2one('construction.portal.member', string='Persona', required=True)
    pin = fields.Char(string='PIN', required=True)

    def action_apply(self):
        self.ensure_one()
        self.member_id.action_set_pin(self.pin)
        return {'type': 'ir.actions.act_window_close'}
