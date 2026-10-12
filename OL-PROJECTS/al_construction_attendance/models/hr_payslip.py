# -*- coding: utf-8 -*-
"""Costo de personal por sede (v1.5, fase 18): la planilla repartida por obra
lleva además la etapa de la sede y la partida MODF, para que el costo quede
por obra › etapa › partida como el presupuesto del plan."""
from odoo import models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _l10n_pe_tareaje_distribution(self):
        distribution = super()._l10n_pe_tareaje_distribution()
        if not distribution:
            return distribution
        return self._l10n_pe_site_cost_keys(distribution)

    def _l10n_pe_default_cost_distribution(self):
        return self._l10n_pe_site_cost_keys(super()._l10n_pe_default_cost_distribution() or {})

    def _l10n_pe_site_cost_keys(self, distribution):
        """Cada clave que es solo la cuenta de una sede suma la etapa de la
        sede y la partida MODF de la compañía."""
        self.ensure_one()
        Site = self.env['l10n_pe.hr.construction.site'].sudo()
        modf = self.company_id.construction_labor_cost_account_id
        result = {}
        for key, percent in distribution.items():
            ids = [int(part) for part in str(key).split(',') if part]
            if len(ids) == 1:
                # sudo: la sede es un maestro de RR. HH.; solo se lee su etapa.
                site = Site.search([('analytic_account_id', '=', ids[0])], limit=1)
                extra = (site.default_stage_account_id | modf).ids if site else []
                if extra:
                    key = ','.join(str(i) for i in sorted(set(ids + extra)))
            result[key] = result.get(key, 0.0) + percent
        return result
