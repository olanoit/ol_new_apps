# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountAsset(models.Model):
    _inherit = 'account.asset'

    # ----- Identificación SUNAT (formato 7.1, campos 4-14) -----
    l10n_pe_ple_catalog = fields.Char(
        string='Catálogo (T13)', size=1, default='9',
        help='Código del catálogo utilizado, tabla 13 de SUNAT '
             '(9 = catálogo propio). Los formatos 7.3 y 7.4 solo admiten '
             'los valores 3 y 9.')
    l10n_pe_ple_code = fields.Char(
        string='Código del activo (PLE)', size=24, copy=False,
        help='Código único propio del activo fijo (campo 5 del formato 7.1).')
    l10n_pe_asset_type = fields.Char(
        string='Tipo de activo (T18)', size=1,
        help='Código del tipo de activo fijo según la tabla 18 del Anexo 3 '
             'de SUNAT. Obligatorio para el formato 7.1.')
    l10n_pe_asset_status = fields.Char(
        string='Estado del activo (T19)', size=1, default='1',
        help='Estado del activo fijo según la tabla 19 del Anexo 3 de SUNAT.')
    l10n_pe_brand = fields.Char(string='Marca', size=20)
    l10n_pe_model = fields.Char(string='Modelo', size=20)
    l10n_pe_plate = fields.Char(string='Serie / placa', size=30)

    # ----- Depreciación SUNAT (campos 26-28) -----
    l10n_pe_depre_method = fields.Char(
        string='Método depreciación (T20)', size=1,
        compute='_compute_l10n_pe_depre_method', store=True, readonly=False,
        help='Código del método de depreciación según la tabla 20 de SUNAT '
             '(1 = línea recta). Se propone 1 para el método lineal de Odoo '
             'y 9 para el resto; puede corregirse manualmente.')
    l10n_pe_depre_auth_doc = fields.Char(
        string='Doc. autorización cambio de método', size=20,
        help='Nº del documento de autorización del cambio del método de '
             'depreciación (campo 27 del 7.1). «-» si no aplica.')
    l10n_pe_depre_rate = fields.Float(
        string='% depreciación SUNAT', digits=(5, 2),
        compute='_compute_l10n_pe_depre_rate', store=True, readonly=False,
        help='Porcentaje anual de depreciación (campo 28 del 7.1, '
             'obligatorio con método 1). Se propone 100/años de vida útil.')

    # ----- Diferencia de cambio (formato 7.3) -----
    l10n_pe_fx_currency_id = fields.Many2one(
        'res.currency', string='Moneda de adquisición (ME)',
        help='Moneda extranjera de adquisición: el activo se incluirá en el '
             'formato 7.3 (diferencia de cambio).')
    l10n_pe_fx_amount = fields.Float(
        string='Valor adquisición en ME', digits=(14, 2),
        help='Valor de adquisición en moneda extranjera (campo 7 del 7.3).')
    l10n_pe_fx_rate = fields.Float(
        string='TC a fecha de adquisición', digits=(6, 3),
        help='Tipo de cambio a la fecha de adquisición (campo 8 del 7.3).')

    # ----- Arrendamiento financiero (formato 7.4) -----
    l10n_pe_is_leasing = fields.Boolean(
        string='Arrendamiento financiero',
        help='Marcar para incluir el activo en el formato 7.4.')
    l10n_pe_leasing_contract = fields.Char(
        string='Nº contrato leasing', size=20)
    l10n_pe_leasing_date = fields.Date(string='Fecha del contrato')
    l10n_pe_leasing_start = fields.Date(string='Inicio del arrendamiento')
    l10n_pe_leasing_installments = fields.Integer(string='Nº cuotas pactadas')
    l10n_pe_leasing_total = fields.Monetary(
        string='Monto total del contrato', currency_field='currency_id')

    @api.depends('method')
    def _compute_l10n_pe_depre_method(self):
        for asset in self:
            asset.l10n_pe_depre_method = (
                '1' if asset.method == 'linear' else '9')

    @api.depends('method_number', 'method_period')
    def _compute_l10n_pe_depre_rate(self):
        for asset in self:
            years = asset.method_number * (
                1.0 if asset.method_period == '12' else 1.0 / 12.0)
            asset.l10n_pe_depre_rate = 100.0 / years if years else 0.0
