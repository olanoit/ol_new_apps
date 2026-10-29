# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Nombre del documento con que se identifica el contacto (p. ej. el
    # representante legal en boletas y certificados). Odoo 20 lo deduce de
    # sus identificadores; antes era l10n_latam_identification_type_id.name.
    l10n_pe_document_label = fields.Char(
        string='Tipo de documento', compute='_compute_l10n_pe_document_label')

    @api.depends('vat', 'additional_identifiers', 'country_id')
    def _compute_l10n_pe_document_label(self):
        for partner in self:
            vals = partner._get_preferred_legal_entity_identifier_vals()
            partner.l10n_pe_document_label = vals.get('label') or (
                'RUC' if partner.l10n_pe_sunat_id_code == '6' else '')
