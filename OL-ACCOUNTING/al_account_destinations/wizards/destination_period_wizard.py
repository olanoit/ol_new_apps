# -*- coding: utf-8 -*-
"""Destinos del periodo: cuadre 79 vs Elemento 9 y regeneración.

PCGE 2019, cuenta 79: «el saldo acreedor de esta cuenta debe ser igual a la
sumatoria de los saldos deudores de las cuentas de costos y gastos (Elemento
9), con los cuales se compensa al cierre del periodo». El asistente muestra
ese cuadre para un rango de fechas y vuelve a generar los asientos de
destino de los comprobantes del rango (p. ej. tras cambiar los repartos).
"""
from odoo import _, api, fields, models


class L10nPeDestinationPeriodWizard(models.TransientModel):
    _name = 'l10n_pe.destination.period.wizard'
    _description = 'Destinos del periodo'
    _check_company_auto = True

    # El cuadre es del RUC: compañía raíz y todas sus sucursales.
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, readonly=True,
        default=lambda self: self.env.company.root_id)
    currency_id = fields.Many2one(related='company_id.currency_id')
    dest_type = fields.Selection(related='company_id.l10n_pe_dest_type')
    date_from = fields.Date(
        string='Desde', required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_to = fields.Date(
        string='Hasta', required=True, default=fields.Date.context_today)
    balance_79 = fields.Monetary(
        string='Saldo acreedor 79', compute='_compute_balances',
        help='Cargas imputables a cuentas de costos y gastos del periodo.')
    balance_9 = fields.Monetary(
        string='Saldo deudor Elemento 9', compute='_compute_balances',
        help='Costos y gastos por función del periodo.')
    difference = fields.Monetary(string='Diferencia', compute='_compute_balances')
    move_count = fields.Integer(
        string='Comprobantes con destino', compute='_compute_move_count')

    def _period_balance(self, prefix):
        """Saldo (debe − haber) de las cuentas que empiezan por ``prefix``
        en el periodo, con comprobantes publicados de la compañía."""
        self.ensure_one()
        lines = self.env['account.move.line'].with_company(self.company_id)
        groups = lines._read_group(
            [('company_id', 'child_of', self.company_id.id),
             ('parent_state', '=', 'posted'),
             ('date', '>=', self.date_from), ('date', '<=', self.date_to),
             ('account_id.code', '=like', prefix + '%')],
            aggregates=['balance:sum'])
        return groups[0][0] if groups else 0.0

    @api.depends('company_id', 'date_from', 'date_to')
    def _compute_balances(self):
        for wizard in self:
            if not (wizard.date_from and wizard.date_to):
                wizard.balance_79 = wizard.balance_9 = wizard.difference = 0.0
                continue
            wizard.balance_79 = -wizard._period_balance('79')
            wizard.balance_9 = wizard._period_balance('9')
            wizard.difference = wizard.currency_id.round(wizard.balance_9 - wizard.balance_79)

    def _source_moves(self):
        """Comprobantes publicados del rango que tienen o pueden tener destino."""
        self.ensure_one()
        prefix = '6' if self.company_id.l10n_pe_dest_type == '6a9' else '9'
        Move = self.env['account.move'].with_company(self.company_id)
        return Move.search([
            ('company_id', 'child_of', self.company_id.id),
            ('state', '=', 'posted'),
            ('l10n_pe_is_destiny_entry', '=', False),
            ('date', '>=', self.date_from), ('date', '<=', self.date_to),
            '|', ('l10n_pe_destiny_move_id', '!=', False),
            ('line_ids.account_id.code', '=like', prefix + '%'),
        ], order='date, id')

    @api.depends('company_id', 'date_from', 'date_to')
    def _compute_move_count(self):
        for wizard in self:
            wizard.move_count = len(wizard._source_moves()) \
                if wizard.date_from and wizard.date_to else 0

    def action_regenerate(self):
        """Vuelve a generar el asiento de destino de cada comprobante del
        periodo con la configuración actual (por cuenta y por analítica)."""
        self.ensure_one()
        moves = self._source_moves()
        for move in moves:
            move._l10n_pe_create_destiny_entry()
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _('Destinos del periodo'),
                'message': _('Se regeneraron los destinos de %s comprobantes.', len(moves)),
                'type': 'success', 'next': {'type': 'ir.actions.act_window_close'},
            },
        }
