# -*- coding: utf-8 -*-
"""Orden de fabricación desde el plan (W-04): un producto de tipología por los
ambientes incluidos y componentes de la BOM. Al confirmar se controla el saldo
de las líneas de producción y armado; al cerrarla, sus consumos suben lo
consumido de esas líneas (asignaciones de tipo «Orden de fabricación»).

Fabricación por etapas (paquete 1.10, M110-04): cada orden compara solo las
etapas de su lista de materiales (el corte, lo de producción de piezas; el
armado, lo de armado) y el producto intermedio que llega de la etapa anterior
no se compara con el plan. La orden hija que crea Odoo por las rutas hereda
el plan y los ambientes de la madre."""
from collections import defaultdict

from markupsafe import Markup

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang

from odoo.addons.al_construction_planner.models.common import EXCEED_STATES

# Las etapas que consume la OF son las de fabricación y las marcadas «Consume
# en la orden de fabricación» del catálogo (en mobiliario, producción y
# armado); el resto de la BOM se pide a la obra con el requerimiento de obra.


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    construction_plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan de recursos', readonly=True, copy=False,
        index='btree_not_null', check_company=True)
    construction_space_task_ids = fields.Many2many(
        'project.task', 'mrp_production_construction_space_rel', 'production_id', 'task_id',
        string='Ambientes incluidos', copy=False, check_company=True)
    construction_allocation_ids = fields.One2many(
        'construction.resource.plan.allocation', 'production_id',
        string='Asignaciones del plan')
    construction_exceed_state = fields.Selection(
        EXCEED_STATES, string='Control de plan', default='ok', copy=False, readonly=True)
    construction_exceed_reason = fields.Text(string='Justificación del exceso', copy=False)
    construction_parent_id = fields.Many2one(
        'mrp.production', string='Orden de la etapa siguiente', readonly=True, copy=False,
        index='btree_not_null',
        help='La orden del plan de la que viene esta por las rutas (paquete 1.10, M110-04): '
             'el corte que abastece al armado.')

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals:
            self.env['construction.resource.plan.allocation']._refresh_for_documents(
                'production_id', self)
        return res

    # ------------------------------------------------------------------
    # Etapas de la orden (M110-04)
    # ------------------------------------------------------------------
    def _construction_order_stages(self):
        """Etapas que fabrica esta orden: las de su lista de materiales que
        consumen en la orden. Una lista sin etapas (las planas de siempre)
        fabrica todas las de la orden de fabricación."""
        self.ensure_one()
        # El operario de planta no lee el catálogo de etapas del planificador:
        # solo se toman los códigos de las etapas.
        production_codes = self.env['construction.stage'].sudo()._production_codes()
        # La lista la lee quien confirma en planta, aunque no administre listas.
        bom_sudo = self.sudo().bom_id
        stages = set(bom_sudo.bom_line_ids.mapped('construction_consumption_stage'))
        own = tuple(code for code in production_codes if code in stages)
        return own or production_codes

    def _construction_accessory_stages(self):
        """Etapas de la orden cuyos materiales se piden con «Pedir accesorios»."""
        self.ensure_one()
        # Mismo motivo: solo los códigos de las etapas con accesorios a pedido.
        accessory = self.env['construction.stage'].sudo()._accessory_codes()
        return tuple(code for code in self._construction_order_stages() if code in accessory)

    def _construction_is_intermediate(self, move):
        """El intermedio de la etapa anterior (el paquete de piezas): marcado
        en la lista, o sin etapa y con lista de materiales propia (listas
        hechas a mano)."""
        line = move.bom_line_id
        if line.construction_intermediate:
            return True
        if line.construction_consumption_stage:
            return False
        product = move.product_id
        return bool(self.env['mrp.bom']._bom_find(
            product, company_id=self.company_id.id, bom_type='normal')[product])

    def _construction_plan_lines(self, product):
        """Líneas de material del plan en los ambientes y las etapas de la OF."""
        self.ensure_one()
        return self.env['construction.resource.plan.line'].search([
            ('plan_id', '=', self.construction_plan_id.id),
            ('product_id', '=', product.id),
            ('resource_type', '=', 'material'),
            ('stage', 'in', self._construction_order_stages()),
            ('space_task_id', 'in', self.construction_space_task_ids.ids),
        ])

    def _construction_component_qty(self):
        """{producto: cantidad en su UdM} de los componentes de las etapas de
        la orden (por la etapa de la línea de BOM o porque el plan lo tiene en
        esas etapas), sin el producto intermedio."""
        self.ensure_one()
        result = defaultdict(float)
        stages = self._construction_order_stages()
        for move in self.move_raw_ids.filtered(lambda m: m.state != 'cancel'):
            stage = move.bom_line_id.construction_consumption_stage
            if stage and stage not in stages:
                continue
            if self._construction_is_intermediate(move):
                continue
            # El retazo entrega parte de la necesidad del tablero, que ya se
            # compara (M111-15): no es material sin presupuesto.
            if move._construction_is_remnant():
                continue
            # Planchas enteras (M111-12): se compara la necesidad, no el
            # entero que se entrega.
            result[move.product_id] += move.uom_id._compute_quantity(
                move.construction_need_qty, move.product_id.uom_id, round=False) \
                if move.construction_need_qty else move.product_qty
        return result

    def _construction_sync_allocations(self):
        Allocation = self.env['construction.resource.plan.allocation']
        for production in self.filtered('construction_plan_id'):
            own = production.construction_allocation_ids
            values = []
            for product, qty in production._construction_component_qty().items():
                plan_lines = production._construction_plan_lines(product)
                if not plan_lines:
                    continue
                shares = plan_lines._supply_split(qty, own)
                values += [{
                    'plan_line_id': plan_line.id,
                    'kind': 'production',
                    'production_id': production.id,
                    'qty_allocated': share,
                } for plan_line, share in shares.items()
                    if not plan_line.product_uom_id.is_zero(share)]
            own.unlink()
            Allocation.create(values)

    def _construction_get_excess(self):
        """[(producto, saldo, pedido, exceso)] en la UdM del producto. El
        control compara pedido menos saldo con la tolerancia; el exceso que se
        muestra nunca es mayor que lo pedido (paquete 1.10, M110-08)."""
        self.ensure_one()
        rows = []
        own = self.construction_allocation_ids
        for product, qty in self._construction_component_qty().items():
            plan_lines = self._construction_plan_lines(product)
            if not plan_lines:
                # Componente de producción o armado que el plan no tiene.
                rows.append((product, 0.0, qty, qty))
                continue
            balance, tolerance, excess = plan_lines._supply_check(qty, own)
            if product.uom_id.compare(excess, tolerance) > 0:
                rows.append((product, balance, qty, min(qty, excess)))
        return rows

    def _construction_excess_text(self, rows):
        return '\n'.join('   · %s: %s %s' % (
            product.display_name, formatLang(self.env, excess, digits=2), product.uom_id.name)
            for product, _balance, _qty, excess in rows)

    def _construction_procurement_excess(self, rows):
        """Orden hija confirmada por Odoo dentro del abastecimiento: no hay
        usuario frente a la pantalla y un error cancelaría la confirmación de
        la madre. Queda «excede» con el aviso en ella y en la madre."""
        self.ensure_one()
        self.construction_exceed_state = 'exceeded'
        body = Markup('%s<br/>%s') % (
            self.env._('%s pide más de lo que queda en el plan:', self.name),
            Markup('<br/>').join(self._construction_excess_text(rows).split('\n')))
        self.message_post(body=body)
        if self.construction_parent_id:
            self.construction_parent_id.message_post(body=body)

    def action_confirm(self):
        checked = self.env.context.get('construction_exceed_checked')
        from_procurement = self.env.context.get('construction_from_procurement')
        planned = self.filtered(lambda p: p.construction_plan_id and p.state == 'draft')
        for production in planned:
            # Quien confirma en planta puede no tener acceso al plan: las
            # asignaciones y el saldo se calculan sin sus permisos, solo para
            # esta OF.
            production_sudo = production.sudo()
            production_sudo._construction_sync_allocations()
            rows = production_sudo._construction_get_excess()
            if not rows:
                production.construction_exceed_state = 'ok'
                continue
            if from_procurement:
                production_sudo._construction_procurement_excess(rows)
                continue
            # Política de producción del plan (v1.8, M18-05: por tipo de recurso).
            policy = production_sudo.construction_plan_id._exceed_policy_for('production')
            if policy == 'block':
                raise UserError(self.env._(
                    'La OF %(production)s pide más de lo que queda en el plan %(plan)s y su '
                    'política es bloquear:\n\n%(lines)s',
                    production=production.name,
                    plan=production_sudo.construction_plan_id.display_name,
                    lines=production._construction_excess_text(rows)))
            if not checked:
                wizard = self.env['construction.plan.exceed.wizard'].create({
                    'production_id': production.id,
                    'reason': production.construction_exceed_reason,
                })
                return wizard._get_action()
        # Planchas enteras (paquete 1.11, M111-12): después del control de
        # exceso, que mide la necesidad, y antes de que nazca el despacho a
        # producción. Todas las órdenes en borrador, con plan o sin él.
        self.filtered(lambda p: p.state == 'draft')._construction_round_whole_sheets()
        res = super().action_confirm()
        # Mismo motivo: la OF solo pasa el plan a «En ejecución».
        plans_sudo = planned.construction_plan_id.sudo()
        plans_sudo._mark_in_progress()
        return res
