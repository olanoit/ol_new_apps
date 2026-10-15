# -*- coding: utf-8 -*-
"""OC de servicio de las contratas (fases 5 y 6): una abierta por contrata y
obra, que concentra sus asignaciones y recibe cada liquidación semanal."""
from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    construction_plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan de recursos', copy=False,
        index='btree_not_null', check_company=True)
    # Una OC de servicio abierta por contrata y obra (P-05): concentra todas
    # las asignaciones de la contrata y recibe cada liquidación semanal.
    construction_is_service_order = fields.Boolean(
        string='OC de servicio de obra', copy=False, readonly=True,
        help='Creada por «Asignar contrata»: una por contrata y obra; recibe las liquidaciones '
             'semanales.')
    construction_project_id = fields.Many2one(
        'project.project', string='Obra de la contrata', copy=False, readonly=True,
        index='btree_not_null', check_company=True)
    construction_settlement_ids = fields.One2many(
        'construction.contract.settlement', 'purchase_order_id', string='Liquidaciones')
    construction_settlement_count = fields.Integer(
        string='Nº de liquidaciones', compute='_compute_construction_settlement_count')

    @api.depends('construction_settlement_ids')
    def _compute_construction_settlement_count(self):
        for order in self:
            order.construction_settlement_count = len(order.construction_settlement_ids)

    def _construction_open_service_order(self, partner, project):
        """OC de servicio abierta de la contrata en la obra (no anulada ni
        bloqueada)."""
        return self.search([
            ('construction_is_service_order', '=', True),
            ('partner_id', '=', partner.id),
            ('construction_project_id', '=', project.id),
            ('state', '!=', 'cancel'),
            ('locked', '=', False),
        ], order='id desc', limit=1)

    def write(self, vals):
        res = super().write(vals)
        # Confirmar o cancelar cambia el estado de las OC de servicio en las
        # líneas del plan.
        if 'state' in vals:
            self.env['construction.resource.plan.allocation']._refresh_for_documents(
                'purchase_line_id', self.order_line)
        return res

    def action_view_construction_settlements(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Liquidaciones de %s', self.name),
            'res_model': 'construction.contract.settlement',
            'view_mode': 'list,form',
            'domain': [('purchase_order_id', '=', self.id)],
            'context': {'create': False},
        }


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    construction_allocation_ids = fields.One2many(
        'construction.resource.plan.allocation', 'purchase_line_id',
        string='Asignaciones del plan')
    construction_activity_id = fields.Many2one(
        'construction.labor.activity', string='Actividad de obra', copy=False,
        index='btree_not_null', check_company=True)
    construction_retention_pct = fields.Float(
        string='Retención de la contrata (%)', digits=(5, 2), copy=False,
        help='De la tarifa vigente al asignar la contrata; se aplica en cada liquidación.')

    def write(self, vals):
        res = super().write(vals)
        if {'qty_received', 'qty_received_manual', 'product_qty'} & set(vals):
            self.env['construction.resource.plan.allocation']._refresh_for_documents(
                'purchase_line_id', self)
        return res


class ConstructionResourcePlanLine(models.Model):
    _inherit = 'construction.resource.plan.line'

    def _get_driver_amounts(self):
        """Además del personal propio, lo asignado a la OC de servicio de la
        contrata: comprometido lo no recibido y real lo recibido, a la tarifa
        de la OC."""
        committed, actual = super()._get_driver_amounts()
        for allocation in self.allocation_ids.filtered(
                lambda a: a.kind == 'service_order' and a.state != 'cancel'):
            # La tarifa de la OC se lee aunque el usuario del plan no tenga
            # acceso a compras: solo para valorizar.
            po_line_sudo = allocation.sudo().purchase_line_id
            price = po_line_sudo.price_unit
            committed += max(allocation.qty_allocated - allocation.qty_done, 0.0) * price
            actual += allocation.qty_done * price
        return committed, actual
