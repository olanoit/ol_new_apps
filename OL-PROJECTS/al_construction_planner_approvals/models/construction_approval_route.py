# -*- coding: utf-8 -*-
"""Tabla de rutas de aprobación (paquete 1.9, M19-07).

Cada fila es un tramo: tipo de documento, tipo de cambio y desde qué
porcentaje o monto aplica, con el tipo de aprobación, los aprobadores
(usuarios o grupos, «basta uno» o «todos») y los seguidores. Los tramos van
en escalera: un exceso que llega al tercer tramo pasa por los tres, en orden."""
from odoo import api, fields, models
from odoo.exceptions import ValidationError

DOCUMENT_TYPES = [
    ('plan', 'Plan de recursos'),
    ('material_request', 'Requerimiento de obra'),
]
CHANGE_TYPES = [
    ('all', 'Todo el documento'),
    ('material', 'Cambio de material'),
    ('quantity', 'Cambio de cantidad'),
]
BASES = [
    ('percent', 'Porcentaje'),
    ('amount', 'Monto'),
]
APPROVAL_RULES = [
    ('any', 'Basta uno'),
    ('all', 'Todos'),
]


class ConstructionApprovalRoute(models.Model):
    _name = 'construction.approval.route'
    _description = 'Ruta de aprobación de obra'
    _order = 'company_id, document_type, change_type, threshold, sequence, id'
    _check_company_auto = True

    name = fields.Char(string='Tramo', required=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    document_type = fields.Selection(
        DOCUMENT_TYPES, string='Documento', required=True, index=True)
    change_type = fields.Selection(
        CHANGE_TYPES, string='Tipo de cambio', required=True, default='all',
        help='Todo el documento: aplica a cualquier envío (por ejemplo, el plan). Cambio de '
             'material: un material que no está en el plan o lo reemplaza. Cambio de cantidad: '
             'más de lo que queda en el plan.')
    basis = fields.Selection(
        BASES, string='Base', required=True, default='percent',
        help='Porcentaje: el exceso sobre lo presupuestado (la línea con más exceso). Monto: '
             'el exceso en la moneda de la compañía (el plan, su total).')
    threshold = fields.Float(
        string='Desde', digits=(16, 2),
        help='El tramo aplica cuando el exceso supera este valor; con 0 aplica siempre. Un '
             'exceso que supera varios tramos pasa por todos, del menor al mayor.')
    category_id = fields.Many2one(
        'approval.category', string='Tipo de aprobación', required=True, check_company=True,
        domain="[('approval_type', '=', 'construction')]",
        default=lambda self: self.env['approval.category']._construction_category(
            self.env.company))
    approver_ids = fields.One2many(
        'construction.approval.route.approver', 'route_id', string='Aprobadores', copy=True)
    approval_rule = fields.Selection(
        APPROVAL_RULES, string='Regla', required=True, default='any',
        help='Basta uno: el tramo queda aprobado con la primera aprobación. Todos: aprueba '
             'cada usuario de la lista y una persona de cada grupo.')
    follower_user_ids = fields.Many2many(
        'res.users', 'construction_approval_route_follower_user_rel', 'route_id', 'user_id',
        string='Seguidores', domain=[('share', '=', False)])
    follower_group_ids = fields.Many2many(
        'res.groups', 'construction_approval_route_follower_group_rel', 'route_id', 'group_id',
        string='Grupos seguidores', help='Por ejemplo, Logística.')
    notify_project_manager = fields.Boolean(
        string='Jefe de proyectos como seguidor', default=True,
        help='El responsable de la obra sigue la solicitud y el documento.')
    note = fields.Text(string='Notas')

    @api.constrains('approver_ids')
    def _check_approvers(self):
        for route in self:
            if not route.approver_ids:
                raise ValidationError(self.env._(
                    'El tramo «%s» necesita al menos un aprobador.', route.name))

    @api.constrains('change_type', 'document_type')
    def _check_change_type(self):
        for route in self:
            if route.document_type == 'plan' and route.change_type != 'all':
                raise ValidationError(self.env._(
                    'El plan de recursos se aprueba completo: su tipo de cambio es «Todo el '
                    'documento».'))

    @api.model
    def _construction_ladder(self, company, document_type, values):
        """Tramos que recorre un envío, en orden: ``values`` es {tipo de
        cambio: {'percent': %, 'amount': monto}} con los cambios del
        documento («all» para el documento completo)."""
        routes = self.search([
            ('company_id', '=', company.id), ('document_type', '=', document_type),
            ('change_type', 'in', list(values))])
        ladder = self.browse()
        for route in routes:
            value = values[route.change_type][route.basis]
            if route.threshold <= 0 or value > route.threshold:
                ladder |= route
        return ladder.sorted(lambda r: (r.threshold, r.sequence, r.id))

    def _construction_users(self, exclude=None):
        """{clave del aprobador: usuarios} del tramo. Un grupo vale por sus
        usuarios internos activos de la compañía, sin quien solicita."""
        self.ensure_one()
        exclude = exclude or self.env['res.users']
        result = {}
        for approver in self.approver_ids:
            users = approver.user_id or approver.group_id.all_user_ids
            users = users.filtered(
                lambda u: u.active and not u.share and self.company_id in u.company_ids) - exclude
            if users:
                result['%s-%s' % (self.id, approver.id)] = users
        return result

    def _construction_follower_partners(self, project):
        partners = self.env['res.partner']
        for route in self:
            partners |= route.follower_user_ids.partner_id
            partners |= route.follower_group_ids.all_user_ids.filtered(
                lambda u: u.active and not u.share).partner_id
            if route.notify_project_manager and project.user_id:
                partners |= project.user_id.partner_id
        return partners


class ConstructionApprovalRouteApprover(models.Model):
    _name = 'construction.approval.route.approver'
    _description = 'Aprobador del tramo'
    _order = 'route_id, sequence, id'

    route_id = fields.Many2one(
        'construction.approval.route', string='Tramo', required=True, ondelete='cascade',
        index=True)
    company_id = fields.Many2one(related='route_id.company_id', store=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    user_id = fields.Many2one(
        'res.users', string='Usuario', domain=[('share', '=', False)])
    group_id = fields.Many2one(
        'res.groups', string='Grupo', help='Cualquiera de sus usuarios puede aprobar por el grupo.')

    _user_or_group = models.Constraint(
        'CHECK((user_id IS NULL) != (group_id IS NULL))',
        'Cada aprobador es un usuario o un grupo, no los dos.')

    @api.depends('user_id', 'group_id')
    def _compute_display_name(self):
        for approver in self:
            approver.display_name = approver.user_id.name or approver.group_id.display_name
