# -*- coding: utf-8 -*-
"""La plantilla de impresión por defecto en Perú es la boleta legal."""
from odoo import api, models


class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'

    @api.model
    def _get_default_report_id(self):
        """Estructuras nuevas de una compañía peruana → boleta D.S. 001-98-TR.

        Las que ya existan o apunten a una plantilla no peruana se
        redirigen igualmente al imprimir (``hr.payslip._get_pdf_reports``);
        esto solo evita que el campo muestre una plantilla que nunca se
        va a usar.
        """
        if self.env.company.country_id.code == 'PE':
            boleta = self._l10n_pe_boleta_report()
            if boleta:
                return boleta
        return super()._get_default_report_id()

    @api.model
    def _l10n_pe_boleta_report(self):
        return self.env.ref('al_hr_pe_reports.action_report_boleta_pago',
                            raise_if_not_found=False)

    @api.model
    def _l10n_pe_sync_boleta_report(self):
        """Pone la boleta en las estructuras peruanas que aún apuntan a la
        plantilla genérica de Odoo.

        Se invoca desde un ``<function>`` de datos, que sí corre en cada
        actualización del módulo — un ``<record>`` con ``noupdate`` no
        habría tocado nunca las estructuras ya existentes. Es idempotente
        y respeta cualquier plantilla que el cliente haya elegido.
        """
        boleta = self._l10n_pe_boleta_report()
        peru = self.env.ref('base.pe', raise_if_not_found=False)
        if not boleta or not peru:
            return False
        generic = self.env.ref('hr_payroll.action_report_payslip',
                               raise_if_not_found=False)
        structures = self.with_context(active_test=False).search([
            ('country_id', '=', peru.id),
        ]).filtered(lambda s: not s.report_id or s.report_id == generic)
        if structures:
            structures.report_id = boleta
        return True
