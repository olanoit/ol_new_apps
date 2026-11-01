# -*- coding: utf-8 -*-
"""Paquete 1.16, etapa 4, bloque 4c (segunda parte): lo que falta de CR-22 g
en la hoja de presupuesto.

INSUMOS y APU llevan el nombre primero y el código al final; APU_DETALLE
elige la receta por nombre («nombre · código»), calcula su código y pinta una
banda de color por receta. El recorrido calcula las fórmulas en el navegador:
el costo unitario de la receta y el de una partida que la usa.
"""
import base64
import json

from odoo import Command
from odoo.tests import HttpCase, tagged

from ..models.project_project import BUDGET_LAYOUT


@tagged('post_install', '-at_install')
class TestPackage116Stage4cBudgetTour(HttpCase):

    def test_budget_formulas_with_code_last(self):
        env = self.env
        hour = env.ref('uom.product_uom_hour')
        m2 = env.ref('uom.product_uom_square_meter')
        unit = env.ref('uom.product_uom_unit')
        stage = env['construction.stage'].create({
            'name': 'Muros CR-22 g (test)', 'code': 'cr22g_test_stage', 'sequence': 930})
        mason = env['construction.labor.activity'].create({
            'code': 'CR22G-OP', 'name': 'Operario CR-22 g (test)', 'stage': stage.code,
            'default_price': 25.0, 'uom_id': hour.id})
        brick = env['product.product'].create({
            'name': 'Ladrillo CR-22 g (test)', 'default_code': 'CR22G-LAD',
            'standard_price': 37.13, 'uom_id': m2.id})
        tools = env['product.product'].create({
            'name': 'Herramientas CR-22 g (test)', 'default_code': 'CR22G-HER'})
        project = env['project.project'].create({
            'name': 'Obra CR-22 g (test)', 'is_construction_site': True})
        env['construction.execution.template'].create({
            'code': 'CR22G-R01', 'name': 'Muro CR-22 g (test)', 'uom_id': m2.id,
            'project_id': project.id,
            'line_ids': [
                Command.create({'resource_type': 'labor', 'activity_id': mason.id,
                                'stage': stage.code, 'product_uom_id': hour.id,
                                'qty': 0.2584, 'price_unit': 25.0}),
                Command.create({'resource_type': 'material', 'product_id': brick.id,
                                'stage': stage.code, 'product_uom_id': m2.id,
                                'qty': 1.0, 'price_unit': 37.13}),
                Command.create({'resource_type': 'equipment', 'product_id': tools.id,
                                'stage': stage.code, 'product_uom_id': unit.id,
                                'calc_method': 'pct_labor', 'calc_pct': 3.0}),
            ]})
        data = env['project.project']._construction_budget_spreadsheet_data(None, project)
        env['documents.document'].create({
            'name': 'Presupuesto con el código al final (test)',
            'mimetype': 'application/o-spreadsheet', 'handler': 'spreadsheet',
            'datas': base64.b64encode(json.dumps(data).encode()),
            'construction_project_id': project.id, 'construction_sheet_kind': 'budget',
            'construction_sheet_layout': BUDGET_LAYOUT,
        })
        self.start_tour('/odoo', 'al_construction_budget_formulas', login='admin')
