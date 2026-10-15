# -*- coding: utf-8 -*-
from odoo import fields, models

from odoo.addons.al_construction_planner.models.common import PURCHASE_DESTINATIONS


class PurchaseRequest(models.Model):
    _inherit = 'purchase.request'

    construction_plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan de recursos', readonly=True, copy=False,
        index='btree_not_null', check_company=True)

    def _al_site_name(self):
        """La compra masiva del plan no tiene requerimiento de obra: la obra
        es la del plan."""
        return super()._al_site_name() or self.construction_plan_id.project_id.name or ''

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals:
            self.env['construction.resource.plan.allocation']._refresh_for_documents(
                'purchase_request_line_id', self.line_ids)
        return res


class PurchaseRequestLine(models.Model):
    _inherit = 'purchase.request.line'

    construction_allocation_ids = fields.One2many(
        'construction.resource.plan.allocation', 'purchase_request_line_id',
        string='Asignaciones del plan')
    construction_plan_mode = fields.Selection(
        PURCHASE_DESTINATIONS,
        string='Modo de compra masiva', readonly=True, copy=False)

    def write(self, vals):
        res = super().write(vals)
        if {'cancelled', 'product_qty', 'product_uom_id'} & set(vals):
            self.env['construction.resource.plan.allocation']._refresh_for_documents(
                'purchase_request_line_id', self)
        return res


class PurchaseRequestLineMakePurchaseOrder(models.TransientModel):
    _inherit = 'purchase.request.line.make.purchase.order'

    def _al_is_general_stock(self, item):
        """La compra masiva del plan directo a la obra (v1.7, M17-14) conserva
        la analítica de la obra."""
        if item.line_id.construction_plan_mode == 'project':
            return False
        return super()._al_is_general_stock(item)

    def _al_final_location(self, item):
        """Directo a la obra: la OC entrega en la ubicación de la obra."""
        line = item.line_id
        if line.construction_plan_mode == 'project':
            return line.request_id.construction_plan_id.project_id.construction_location_id
        return super()._al_final_location(item)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def write(self, vals):
        res = super().write(vals)
        # Confirmar o cancelar cambia el comprado de las compras masivas.
        if 'state' in vals:
            self.env['construction.resource.plan.allocation']._refresh_for_documents(
                'purchase_request_line_id', self.order_line.purchase_request_lines)
        return res
