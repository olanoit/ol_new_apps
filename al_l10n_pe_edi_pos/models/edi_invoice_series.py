# -*- coding: utf-8 -*-
from odoo import api, models


class EdiInvoiceSeries(models.Model):
    _name = 'edi.invoice.series'
    _inherit = ['edi.invoice.series', 'pos.load.mixin']

    @api.model
    def _load_pos_data_fields(self, config):
        return ['name', 'edi_type_code', 'state', 'company_id', 'write_date']

    @api.model
    def _load_pos_data_domain(self, data, config):
        return [('company_id', '=', config.company_id.id),
                ('state', '=', 'publish')]
