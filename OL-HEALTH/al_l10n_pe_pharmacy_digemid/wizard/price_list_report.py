# -*- coding: utf-8 -*-
"""Lista de precios por principio activo, de menor a mayor y por DCI en
orden alfabético (Ley 29459, art. 39.3), con el aviso de los productos de
empresas vinculadas (Ley 32033, art. 4; DS 014-2011-SA, art. 32-B)."""
from collections import defaultdict

from odoo import api, models


class ReportPharmacyPriceList(models.AbstractModel):
    _name = 'report.al_l10n_pe_pharmacy_digemid.report_price_list'
    _description = 'Lista de precios por DCI'

    @api.model
    def _get_report_values(self, docids, data=None):
        companies = self.env['res.company'].browse(docids)
        groups = {}
        linked = {}
        for company in companies:
            templates = self.env['product.template'].search([
                ('pharmacy_ok', '=', True), ('sale_ok', '=', True),
                ('pharmacy_composition', '!=', False),
                '|', ('company_id', '=', False), ('company_id', '=', company.id)])
            by_composition = defaultdict(lambda: self.env['product.template'])
            for template in templates:
                by_composition[template.pharmacy_composition] |= template
            groups[company.id] = [
                (composition, by_composition[composition].sorted(lambda t: (t.list_price, t.name)))
                for composition in sorted(by_composition, key=str.lower)]
            linked[company.id] = templates.filtered('pharmacy_linked_company')
        return {'docs': companies, 'groups': groups, 'linked': linked}
