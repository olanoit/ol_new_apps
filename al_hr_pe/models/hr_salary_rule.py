# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

from .l10n_pe_rule_formulas import (
    L10N_PE_AUDIT_RULES, L10N_PE_EXTRA_HOURS_TYPES)

_logger = logging.getLogger(__name__)


def _normalize(code):
    return '\n'.join(line.rstrip() for line in (code or '').strip().splitlines())


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    # Código del concepto en la planilla electrónica (PLAME): lo consumen
    # los exportadores .rem. Sin company_id: las reglas son globales y sus
    # cuentas contables ya son company_dependent en v19 (hr_payroll_account).
    sunat_code = fields.Char(
        string='Código SUNAT (PLAME)',
        help='Código del concepto remunerativo en la tabla 22 de la '
             'planilla electrónica.')

    @api.model
    def _l10n_pe_sync_formulas(self):
        """Lleva las reglas PE (``noupdate``) a la fórmula vigente.

        Solo reescribe la regla si su fórmula coincide con una de las
        entregadas antes; si fue retocada a mano, la deja y avisa.
        """
        for xmlid, (old_codes, new_code) in L10N_PE_AUDIT_RULES.items():
            rule = self.env.ref('al_hr_pe.%s' % xmlid, raise_if_not_found=False)
            if not rule:
                continue
            if isinstance(old_codes, str):
                old_codes = (old_codes,)
            current = _normalize(rule.amount_python_compute)
            if current == _normalize(new_code):
                continue
            if current not in {_normalize(code) for code in old_codes}:
                _logger.warning(
                    'al_hr_pe: la regla %s tiene una fórmula modificada a '
                    'mano; no se actualiza. Revísela con la versión del '
                    'módulo.', xmlid)
                continue
            rule.amount_python_compute = new_code
            _logger.info('al_hr_pe: fórmula de la regla %s actualizada.', xmlid)
        for xmlid in L10N_PE_EXTRA_HOURS_TYPES:
            work_entry_type = self.env.ref(
                'al_hr_pe.%s' % xmlid, raise_if_not_found=False)
            if work_entry_type and not work_entry_type.is_extra_hours:
                work_entry_type.is_extra_hours = True
        return True
