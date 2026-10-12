# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class AlPeDemo(models.AbstractModel):
    _inherit = 'al.pe.demo'

    @api.model
    def _load_demo_monthly_tax(self):
        """Régimen general desde el 1 de enero, coeficientes de ejemplo y el
        PDT 621 de los dos últimos meses cerrados, calculado con los
        movimientos de la compañía demo."""
        company = self._demo_company()
        if not company:
            return
        env = self._demo_env(company)
        today = fields.Date.context_today(self)
        root = company.root_id
        self._demo_record('al_l10n_pe_monthly_tax.demo_regime', env['l10n_pe.tax.regime'], {
            'company_id': root.id, 'regime': 'general', 'date_from': today.replace(month=1, day=1),
            'note': 'Régimen General (demostración)'})
        if not root.l10n_pe_income_coefficient:
            root.write({'l10n_pe_income_coefficient': 0.0185, 'l10n_pe_income_coefficient_jan_feb': 0.0150})
        for months_back in (2, 1):
            period = today.replace(day=1) - relativedelta(months=months_back)
            xmlid = 'al_l10n_pe_monthly_tax.demo_monthly_tax_%s' % months_back
            if self._demo_ref(xmlid):
                continue
            record = env['l10n_pe.monthly.tax'].search([
                ('company_id', '=', company.id), ('year', '=', period.year), ('month', '=', str(period.month))])
            if not record:
                record = env['l10n_pe.monthly.tax'].create({'year': period.year, 'month': str(period.month)})
                self._demo_xmlid(xmlid, record)
            record.action_compute()
