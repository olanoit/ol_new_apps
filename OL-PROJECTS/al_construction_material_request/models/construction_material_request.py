# -*- coding: utf-8 -*-
from lxml import etree
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Campos que Logística puede ajustar durante y después de la aprobación.
LOGISTICS_EDITABLE_FIELDS = ['location_dest_id', 'date_required', 'priority']

# Motivo del material extra (v1.6, M16-05): lo que se pide fuera de lo
# previsto para reponer o corregir en obra.
EXTRA_REASONS = [
    ('waste', 'Merma'),
    ('measure_error', 'Error de medida'),
    ('client_change', 'Cambio del cliente'),
    ('replacement', 'Reposición'),
]

# Tipo de requerimiento (paquete 1.11, M111-10): de obra o interno de un
# área (Administración, Comercial…) para material de oficina o de consumo.
REQUEST_TYPES = [
    ('site', 'Obra'),
    ('internal', 'Interno'),
]

# Pide para obras (M111-20 A); «Solicitante interno» solo hace internos.
SITE_REQUESTER_GROUP = 'al_construction_material_request.group_construction_requester'

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
    request_type = fields.Selection(
        REQUEST_TYPES, string='Tipo', default=lambda self: self._default_request_type(),
        required=True, tracking=True,
        help='Obra: material para una obra. Interno: material de oficina o de consumo de '
             'un área; sale a la ubicación de consumo interno del almacén.')
    # Obligatoria en los de obra (_check_request_type); el interno puede
    # llevarla (7.3).
    project_id = fields.Many2one(
        'project.project', string='Obra', index=True,
        tracking=True, check_company=True,
        domain="[('is_construction_site', '=', True)]")
    area_plan_id = fields.Many2one(
        related='company_id.construction_area_plan_id', string='Plan de las áreas')
    area_id = fields.Many2one(
        'account.analytic.account', string='Área', index='btree_not_null',
        tracking=True, check_company=True,
        domain="[('plan_id', '=?', area_plan_id)]",
        help='Área que pide el material interno: va a la analítica de cada línea y al gasto.')
    # Revisor de la regla de aprobación de los internos: el jefe del
    # departamento del solicitante (si Empleados está instalado).
    construction_department_manager_id = fields.Many2one(
        'res.users', string='Jefe del departamento',
        compute='_compute_construction_department_manager_id')
    project_manager_id = fields.Many2one(
        related='project_id.user_id', string='Jefe de proyecto', store=True)
    construction_without_rule = fields.Boolean(
        string='Sin regla de aprobación', compute='_compute_construction_without_rule')
    task_id = fields.Many2one(
        'project.task', string='Tarea', check_company=True,
        domain="[('project_id', '=', project_id)]")
    location_src_id = fields.Many2one(
        'stock.location', string='Almacén por defecto', required=True, check_company=True,
        compute='_compute_location_src_id', store=True, readonly=False,
        precompute=True, domain="[('usage', '=', 'internal')]",
        help='Origen de las líneas que ninguna ruta abastece (M111-20 C).')
    construction_source_summary = fields.Char(
        string='Pedir al almacén', compute='_compute_construction_source_summary',
        help='Almacenes de donde salen las líneas, con su número de materiales.')
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
    is_extra = fields.Boolean(
        string='Material extra', tracking=True, copy=False,
        help='Material que no estaba previsto (merma, error de medida, cambio del cliente o '
             'reposición): necesita un motivo.')
    extra_reason = fields.Selection(
        EXTRA_REASONS, string='Motivo del extra', tracking=True, copy=False)
    note = fields.Html(string='Notas')
    line_ids = fields.One2many(
        'construction.material.request.line', 'request_id', string='Materiales',
        copy=True)
    amount_estimated = fields.Monetary(
        string='Valor estimado', compute='_compute_amount_estimated', store=True,
        help='Cantidad × costo del producto. Lo usan las reglas de aprobación.')

    picking_ids = fields.One2many(
        'stock.picking', 'construction_request_id', string='Transferencias')
    # Como purchase.order.reference_ids: agrupa transferencias y movimientos
    # del requerimiento (en 19.0 sustituye al grupo de abastecimiento).
    stock_reference_id = fields.Many2one(
        'stock.reference', string='Referencia de inventario', copy=False, readonly=True)
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
    # Solicitante interno (M111-20 A): sin el grupo «Solicitante», el usuario
    # solo hace requerimientos internos.
    user_is_site_requester = fields.Boolean(
        string='Pide para obras', compute='_compute_user_is_logistics')

    @api.model
    def _default_request_type(self):
        # Solo quien no pide para obras empieza en «Interno»; los procesos
        # internos (portal, asistentes con sudo) siguen creando de obra.
        if self.env.su or self.env.user.has_group(SITE_REQUESTER_GROUP):
            return 'site'
        return 'internal'

    @api.depends_context('uid')
    def _compute_user_is_logistics(self):
        is_logistics = self.env.user.has_group(
            'al_construction_material_request.group_construction_logistics')
        is_site = self.env.user.has_group(SITE_REQUESTER_GROUP)
        for request in self:
            request.user_is_logistics = is_logistics
            request.user_is_site_requester = is_site

    @api.depends('line_ids.location_src_id', 'location_src_id')
    def _compute_construction_source_summary(self):
        for request in self:
            counts = {}
            for line in request.line_ids.filtered(lambda l: not l.cancelled):
                source = line._get_source_location()
                name = source.warehouse_id.name or source.display_name
                counts[name] = counts.get(name, 0) + 1
            request.construction_source_summary = ' · '.join(
                '%s · %s' % (name, count) for name, count in counts.items()) or False

    @api.constrains('request_type', 'requested_by')
    def _check_site_requester(self):
        if self.env.su:
            return
        for request in self.filtered(lambda r: r.request_type == 'site'):
            if not self.env.user.has_group(SITE_REQUESTER_GROUP):
                raise ValidationError(_(
                    'Solo el grupo «Solicitante» pide material para obras: %s es un '
                    'requerimiento interno.', request.name))

    @api.depends('requested_by')
    def _compute_construction_department_manager_id(self):
        for request in self:
            manager = self.env['res.users']
            if 'employee_ids' in request.requested_by._fields:
                # El solicitante no lee las fichas de empleado de otros: solo
                # se busca el usuario del jefe de su departamento.
                employee_sudo = request.requested_by.sudo().employee_ids.filtered(
                    lambda e: e.company_id == request.company_id)[:1]
                manager = employee_sudo.department_id.manager_id.user_id.sudo(False)
                if manager == request.requested_by:
                    manager = employee_sudo.parent_id.user_id.sudo(False)
            request.construction_department_manager_id = manager

    @api.constrains('request_type', 'project_id')
    def _check_request_type(self):
        # El interno puede llevar la obra (EPP y útiles de la obra, 7.3): se
        # carga a su área, pero aparece en la obra y en sus reportes.
        for request in self:
            if request.request_type == 'site' and not request.project_id:
                raise ValidationError(_('Indique la obra del requerimiento %s.', request.name))

    @api.onchange('request_type')
    def _onchange_request_type(self):
        if self.request_type == 'internal':
            self.task_id = False
        else:
            self.area_id = False

    def _compute_construction_without_rule(self):
        """Ninguna regla de aprobación, salvo la de «sin regla», aplica al
        requerimiento (7.4)."""
        Definition = self.env['tier.definition'].sudo()
        definitions = Definition.search([
            ('model', '=', self._name), ('construction_site_fallback', '=', False)])
        for request in self:
            applicable = definitions.filtered(
                lambda d: not d.company_id or d.company_id == request.company_id)
            request.construction_without_rule = not any(
                request.evaluate_tier(definition) for definition in applicable)

    @api.depends('company_id')
    def _compute_location_src_id(self):
        for request in self:
            if not request.location_src_id:
                request.location_src_id = request.company_id.construction_src_location_id

    @api.depends('project_id', 'request_type', 'location_src_id')
    def _compute_location_dest_id(self):
        for request in self:
            if request.request_type == 'internal':
                request.location_dest_id = (
                    request.location_src_id.warehouse_id.construction_consumption_location_id)
            else:
                request.location_dest_id = request.project_id.construction_location_id

    @api.depends('project_id', 'request_type', 'area_id')
    def _compute_analytic_distribution(self):
        for request in self:
            if request.request_type == 'internal':
                request.analytic_distribution = (
                    {str(request.area_id.id): 100} if request.area_id else False)
            elif request.project_id:
                request.analytic_distribution = (
                    request.project_id._get_analytic_distribution()
                    or request.analytic_distribution)

    @api.depends('line_ids.product_uom_qty', 'line_ids.product_id', 'company_id')
    def _compute_amount_estimated(self):
        # Costo × cantidad en la UdM del producto (como purchase con
        # product_uom_qty): el costo estándar está en esa unidad.
        for request in self:
            request.amount_estimated = sum(
                line.product_uom_qty * line.product_id.with_company(request.company_id).standard_price
                for line in request.line_ids.filtered('product_id'))

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
            if request.request_type == 'internal':
                if not request.area_id:
                    raise UserError(_('Indique el área que pide %s.', request.name))
                if not request.location_dest_id:
                    raise UserError(_(
                        'El almacén %s no tiene ubicación de consumo interno: use «Completar '
                        'configuración» en los ajustes de Requerimientos de obra.',
                        request.location_src_id.warehouse_id.name or request.location_src_id.display_name))
                # El proveedor no entrega en una ubicación de consumo: lo que
                # falte se compra al almacén y sale de ahí.
                request.line_ids.filtered(lambda l: l.supply_mode == 'direct').supply_mode = 'central'
                continue
            if not request.location_dest_id:
                raise UserError(_(
                    'La obra %s no tiene ubicación de obra.', request.project_id.name))
            if request.is_extra and not request.extra_reason:
                raise UserError(_(
                    'Indique el motivo del material extra de %s.', request.name))

    def _check_state(self, allowed):
        if any(request.state not in allowed for request in self):
            raise UserError(_(
                'La acción no está permitida en el estado actual del requerimiento.'))

    def action_request_approval(self):
        """Pide las revisiones que apliquen. Si ninguna regla de aprobación
        aplica (p. ej. montos bajos sin regla), se aprueba directamente."""
        self._check_state(('draft',))
        self.filtered(lambda r: r.request_type == 'internal')._construction_ensure_internal_setup()
        self._check_ready_to_submit()
        self.write({'state': 'to_approve'})
        for request in self:
            reviews = request.request_validation() if request.need_validation else False
            if not reviews:
                request._write_approved()

    def _construction_ensure_internal_setup(self):
        """Ubicación de consumo interno y tipo «Consumo interno» del almacén
        de origen, creados la primera vez."""
        # Quien pide (un área) no configura almacenes: solo se completa lo que
        # falte en el almacén de origen de su requerimiento.
        warehouses_sudo = self.location_src_id.warehouse_id.sudo()
        warehouses_sudo._construction_ensure_internal_consumption()
        for request in self.filtered(lambda r: not r.location_dest_id):
            request.location_dest_id = (
                request.location_src_id.warehouse_id.construction_consumption_location_id)

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
