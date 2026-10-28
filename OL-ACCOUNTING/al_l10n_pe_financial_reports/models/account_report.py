# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountReport(models.Model):
    _inherit = 'account.report'

    l10n_pe_exclude_closing = fields.Selection(
        [('journal', 'Todos los asientos de los diarios de cierre'),
         ('balance', 'Solo el cierre y la reapertura del balance')],
        string='Sin asientos de cierre (PE)',
        help='Asientos de cierre que el informe no cuenta; siguen en el Libro '
             'diario y en el Libro mayor.\n'
             '* Todos: para los informes del ejercicio (Estado de resultados, '
             'hoja de trabajo), que saldrían en cero después del cierre.\n'
             '* Solo el balance: para el Balance, que así muestra el resultado '
             'ya trasladado a la 59 y no queda en cero al 31/12.')

    def _init_options_l10n_pe_exclude_closing(self, options, previous_options):
        # get_options() arma las opciones desde cero en cada llamada, así que
        # el dominio no se acumula. Las variantes se reenrutan antes de este
        # inicializador: self ya es la variante peruana.
        if self.l10n_pe_exclude_closing == 'journal':
            condition = ('journal_id.l10n_pe_journal_kind', '!=', 'closing')
        elif self.l10n_pe_exclude_closing == 'balance':
            condition = ('move_id.l10n_pe_closing_step', 'not in', ('balance', 'reopening'))
        else:
            return
        options['forced_domain'] = [*options.get('forced_domain', []), condition]
