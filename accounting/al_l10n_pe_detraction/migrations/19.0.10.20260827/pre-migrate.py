# -*- coding: utf-8 -*-
"""Vincula a su xmlid los códigos 007, 011, 016, 023, 032 y 041.

Esta versión los añade a los datos del módulo. En una base donde ya se
crearon desde el contraste con SUNAT, cargar los datos intentaría crearlos
otra vez y chocaría con la unicidad del código. Se registra su xmlid antes
de la carga, como ``noupdate``: los datos los reconocen y no los tocan.
"""
import logging

_logger = logging.getLogger(__name__)

CODES = ('007', '011', '016', '023', '032', '041')
MODULE = 'al_l10n_pe_detraction'


def migrate(cr, version):
    cr.execute("""
        INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
        SELECT %s, 'detraction_' || t.code, 'l10n_pe.detraction.type', t.id, TRUE
          FROM l10n_pe_detraction_type t
         WHERE t.code IN %s
           AND NOT EXISTS (
                SELECT 1 FROM ir_model_data d
                 WHERE d.module = %s AND d.name = 'detraction_' || t.code)
    """, (MODULE, CODES, MODULE))
    if cr.rowcount:
        _logger.info('%s: %s código(s) del contraste vinculados a sus datos.',
                     MODULE, cr.rowcount)
