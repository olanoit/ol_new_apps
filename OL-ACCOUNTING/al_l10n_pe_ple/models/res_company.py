# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_ple_simplified = fields.Boolean(
        string='Libros PLE simplificados',
        help='Habilita la generación de los formatos simplificados del PLE '
             '(5.2/5.4 Diario Simplificado, 8.3 Compras Simplificado y '
             '14.2 Ventas Simplificado). Son EXCLUYENTES con los formatos '
             'completos (5.1/5.3, 8.1, 14.1): solo aplican a contribuyentes '
             'autorizados a llevar contabilidad simplificada.')

    def _get_company_root_delegated_field_names(self):
        # El régimen contable es del RUC: las sucursales usan el de su raíz.
        return super()._get_company_root_delegated_field_names() + [
            'l10n_pe_ple_simplified',
        ]


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_ple_simplified = fields.Boolean(
        related='company_id.l10n_pe_ple_simplified', readonly=False)
