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

# Los tipos de documento (compra masiva, requerimiento de obra, OF, OC de
# servicio, turno) los agrega cada puente (v1.7, M17-07) con su campo, su
# estado y sus cantidades: ver _kind_fields y los ganchos _get_document_*.
MEASURES = ('purchased', 'dispatched', 'consumed', 'done')


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
    kind = fields.Selection([], string='Documento', required=True)
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

    _qty_allocated_positive = models.Constraint(
        'CHECK(qty_allocated >= 0)', 'La cantidad asignada no puede ser negativa.')

    @api.model
    def _kind_fields(self):
        """{tipo: campo del documento enlazado}; cada puente agrega el suyo."""
        return {}

    @api.model
    def _kind_done_measures(self):
        """{tipo: medida que es su «Ejecutado»} (por defecto «done»)."""
        return {}

    @api.constrains('kind')
    def _check_kind(self):
        fields_by_kind = self._kind_fields()
        for allocation in self:
            linked = [f for f in fields_by_kind.values() if allocation[f]]
            if len(linked) != 1 or not allocation[fields_by_kind[allocation.kind]]:
                raise ValidationError(self.env._(
                    'La asignación de tipo «%s» debe enlazar ese documento y ningún otro.',
                    dict(self._fields['kind']._description_selection(self.env)).get(
                        allocation.kind, allocation.kind)))

    def _document(self):
        self.ensure_one()
        field = self._kind_fields().get(self.kind)
        return self[field] if field else False

    def _document_record(self):
        """El documento que se abre (la cabecera: requerimiento, OC…)."""
        return self._document()

    @api.depends('kind')
    def _compute_document_name(self):
        for allocation in self:
            document = allocation._document_record() if allocation.kind else False
            allocation.document_name = document.display_name if document else False

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------
    @api.depends('kind')
    def _compute_state(self):
        now = fields.Datetime.now()
        for allocation in self:
            allocation.state = allocation._get_document_state(now)

    def _get_document_state(self, now):
        """Estado de la asignación según su documento: cada puente resuelve el
        suyo y llama a super() para los demás."""
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
        """Clave del documento que se reparte (la OF, por componente)."""
        self.ensure_one()
        return (self.kind, self._document().id)

    def _to_uom(self, qty, from_uom):
        """``qty`` de ``from_uom`` a la UdM del producto de la línea."""
        uom = self._product_uom()
        if from_uom and uom and from_uom != uom:
            return from_uom._compute_quantity(qty, uom, rounding_method='HALF-UP')
        return qty

    def _get_document_totals(self):
        """Totales del documento de ``self`` (primera asignación del grupo), en
        la UdM del producto: {medida: cantidad}. Los da el puente del tipo."""
        self.ensure_one()
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
        for kind, field in self._kind_fields().items():
            ids = self.filtered(lambda a, k=kind: a.kind == k)[field].ids
            if ids:
                domain = domain and ['|'] + domain + [(field, 'in', ids)] or [(field, 'in', ids)]
        if not domain:
            return self
        return self.search(domain) | self

    def _get_extra_measures(self):
        """{asignación: {medida: cantidad en la UdM del producto}} que no salen
        del reparto del documento (el consumo en obra de los requerimientos)."""
        return {}

    @api.depends('kind', 'qty_allocated', 'plan_line_id.date_needed')
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
            for allocation, measures in real._get_extra_measures().items():
                values[allocation].update(measures)
        done_measures = self._kind_done_measures()
        for allocation in self:
            vals = values.get(allocation, {})
            converted = {m: allocation._from_product_uom(vals.get(m, 0.0)) for m in MEASURES}
            allocation.qty_purchased = converted['purchased']
            allocation.qty_dispatched = converted['dispatched']
            allocation.qty_consumed = converted['consumed']
            allocation.qty_done = converted[done_measures.get(allocation.kind, 'done')]

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

    def _get_open_document_dates(self):
        """[(documento, fecha)] que Logística revisa si cambian las fechas del
        plan (requerimiento, compra masiva y sus OC, OC de servicio)."""
        return []

    def _is_purchasing(self):
        """La asignación está en compras (estado «En compra» de la línea)."""
        return False

    def _get_requested_qty(self):
        """Lo que la asignación cuenta como «Pedido» de su línea (en la unidad
        de la línea): lo asignado; si el documento se canceló, solo lo hecho."""
        self.ensure_one()
        return self.qty_done if self.state == 'cancel' else self.qty_allocated

    def action_open_document(self):
        self.ensure_one()
        document = self._document_record()
        return {
            'type': 'ir.actions.act_window',
            'res_model': document._name,
            'res_id': document.id,
            'view_mode': 'form',
        }
