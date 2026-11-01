# -*- coding: utf-8 -*-
"""Subsidios EsSalud de los obreros de construcción civil.

El histórico del subsidio (``al_hr_pe_benefits``) solo leía boletas de la
estructura BASE: un obrero con un año de boletas semanales salía con
base 0 y subsidio 0. Aquí se suma la estructura del régimen con su base
afecta a EsSalud (TREM); las semanas se agrupan en el mes en que
terminan, que es el de su PLAME.
"""
from odoo import api, models

#: Columna del histórico en que se muestra cada concepto del régimen (solo
#: informativo: el total del mes es TREM).
SUBSIDY_BUCKETS = {
    'JOR': 'wage', 'DSO': 'wage', 'BUC': 'wage',
    'VAC10': 'vacation',
    'HE60': 'extra_hours', 'HE100': 'extra_hours',
}


class HrSubsidies(models.Model):
    _inherit = 'hr.subsidies'

    @api.model
    def _l10n_pe_subsidy_structures(self):
        structures = super()._l10n_pe_subsidy_structures()
        structure = self.env.ref(
            'al_hr_pe_construction.construction_structure',
            raise_if_not_found=False)
        if structure:
            structures[structure] = 'TREM'
        return structures

    def _l10n_pe_subsidy_bucket(self, line, param):
        if line.slip_id.struct_id == self.env.ref(
                'al_hr_pe_construction.construction_structure',
                raise_if_not_found=False):
            return SUBSIDY_BUCKETS.get(line.code, False)
        return super()._l10n_pe_subsidy_bucket(line, param)
