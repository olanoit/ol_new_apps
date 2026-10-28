# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Marcan los asientos que genera el asistente de cierre del ejercicio:
    # al rehacer el cierre solo se borran estos borradores, nunca otros
    # asientos del diario de cierre.
    l10n_pe_closing_date = fields.Date(
        string='Cierre del ejercicio', copy=False, readonly=True,
        index='btree_not_null')
    l10n_pe_closing_step = fields.Selection(
        [('result', 'Determinación del resultado'),
         ('balance', 'Cierre de cuentas de balance'),
         ('reopening', 'Reapertura')],
        string='Paso del cierre', copy=False, readonly=True)
