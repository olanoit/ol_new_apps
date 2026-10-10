# -*- coding: utf-8 -*-
"""Orden de fabricación desde el plan (W-04): un producto de tipología por los
ambientes incluidos y componentes de la BOM. Al confirmar se controla el saldo
de las líneas de producción y armado; al cerrarla, sus consumos suben lo
consumido de esas líneas (asignaciones de tipo «Orden de fabricación»)."""
from collections import defaultdict

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang

from .common import EXCEED_STATES

# Etapas que consume la OF: el resto de la BOM (instalación, acabado) se pide
# a la obra con el requerimiento de obra.
PRODUCTION_STAGES = ('production', 'assembly')


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

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals:
            self.env['construction.resource.plan.allocation']._refresh_for_documents(
                'production_id', self)
        return res

    def _construction_plan_lines(self, product):
        """Líneas de producción y armado del material en los ambientes de la OF."""
        self.ensure_one()
        return self.env['construction.resource.plan.line'].search([
            ('plan_id', '=', self.construction_plan_id.id),
            ('product_id', '=', product.id),
            ('resource_type', '=', 'material'),
            ('stage', 'in', PRODUCTION_STAGES),
            ('space_task_id', 'in', self.construction_space_task_ids.ids),
        ])

    def _construction_component_qty(self):
        """{producto: cantidad en su UdM} de los componentes de producción y
        armado (por la etapa de la línea de BOM o porque el plan lo tiene en
        esas etapas)."""
        self.ensure_one()
        result = defaultdict(float)
        for move in self.move_raw_ids.filtered(lambda m: m.state != 'cancel'):
            stage = move.bom_line_id.construction_consumption_stage
            if stage and stage not in PRODUCTION_STAGES:
                continue
            result[move.product_id] += move.product_qty
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
        """[(producto, saldo, pedido, exceso)] en la UdM del producto."""
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
                rows.append((product, balance, qty, excess))
        return rows

    def _construction_excess_text(self, rows):
        return '\n'.join('   · %s: %s %s' % (
            product.display_name, formatLang(self.env, excess, digits=2), product.uom_id.name)
            for product, _balance, _qty, excess in rows)

    def action_confirm(self):
        checked = self.env.context.get('construction_exceed_checked')
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
            policy = production_sudo.construction_plan_id.exceed_policy
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
        res = super().action_confirm()
        # Mismo motivo: la OF solo pasa el plan a «En ejecución».
        plans_sudo = planned.construction_plan_id.sudo()
        plans_sudo._mark_in_progress()
        return res
