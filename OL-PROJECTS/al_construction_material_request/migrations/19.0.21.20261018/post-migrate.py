# -*- coding: utf-8 -*-
"""Los datos de demostración ya no llevan el prefijo «[DEMO]»: en las bases
que ya los tienen (son noupdate) se quita a los registros de la demo de este
módulo que lo conservan, y a la ubicación de la obra que lleva su nombre."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

MODULE = 'al_construction_material_request'
PREFIX = '[DEMO] '
FIELDS = ('name', 'note')


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for data in env['ir.model.data'].search([('module', '=', MODULE), ('name', '=like', 'demo_%')]):
        if data.model not in env:
            continue
        record = env[data.model].browse(data.res_id).exists()
        if not record:
            continue
        values = {}
        for field in FIELDS:
            value = record[field] if field in record._fields else None
            # La nota es HTML: el prefijo va dentro del primer párrafo.
            if isinstance(value, str) and (value.startswith(PREFIX) or value.startswith('<p>' + PREFIX)):
                values[field] = value.replace(PREFIX, '', 1)
        if not values:
            continue
        location = record.construction_location_id if data.model == 'project.project' else None
        try:
            with cr.savepoint():
                if location and location.name == record.name:
                    location.name = values['name']
                record.write(values)
        except Exception:  # noqa: BLE001 - un registro bloqueado no detiene la actualización
            _logger.warning('No se pudo renombrar %s: %s', record, values)
