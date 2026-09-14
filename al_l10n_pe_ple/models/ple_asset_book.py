# -*- coding: utf-8 -*-
"""Libro 7 — Registro de Activos Fijos: fuente única de datos.

El reporte en pantalla (``l10n_pe.ple.asset.report.handler``) y el asistente
de exportación (``l10n_pe.ple.export.wizard``) leen de aquí, de modo que lo que
el contador revisa en pantalla es exactamente lo que va en el TXT.

Estructura: Anexo 2 de SUNAT (``docs/ple/Estructura del PLE.xls``, hoja 7).
Todos los importes del 7.1 admiten signo; los retiros y su depreciación se
informan en **negativo** para que cada fila cuadre como en el formato físico:
valor histórico = saldo inicial + adquisiciones + mejoras + retiros + ajustes.
"""
from datetime import date

from odoo import _, api, models
from odoo.exceptions import UserError

# Estados de ``account.asset`` que forman parte del registro.
ASSET_BOOK_STATES = ('open', 'paused', 'close')

# Importes del 7.1 que se suman en los totales del reporte.
ASSET_71_AMOUNTS = (
    'initial', 'additions', 'improvements', 'retirements', 'other_adjust',
    'historical_value', 'inflation_adjust', 'adjusted_value',
    'dep_prior', 'dep_year', 'dep_retirements', 'dep_other',
    'dep_historical', 'dep_inflation', 'dep_adjusted',
)


