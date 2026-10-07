# -*- coding: utf-8 -*-
"""Versión 5: el T.C. del cierre es el del cierre de operaciones de la fecha
del balance (art. 34 del Reglamento de la LIR), que SUNAT publica con fecha
del día siguiente.

Los cierres aún no contabilizados que usaban la opción por defecto anterior
(«Último día del mes») pasan a la nueva y vuelven a borrador si estaban
calculados. Los contabilizados no se tocan.
"""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    closures = env['l10n_pe.exchange.closure'].search([
        ('state', 'in', ('draft', 'computed')), ('rate_day', '=', 'last')])
    if closures:
        closures.write({'rate_day': 'close', 'rate_purchase': 0.0, 'rate_sale': 0.0})
