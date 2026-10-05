# -*- coding: utf-8 -*-
"""Correcciones de la auditoría de planillas (27/09/2026).

La lógica vive en ``hr.salary.rule._l10n_pe_sync_formulas`` (ver
``models/l10n_pe_rule_formulas.py``): reescribe por xmlid las reglas
``noupdate`` cuya fórmula sigue igual a una entregada antes y marca
HE25/HE35/HE100 como horas extra. El módulo también la invoca desde datos
en cada actualización, así que es idempotente.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['hr.salary.rule']._l10n_pe_sync_formulas()
