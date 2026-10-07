# -*- coding: utf-8 -*-
"""Versión 9: impuesto y secuencia con los xmlids oficiales, y los pagos con
retención ya numerados quedan «por enviar»."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    from odoo.addons.al_l10n_pe_retention.hooks import _l10n_pe_retention_load_template

    env = api.Environment(cr, SUPERUSER_ID, {})
    _l10n_pe_retention_load_template(env)
    env['account.payment'].search([
        ('l10n_pe_edi_retention_number', '!=', False), ('l10n_pe_edi_status', '=', False),
    ]).write({'l10n_pe_edi_status': 'to_send'})
