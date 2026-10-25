# -*- coding: utf-8 -*-
"""Tipo de despacho según el destino (paquete 1.11, M111-22): lo que el
requerimiento lleva a la preproducción de una planta sale con el tipo
«Elegir componentes» de su almacén (pbm_type_id), como el material que Odoo
lleva a producción; lo que va a la obra, con «Despacho a obra»."""
from odoo import models


class ConstructionMaterialRequest(models.Model):
    _inherit = 'construction.material.request'

    def _construction_preproduction_type(self, destination):
        """«Elegir componentes» del almacén de la preproducción, si está activo."""
        if not destination.construction_preproduction:
            return self.env['stock.picking.type']
        # Quien procesa (Logística) puede no leer la configuración del almacén
        # de la planta: solo se toma su tipo.
        picking_type = destination.sudo().warehouse_id.pbm_type_id
        return picking_type.sudo(False) if picking_type.active else self.env['stock.picking.type']

    def _get_dispatch_picking_type_for(self, source, destination):
        return self._construction_preproduction_type(destination) \
            or super()._get_dispatch_picking_type_for(source, destination)

    def _get_dispatch_picking_types(self):
        types = super()._get_dispatch_picking_types()
        destinations = self.location_dest_id | self.line_ids.location_dest_id
        for destination in destinations:
            types |= self._construction_preproduction_type(destination)
        return types
