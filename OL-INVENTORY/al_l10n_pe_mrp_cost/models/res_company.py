# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_mrp_labor_account_id = fields.Many2one(
        'account.account', string='Contrapartida del ajuste de mano de obra',
        check_company=True,
        help='Cuenta que se abona al cargar a las órdenes la diferencia entre el '
             'costo hora real del mes y el usado (PCGE: 71 Variación de la '
             'producción almacenada).')
