# -*- coding: utf-8 -*-
"""Hoja de trabajo (formatos 1 y 2).

Una línea por cuenta con sus sumas y saldos, y el saldo repartido entre las
columnas de balance (activo/pasivo), de resultados por naturaleza y de
resultados por función. Al pie, las sumas, el resultado del ejercicio que
iguala cada par de columnas y los totales.

El formato 2 añade los saldos iniciales y los movimientos del periodo antes
de las sumas; las columnas que muestra cada informe son las de su registro
``account.report``.
"""
from collections import defaultdict

from odoo import _, fields, models
from odoo.tools import SQL

from odoo.addons.account_reports.utils.report_data_objects import AccountReportLineData

PNL_GROUPS = ('income', 'expense')
# Resultados por naturaleza: gastos 60-68 e ingresos 70-78 del PCGE, más el
# impuesto a la renta (88). La 69 (costo de ventas), la 79 y la clase 9 son
# de la presentación por función.
NATURE_PREFIXES = tuple(str(code) for code in range(60, 69)) \
    + tuple(str(code) for code in range(70, 79)) + ('88',)

COLUMN_LABELS = (
    'init_debit', 'init_credit', 'period_debit', 'period_credit',
    'sum_debit', 'sum_credit', 'balance_debit', 'balance_credit',
    'asset', 'liability', 'nature_loss', 'nature_profit',
    'function_loss', 'function_profit',
)
# Pares que el resultado del ejercicio iguala (debe, haber).
RESULT_PAIRS = (('asset', 'liability'), ('nature_loss', 'nature_profit'),
                ('function_loss', 'function_profit'))


def _split(amount):
    """Saldo (debe - haber) en el par (deudor, acreedor)."""
    return (amount, 0.0) if amount > 0 else (0.0, -amount)


