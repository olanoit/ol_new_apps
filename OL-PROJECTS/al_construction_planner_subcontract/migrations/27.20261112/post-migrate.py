# -*- coding: utf-8 -*-
"""Paquete 1.22, M122-03: las líneas de liquidación con re-trabajo toman el
motivo del catálogo de sus avances (el núcleo ya los migró)."""
from odoo.tools import SQL


def migrate(cr, version):
    if not version:
        return
    cr.execute(SQL("""
        UPDATE construction_contract_settlement_line l
           SET rework_reason_id = p.rework_reason_id
          FROM construction_contract_settlement s, construction_task_progress p
         WHERE l.settlement_id = s.id AND l.is_rework AND l.rework_reason_id IS NULL
           AND l.rework_reason IS NOT NULL AND p.rework_reason = l.rework_reason
           AND p.rework_reason_id IS NOT NULL AND p.company_id = s.company_id
    """))
