# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    l10n_pe_boleta_journal_id = fields.Many2one(
        'account.journal', string='Diario de boletas',
        check_company=True,
        domain="[('type', '=', 'sale'), ('l10n_latam_use_documents', '=', True)]",
        help='Diario (serie B###) donde se crean las boletas de venta '
             'electrónicas emitidas desde este TPV.')
    l10n_pe_factura_journal_id = fields.Many2one(
        'account.journal', string='Diario de facturas',
        check_company=True,
        domain="[('type', '=', 'sale'), ('l10n_latam_use_documents', '=', True)]",
        help='Diario (serie F###) donde se crean las facturas electrónicas '
             'emitidas desde este TPV.')
    # Bandera única que consume el frontend: el flujo CPE se activa solo
    # cuando ambos diarios están configurados.
    l10n_pe_cpe_enabled = fields.Boolean(
        string='CPE en el TPV', compute='_compute_l10n_pe_cpe_enabled')
    # Series CPE publicadas de cada diario, para el selector de serie en
    # caja (pos.config carga todos sus campos al frontend).
    l10n_pe_boleta_series_ids = fields.Many2many(
        'edi.invoice.series', compute='_compute_l10n_pe_series',
        string='Series de boletas')
    l10n_pe_factura_series_ids = fields.Many2many(
        'edi.invoice.series', compute='_compute_l10n_pe_series',
        string='Series de facturas')

    @api.depends('l10n_pe_boleta_journal_id.edi_series_ids',
                 'l10n_pe_factura_journal_id.edi_series_ids')
    def _compute_l10n_pe_series(self):
        for config in self:
            config.l10n_pe_boleta_series_ids = (
                config.l10n_pe_boleta_journal_id.edi_series_ids.filtered(
                    lambda s: s.state == 'publish'))
            config.l10n_pe_factura_series_ids = (
                config.l10n_pe_factura_journal_id.edi_series_ids.filtered(
                    lambda s: s.state == 'publish'))

    @api.depends('l10n_pe_boleta_journal_id', 'l10n_pe_factura_journal_id',
                 'company_id.country_code')
    def _compute_l10n_pe_cpe_enabled(self):
        for config in self:
            config.l10n_pe_cpe_enabled = bool(
                config.company_id.country_code == 'PE'
                and config.l10n_pe_boleta_journal_id
                and config.l10n_pe_factura_journal_id)
