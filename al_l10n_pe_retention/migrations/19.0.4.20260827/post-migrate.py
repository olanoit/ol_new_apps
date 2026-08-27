# -*- coding: utf-8 -*-
"""Unifica los campos de las dos excepciones al régimen de retenciones.

Hasta la 3.x el módulo definía en ``res.partner`` sus propios
``l10n_pe_retention_agent`` y ``l10n_pe_good_contributor``, de marcado
manual, mientras ``l10n_pe_vat_sunat`` mantenía ``is_retention_agent`` e
``is_good_taxpayer`` verificados contra el padrón oficial. Decidía el par
manual, de modo que un proveedor reconocido por el padrón seguía
sufriendo retención mientras nadie replicase la marca a mano.

Ahora la fuente única es el par del padrón. Esta migración vuelca lo que
se hubiera marcado a mano para no perder configuración; la marca manual
gana, porque el padrón puede ir por detrás de la designación de SUNAT.

Odoo no elimina la columna de un campo retirado, así que las dos
antiguas siguen en la tabla y se leen por SQL.
"""
import logging

_logger = logging.getLogger(__name__)

PARES = [
    ('l10n_pe_retention_agent', 'is_retention_agent'),
    ('l10n_pe_good_contributor', 'is_good_taxpayer'),
]


def migrate(cr, version):
    for viejo, nuevo in PARES:
        cr.execute("""
            SELECT 1 FROM information_schema.columns
             WHERE table_name = 'res_partner' AND column_name IN (%s, %s)
             GROUP BY 1 HAVING count(*) = 2
        """, (viejo, nuevo))
        if not cr.fetchone():
            _logger.info(
                'al_l10n_pe_retention: %s o %s no existe, nada que volcar.',
                viejo, nuevo)
            continue
        cr.execute("""
            UPDATE res_partner SET {nuevo} = TRUE
             WHERE {viejo} IS TRUE AND {nuevo} IS DISTINCT FROM TRUE
        """.format(viejo=viejo, nuevo=nuevo))
        _logger.info(
            'al_l10n_pe_retention: %s contactos volcados de %s a %s.',
            cr.rowcount, viejo, nuevo)
