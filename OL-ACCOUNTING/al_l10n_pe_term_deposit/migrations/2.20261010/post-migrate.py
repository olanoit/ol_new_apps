# -*- coding: utf-8 -*-
"""Versión 2: enlaza los asientos existentes con su depósito y marca sus
apuntes de ingreso por intereses (reporte «Intereses devengados»)."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['l10n_pe.term.deposit'].search([])._l10n_pe_link_existing_moves()
