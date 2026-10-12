# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    l10n_pe_require_operation_number = fields.Boolean(
        string='Exigir número de operación',
        help='Los pagos de este diario no se confirman sin el número de operación del banco, '
             'que sustenta el uso de medios de pago (bancarización) y se cruza con el extracto.')
