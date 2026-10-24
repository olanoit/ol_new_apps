# -*- coding: utf-8 -*-
"""CREVAL v1.0, 6.7: la hoja de trabajo pasa a ser genérica (presupuesto y
plan). Las hojas que ya existían son el maestro de mobiliario, que ahora vive
en el puente al_construction_planner_spreadsheet_furniture."""
from odoo.tools import SQL


def migrate(cr, version):
    cr.execute(SQL(
        "UPDATE documents_document SET construction_sheet_kind = 'furniture' "
        "WHERE construction_project_id IS NOT NULL AND construction_sale_order_id IS NULL"))
