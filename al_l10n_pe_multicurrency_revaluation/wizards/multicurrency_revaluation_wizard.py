# -*- coding: utf-8 -*-
from odoo import _, api, models


class AccountMulticurrencyRevaluationWizard(models.TransientModel):
    _inherit = 'account.multicurrency.revaluation.wizard'

    @api.model
    def _get_move_vals(self):
        """Cita en cada línea de provisión el T.C. realmente aplicado.

        El importe ya es correcto: sale de la columna de ajuste del informe,
        que respeta el tipo de cambio de cada cuenta. Solo cambia la etiqueta,
        que en el nativo siempre cita la tasa genérica de la moneda.
        """
        vals = super()._get_move_vals()
        options = self.env.context.get('multicurrency_revaluation_report_options') or {}
        if 'l10n_pe_revaluation_groups' not in options \
                or self.env.company.account_fiscal_country_id.code != 'PE':
            return vals
        handler = self.env['account.multicurrency.revaluation.report.handler']
        # El nativo agrega las líneas de dos en dos: la provisión sobre la
        # cuenta revaluada y su contrapartida de ingreso o gasto.
        for command in vals['line_ids'][::2]:
            line = command[2]
            rate = handler._l10n_pe_rate_display(options, line['account_id'], line['currency_id'])
            if rate:
                line['name'] = _(
                    'Provisión de %(currency)s (T.C. %(rate)s)',
                    currency=self.env['res.currency'].browse(line['currency_id']).display_name,
                    rate=rate,
                )
        return vals