class L10nPePleAssetBook(models.AbstractModel):
    _name = 'l10n_pe.ple.asset.book'
    _inherit = 'l10n_pe.ple.mixin'
    _description = 'PLE SUNAT - Registro de Activos Fijos (Libro 7)'

    # ------------------------------------------------------------------
    # Selección de activos
    # ------------------------------------------------------------------
    @api.model
    def _asset_year_range(self, year):
        return date(year, 1, 1), date(year, 12, 31)

    @api.model
    def _asset_book_assets(self, company, year, extra_domain=None):
        """Activos raíz vigentes durante el ejercicio (excluye modelos,
        borradores, cancelados y los hijos por aumento de valor, que se
        agregan al padre)."""
        date_from, date_to = self._asset_year_range(year)
        domain = [
            ('company_id', '=', company.id),
            ('state', 'in', ASSET_BOOK_STATES),
            ('parent_id', '=', False),
            ('acquisition_date', '<=', date_to),
            '|', ('disposal_date', '=', False),
            ('disposal_date', '>=', date_from),
        ]
        return self.env['account.asset'].search(
            domain + (extra_domain or []), order='acquisition_date, id')

    @api.model
    def _asset_depreciation_sums(self, assets, date_from, date_to):
        """``{id raíz: {'prior', 'year', 'other'}}`` desde los asientos
        publicados del activo y de sus hijos.

        Solo cuenta ``depreciation_value`` de los asientos de depreciación
        (``prior`` antes de ``date_from``, ``year`` dentro del rango) y, como
        otros ajustes del ejercicio, las revaluaciones negativas. Un asiento
        manual vinculado al activo no lleva tipo y se toma como depreciación.
        Los asientos de baja o venta no son depreciación: su total ronda el
        valor original del activo y antes inflaba el campo 30.
        """
        children = assets.children_ids
        root_of = {asset.id: asset.id for asset in assets}
        root_of.update({child.id: child.parent_id.id for child in children})
        result = {asset.id: dict.fromkeys(('prior', 'year', 'other'), 0.0)
                  for asset in assets}
        moves = self.env['account.move'].search_read(
            [('asset_id', 'in', (assets | children).ids),
             ('state', '=', 'posted'),
             ('asset_move_type', 'in',
              ('depreciation', 'negative_revaluation', False)),
             ('date', '<=', date_to)],
            ['asset_id', 'date', 'depreciation_value', 'asset_move_type'])
        for move in moves:
            sums = result[root_of[move['asset_id'][0]]]
            if move['date'] < date_from:
                sums['prior'] += move['depreciation_value']
            elif move['asset_move_type'] != 'negative_revaluation':
                sums['year'] += move['depreciation_value']
            else:
                sums['other'] += move['depreciation_value']
        for asset in assets:
            # depreciación importada de sistemas previos = acumulada anterior
            result[asset.id]['prior'] += asset.already_depreciated_amount_import
        return result

    @api.model
    def _asset_code(self, asset):
        return self._ple_text(
            asset.l10n_pe_ple_code, 24, default='AF%06d' % asset.id)

    @api.model
    def _asset_require(self, assets, field_name, label):
        missing = assets.filtered(lambda a: not a[field_name])
        if missing:
            raise UserError(_(
                'Los siguientes activos no tienen configurado «%(label)s» '
                '(pestaña PLE SUNAT): %(assets)s',
                label=label,
                assets=', '.join(missing.mapped('display_name')[:20])))

    # ------------------------------------------------------------------
    # 7.1 — valores (numéricos, para pantalla y TXT)
    # ------------------------------------------------------------------
    @api.model
    def _asset_71_values(self, company, year):
        """Lista de ``(activo, valores)`` del 7.1 con importes numéricos."""
        date_from, date_to = self._asset_year_range(year)
        assets = self._asset_book_assets(company, year)
        dep_sums = self._asset_depreciation_sums(assets, date_from, date_to)
        result = []
        for asset in assets:
            children = asset.children_ids.filtered(
                lambda c: c.state in ASSET_BOOK_STATES)
            prior_children = sum(
                c.original_value for c in children
                if (c.acquisition_date or date_from) < date_from)
            year_children = sum(
                c.original_value for c in children
                if date_from <= (c.acquisition_date or date_from) <= date_to)
            initial = additions = improvements = 0.0
            if asset.acquisition_date < date_from:
                initial = asset.original_value + prior_children
            else:
                additions = asset.original_value
                improvements += prior_children
            improvements += year_children

            dep = dep_sums[asset.id]
            retirements = dep_retirements = 0.0
            if asset.disposal_date and date_from <= asset.disposal_date <= date_to:
                # Sale del registro todo lo que entró: valor y depreciación.
                retirements = -(initial + additions + improvements)
                dep_retirements = -(dep['prior'] + dep['year'] + dep['other'])

            historical = initial + additions + improvements + retirements
            dep_historical = (dep['prior'] + dep['year'] + dep_retirements
                              + dep['other'])
            result.append((asset, {
                'code': self._asset_code(asset),
                'catalog': asset.l10n_pe_ple_catalog or '9',
                'asset_type': asset.l10n_pe_asset_type or '',
                'account_code': asset.account_asset_id.code or '',
                'status': asset.l10n_pe_asset_status or '1',
                'name': asset.name or '',
                'brand': asset.l10n_pe_brand or '-',
                'model': asset.l10n_pe_model or '-',
                'plate': asset.l10n_pe_plate or '-',
                'initial': initial,
                'additions': additions,
                'improvements': improvements,
                'retirements': retirements,
                'other_adjust': 0.0,
                'historical_value': historical,
                'inflation_adjust': 0.0,
                'adjusted_value': historical,
                'acquisition_date': asset.acquisition_date,
                'start_date': asset.prorata_date or asset.acquisition_date,
                'method': asset.l10n_pe_depre_method or '9',
                'auth_doc': asset.l10n_pe_depre_auth_doc or '-',
                'rate': asset.l10n_pe_depre_rate,
                'dep_prior': dep['prior'],
                'dep_year': dep['year'],
                'dep_retirements': dep_retirements,
                'dep_other': dep['other'],
                'dep_historical': dep_historical,
                'dep_inflation': 0.0,
                'dep_adjusted': dep_historical,
            }))
        return result

    # ------------------------------------------------------------------
    # TXT — líneas por formato
    # ------------------------------------------------------------------
    @api.model
    def _asset_period(self, year):
        return '%04d0000' % year

    @api.model
    def _asset_71_lines(self, company, year):
        """7.1 — 37 campos por activo."""
        rows = self._asset_71_values(company, year)
        self._asset_require(
            self.env['account.asset'].browse([asset.id for asset, _v in rows]),
            'l10n_pe_asset_type', 'Tipo de activo (T18)')
        amount = self._ple_amount
        lines = []
        for asset, v in rows:
            lines.append([
                self._asset_period(year),                   # 1
                asset.id,                                   # 2 CUO
                'M%d' % asset.id,                           # 3
                self._ple_text(v['catalog'], 1, '9'),       # 4
                v['code'],                                  # 5
                '',                                         # 6 UNSPSC (op)
                '',                                         # 7 (op)
                self._ple_text(v['asset_type'], 1),         # 8
                self._ple_text(v['account_code'], 24),      # 9
                self._ple_text(v['status'], 1, '1'),        # 10
                self._ple_text(v['name'], 40),              # 11
                self._ple_text(v['brand'], 20, '-'),        # 12
                self._ple_text(v['model'], 20, '-'),        # 13
                self._ple_text(v['plate'], 30, '-'),        # 14
                amount(v['initial']),                       # 15
                amount(v['additions']),                     # 16
                amount(v['improvements']),                  # 17
                amount(v['retirements']),                   # 18
                amount(v['other_adjust']),                  # 19
                amount(0.0),                                # 20 reval. voluntaria
                amount(0.0),                                # 21 reval. reorganización
                amount(0.0),                                # 22 otras reval.
                amount(v['inflation_adjust']),              # 23
                self._ple_date(v['acquisition_date']),      # 24
                self._ple_date(v['start_date']),            # 25
                self._ple_text(v['method'], 1, '9'),        # 26
                self._ple_text(v['auth_doc'], 20, '-'),     # 27
                amount(v['rate']),                          # 28
                amount(v['dep_prior']),                     # 29
                amount(v['dep_year']),                      # 30
                amount(v['dep_retirements']),               # 31
                amount(v['dep_other']),                     # 32
                amount(0.0),                                # 33 dep. reval. voluntaria
                amount(0.0),                                # 34 dep. reval. reorg.
                amount(0.0),                                # 35 dep. otras reval.
                amount(v['dep_inflation']),                 # 36
                '1',                                        # 37 estado
            ])
        return lines

    @api.model
    def _asset_73_lines(self, company, year):
        """7.3 — Diferencia de cambio (15 campos)."""
        date_from, date_to = self._asset_year_range(year)
        assets = self._asset_book_assets(
            company, year, [('l10n_pe_fx_currency_id', '!=', False)])
        self._asset_require(assets, 'l10n_pe_fx_amount', 'Valor adquisición en ME')
        self._asset_require(assets, 'l10n_pe_fx_rate', 'TC a fecha de adquisición')
        dep_sums = self._asset_depreciation_sums(assets, date_from, date_to)
        lines = []
        for asset in assets:
            close_rate = self.env['res.currency']._get_conversion_rate(
                asset.l10n_pe_fx_currency_id, company.currency_id, company,
                date_to)
            mn_value = asset.original_value
            fx_adjust = asset.l10n_pe_fx_amount * close_rate - mn_value
            lines.append([
                self._asset_period(year),                          # 1
                asset.id,                                          # 2 CUO
                'M%d' % asset.id,                                  # 3
                self._ple_text(asset.l10n_pe_ple_catalog, 1, '9'), # 4
                self._asset_code(asset),                           # 5
                self._ple_date(asset.acquisition_date),            # 6
                self._ple_amount(asset.l10n_pe_fx_amount),         # 7
                self._ple_rate(asset.l10n_pe_fx_rate),             # 8
                self._ple_amount(mn_value),                        # 9
                self._ple_rate(close_rate),                        # 10
                self._ple_amount(fx_adjust),                       # 11
                self._ple_amount(dep_sums[asset.id]['year']),      # 12
                self._ple_amount(0.0),                             # 13
                self._ple_amount(dep_sums[asset.id]['other']),     # 14
                '1',                                               # 15 estado
            ])
        return lines

    @api.model
    def _asset_74_lines(self, company, year):
        """7.4 — Arrendamiento financiero (11 campos)."""
        assets = self._asset_book_assets(
            company, year, [('l10n_pe_is_leasing', '=', True)])
        self._asset_require(assets, 'l10n_pe_leasing_contract', 'Nº contrato leasing')
        self._asset_require(assets, 'l10n_pe_leasing_date', 'Fecha del contrato')
        lines = []
        for asset in assets:
            lines.append([
                self._asset_period(year),                          # 1
                asset.id,                                          # 2 CUO
                'M%d' % asset.id,                                  # 3
                self._ple_text(asset.l10n_pe_ple_catalog, 1, '9'), # 4
                self._ple_text(asset.l10n_pe_leasing_contract, 20),  # 5
                self._ple_date(asset.l10n_pe_leasing_date),        # 6
                self._asset_code(asset),                           # 7
                self._ple_date(asset.l10n_pe_leasing_start
                               or asset.acquisition_date),         # 8
                asset.l10n_pe_leasing_installments or 0,           # 9
                self._ple_amount(asset.l10n_pe_leasing_total),     # 10
                '1',                                               # 11 estado
            ])
        return lines

    @api.model
    def _asset_lines(self, book_code, company, year):
        builders = {
            '070100': self._asset_71_lines,
            '070300': self._asset_73_lines,
            '070400': self._asset_74_lines,
        }
        return builders[book_code](company, year)
