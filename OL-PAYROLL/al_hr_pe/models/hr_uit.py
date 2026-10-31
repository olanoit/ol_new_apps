# -*- coding: utf-8 -*-
"""UIT y RMV sobre los parámetros de reglas nativos de Odoo 20.

Son valores nacionales con vigencia (D.S. del MEF y del MTPE): viven en
``hr.rule.parameter`` (códigos ``l10n_pe_uit`` y ``l10n_pe_rmv``), con su
historial de versiones nativo, y las fórmulas pueden leerlos con
``payslip._rule_parameter``. Aquí quedan solo los accesos con las reglas
peruanas: la UIT es la del año (error si no está cargada) y la RMV la vigente a
la fecha (0 si no hay).
"""
from datetime import date

from odoo import api, models
from odoo.exceptions import UserError

UIT_CODE = 'l10n_pe_uit'
RMV_CODE = 'l10n_pe_rmv'


class HrRuleParameter(models.Model):
    _inherit = 'hr.rule.parameter'

    @api.model
    def _l10n_pe_get_uit(self, year):
        """UIT del año; error claro si ese año no está cargado (la renta de
        5ta no puede calcular con la UIT de otro año)."""
        value = self.env['hr.rule.parameter.value'].sudo().search([
            ('code', '=', UIT_CODE),
            ('date_from', '>=', date(year, 1, 1)), ('date_from', '<=', date(year, 12, 31)),
        ], limit=1)
        if not value:
            raise UserError(self.env._(
                'No está registrada la UIT del año %(year)s (Nómina ▸ Configuración ▸ '
                'Perú ▸ UIT).', year=year))
        return float(self._get_parameter_from_code(UIT_CODE, value.date_from))

    @api.model
    def _l10n_pe_get_rmv(self, on_date):
        """RMV vigente a ``on_date``; 0 si la tabla no la cubre."""
        return float(self.sudo()._get_parameter_from_code(
            RMV_CODE, on_date, raise_if_not_found=False) or 0.0)


class HrRuleParameterValue(models.Model):
    _inherit = 'hr.rule.parameter.value'

    @api.model_create_multi
    def create(self, vals_list):
        values = super().create(vals_list)
        values._l10n_pe_refresh_rmv_snapshot()
        return values

    def write(self, vals):
        res = super().write(vals)
        self._l10n_pe_refresh_rmv_snapshot()
        return res

    def _l10n_pe_refresh_rmv_snapshot(self):
        """Una RMV nueva (D.S. cargado después de crear el lote) llega a
        las boletas PE en borrador del periodo que cubre; las cerradas
        conservan la suya."""
        rmv = self.filtered(lambda value: value.code == RMV_CODE)
        if not rmv:
            return
        slips = self.env['hr.payslip'].sudo().search([
            ('state', '=', 'draft'),
            ('struct_id.country_id.code', '=', 'PE'),
            ('date_to', '>=', min(rmv.mapped('date_from'))),
        ])
        if slips:
            self.env.add_to_compute(slips._fields['rmv'], slips)
