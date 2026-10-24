# -*- coding: utf-8 -*-
"""CREVAL v1.0, CR-10: una sola semana para el avance y la valorización. Las
obras con órdenes de corte semanal pasan a cerrar su semana ese día; si sus
órdenes tienen cortes distintos, la obra no cambia y queda en el registro."""
import logging
from collections import defaultdict

from odoo import SUPERUSER_ID, api


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    cutoffs = defaultdict(set)
    for terms in env['construction.contract.condition'].with_context(active_test=False).search([
            ('order_id', '!=', False), ('frequency', '=', 'weekly'),
            ('cutoff_weekday', '!=', False)]):
        project = terms.order_id.construction_project_id
        if project:
            cutoffs[project].add(terms.cutoff_weekday)
    for project, days in cutoffs.items():
        if len(days) > 1:
            _logger.warning('Obra %s: órdenes con cortes semanales distintos %s; la semana de la '
                            'obra no cambia.', project.display_name, sorted(days))
            continue
        start_day = str((int(days.pop()) + 1) % 7)
        if project.construction_week_start_day != start_day:
            _logger.info('Obra %s: la semana empieza el día %s (corte de sus órdenes).',
                         project.display_name, start_day)
            project.construction_week_start_day = start_day
