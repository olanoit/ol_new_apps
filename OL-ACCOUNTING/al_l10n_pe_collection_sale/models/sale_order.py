from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    l10n_pe_collection_hold_warning = fields.Char(
        string='Bloqueo de crédito', compute='_compute_l10n_pe_collection_hold_warning')

    @api.depends('partner_id', 'company_id')
    def _compute_l10n_pe_collection_hold_warning(self):
        for order in self:
            partner = order.partner_id.commercial_partner_id
            order.l10n_pe_collection_hold_warning = _(
                '%s tiene el crédito bloqueado por cobranza: no se puede confirmar el pedido hasta que '
                'regularice su deuda o el administrador de cobranza lo libere.', partner.name,
            ) if partner and partner.sudo()._l10n_pe_collection_is_on_hold(order.company_id) else False
            # sudo: el vendedor no necesita permisos de cobranza para ver el bloqueo.

    def action_confirm(self):
        for order in self:
            partner = order.partner_id.commercial_partner_id
            if partner.sudo()._l10n_pe_collection_is_on_hold(order.company_id):
                raise UserError(_(
                    'No se puede confirmar %(order)s: %(partner)s tiene el crédito bloqueado por cobranza.',
                    order=order.name, partner=partner.name))
        return super().action_confirm()