class AccountPeWorksheetReportHandler(models.AbstractModel):
    _name = 'account.pe.worksheet.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = 'Hoja de trabajo (Perú)'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        # Las columnas son fijas: sin comparación de periodos.
        options.pop('comparison', None)

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        # Sin comparación ni agrupación analítica hay una sola agrupación de
        # columnas.
        group_options = next(iter(report._split_options_per_column_group(options).values()))
        rows = self._l10n_pe_get_rows(report, group_options)
        lines = [(0, self._l10n_pe_line(report, options, row)) for row in rows]

        sums = {label: sum(row[label] for row in rows) for label in COLUMN_LABELS}
        result = {label: 0.0 for label in COLUMN_LABELS}
        for debit_label, credit_label in RESULT_PAIRS:
            difference = sums[debit_label] - sums[credit_label]
            # Utilidad: el debe supera al haber y el resultado va al haber
            # (y al revés con pérdida), como en la hoja de trabajo manual.
            if difference > 0:
                result[credit_label] = difference
            else:
                result[debit_label] = -difference
        grand = {label: sums[label] + result[label] for label in COLUMN_LABELS}

        for markup, name, values in (
            ('pe_ws_sums', _('Sumas'), sums),
            ('pe_ws_result', _('Resultado del ejercicio'), result),
            ('pe_ws_totals', _('Totales'), grand),
        ):
            lines.append((0, AccountReportLineData(
                id=report._get_generic_line_id(None, None, markup=markup),
                name=name,
                level=1,
                css_class='total',
                columns=self._l10n_pe_columns(report, options, values),
            )))
        return lines

    def _l10n_pe_line(self, report, options, row):
        account = row.get('account')
        if account:
            line_id = report._get_generic_line_id('account.account', account.id)
            name = account.display_name
        else:
            line_id = report._get_generic_line_id(None, None, markup='pe_ws_prior_results')
            name = _('Resultados de ejercicios anteriores')
        return AccountReportLineData(
            id=line_id,
            name=name,
            level=2,
            caret_options='account.account' if account else None,
            columns=self._l10n_pe_columns(report, options, row),
        )

    def _l10n_pe_columns(self, report, options, values):
        return [
            report._build_column_data(values.get(column['expression_label'], 0.0), column, options=options)
            for column in options['columns']
        ]

    def _l10n_pe_get_rows(self, report, options):
        """Filas de la hoja de trabajo para una agrupación de columnas."""
        company = self.env.company
        date_from = fields.Date.to_date(options['date']['date_from'])
        fiscalyear_start = company.compute_fiscalyear_dates(date_from)['date_from']
        query = report._get_report_query(options, 'from_beginning')
        self.env.cr.execute(SQL(
            """
            SELECT account_move_line.account_id,
                   SUM(CASE WHEN account_move_line.date < %(date_from)s
                            THEN %(balance)s ELSE 0 END) AS initial,
                   SUM(CASE WHEN account_move_line.date < %(fiscalyear_start)s
                            THEN %(balance)s ELSE 0 END) AS before_fiscalyear,
                   SUM(CASE WHEN account_move_line.date >= %(date_from)s
                            THEN %(debit)s ELSE 0 END) AS period_debit,
                   SUM(CASE WHEN account_move_line.date >= %(date_from)s
                            THEN %(credit)s ELSE 0 END) AS period_credit
              FROM %(table_references)s
             WHERE %(search_condition)s
          GROUP BY account_move_line.account_id
            """,
            date_from=date_from,
            fiscalyear_start=fiscalyear_start,
            # Odoo 20: el importe convertido (multicompañía) lo da la tabla del query.
            balance=query.table.consolidation_balance,
            debit=query.table.consolidation_debit,
            credit=query.table.consolidation_credit,
            table_references=query.from_clause,
            search_condition=query.where_clause,
        ))
        results = self.env.cr.dictfetchall()

        accounts = self.env['account.account'].browse(
            [result['account_id'] for result in results]).with_company(company)
        function_prefixes = tuple(
            prefix.strip() for prefix in (company.l10n_pe_ws_function_prefixes or '').split(',')
            if prefix.strip())
        currency = company.currency_id

        rows = []
        prior_results = 0.0
        for result in results:
            account = accounts.browse(result['account_id'])
            initial = currency.round(result['initial'] or 0.0)
            if account.internal_group in PNL_GROUPS:
                # Las cuentas de resultados empiezan en cero cada ejercicio; lo
                # de ejercicios anteriores va a una sola línea de patrimonio.
                before_fiscalyear = currency.round(result['before_fiscalyear'] or 0.0)
                initial -= before_fiscalyear
                prior_results += before_fiscalyear
            row = self._l10n_pe_row(account, initial, currency.round(result['period_debit'] or 0.0),
                                    currency.round(result['period_credit'] or 0.0), function_prefixes)
            if not all(currency.is_zero(row[label]) for label in COLUMN_LABELS):
                rows.append(row)
        rows.sort(key=lambda row: row['account'].code or '')

        if not currency.is_zero(prior_results):
            rows.insert(0, self._l10n_pe_row(None, prior_results, 0.0, 0.0, function_prefixes))
        return rows

    def _l10n_pe_row(self, account, initial, period_debit, period_credit, function_prefixes):
        row = defaultdict(float)
        row['account'] = account
        row['init_debit'], row['init_credit'] = _split(initial)
        row['period_debit'] = period_debit
        row['period_credit'] = period_credit
        row['sum_debit'] = row['init_debit'] + period_debit
        row['sum_credit'] = row['init_credit'] + period_credit
        balance = row['sum_debit'] - row['sum_credit']
        row['balance_debit'], row['balance_credit'] = _split(balance)

        if account is None or account.internal_group not in (*PNL_GROUPS, 'off'):
            # Cuentas de balance (y la línea de ejercicios anteriores).
            row['asset'], row['liability'] = _split(balance)
        elif account.internal_group in PNL_GROUPS:
            code = account.code or ''
            if code.startswith(NATURE_PREFIXES):
                row['nature_loss'], row['nature_profit'] = _split(balance)
            if function_prefixes and code.startswith(function_prefixes):
                row['function_loss'], row['function_profit'] = _split(balance)
        return row
