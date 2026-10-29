from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_wh_cost = fields.Boolean(related='company_id.l10n_pe_wh_cost', readonly=False)
    l10n_pe_stock_lock_date = fields.Date(related='company_id.l10n_pe_stock_lock_date')
