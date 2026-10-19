# -*- coding: utf-8 -*-
"""Orden hija con el plan (paquete 1.10, M110-04).

En Odoo 19 cada orden tiene su grupo de fabricación. El componente de la
madre lleva ese grupo a los valores de abastecimiento, cada regla lo pasa a
los movimientos del traslado y así llega a la regla de fabricación de la
planta anterior (el corte). Con él se encuentra la madre y la hija hereda su
plan y sus ambientes. El enlace madre-hija nativo no sirve aquí: Odoo lo
escribe después de confirmar la hija (``_post_run_manufacture``)."""
from odoo import Command, api, models


class StockRule(models.Model):
    _inherit = 'stock.rule'

    @api.model
    def _run_manufacture(self, procurements):
        # La hija se confirma dentro de la confirmación de la madre: sin
        # asistente de exceso ni error que la cancele.
        return super(StockRule, self.with_context(
            construction_from_procurement=True))._run_manufacture(procurements)

    def _prepare_mo_vals(self, product_id, product_qty, product_uom, location_dest_id, name,
                         origin, company_id, values, bom):
        mo_values = super()._prepare_mo_vals(
            product_id, product_qty, product_uom, location_dest_id, name, origin, company_id,
            values, bom)
        group_id = values.get('production_group_id')
        if group_id:
            # El abastecimiento corre sin los permisos de quien confirma: solo
            # se lee la madre para copiar su plan y sus ambientes.
            group_sudo = self.env['mrp.production.group'].sudo().browse(group_id)
            parents = group_sudo.production_ids.filtered('construction_plan_id')
            if len(parents) == 1:
                # Los módulos no se heredan: se producen en la última etapa.
                mo_values.update({
                    'construction_plan_id': parents.construction_plan_id.id,
                    'construction_space_task_ids': [
                        Command.set(parents.construction_space_task_ids.ids)],
                    'construction_parent_id': parents.id,
                })
        return mo_values
