# -*- coding: utf-8 -*-
"""Ayudas que nombran la orden de fabricación (paquete 3 de CREVAL, CR-26).

El núcleo habla de producción en taller: una obra de construcción sin
Fabricación no ve órdenes de fabricación ni plantas. Con este puente
instalado, las ayudas vuelven a nombrar la orden de fabricación."""
from odoo import fields, models


class ConstructionStage(models.Model):
    _inherit = 'construction.stage'

    kind = fields.Selection(
        help='Fabricación: la etapa se hace en taller y habilita la orden de fabricación. '
             'Ejecución en campo: se asigna a una contrata o a una cuadrilla. Control: '
             'pruebas, protocolos o entregas sin recurso propio.')
    production_consumption = fields.Boolean(
        string='Consume en la orden de fabricación',
        help='Los materiales de esta etapa salen con la orden de fabricación aunque la etapa '
             'se ejecute en campo (armado de mobiliario).')


class ConstructionResourceType(models.Model):
    _inherit = 'construction.resource.type'

    behavior = fields.Selection(
        help='Lo que hace el planificador con la línea: material y equipo se compran o salen '
             'del almacén, la contrata se asigna y se liquida por avance, el personal propio '
             'se asigna en cuadrillas y la producción sale de una orden de fabricación.')


class ConstructionResourcePlanLine(models.Model):
    _inherit = 'construction.resource.plan.line'

    qty_requested = fields.Float(
        help='Material: requerimientos de obra y órdenes de fabricación. Contrata: OC de '
             'servicio. Personal propio: horas de turnos.')
    qty_dispatched = fields.Float(
        help='Llegado a la obra y entregado a la planta para las órdenes de fabricación.')
    qty_consumed = fields.Float(
        help='Consumo en obra y componentes consumidos de las órdenes de fabricación.')
