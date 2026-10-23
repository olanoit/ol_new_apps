# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # Se copia: las entregas parciales (backorders) siguen vinculadas.
    construction_request_id = fields.Many2one(
        'construction.material.request', string='Requerimiento de obra',
        index='btree_not_null', readonly=True)
    # Quien la valida (paquete 1.11, M111-11): el responsable (user_id) queda
    # con quien la creó y el vale de despacho necesita al almacenero.
    construction_validated_by_id = fields.Many2one(
        'res.users', string='Validado por', readonly=True, copy=False)

    def _sanity_check(self):
        """El despacho a obra de un requerimiento lo valida el almacén
        (Logística), no quien lo pidió (v1.6, M16-10)."""
        dispatches = self.filtered(
            lambda p: p.construction_request_id
            # El almacenero puede no leer el requerimiento: solo su tipo.
            and p.picking_type_id == p.construction_request_id.sudo()._get_dispatch_picking_type())
        if dispatches and not self.env.su and not self.env.user.has_group(
                'al_construction_material_request.group_construction_logistics'):
            raise UserError(_(
                'El despacho a obra %s lo valida el almacén (grupo Logística de '
                'requerimientos de obra).', ', '.join(dispatches.mapped('name'))))
        return super()._sanity_check()

    def _action_done(self):
        res = super()._action_done()
        self.filtered(lambda p: p.state == 'done').write(
            {'construction_validated_by_id': self.env.uid})
        return res

    def _get_dispatch_slip_user(self):
        """«Despachado por» del vale: quien validó la transferencia o, si
        aún no se valida, quien imprime."""
        self.ensure_one()
        if self.state == 'done' and self.construction_validated_by_id:
            return self.construction_validated_by_id
        return self.env.user
