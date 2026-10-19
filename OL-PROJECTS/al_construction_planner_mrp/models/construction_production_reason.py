# -*- coding: utf-8 -*-
"""Motivo obligatorio en la orden de posventa (paquete 1.10, M110-06).

La orden de fabricación nativa no tiene motivo, solo el texto libre
«Origen». Las órdenes de posventa, garantía y reposición urgente llevan un
motivo de una lista configurable: separa el reproceso (falla, daño, pérdida)
del reemplazo pedido por el cliente, que genera un adicional. El tipo de
operación dice si sus órdenes piden motivo."""
from odoo import api, fields, models
from odoo.exceptions import UserError


class ConstructionProductionReason(models.Model):
    _name = 'construction.production.reason'
    _description = 'Motivo de fabricación'
    _order = 'sequence, name, id'
    _check_company_auto = True

    name = fields.Char(string='Motivo', required=True, translate=True)
    code = fields.Char(string='Código')
    sequence = fields.Integer(string='Orden', default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', index=True,
        help='Vacío: el motivo vale para todas las compañías.')
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Etapa analítica', check_company=True,
        help='Etapa del modelo analítico a la que va el costo de estas órdenes (Reproceso, '
             'Armado…).')
    generates_additional = fields.Boolean(
        string='Genera adicional al cliente',
        help='El cambio lo pidió el cliente: el costo se cobra como adicional.')
    note = fields.Text(string='Descripción')


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    construction_reason_required = fields.Boolean(
        string='Pide motivo',
        help='Las órdenes de fabricación de esta operación no se confirman sin un motivo de '
             'fabricación (posventa, garantía, reposición urgente).')


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    construction_reason_required = fields.Boolean(
        related='picking_type_id.construction_reason_required', string='Pide motivo')
    construction_reason_id = fields.Many2one(
        'construction.production.reason', string='Motivo', index='btree_not_null',
        check_company=True, tracking=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    construction_reason_note = fields.Text(string='Detalle del motivo')

    @api.model
    def _construction_check_reason(self, productions):
        missing = productions.filtered(
            lambda p: p.construction_reason_required and not p.construction_reason_id)
        if missing:
            raise UserError(self.env._(
                'Esta operación pide motivo: indíquelo en %s antes de confirmar.',
                ', '.join(missing.mapped('name'))))

    def action_confirm(self):
        self._construction_check_reason(self.filtered(lambda p: p.state == 'draft'))
        return super().action_confirm()
