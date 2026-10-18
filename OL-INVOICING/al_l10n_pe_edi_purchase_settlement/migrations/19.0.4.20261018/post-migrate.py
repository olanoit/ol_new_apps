# -*- coding: utf-8 -*-
"""Los datos de demostración ya no llevan «DEMO» en el nombre: en las bases
que ya los tienen se renombran los registros de la demo de este módulo (y
las líneas de sus asientos). Solo cambia lo que conserva el texto viejo."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

MODULE = 'al_l10n_pe_edi_purchase_settlement'
# Reemplazos en orden; «=texto» reemplaza solo el valor exacto.
RENAMES = [('DEMO-CAFE', 'CAFE-PERG'), ('DEMO-ORO', 'ORO-BRUTO'), ('DEMO LC Quispe', 'Quispe'), ('DEMO LC Café', 'Café'), ('DEMO LC Oro', 'Oro'), ('DEMO LC ', 'LC-')]
FIELDS = ('name', 'ref', 'memo', 'payment_reference', 'origin', 'invoice_origin', 'default_code')


def _rename(value):
    for old, new in RENAMES:
        if old.startswith('='):
            if value == old[1:]:
                value = new
        else:
            value = value.replace(old, new)
    return value


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for data in env['ir.model.data'].search([('module', '=', MODULE), ('name', '=like', 'demo_%')]):
        if data.model not in env:
            continue
        record = env[data.model].browse(data.res_id).exists()
        records = list(record) + (list(record.line_ids) if record and data.model == 'account.move' else [])
        for rec in records:
            values = {}
            for field in FIELDS:
                if field in rec._fields and rec._fields[field].type in ('char', 'text') \
                        and isinstance(rec[field], str) and 'DEMO' in rec[field]:
                    new = _rename(rec[field])
                    if new != rec[field]:
                        values[field] = new
            if not values:
                continue
            try:
                with cr.savepoint():
                    rec.write(values)
            except Exception:  # noqa: BLE001 - un registro bloqueado no detiene la actualización
                _logger.warning('No se pudo renombrar %s: %s', rec, values)
    # Etiquetas de asientos generados a partir de la demo (cesiones, líneas
    # con el nombre del producto), que no tienen xmlid propio.
    olds = [old for old, _new in RENAMES if not old.startswith('=') and old.startswith('DEMO')]
    for old in olds:
        for line in env['account.move.line'].search([('name', 'like', old)]):
            new = _rename(line.name)
            if new != line.name:
                try:
                    with cr.savepoint():
                        line.name = new
                except Exception:  # noqa: BLE001
                    _logger.warning('No se pudo renombrar %s', line)
