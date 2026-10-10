# -*- coding: utf-8 -*-
"""Asignaciones del plan (fase 4, «Asignaciones y compras»).

Un documento cubre varias líneas del plan: una línea de compra masiva de
melamina cubre seis pisos, una OF cubre varias cocinas. La asignación guarda
qué parte del documento corresponde a cada línea; lo hecho del documento
(comprado, llegado a obra, consumido) se reparte entre sus asignaciones por
fecha de necesidad: primero la línea que se necesita antes y el sobrante, a
la última."""
from collections import defaultdict
from datetime import date, datetime, time

from odoo import api, fields, models
from odoo.exceptions import ValidationError

KINDS = [
    ('purchase_request', 'Compra masiva'),
    ('material_request', 'Requerimiento de obra'),
    ('production', 'Orden de fabricación'),
    ('service_order', 'OC de servicio'),
    ('planning_slot', 'Turno'),
]
# Campo del documento enlazado según el tipo de asignación.
DOCUMENT_FIELDS = {
    'purchase_request': 'purchase_request_line_id',
    'material_request': 'material_request_line_id',
    'production': 'production_id',
    'service_order': 'purchase_line_id',
    'planning_slot': 'slot_id',
}
# Medida que es el «Ejecutado» de cada tipo.
DONE_MEASURE = {
    'purchase_request': 'done',
    'material_request': 'dispatched',
    'production': 'consumed',
    'service_order': 'done',
    'planning_slot': 'done',
}
MEASURES = ('purchased', 'dispatched', 'consumed', 'done')
# Ubicaciones de consumo: lo que sale de la obra hacia ellas es «Consumo en obra».
CONSUMPTION_USAGES = ('production',)


def distribute(total, items):
    """Reparte ``total`` entre ``items`` [(clave, tope)] en su orden: cada uno
    recibe hasta su tope y el sobrante va al último. {clave: cantidad}."""
    result = {}
    left = max(total, 0.0)
    for key, cap in items:
        share = min(max(cap, 0.0), left)
        result[key] = share
        left -= share
    if items and left > 0:
        result[items[-1][0]] += left
    return result


