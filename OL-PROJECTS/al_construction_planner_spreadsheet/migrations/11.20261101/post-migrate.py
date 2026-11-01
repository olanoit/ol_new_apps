# -*- coding: utf-8 -*-
"""Paquete 1.16, bloque 4c: la hoja de Odoo 19 no tiene REPT. Las fórmulas que
leían el código de «nombre · unidad · código» (APU_DETALLE del presupuesto,
BOM y PIEZAS del maestro) y el grupo y la categoría de REFERENCIAS daban
#NAME?. Se reescriben con TEXTBEFORE y TEXTAFTER en las hojas ya creadas: en
sus datos, en la última foto y en las revisiones. No se toca nada más."""
from odoo import SUPERUSER_ID, api

from odoo.addons.al_construction_planner_spreadsheet.models.sheet_migration import (
    migrate_documents, migrate_revisions, replace_in_cells, replace_rept,
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    documents = env['documents.document'].with_context(active_test=False).search(
        [('construction_sheet_kind', '!=', False), ('handler', '=', 'spreadsheet')])
    migrate_documents(env, documents, lambda data: replace_in_cells(data, replace_rept))
    migrate_revisions(env, documents, replace_rept, 'REPT(')
