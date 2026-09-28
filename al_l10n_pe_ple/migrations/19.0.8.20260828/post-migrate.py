# -*- coding: utf-8 -*-
"""Clasificación RCE (campo 33) solo en facturas de proveedor.

Hasta esta versión el cálculo almacenado se aplicaba a todos los asientos,
también a ventas y asientos manuales, donde el campo no tiene sentido. Ahora
solo se propone en facturas y notas de crédito de proveedor en borrador; se
vacía el valor que quedó guardado en el resto. Las facturas de proveedor no
se tocan: su clasificación puede haberse corregido a mano o declarado.
"""
import logging

from odoo.tools import SQL

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(SQL(
        """
        UPDATE account_move
           SET l10n_pe_rce_classification = NULL
         WHERE l10n_pe_rce_classification IS NOT NULL
           AND move_type NOT IN %s
        """,
        ('in_invoice', 'in_refund'),
    ))
    if cr.rowcount:
        _logger.info('al_l10n_pe_ple: clasificación RCE vaciada en %s asiento(s) '
                     'que no son de compra.', cr.rowcount)
