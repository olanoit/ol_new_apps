# -*- coding: utf-8 -*-
"""Trazabilidad del asiento de cierre y del T.C. aplicado en cada apunte."""
from odoo import fields, models

from .analytic_tools import merge_analytic_distributions


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_exchange_closure_id = fields.Many2one(
        comodel_name='l10n_pe.exchange.closure',
        string='Cierre de tipo de cambio', copy=False, index='btree_not_null',
        ondelete='set null', readonly=True,
        help='Cierre mensual que generó este asiento de ajuste.')


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    l10n_pe_closing_rate = fields.Float(
        string='T.C. de cierre', digits='Dual_Currency_TRM', copy=False,
        readonly=True,
        help='Tipo de cambio (compra o venta, según la cuenta) con el que se '
             'revaluó el saldo en este cierre.')

    def _l10n_pe_closing_analytic_distribution(self):
        """Distribución analítica que corresponde a este apunte de origen.

        Las líneas de balance (por cobrar, por pagar, bancos) casi nunca
        llevan analítica: la llevan las líneas de ingreso o gasto del mismo
        documento. Por eso, si el apunte no tiene distribución propia, se
        hereda la de sus hermanas del asiento, ponderada por importe.
        """
        self.ensure_one()
        if self.analytic_distribution:
            return self.analytic_distribution
        # Un asiento de cierre agrupa cuentas y socios distintos: sus líneas
        # de resultado pertenecen a otros grupos, de modo que heredar de las
        # hermanas contagiaría analítica ajena. Además su analítica ya se
        # registró en el mes que le tocaba.
        if self.move_id.l10n_pe_exchange_closure_id:
            return False
        siblings = self.move_id.line_ids.filtered(
            lambda line: line != self and line.analytic_distribution)
        if self.partner_id:
            # En un documento normal todas las líneas comparten el socio; si
            # el asiento mezcla varios, se prefieren las del mismo socio.
            siblings = siblings.filtered(
                lambda line: line.partner_id == self.partner_id) or siblings
        if not siblings:
            return False
        precision = self.env['decimal.precision'].precision_get(
            'Percentage Analytic')
        return merge_analytic_distributions(
            [(line.analytic_distribution, line.balance) for line in siblings],
            precision=precision)
