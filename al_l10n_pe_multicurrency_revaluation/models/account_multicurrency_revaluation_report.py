# -*- coding: utf-8 -*-
"""T.C. compra/venta por cuenta en ganancias/pérdidas no realizadas.

La consulta de Enterprise aplica una sola tasa por moneda
(``options['currency_rates']``) y no tiene un punto de extensión por cuenta.
En lugar de copiarla, se ejecuta la original varias veces —una para las
cuentas sin tipo de cambio peruano y otra por cada tipo (compra, venta)—,
cada una restringida a sus cuentas con ``forced_domain`` y con sus propias
tasas, y se suman los resultados por clave de agrupación.
"""
from odoo import api, models

RATE_COLUMN = 'rate_used'


class AccountMulticurrencyRevaluationReportHandler(models.AbstractModel):
    _inherit = 'account.multicurrency.revaluation.report.handler'

    # ------------------------------------------------------------------
    # Opciones
    # ------------------------------------------------------------------
    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options['l10n_pe_revaluation_groups'] = []
        company = self.env.company
        if company.account_fiscal_country_id.code != 'PE':
            # La columna T.C. es parte fija del informe: fuera de Perú se quita
            # para que no aparezca vacía.
            options['columns'] = [
                column for column in options['columns']
                if column.get('expression_label') != RATE_COLUMN
            ]
            return

        date_to = options['date']['date_to']
        currencies = self.env['res.currency'].browse(
            int(currency_id) for currency_id in options['currency_rates'])
        Account = self.env['account.account'].with_company(company)
        groups = []
        for rate_type in ('purchase', 'sale'):
            accounts = Account.search([
                *Account._check_company_domain(company),
                ('l10n_pe_revaluation_rate_type', '=', rate_type),
            ])
            if not accounts:
                continue
            values = currencies._l10n_pe_revaluation_rates(company, date_to, rate_type)
            groups.append({
                'rate_type': rate_type,
                'account_ids': accounts.ids,
                'rates': {str(currency_id): value for currency_id, value in values.items()},
            })
        # Las cuentas se agrupan aquí y no en cada consulta: las opciones viajan
        # al asistente del asiento de ajuste, que así revalúa igual que el informe.
        options['l10n_pe_revaluation_groups'] = groups

    # ------------------------------------------------------------------
    # T.C. mostrado
    # ------------------------------------------------------------------
    @api.model
    def _l10n_pe_format_rate(self, value):
        """``S/ 3.750``: soles por unidad de moneda extranjera, a 3 decimales."""
        currency = self.env.company.currency_id
        amount = f'{value:.3f}'
        if currency.position == 'after':
            return f'{amount} {currency.symbol}'
        return f'{currency.symbol} {amount}'

    @api.model
    def _l10n_pe_generic_rate(self, options, currency_id):
        rate = options['currency_rates'].get(str(currency_id), {}).get('rate')
        return 1.0 / float(rate) if rate else 0.0

    @api.model
    def _l10n_pe_rate_display(self, options, account_id, currency_id):
        """T.C. que el informe aplica a una cuenta y moneda, ya formateado."""
        for group in options.get('l10n_pe_revaluation_groups') or []:
            if account_id in group['account_ids'] and str(currency_id) in group['rates']:
                return self._l10n_pe_format_rate(group['rates'][str(currency_id)])
        value = self._l10n_pe_generic_rate(options, currency_id)
        return self._l10n_pe_format_rate(value) if value else ''

    def _custom_line_postprocessor(self, report, options, lines):
        lines = super()._custom_line_postprocessor(report, options, lines)
        if 'l10n_pe_revaluation_groups' not in options \
                or self.env.company.account_fiscal_country_id.code != 'PE':
            return lines
        # En Perú el tipo de cambio se expresa en soles por dólar, como la
        # columna T.C.: «USD (1 USD = S/ 3.750)» y no «1 PEN = 0.266667 USD».
        for line in lines:
            res_model, res_id = report._get_model_info_from_id(line['id'])
            if res_model != 'res.currency':
                continue
            value = self._l10n_pe_generic_rate(options, res_id)
            if value:
                name = self.env['res.currency'].browse(res_id).display_name
                line['name'] = f'{name} (1 {name} = {self._l10n_pe_format_rate(value)})'
        return lines

    # ------------------------------------------------------------------
    # Motor
    # ------------------------------------------------------------------
    def _multi_currency_revaluation_get_custom_lines(self, options, line_code, current_groupby, next_groupby, offset=0, limit=None):
        if not current_groupby:
            # Línea principal: el nativo no calcula nada.
            result = super()._multi_currency_revaluation_get_custom_lines(
                options, line_code, current_groupby, next_groupby, offset=offset, limit=limit)
            return {**result, RATE_COLUMN: ''}

        groups = options.get('l10n_pe_revaluation_groups') or []
        if not groups:
            result = super()._multi_currency_revaluation_get_custom_lines(
                options, line_code, current_groupby, next_groupby, offset=offset, limit=limit)
            return [(key, self._l10n_pe_add_rate(options, vals, {}))
                    for key, vals in result]

        forced_domain = list(options.get('forced_domain') or [])
        grouped_ids = [account_id for group in groups for account_id in group['account_ids']]
        passes = [({
            **options,
            'forced_domain': forced_domain + [('account_id', 'not in', grouped_ids)],
        }, {})]
        for group in groups:
            currency_rates = {
                key: dict(values, rate=1.0 / group['rates'][key]) if key in group['rates'] else values
                for key, values in options['currency_rates'].items()
            }
            passes.append(({
                **options,
                'currency_rates': currency_rates,
                'forced_domain': forced_domain + [('account_id', 'in', group['account_ids'])],
            }, group['rates']))

        merged = {}
        for pass_options, overrides in passes:
            # Sin paginar: la paginación se aplica tras sumar los resultados.
            result = super()._multi_currency_revaluation_get_custom_lines(
                pass_options, line_code, current_groupby, next_groupby)
            for key, vals in result:
                vals = self._l10n_pe_add_rate(options, vals, overrides)
                merged[key] = self._l10n_pe_merge(merged[key], vals) if key in merged else vals

        keys = sorted(merged, key=lambda key: (key is None, key))
        keys = keys[offset:]
        if limit:
            keys = keys[:limit]
        return [(key, merged[key]) for key in keys]

    @api.model
    def _l10n_pe_add_rate(self, options, vals, overrides):
        currency_id = vals.get('currency_id')
        display = ''
        if currency_id:
            value = overrides.get(str(currency_id)) or self._l10n_pe_generic_rate(options, currency_id)
            display = self._l10n_pe_format_rate(value) if value else ''
        return {**vals, RATE_COLUMN: display}

    @api.model
    def _l10n_pe_merge(self, first, second):
        """Suma dos resultados de la misma clave de agrupación.

        El saldo en moneda extranjera solo se suma si ambos son de la misma
        moneda, como hace el nativo; el T.C. queda en blanco si difiere, porque
        mezclar dos tipos de cambio en un total no tiene sentido.
        """
        same_currency = first['currency_id'] is not None \
            and first['currency_id'] == second['currency_id']
        merged = dict(first)
        for field in ('balance_operation', 'balance_current', 'adjustment'):
            merged[field] = (first[field] or 0.0) + (second[field] or 0.0)
        merged.update({
            'balance_currency': ((first['balance_currency'] or 0.0) + (second['balance_currency'] or 0.0)
                                 if same_currency else None),
            'currency_id': first['currency_id'] if same_currency else None,
            'has_sublines': first['has_sublines'] or second['has_sublines'],
            RATE_COLUMN: first[RATE_COLUMN] if first[RATE_COLUMN] == second[RATE_COLUMN] else '',
        })
        return merged
