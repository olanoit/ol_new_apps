# -*- coding: utf-8 -*-
"""Descuento del material extra a la contrata (v1.6, M16-08): los extras
aprobados con «Descontar a la contrata» entran a su siguiente liquidación
semanal en la obra como líneas negativas."""
from odoo import Command, api, fields, models
from odoo.exceptions import UserError


class ConstructionContractSettlement(models.Model):
    _inherit = 'construction.contract.settlement'

    discount_request_ids = fields.One2many(
        'construction.material.request', 'construction_discount_settlement_id',
        string='Material extra descontado', readonly=True,
        help='Extras aprobados con «Descontar a la contrata» (v1.6, M16-08): entran como líneas '
             'negativas y bajan el neto.')

    @api.depends('discount_request_ids.construction_discount_amount')
    def _compute_amounts(self):
        return super()._compute_amounts()

    def _get_discount_amount(self):
        return super()._get_discount_amount() + sum(
            self.discount_request_ids.mapped('construction_discount_amount'))

    def _construction_refresh_discounts(self):
        super()._construction_refresh_discounts()
        self._refresh_discounts()

    def _refresh_discounts(self):
        """Toma los extras aprobados con descuento a esta contrata en la obra
        que aún no se descontaron (v1.6, M16-08)."""
        self.ensure_one()
        # sudo: quien prepara la liquidación (supervisor o cron) no siempre ve
        # los requerimientos de obra; solo se enlazan los de esta contrata y
        # esta obra.
        Request_sudo = self.env['construction.material.request'].sudo()
        pending_sudo = Request_sudo.search([
            ('construction_discount', '=', True),
            ('construction_discount_partner_id', 'child_of', self.partner_id.commercial_partner_id.id),
            ('project_id', '=', self.project_id.id),
            ('state', 'in', ('approved', 'in_progress', 'done')),
            '|', ('construction_discount_settlement_id', '=', False),
            ('construction_discount_settlement_id.state', '=', 'cancel'),
        ])
        if pending_sudo:
            pending_sudo.write({'construction_discount_settlement_id': self.id})

    def _invoice_discount_line_values(self):
        line_vals = super()._invoice_discount_line_values()
        if not self.currency_id.is_zero(self.amount_discount):
            discount_account = self.company_id.construction_discount_account_id
            if not discount_account:
                raise UserError(self.env._(
                    'Configure la cuenta del descuento de material a contratas (Ajustes ▸ '
                    'Planificación de obra) para aprobar la liquidación %s.', self.name))
            for request in self.discount_request_ids:
                line_vals.append({
                    'display_type': 'product',
                    'name': self.env._('Descuento por material extra %s', request.name),
                    'account_id': discount_account.id,
                    'quantity': 1.0,
                    'price_unit': -request.construction_discount_amount,
                    'tax_ids': [Command.clear()],
                })
        return line_vals

    def _construction_release_discounts(self):
        super()._construction_release_discounts()
        # sudo: el supervisor puede no ver los requerimientos; vuelven a quedar
        # pendientes para la siguiente liquidación de la contrata.
        self.sudo().discount_request_ids.write({'construction_discount_settlement_id': False})
