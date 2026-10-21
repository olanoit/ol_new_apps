from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    l10n_pe_forecast_exclude = fields.Boolean(
        string='Fondos no disponibles',
        help='El saldo de esta cuenta no se puede usar libremente (p. ej. la cuenta de '
             'detracciones del Banco de la Nación): el flujo de caja proyectado lo muestra '
             'aparte y no lo suma al saldo inicial.')
