# -*- coding: utf-8 -*-
"""Avisos al celular del portal de obra (paquete 6, CR-57).

Los avisos son mensajes de Odoo dirigidos a las personas del portal de la
obra: el envío web nativo (``mail.push.device``) los lleva al celular donde
la persona activó los avisos, con la aplicación cerrada, y el correo queda
de respaldo. Qué avisos recibe cada papel es configuración de la empresa
(``construction.portal.notice.rule``).

* Pedido urgente por aprobar: al enviar a aprobación un requerimiento urgente.
* Entrega en camino a la obra: una acción programada revisa las entregas
  listas para recibir en la ubicación de cada obra con portal.
* Avance reportado fuera del radio de la obra.
* Avance validado o rechazado: a quien lo reportó."""
from odoo import api, fields, models

from .portal_member import PORTAL_ROLES

NOTICE_EVENTS = [
    ('urgent_request', 'Pedido urgente por aprobar'),
    ('delivery', 'Entrega en camino a la obra'),
    ('out_of_radius', 'Avance reportado fuera del radio de la obra'),
    ('progress_decision', 'Avance validado o rechazado (a quien lo reportó)'),
]


class ConstructionPortalNoticeRule(models.Model):
    _name = 'construction.portal.notice.rule'
    _description = 'Aviso al celular del portal de obra'
    _order = 'event, role'
    _check_company_auto = True

    event = fields.Selection(NOTICE_EVENTS, string='Aviso', required=True)
    role = fields.Selection(PORTAL_ROLES, string='Papel que lo recibe', required=True)
    company_id = fields.Many2one('res.company', string='Compañía', index=True,
                                 help='Vacío: para todas las compañías.')
    active = fields.Boolean(default=True)

    _event_role_unique = models.UniqueIndex(
        '(event, role, COALESCE(company_id, 0))', 'Ese aviso ya está configurado para ese papel.')

    @api.model
    def _roles_for(self, event, company):
        # sudo: la configuración de avisos la lee el servicio del portal.
        rules = self.sudo().search([('event', '=', event),
                                    ('company_id', 'in', (company.id, False))])
        return set(rules.mapped('role'))


class ConstructionPortalService(models.AbstractModel):
    _inherit = 'construction.portal.service'

    @api.model
    def _notice_users(self, project, event, users=None):
        """Usuarios del portal de la obra que reciben el aviso ``event``
        según su papel (y, si se pasan, solo entre ``users``)."""
        company = project.company_id or self.env.company
        roles = self.env['construction.portal.notice.rule']._roles_for(event, company)
        if not roles:
            return self.env['res.users']
        # sudo: el personal del portal de la obra.
        members = self.env['construction.portal.member'].sudo().search([
            ('project_id', '=', project.id), ('active', '=', True), ('role', 'in', list(roles))])
        recipients = members.user_id
        if users is not None:
            recipients &= users
        return recipients

    @api.model
    def _portal_notice(self, record, project, event, body, users=None, author=None):
        """Mensaje en ``record`` para quienes reciben el aviso: llega al
        celular por el envío web y al correo. Devuelve los destinatarios."""
        recipients = self._notice_users(project, event, users)
        author = author or self.env.user.partner_id
        partners = recipients.partner_id - author
        if not partners:
            return recipients.browse()
        # sudo: el aviso lo deja el sistema en el registro de la obra.
        record.sudo().message_post(
            body=body, author_id=author.id, partner_ids=partners.ids,
            message_type='comment', subtype_xmlid='mail.mt_note')
        return recipients

    @api.model
    def push_key(self):
        """Clave pública del envío web de Odoo (VAPID) para suscribir el
        celular."""
        return {'public_key': self.env['mail.push.device'].sudo().get_web_push_vapid_public_key()}

    @api.model
    def push_subscribe(self, values):
        """Registra el celular de la persona para los avisos (o lo quita)."""
        Device = self.env['mail.push.device']
        if values.get('unsubscribe'):
            Device.unregister_devices(endpoint=values.get('endpoint'))
            return {'status': 'done'}
        # El registro nativo usa el usuario de la sesión (el del portal).
        Device.register_devices(
            vapid_public_key=values.get('vapid_public_key'), endpoint=values.get('endpoint'),
            keys=values.get('keys'), expirationTime=values.get('expirationTime'),
            previousEndpoint=values.get('previousEndpoint') or values.get('endpoint'))
        return {'status': 'done'}


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    construction_portal_notified = fields.Boolean(
        string='Aviso de entrega enviado', copy=False, readonly=True,
        help='El personal del portal de la obra ya recibió el aviso de esta entrega.')

    def _action_done(self):
        """Paquete 1.21, M121-02: al validar la salida a obra, la recepción
        encadenada queda lista y el aviso «Entrega en camino» sale enseguida
        (la acción programada corre al momento). Sale sin hacer nada si la
        transferencia no es de un requerimiento de obra."""
        res = super()._action_done()
        dispatches = self.filtered(lambda p: p.state == 'done' and p.construction_request_id)
        if dispatches and dispatches.move_ids.move_dest_ids.picking_id.filtered(
                lambda p: p.state == 'assigned'):
            # sudo: el almacenero que valida no administra acciones programadas.
            cron_sudo = self.env.ref(
                'al_construction_portal.ir_cron_construction_portal_delivery_notice').sudo()
            cron_sudo._trigger()
        return res

    @api.model
    def _cron_construction_portal_delivery_notice(self):
        """Entregas listas para recibir en la obra: aviso al personal del
        portal (una vez por entrega). Solo mira las ubicaciones de las obras
        con portal; el resto de las transferencias no se toca."""
        # sudo: la acción programada revisa las obras con portal.
        projects = self.env['construction.portal.member'].sudo().search([
            ('active', '=', True)]).project_id.filtered('construction_location_id')
        service = self.env['construction.portal.service'].sudo()
        for project in projects:
            location = project.construction_location_id
            pickings = self.sudo().search([
                ('location_dest_id', 'child_of', location.id), ('state', '=', 'assigned'),
                ('construction_portal_notified', '=', False)]).filtered(
                lambda p: not p.location_id._child_of(location))
            for picking in pickings:
                origin = picking.partner_id.commercial_partner_id.name or picking.origin or ''
                body = self.env._('Entrega en camino a la obra %(project)s: %(name)s%(origin)s.',
                                  project=project.display_name, name=picking.name,
                                  origin=(' · %s' % origin) if origin else '')
                service._portal_notice(picking, project, 'delivery', body,
                                       author=self.env.ref('base.partner_root'))
                picking.construction_portal_notified = True
