# -*- coding: utf-8 -*-
"""v1.8, M18-13: las recetas copiadas de un Work Item quedan vinculadas a él
para sincronizarse en los dos sentidos. Con el paquete Construction en la
base, cada línea se vincula con la línea del Work Item de su posición y se
toman las huellas de hoy; sin él, solo se guarda el Work Item."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Template = env['construction.execution.template'].with_context(active_test=False)
    linked = 0
    for template in Template.search([('source', '=', 'work_item'), ('work_item_id', '=', 0)]):
        model, _sep, item_id = (template.source_ref or '').partition(',')
        if model != 'x_work_item' or not item_id.isdigit():
            continue
        if Template._work_item_available():
            template._link_work_item(int(item_id))
        if not template.work_item_id:
            template.with_context(construction_sync_writing=True).work_item_id = int(item_id)
        linked += 1
    _logger.info('Planificador v1.8: %s recetas vinculadas a su Work Item', linked)
