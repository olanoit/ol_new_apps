# -*- coding: utf-8 -*-
"""Recalcula los campos almacenados cuyo cálculo cambió en la versión 7.

* ``l10n_pe.letter.line.adeudado``: ahora sale del apunte enlazado a la letra
  (``l10n_pe_letter_line_id``) y se rehace al cambiar el importe.
* ``l10n_pe.letter.is_all_paid``: depende del adeudado de las letras.
* ``l10n_pe.letter.payment_ids``: los pagos se leen de las conciliaciones.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    lines = env['l10n_pe.letter.line'].with_context(active_test=False).search([])
    env.add_to_compute(lines._fields['adeudado'], lines)
    lines._recompute_recordset(['adeudado'])

    letters = env['l10n_pe.letter'].with_context(active_test=False).search([])
    for fname in ('is_all_paid', 'payment_ids'):
        env.add_to_compute(letters._fields[fname], letters)
    letters._recompute_recordset(['is_all_paid', 'payment_ids'])
    # related_payment_count depende de payment_ids
    env.flush_all()
    _logger.info('al_l10n_pe_account_letter: adeudado, pagos y «todas pagadas» '
                 'recalculados en %s letra(s) y %s canje(s).', len(lines), len(letters))
