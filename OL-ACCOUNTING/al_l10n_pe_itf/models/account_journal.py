from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    l10n_pe_itf_applies = fields.Boolean(
        string='Afecto al ITF',
        help='El banco cobra el ITF (0,005 %) en los cargos y abonos de esta cuenta: se registra al '
             'confirmar cada pago o cobro. Desmárquelo en las cuentas exoneradas con declaración '
             'jurada ante el banco (detracciones, remuneraciones, CTS).')
