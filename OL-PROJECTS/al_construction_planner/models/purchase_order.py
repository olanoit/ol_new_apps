# -*- coding: utf-8 -*-
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
