# -*- coding: utf-8 -*-
from lxml import etree
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Campos que Logística puede ajustar durante y después de la aprobación.
LOGISTICS_EDITABLE_FIELDS = ['location_dest_id', 'date_required', 'priority']

STATES = [
    ('draft', 'Borrador'),
    ('to_approve', 'En aprobación'),
    ('approved', 'Aprobado'),
    ('rejected', 'Rechazado'),
    ('in_progress', 'En proceso'),
    ('done', 'Hecho'),
    ('cancel', 'Cancelado'),
]


class ConstructionMaterialRequest(models.Model):
    _name = 'construction.material.request'
    _description = 'Requerimiento de materiales de obra'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'analytic.mixin', 'tier.validation']
    _order = 'priority desc, date_request desc, id desc'
    _check_company_auto = True

    # Aprobación multinivel (OCA base_tier_validation, patrón de
    # purchase_request_tier_validation). Las revisiones se piden al pasar a
    # «En aprobación» y el paso a «Aprobado» exige que estén validadas.
    _state_from = ['draft', 'to_approve']
    _state_to = ['approved']
    _cancel_state = 'cancel'
    _tier_validation_manual_config = False

    name = fields.Char(
        string='Número', required=True, readonly=True, copy=False,
        default=lambda self: _('Nuevo'), index='trigram')
    state = fields.Selection(
        STATES, string='Estado', default='draft', required=True,
        readonly=True, copy=False, tracking=True, index=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    project_id = fields.Many2one(
        'project.project', string='Obra', required=True, index=True,
        tracking=True, check_company=True,
        domain="[('is_construction_site', '=', True)]")
    project_manager_id = fields.Many2one(
        related='project_id.user_id', string='Jefe de proyecto', store=True)
    task_id = fields.Many2one(
        'project.task', string='Tarea', check_company=True,
        domain="[('project_id', '=', project_id)]")
    location_src_id = fields.Many2one(
        'stock.location', string='Origen', required=True, check_company=True,
        compute='_compute_location_src_id', store=True, readonly=False,
        precompute=True, domain="[('usage', '=', 'internal')]")
    location_dest_id = fields.Many2one(
        'stock.location', string='Ubicación de obra', check_company=True,
        compute='_compute_location_dest_id', store=True, readonly=False,
        precompute=True, tracking=True, domain="[('usage', '=', 'internal')]")
    requested_by = fields.Many2one(
        'res.users', string='Solicitado por', required=True, tracking=True,
        default=lambda self: self.env.user, index=True)
    date_request = fields.Date(
        string='Fecha', required=True, default=fields.Date.context_today)
    date_required = fields.Date(string='Fecha requerida', tracking=True)
    priority = fields.Selection(
        [('0', 'Normal'), ('1', 'Urgente')], string='Prioridad', default='0')
    note = fields.Html(string='Notas')
    line_ids = fields.One2many(
        'construction.material.request.line', 'request_id', string='Materiales',
        copy=True)
    amount_estimated = fields.Monetary(
        string='Valor estimado', compute='_compute_amount_estimated', store=True,
        help='Cantidad × costo del producto. Lo usan las reglas de aprobación.')

    picking_ids = fields.One2many(
        'stock.picking', 'construction_request_id', string='Transferencias')
    picking_count = fields.Integer(string='Nº de transferencias', compute='_compute_counts')
    purchase_request_ids = fields.One2many(
        'purchase.request', 'construction_request_id',
        string='Requerimientos de compra')
    purchase_request_count = fields.Integer(
        string='Nº de requerimientos de compra', compute='_compute_counts')
    purchase_order_ids = fields.Many2many(
        'purchase.order', compute='_compute_purchase_order_ids',
        string='Órdenes de compra')
    purchase_order_count = fields.Integer(
        string='Nº de órdenes de compra', compute='_compute_purchase_order_ids')
    user_is_logistics = fields.Boolean(
        string='Usuario de logística', compute='_compute_user_is_logistics')

    @api.depends_context('uid')
    def _compute_user_is_logistics(self):
        is_logistics = self.env.user.has_group(
            'al_construction_material_request.group_construction_logistics')
        for request in self:
            request.user_is_logistics = is_logistics

    @api.depends('company_id')
    def _compute_location_src_id(self):
        for request in self:
            if not request.location_src_id:
                request.location_src_id = request.company_id.construction_src_location_id

    @api.depends('project_id')
    def _compute_location_dest_id(self):
        for request in self:
            request.location_dest_id = request.project_id.construction_location_id

    @api.depends('project_id')
    def _compute_analytic_distribution(self):
        for request in self:
            if request.project_id:
                request.analytic_distribution = (
                    request.project_id._get_analytic_distribution()
                    or request.analytic_distribution)

    @api.depends('line_ids.product_qty', 'line_ids.product_uom_id',
                 'line_ids.product_id', 'company_id')
    def _compute_amount_estimated(self):
        for request in self:
            total = 0.0
            for line in request.line_ids.filtered('product_id'):
                product = line.product_id.with_company(request.company_id)
                qty = line.product_uom_id._compute_quantity(
                    line.product_qty, product.uom_id, raise_if_failure=False)
                total += qty * product.standard_price
            request.amount_estimated = total

    def _compute_counts(self):
        for request in self:
            request.picking_count = len(request.picking_ids)
            request.purchase_request_count = len(request.purchase_request_ids)

    def _compute_purchase_order_ids(self):
        for request in self:
            orders = request.purchase_request_ids.line_ids.purchase_lines.order_id
            request.purchase_order_ids = orders
            request.purchase_order_count = len(orders)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                company = self.env['res.company'].browse(
                    vals.get('company_id')) or self.env.company
                vals['name'] = self.env['ir.sequence'].with_company(
                    company).next_by_code('construction.material.request') or _('Nuevo')
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_only_draft(self):
        if any(request.state not in ('draft', 'cancel') for request in self):
            raise UserError(_('Solo se eliminan requerimientos en borrador o cancelados.'))

    # ------------------------------------------------------------------
    # Flujo y aprobación por niveles
    # ------------------------------------------------------------------
    def _check_ready_to_submit(self):
        for request in self:
            if not request.line_ids:
                raise UserError(_('Agregue al menos un material a %s.', request.name))
            if not request.location_dest_id:
                raise UserError(_(
                    'La obra %s no tiene ubicación de obra.', request.project_id.name))

    def _check_state(self, allowed):
        if any(request.state not in allowed for request in self):
            raise UserError(_(
                'La acción no está permitida en el estado actual del requerimiento.'))

    def action_request_approval(self):
        """Pide las revisiones que apliquen. Si ninguna regla de aprobación
        aplica (p. ej. montos bajos sin regla), se aprueba directamente."""
        self._check_state(('draft',))
        self._check_ready_to_submit()
        self.write({'state': 'to_approve'})
        for request in self:
            reviews = request.request_validation() if request.need_validation else False
            if not reviews:
                request._write_approved()

    def _write_approved(self):
        # need_validation no tiene depends: su caché conserva el valor de
        # antes de crear las revisiones y OCA intentaría pedirlas de nuevo.
        self.invalidate_recordset(['need_validation', 'review_ids', 'validation_status'])
        # Guarda de reentrada: al escribir «Aprobado», tier.validation puede
        # volver a llamar a _validate_tier.
        self.with_context(al_construction_approving=True).write({'state': 'approved'})

    def _validate_tier(self, tiers=False):
        res = super()._validate_tier(tiers)
        if not self.env.context.get('al_construction_approving'):
            if self.state == 'to_approve' and self.validation_status == 'validated':
                self._write_approved()
        return res

    def _rejected_tier(self, tiers=False):
        res = super()._rejected_tier(tiers)
        if self.state == 'to_approve' and self.validation_status == 'rejected':
            # El rechazo lo escribe el revisor, que no puede editar el
            # documento en revisión: se omite ese control solo para el estado.
            self.with_context(skip_validation_check=True).write({'state': 'rejected'})
        return res

    def action_draft(self):
        self._check_state(('to_approve', 'rejected', 'cancel'))
        # En «En aprobación» las revisiones siguen vivas: se reinician.
        self.filtered(lambda r: r.state == 'to_approve').restart_validation()
        self.write({'state': 'draft'})

    def _get_to_validate_message(self):
        # El es.po de base_tier_validation no traduce este aviso: se da aquí
        # en español.
        icon = Markup('<i class="fa fa-lg fa-info-circle"></i>')
        pending = self.review_ids.filtered(lambda r: r.status == 'pending')[:1]
        if pending and pending.todo_by:
            text = _('Pendiente de aprobación por %s', pending.todo_by)
        else:
            text = _('Este requerimiento de obra necesita aprobación')
        return Markup('%s %s') % (icon, text)

    @api.model
    def _get_under_validation_exceptions(self):
        # La vista limita destino y fecha a Logística; ``priority`` lo cambia
        # el widget de estrella.
        return super()._get_under_validation_exceptions() + LOGISTICS_EDITABLE_FIELDS

    @api.model
    def _get_all_validation_exceptions(self):
        # Sin esto, OCA los deja de solo lectura en la vista durante la revisión.
        return super()._get_all_validation_exceptions() + LOGISTICS_EDITABLE_FIELDS

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        """Quita los botones OCA «Request/Restart Validation»: el flujo usa
        «Solicitar aprobación» y «Volver a borrador», que además mueven el
        estado. Se conservan validar/rechazar y el bloque de revisiones."""
        res = super().get_view(view_id=view_id, view_type=view_type, **options)
        if view_type == 'form':
            doc = etree.XML(res['arch'])
            for node in doc.xpath(
                    "//button[@name='request_validation' or @name='restart_validation']"):
                node.getparent().remove(node)
            res['arch'] = etree.tostring(doc, encoding='unicode')
        return res

    def action_cancel(self):
        self._check_state(('draft', 'to_approve', 'approved', 'rejected', 'in_progress'))
        self.write({'state': 'cancel'})

    # ------------------------------------------------------------------
    # Botones inteligentes
    # ------------------------------------------------------------------
    def action_view_pickings(self):
        self.ensure_one()
        return self._action_view_records('stock.action_picking_tree_all', self.picking_ids)

    def action_view_purchase_requests(self):
        self.ensure_one()
        return self._action_view_records(
            'purchase_request.purchase_request_form_action', self.purchase_request_ids)

    def action_view_purchase_orders(self):
        self.ensure_one()
        return self._action_view_records('purchase.purchase_form_action', self.purchase_order_ids)

    def _get_report_related_documents(self):
        """Nombres de los documentos relacionados para el vale."""
        self.ensure_one()
        # El vale lo imprime también el residente, sin acceso a inventario ni
        # compras: solo se leen los nombres de los documentos.
        request_sudo = self.sudo()
        return [(label, ', '.join(records.mapped('name'))) for label, records in (
            (_('Transferencias'), request_sudo.picking_ids),
            (_('Requerimientos de compra'), request_sudo.purchase_request_ids),
            (_('Órdenes de compra'), request_sudo.purchase_order_ids),
        ) if records]

    def _action_view_records(self, xmlid, records):
        action = self.env['ir.actions.act_window']._for_xml_id(xmlid)
        action['domain'] = [('id', 'in', records.ids)]
        action['context'] = {'create': False}
        if len(records) == 1:
            action['views'] = [(False, 'form')]
            action['res_id'] = records.id
        return action
