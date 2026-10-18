# -*- coding: utf-8 -*-
"""Estado sanitario del lote (Manual BPOF 7.5.1): solo los lotes disponibles
se reservan y se venden. Cuarentena (recepción no conforme, devolución por
verificar), bloqueado (alerta sanitaria, retiro) y vencido (por fecha)."""
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain

LOT_STATES = [
    ('available', 'Disponible'),
    ('quarantine', 'Cuarentena'),
    ('blocked', 'Bloqueado'),
    ('expired', 'Vencido'),
]


class StockLot(models.Model):
    _inherit = 'stock.lot'

    pharmacy_state = fields.Selection(
        LOT_STATES, string='Estado sanitario', default='available', required=True,
        tracking=True, index=True,
        help='Solo los lotes disponibles se reservan y se venden.')
    pharmacy_state_reason = fields.Char(string='Motivo del estado', tracking=True)
    pharmacy_expiry_soon = fields.Boolean(
        string='Por vencer', compute='_compute_pharmacy_expiry_soon',
        search='_search_pharmacy_expiry_soon',
        help='Vence dentro de los días de aviso de la compañía (Ajustes de Inventario).')

    @api.depends('expiration_date', 'company_id.pharmacy_expiry_alert_days')
    def _compute_pharmacy_expiry_soon(self):
        now = fields.Datetime.now()
        for lot in self:
            days = (lot.company_id or self.env.company).pharmacy_expiry_alert_days
            lot.pharmacy_expiry_soon = bool(
                lot.expiration_date and now <= lot.expiration_date <= now + timedelta(days=days))

    def _search_pharmacy_expiry_soon(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            return NotImplemented
        now = fields.Datetime.now()
        limit = now + timedelta(days=self.env.company.pharmacy_expiry_alert_days)
        domain = Domain('expiration_date', '>=', now) & Domain('expiration_date', '<=', limit)
        return domain if (operator == '=') == value else ~domain

    def _pharmacy_set_state(self, state, reason=False):
        self.write({'pharmacy_state': state, 'pharmacy_state_reason': reason})

    def action_pharmacy_release(self):
        if not self.env.user.has_group('al_pharmacy_base.group_pharmacy_pharmacist'):
            raise UserError(self.env._('Solo un químico farmacéutico libera lotes (BPOF 7.5.1.31).'))
        expired = self.filtered(lambda lot: lot.expiration_date
                                and lot.expiration_date < fields.Datetime.now())
        if expired:
            raise UserError(self.env._('Un lote vencido no se libera: %s',
                                       ', '.join(expired.mapped('name'))))
        self._pharmacy_set_state('available',
                                 self.env._('Liberado por %s', self.env.user.name))

    def action_pharmacy_quarantine(self):
        self._pharmacy_set_state('quarantine', self.env._('Puesto en cuarentena por %s',
                                                          self.env.user.name))

    @api.model
    def _cron_pharmacy_expire_lots(self):
        expired = self.search([
            ('expiration_date', '<', fields.Datetime.now()),
            ('pharmacy_state', '!=', 'expired'),
        ])
        expired._pharmacy_set_state('expired', self.env._('Vencido'))
        return expired
