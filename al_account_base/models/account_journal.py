# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    l10n_pe_journal_kind = fields.Selection(
        [('movement', 'Movimiento'),
         ('opening', 'Apertura'),
         ('closing', 'Cierre')],
        string='Naturaleza del diario', default='movement',
        help='Distingue los asientos de apertura y de cierre de los de '
             'movimiento. Los libros electrónicos los tratan de forma '
             'distinta: el asiento de apertura abre el ejercicio y el de '
             'cierre lo salda, y ninguno de los dos es una operación del '
             'periodo.')

    l10n_pe_exclude_from_books = fields.Boolean(
        string='Excluir de los libros electrónicos',
        help='Los asientos de este diario no se incluyen en los libros '
             'electrónicos. Se usa para diarios auxiliares o de conciliación '
             'que no representan operaciones declarables.')
