# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    # El centro de costo decide la función: la parte del gasto distribuida a
    # esta cuenta analítica va a su cuenta del Elemento 9 en el asiento de
    # destino (p. ej. Administración → 94, Ventas → 95, Producción → 92).
    l10n_pe_destination_account_id = fields.Many2one(
        'account.account', string='Cuenta de destino', check_company=True,
        help='Cuenta del Elemento 9 (o de la clase 6 si la compañía trabaja '
             'de 9 a 6) a la que va la parte del gasto distribuida a esta '
             'cuenta analítica en el asiento de destino.')
