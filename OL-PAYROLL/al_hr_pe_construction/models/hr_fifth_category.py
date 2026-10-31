# -*- coding: utf-8 -*-
"""Renta de 5ta categoría de los obreros de construcción civil.

El motor de la quinta (al_hr_pe_benefits) liquida un lote mensual con las
reglas de la estructura BASE. El obrero cobra por semana, en varios lotes,
y con otra estructura: sin esto no se le retenía nunca.

* **Renta del mes**: la regla ``ROAQ`` de la estructura de construcción,
  sumada en todas las boletas semanales del mes.
* **Proyección**: la regla ``PIAQ`` de la última boleta del mes; no se
  proyectan gratificaciones aparte porque ya van en cada planilla (GRAT).
* **Retención**: se exporta a la **última boleta semanal del mes**, que la
  descuenta con su propia regla ``QUINTA``.
"""
from odoo import models


def _construction_structure(env):
    return env.ref('al_hr_pe_construction.construction_structure',
                   raise_if_not_found=False)


def construction_month_slips(env, company, start, end, employees=None):
    """Boletas de construcción civil no anuladas con cierre en el mes."""
    structure = _construction_structure(env)
    if not structure or not start:
        return env['hr.payslip']
    domain = [
        ('struct_id', '=', structure.id),
        ('company_id', '=', company.id),
        ('state', '!=', 'cancel'),
        ('date_to', '>=', start),
        ('date_to', '<=', end),
    ]
    if employees is not None:
        domain.append(('employee_id', 'in', employees.ids))
    return env['hr.payslip'].search(domain)


class HrMainParameter(models.Model):
    _inherit = 'hr.main.parameter'

    def _l10n_pe_fifth_rules(self, kind):
        """Las reglas de la quinta configuradas son de BASE: se suman las
        equivalentes de la estructura de construcción (sin extraordinaria:
        todo lo que paga la boleta semanal es ordinario)."""
        rules = super()._l10n_pe_fifth_rules(kind)
        xmlid = {'ordinary': 'al_hr_pe_construction.rule_ROAQ',
                 'projection': 'al_hr_pe_construction.rule_PIAQ'}.get(kind)
        if xmlid:
            rules |= self.env.ref(xmlid, raise_if_not_found=False) \
                or self.env['hr.salary.rule']
        return rules


class HrFifthCategory(models.Model):
    _inherit = 'hr.fifth.category'

    def _l10n_pe_fifth_slips(self):
        """Añade a los obreros con boletas semanales en el mes.

        Sus boletas viven en un lote por semana; la quinta del lote
        mensual —o la de cualquiera de las semanas— los liquida a todos, y
        la retención va a la última boleta semanal del mes. Un obrero que
        ya está en otra quinta del mes no se repite.
        """
        result = super()._l10n_pe_fifth_slips()
        start, end = self._l10n_pe_month_range()
        slips = construction_month_slips(
            self.env, self.company_id, start, end)
        if not slips:
            return result
        Line = self.env['hr.fifth.category.line']
        Excluded = self.env['hr.fifth.category.line.excluidos']
        others = [('slip_id', 'in', slips.ids),
                  ('fifth_category_id', '!=', self.id)]
        taken = (Line.search(others).employee_id
                 | Excluded.search(others).employee_id)
        for employee in slips.employee_id - taken:
            result[employee] = slips.filtered(
                lambda slip: slip.employee_id == employee
            ).sorted(lambda slip: (slip.date_to, slip.id))[-1]
        return result


class HrFifthCategoryLine(models.Model):
    _inherit = 'hr.fifth.category.line'

    def _l10n_pe_month_slips(self):
        """Todas las boletas semanales del mes del obrero, de cualquier
        lote: la renta del mes es la suma de sus semanas."""
        slips = super()._l10n_pe_month_slips()
        structure = _construction_structure(self.env)
        if not structure or self.slip_id.struct_id != structure:
            return slips
        fifth = self.fifth_category_id
        if fifth:
            start, end = fifth._l10n_pe_month_range()
        else:
            start = self.slip_id.date_to.replace(day=1)
            end = self.slip_id.date_to
        month = construction_month_slips(
            self.env, self.slip_id.company_id, start, end,
            employees=self.employee_id)
        return month or slips
