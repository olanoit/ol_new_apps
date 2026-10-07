"""Versión 9: diarios de letras, cuentas de redondeo y del descuento como campos.

Antes se buscaban por el nombre (diario «Letras por cobrar/pagar», cuenta
«Redondeo»); se marcan los que ya existían y se llenan las cuentas del PCGE
(4511, 6734, 6391) en las compañías peruanas.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['res.company'].search([])._l10n_pe_letter_adopt_named_setup()