class ConstructionResourcePlanAllocation(models.Model):
    _name = 'construction.resource.plan.allocation'
    _description = 'Asignación del plan de recursos'
    _order = 'date_needed, id'
    _check_company_auto = True

    plan_line_id = fields.Many2one(
        'construction.resource.plan.line', string='Línea del plan', required=True,
        ondelete='cascade', index=True, check_company=True)
    plan_id = fields.Many2one(
        related='plan_line_id.plan_id', string='Plan', store=True, index=True)
    project_id = fields.Many2one(related='plan_line_id.project_id', string='Obra', store=True)
    company_id = fields.Many2one(
        related='plan_line_id.company_id', string='Compañía', store=True, index=True)
    task_id = fields.Many2one(related='plan_line_id.task_id', string='Nivel')
    stage = fields.Selection(related='plan_line_id.stage', string='Etapa')
    resource_type = fields.Selection(
        related='plan_line_id.resource_type', string='Tipo de recurso')
    product_id = fields.Many2one(related='plan_line_id.product_id', string='Producto')
    activity_id = fields.Many2one(related='plan_line_id.activity_id', string='Actividad')
    product_uom_id = fields.Many2one(related='plan_line_id.product_uom_id', string='Unidad')
    date_needed = fields.Date(
        related='plan_line_id.date_needed', string='Fecha de necesidad', store=True)
    kind = fields.Selection(KINDS, string='Documento', required=True)
    purchase_request_line_id = fields.Many2one(
        'purchase.request.line', string='Línea de requerimiento de compra',
        ondelete='cascade', index='btree_not_null', check_company=True)
    material_request_line_id = fields.Many2one(
        'construction.material.request.line', string='Línea de requerimiento de obra',
        ondelete='cascade', index='btree_not_null', check_company=True)
    production_id = fields.Many2one(
        'mrp.production', string='Orden de fabricación', ondelete='cascade',
        index='btree_not_null', check_company=True)
    purchase_line_id = fields.Many2one(
        'purchase.order.line', string='Línea de la OC', ondelete='cascade',
        index='btree_not_null', check_company=True)
    slot_id = fields.Many2one(
        'planning.slot', string='Turno', ondelete='cascade', index='btree_not_null',
        check_company=True)
    document_name = fields.Char(string='Referencia', compute='_compute_document_name')
    qty_allocated = fields.Float(string='Asignado', digits='Product Unit', required=True)
    # Quien consulta el plan (planificador, capataz) puede no tener acceso a
    # compras, inventario o fabricación: las cantidades se leen sin esos
    # permisos, solo para mostrarlas y comparar con el plan.
    qty_done = fields.Float(
        string='Ejecutado', compute='_compute_quantities', digits='Product Unit',
        compute_sudo=True, help='Lo hecho del documento, repartido por fecha de necesidad.')
    qty_purchased = fields.Float(
        string='Comprado', compute='_compute_quantities', digits='Product Unit',
        compute_sudo=True)
    qty_dispatched = fields.Float(
        string='Despachado', compute='_compute_quantities', digits='Product Unit',
        compute_sudo=True)
    qty_consumed = fields.Float(
        string='Consumido', compute='_compute_quantities', digits='Product Unit',
        compute_sudo=True)
    state = fields.Selection(
        [('open', 'Abierta'), ('done', 'Hecha'), ('cancel', 'Cancelada')],
        string='Estado', compute='_compute_state', compute_sudo=True,
        help='Sigue al documento enlazado.')

    _one_document = models.Constraint(
        'CHECK(num_nonnulls(purchase_request_line_id, material_request_line_id, '
        'production_id, purchase_line_id, slot_id) = 1)',
        'Cada asignación enlaza exactamente un documento.')
    _qty_allocated_positive = models.Constraint(
        'CHECK(qty_allocated >= 0)', 'La cantidad asignada no puede ser negativa.')

    @api.constrains('kind', *DOCUMENT_FIELDS.values())
    def _check_kind(self):
        for allocation in self:
            if not allocation[DOCUMENT_FIELDS[allocation.kind]]:
                raise ValidationError(self.env._(
                    'La asignación de tipo «%s» debe enlazar ese documento.',
                    dict(KINDS)[allocation.kind]))

    def _document(self):
        self.ensure_one()
        return self[DOCUMENT_FIELDS[self.kind]]

    @api.depends('kind', *DOCUMENT_FIELDS.values())
    def _compute_document_name(self):
        for allocation in self:
            document = allocation._document() if allocation.kind else False
            if allocation.kind == 'purchase_request':
                name = document.request_id.name
            elif allocation.kind == 'material_request':
                name = document.request_id.name
            elif allocation.kind == 'service_order':
                name = document.order_id.name
            else:
                name = document.display_name if document else False
            allocation.document_name = name

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------
    @api.depends('kind', 'purchase_request_line_id.cancelled',
                 'purchase_request_line_id.request_state',
                 'purchase_request_line_id.purchase_lines.state',
                 'material_request_line_id.cancelled', 'material_request_line_id.line_state',
                 'material_request_line_id.request_id.state', 'production_id.state',
                 'purchase_line_id.order_id.state', 'purchase_line_id.qty_received',
                 'slot_id.end_datetime')
    def _compute_state(self):
        now = fields.Datetime.now()
        for allocation in self:
            allocation.state = allocation._get_document_state(now)

    def _get_document_state(self, now):
        kind = self.kind
        if kind == 'purchase_request':
            line = self.purchase_request_line_id
            if line.cancelled or line.request_state == 'rejected':
                return 'cancel'
            confirmed = self._confirmed_purchase_qty(line)
            if line.request_state == 'done' or (
                    line.product_uom_id and line.product_uom_id.compare(
                        confirmed, line.product_qty) >= 0):
                return 'done'
            return 'open'
        if kind == 'material_request':
            line = self.material_request_line_id
            request_state = line.request_id.state
            if line.cancelled or request_state in ('cancel', 'rejected'):
                return 'cancel'
            if request_state == 'done' or line.line_state == 'done':
                return 'done'
            return 'open'
        if kind == 'production':
            state = self.production_id.state
            return {'cancel': 'cancel', 'done': 'done'}.get(state, 'open')
        if kind == 'service_order':
            line = self.purchase_line_id
            if line.order_id.state == 'cancel':
                return 'cancel'
            if line.product_uom_id.compare(line.qty_received, line.product_qty) >= 0:
                return 'done'
            return 'open'
        if kind == 'planning_slot':
            end = self.slot_id.end_datetime
            return 'done' if end and end <= now else 'open'
        return 'open'

    # ------------------------------------------------------------------
    # Cantidades repartidas por fecha de necesidad
    # ------------------------------------------------------------------
    def _product_uom(self):
        """UdM del producto (base de los repartos) o, sin producto, la de la línea."""
        self.ensure_one()
        return self.plan_line_id.product_id.uom_id or self.plan_line_id.product_uom_id

    def _to_product_uom(self, qty):
        line_uom = self.plan_line_id.product_uom_id
        uom = self._product_uom()
        if line_uom and uom and line_uom != uom:
            return line_uom._compute_quantity(qty, uom, rounding_method='HALF-UP')
        return qty

    def _from_product_uom(self, qty):
        line_uom = self.plan_line_id.product_uom_id
        uom = self._product_uom()
        if line_uom and uom and line_uom != uom:
            return uom._compute_quantity(qty, line_uom, rounding_method='HALF-UP')
        return qty

    def _get_document_key(self):
        """Clave del documento que se reparte: la OF se reparte por componente."""
        self.ensure_one()
        if self.kind == 'production':
            return ('production', self.production_id.id, self.plan_line_id.product_id.id)
        return (self.kind, self._document().id)

    @staticmethod
    def _confirmed_purchase_qty(pr_line):
        """Cantidad de la línea OCA en OC confirmadas, en su unidad."""
        qty = 0.0
        for po_line in pr_line.purchase_lines.filtered(lambda l: l.state in ('purchase', 'done')):
            qty += po_line.product_uom_id._compute_quantity(
                po_line.product_qty, pr_line.product_uom_id or po_line.product_uom_id)
        return qty

    def _get_document_totals(self):
        """Totales del documento de ``self`` (primera asignación del grupo), en
        la UdM del producto: {medida: cantidad}."""
        self.ensure_one()
        product = self.plan_line_id.product_id
        uom = self._product_uom()

        def to_uom(qty, from_uom):
            if from_uom and uom and from_uom != uom:
                return from_uom._compute_quantity(qty, uom, rounding_method='HALF-UP')
            return qty

        kind = self.kind
        if kind == 'purchase_request':
            line = self.purchase_request_line_id
            confirmed = self._confirmed_purchase_qty(line)
            active = not (line.cancelled or line.request_state == 'rejected')
            # La compra masiva sube el comprado al crearse (especificación,
            # P-10); si se cancela, queda solo lo que ya llegó a una OC.
            purchased = max(line.product_qty, confirmed) if active else confirmed
            return {'purchased': to_uom(purchased, line.product_uom_id),
                    'done': to_uom(confirmed, line.product_uom_id)}
        if kind == 'material_request':
            line = self.material_request_line_id
            return {'purchased': to_uom(line.qty_purchased, line.product_uom_id),
                    'dispatched': to_uom(line.qty_received_on_site, line.product_uom_id)}
        if kind == 'production':
            date_to = self._construction_date_to()
            moves = self.production_id.move_raw_ids.filtered(
                lambda m: m.state == 'done' and m.product_id == product
                and (not date_to or m.date <= date_to))
            consumed = sum(to_uom(m.quantity, m.product_uom) for m in moves)
            # Lo que la OF consume ya se entregó en planta.
            return {'dispatched': consumed, 'consumed': consumed}
        if kind == 'service_order':
            line = self.purchase_line_id
            return {'done': to_uom(line.qty_received, line.product_uom_id)}
        return {}

    def _construction_date_to(self):
        """Fin del día de corte (``construction_date_to`` del contexto) para
        medir lo consumido hasta esa fecha: la entrega semanal (fase 10)."""
        day = self.env.context.get('construction_date_to')
        return datetime.combine(fields.Date.to_date(day), time.max) if day else None

    @api.model
    def _construction_consumed_at(self, allocations, day):
        """{asignación: consumido hasta ``day``} en la unidad de la línea. Lo
        consumido es un campo calculado sin caché por contexto: se descarta
        antes y después de leerlo con la fecha de corte."""
        measures = ['qty_purchased', 'qty_dispatched', 'qty_consumed', 'qty_done']
        self.invalidate_model(measures)
        dated = allocations.with_context(construction_date_to=day)
        result = {allocation: allocation.qty_consumed for allocation in dated}
        self.invalidate_model(measures)
        return {self.browse(allocation.id): qty for allocation, qty in result.items()}

    def _get_siblings(self):
        """Todas las asignaciones de los documentos de ``self``."""
        domain = []
        for kind, field in DOCUMENT_FIELDS.items():
            ids = self.filtered(lambda a, k=kind: a.kind == k)[field].ids
            if ids:
                domain = domain and ['|'] + domain + [(field, 'in', ids)] or [(field, 'in', ids)]
        if not domain:
            return self
        return self.search(domain) | self

    def _get_site_consumption(self):
        """Consumo en obra de las asignaciones de requerimientos de obra:
        movimientos hechos desde la ubicación de la obra hacia una ubicación
        de consumo (menos las devoluciones), por obra y producto, repartidos
        entre todas las asignaciones de esa obra y producto."""
        allocations = self.filtered(lambda a: a.kind == 'material_request')
        result = {}
        if not allocations:
            return result
        groups = defaultdict(lambda: self.browse())
        for allocation in allocations:
            site = allocation.material_request_line_id.request_id.location_dest_id
            product = allocation.plan_line_id.product_id
            if site and product:
                groups[(site, product)] |= allocation
        Move = self.env['stock.move']
        date_to = self._construction_date_to()
        date_domain = [('date', '<=', date_to)] if date_to else []
        for (site, product), _group in groups.items():
            siblings = self.search([
                ('kind', '=', 'material_request'),
                ('material_request_line_id.request_id.location_dest_id', '=', site.id),
                ('plan_line_id.product_id', '=', product.id),
            ]) | _group
            consumed = 0.0
            for moves, sign in (
                (Move.search([('state', '=', 'done'), ('product_id', '=', product.id),
                              ('location_id', 'child_of', site.id),
                              ('location_dest_id.usage', 'in', CONSUMPTION_USAGES)]
                             + date_domain), 1),
                (Move.search([('state', '=', 'done'), ('product_id', '=', product.id),
                              ('location_dest_id', 'child_of', site.id),
                              ('location_id.usage', 'in', CONSUMPTION_USAGES)]
                             + date_domain), -1),
            ):
                consumed += sign * sum(
                    m.product_uom._compute_quantity(m.quantity, product.uom_id,
                                                    rounding_method='HALF-UP')
                    for m in moves)
            ordered = siblings.sorted(lambda a: (a.date_needed or date.max, a.id))
            shares = distribute(consumed, [(a, a._to_product_uom(a.qty_allocated))
                                           for a in ordered])
            result.update(shares)
        return result

    @api.depends('kind', 'qty_allocated', 'plan_line_id.date_needed',
                 'purchase_request_line_id.product_qty', 'purchase_request_line_id.cancelled',
                 'purchase_request_line_id.request_state',
                 'purchase_request_line_id.purchase_lines.state',
                 'material_request_line_id.qty_purchased',
                 'material_request_line_id.qty_received_on_site',
                 'production_id.move_raw_ids.state', 'production_id.move_raw_ids.quantity',
                 'purchase_line_id.qty_received')
    def _compute_quantities(self):
        real = self.filtered('id')
        values = defaultdict(dict)
        if real:
            groups = defaultdict(lambda: self.browse())
            for allocation in real._get_siblings():
                groups[allocation._get_document_key()] |= allocation
            wanted = {allocation._get_document_key() for allocation in real}
            for key, allocations in groups.items():
                if key not in wanted:
                    continue
                ordered = allocations.sorted(lambda a: (a.date_needed or date.max, a.id))
                items = [(a, a._to_product_uom(a.qty_allocated)) for a in ordered]
                for measure, total in ordered[0]._get_document_totals().items():
                    for allocation, qty in distribute(total, items).items():
                        values[allocation][measure] = qty
            for allocation, qty in real._get_site_consumption().items():
                values[allocation]['consumed'] = qty
        for allocation in self:
            vals = values.get(allocation, {})
            converted = {m: allocation._from_product_uom(vals.get(m, 0.0)) for m in MEASURES}
            allocation.qty_purchased = converted['purchased']
            allocation.qty_dispatched = converted['dispatched']
            allocation.qty_consumed = converted['consumed']
            allocation.qty_done = converted[DONE_MEASURE.get(allocation.kind, 'done')]

    # ------------------------------------------------------------------
    # Control de las líneas (estado y montos almacenados)
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        allocations = super().create(vals_list)
        allocations._refresh_plan_lines()
        return allocations

    def write(self, vals):
        before = self.plan_line_id
        res = super().write(vals)
        (before | self.plan_line_id)._refresh_control()
        return res

    def unlink(self):
        lines = self.plan_line_id
        res = super().unlink()
        lines._refresh_control()
        return res

    def _refresh_plan_lines(self):
        """Actualiza las líneas del plan de estas asignaciones y de las demás
        del mismo documento (lo hecho se reparte entre todas)."""
        allocations = self.exists()
        if allocations:
            allocations._get_siblings().plan_line_id._refresh_control()

    @api.model
    def _refresh_for_documents(self, field, documents):
        """Gancho de los documentos: actualiza las líneas del plan de sus
        asignaciones (``field`` es el campo de la asignación que los enlaza)."""
        if not documents:
            return
        # sudo: el documento lo cambia quien no ve el plan (compras,
        # almacén, planta); solo se actualiza el control de las líneas.
        allocations_sudo = self.sudo().search([(field, 'in', documents.ids)])
        allocations_sudo._refresh_plan_lines()

    def _get_requested_qty(self):
        """Lo que la asignación cuenta como «Pedido» de su línea (en la unidad
        de la línea): lo asignado; si el documento se canceló, solo lo hecho."""
        self.ensure_one()
        if self.kind == 'purchase_request':
            return 0.0
        return self.qty_done if self.state == 'cancel' else self.qty_allocated

    def action_open_document(self):
        self.ensure_one()
        document = self._document()
        if self.kind in ('purchase_request', 'material_request'):
            document = document.request_id
        elif self.kind == 'service_order':
            document = document.order_id
        return {
            'type': 'ir.actions.act_window',
            'res_model': document._name,
            'res_id': document.id,
            'view_mode': 'form',
        }
