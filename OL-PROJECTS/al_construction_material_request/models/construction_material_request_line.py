# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

LINE_STATES = [
    ('pending', 'Pendiente'),
    ('partial', 'Parcial'),
    ('dispatched', 'Despachado'),
    ('purchasing', 'En compra'),
    ('done', 'Completo'),
    ('cancel', 'Cancelado'),
]


class ConstructionMaterialRequestLine(models.Model):
    _name = 'construction.material.request.line'
    _description = 'Línea de requerimiento de materiales de obra'
    _inherit = ['analytic.mixin']
    _order = 'request_id, sequence, id'
    _check_company_auto = True

    request_id = fields.Many2one(
        'construction.material.request', string='Requerimiento', required=True,
        ondelete='cascade', index=True,
        check_company=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    company_id = fields.Many2one(related='request_id.company_id', store=True, index=True)
    state = fields.Selection(related='request_id.state', string='Estado del requerimiento')
    project_id = fields.Many2one(related='request_id.project_id', store=True, index=True)
    date_required = fields.Date(related='request_id.date_required', store=True)
    product_id = fields.Many2one(
        'product.product', string='Material', required=True, check_company=True,
        domain="[('type', '=', 'consu')]")
    allowed_uom_ids = fields.Many2many(
        'uom.uom', string='Unidades permitidas', compute='_compute_allowed_uom_ids')
    product_uom_id = fields.Many2one(
        'uom.uom', string='Unidad', required=True,
        compute='_compute_product_uom_id', store=True, readonly=False, precompute=True,
        domain="[('id', 'in', allowed_uom_ids)]")
    product_qty = fields.Float(
        string='Cantidad', required=True, default=1.0, digits='Product Unit')
    # Como purchase.order.line.product_uom_qty / stock.move.product_qty: la
    # cantidad en la UdM del producto, base de stock y valorización.
    product_uom_qty = fields.Float(
        string='Cantidad en unidad del producto', compute='_compute_product_uom_qty',
        store=True)
    task_id = fields.Many2one(
        'project.task', string='Tarea', check_company=True,
        compute='_compute_task_id', store=True, readonly=False, precompute=True,
        domain="[('project_id', '=', parent.project_id)]")
    supply_mode = fields.Selection(
        [('central', 'Vía almacén central'), ('direct', 'Directo a obra')],
        string='Si hay que comprar', default='central', required=True,
        help='Vía almacén central: la compra llega al central y sale a la obra '
             'por una transferencia ya encadenada. Directo a obra: el proveedor '
             'entrega en la ubicación de la obra.')

    qty_available_now = fields.Float(
        string='Disponible en central', compute='_compute_qty_available_now',
        digits='Product Unit',
        help='Cantidad libre (no reservada) hoy en el origen y sus sububicaciones.')
    qty_available_at_approval = fields.Float(
        string='Disponible al procesar', readonly=True, copy=False, digits='Product Unit')
    qty_to_dispatch = fields.Float(
        string='A despachar', readonly=True, copy=False, digits='Product Unit')
    qty_to_purchase = fields.Float(
        string='A comprar', readonly=True, copy=False, digits='Product Unit')
    qty_dispatched = fields.Float(
        string='Despachado', compute='_compute_qties', store=True, digits='Product Unit')
    qty_purchased = fields.Float(
        string='Comprado', compute='_compute_qties', store=True, digits='Product Unit')
    qty_received_on_site = fields.Float(
        string='Recibido en obra', compute='_compute_qties', store=True, digits='Product Unit')
    line_state = fields.Selection(
        LINE_STATES, string='Situación', compute='_compute_line_state', store=True)
    cancelled = fields.Boolean(string='Cancelada', readonly=True, copy=False)

    move_ids = fields.One2many(
        'stock.move', 'construction_request_line_id', string='Movimientos')
    purchase_request_line_ids = fields.One2many(
        'purchase.request.line', 'construction_request_line_id',
        string='Líneas de requerimiento de compra')

    _qty_positive = models.Constraint(
        'CHECK(product_qty > 0)', 'La cantidad pedida debe ser mayor que cero.')

    def _get_report_analytic_label(self):
        """Cuentas analíticas de la línea para el vale («Estructuras ·
        02.01 Concreto simple»)."""
        self.ensure_one()
        ids = {int(i) for key in (self.analytic_distribution or {}) for i in key.split(',')}
        # Quien imprime (residente) puede no tener acceso a la contabilidad
        # analítica: solo se leen los nombres para mostrarlos.
        accounts_sudo = self.env['account.analytic.account'].sudo().browse(ids).exists()
        return ' · '.join(accounts_sudo.mapped('name'))

    @api.depends('product_id')
    def _compute_allowed_uom_ids(self):
        for line in self:
            line.allowed_uom_ids = line.product_id.uom_id | line.product_id.uom_ids

    @api.depends('product_id')
    def _compute_product_uom_id(self):
        for line in self:
            if not line.product_uom_id or line.product_uom_id not in line.allowed_uom_ids:
                line.product_uom_id = line.product_id.uom_id

    @api.depends('request_id.task_id')
    def _compute_task_id(self):
        for line in self:
            if not line.task_id:
                line.task_id = line.request_id.task_id

    @api.depends('request_id.analytic_distribution')
    def _compute_analytic_distribution(self):
        for line in self:
            if not line.analytic_distribution:
                line.analytic_distribution = line.request_id.analytic_distribution

    @api.depends('product_id', 'product_uom_id', 'product_qty')
    def _compute_product_uom_qty(self):
        # Patrón de purchase.order.line._compute_product_uom_qty: solo se
        # convierte con material y unidad (en el onchange pueden faltar).
        for line in self:
            if line.product_id and line.product_uom_id and line.product_id.uom_id != line.product_uom_id:
                line.product_uom_qty = line.product_uom_id._compute_quantity(
                    line.product_qty, line.product_id.uom_id, rounding_method='HALF-UP')
            else:
                line.product_uom_qty = line.product_qty

    @api.constrains('product_id', 'product_uom_id')
    def _check_uom(self):
        for line in self:
            if line.product_id and line.product_uom_id and not line.product_uom_id._has_common_reference(
                    line.product_id.uom_id):
                raise ValidationError(_(
                    'La unidad %(uom)s no es compatible con la del material %(product)s.',
                    uom=line.product_uom_id.name, product=line.product_id.display_name))

    @api.depends('product_id', 'product_uom_id', 'request_id.location_src_id')
    def _compute_qty_available_now(self):
        for line in self:
            location = line.request_id.location_src_id
            if not (line.product_id and location):
                line.qty_available_now = 0.0
                continue
            # ``location`` en el contexto incluye las sububicaciones (child_of).
            # El residente no tiene acceso a inventario y free_qty lee
            # movimientos de stock: solo se consulta la cantidad libre.
            product_sudo = line.product_id.sudo()
            free = product_sudo.with_context(location=location.id).free_qty
            line.qty_available_now = line.product_id.uom_id._compute_quantity(
                free, line.product_uom_id or line.product_id.uom_id, rounding_method='HALF-UP')

    @api.depends('move_ids.state', 'move_ids.quantity', 'move_ids.location_id',
                 'move_ids.location_dest_id', 'supply_mode',
                 'purchase_request_line_ids.purchased_qty',
                 'purchase_request_line_ids.qty_done',
                 'request_id.location_dest_id', 'request_id.location_src_id')
    def _compute_qties(self):
        for line in self:
            site = line.request_id.location_dest_id
            source = line.request_id.location_src_id
            dispatched = received = 0.0
            # Como purchase_stock (_prepare_qty_received): movimientos hechos
            # convertidos a la UdM de la línea con HALF-UP; lo que sale de la
            # obra (devolución al almacén) resta.
            for move in line.move_ids.filtered(lambda m: m.state == 'done'):
                if not site or not line.product_uom_id:
                    continue
                qty = move.product_uom._compute_quantity(
                    move.quantity, line.product_uom_id, rounding_method='HALF-UP')
                into_site = move.location_dest_id._child_of(site)
                out_of_site = move.location_id._child_of(site) and not into_site
                if into_site and not move.location_id._child_of(site):
                    received += qty
                    if source and move.location_id._child_of(source):
                        dispatched += qty
                elif out_of_site:
                    received -= qty
                    if source and move.location_dest_id._child_of(source):
                        dispatched -= qty
            if line.supply_mode == 'direct':
                # Entrega directa: lo recibido sale de las asignaciones OCA
                # (una línea de OC puede juntar varias líneas de compra).
                received += sum(line.purchase_request_line_ids.mapped('qty_done'))
            line.qty_dispatched = dispatched
            line.qty_received_on_site = received
            line.qty_purchased = sum(line.purchase_request_line_ids.mapped('purchased_qty'))

    @api.depends('cancelled', 'product_qty', 'qty_to_dispatch', 'qty_to_purchase',
                 'qty_received_on_site', 'move_ids.state', 'purchase_request_line_ids')
    def _compute_line_state(self):
        for line in self:
            uom = line.product_uom_id
            if line.cancelled:
                line.line_state = 'cancel'
            elif not line.product_id or not uom or uom.is_zero(line.product_qty):
                # Línea a medio rellenar (onchange de una línea nueva): como en
                # stock.move, sin material no se compara nada.
                line.line_state = 'pending'
            elif uom.compare(line.qty_received_on_site, line.product_qty) >= 0:
                line.line_state = 'done'
            elif uom.compare(line.qty_received_on_site, 0.0) > 0:
                line.line_state = 'partial'
            elif line.purchase_request_line_ids and uom.is_zero(line.qty_to_dispatch):
                line.line_state = 'purchasing'
            elif line.move_ids.filtered(lambda m: m.state != 'cancel'):
                line.line_state = 'dispatched'
            else:
                line.line_state = 'pending'
