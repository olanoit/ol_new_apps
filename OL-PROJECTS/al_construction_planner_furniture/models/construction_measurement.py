# -*- coding: utf-8 -*-
"""Metrado del ambiente en mobiliario (v1.6, M16-03): ML de mueble bajo, ML de
mueble alto y módulos frente a la tipología."""
from odoo import fields, models


class ConstructionMeasurement(models.Model):
    _inherit = 'construction.measurement'

    def _planned_driver_qty(self):
        """Sin metrado del nivel, los ML de la tipología del ambiente y la
        cantidad de sus módulos."""
        planned = super()._planned_driver_qty()
        space = self.task_id
        if planned or space.construction_execution_template_id:
            return planned
        typology = space.construction_typology_id
        modules = self.env['project.task'].search_count([
            ('construction_space_task_id', '=', space.id), ('construction_level', '=', 'module')])
        return {'ml_low': typology.ml_low, 'ml_high': typology.ml_high, 'units': modules}

    def _driver_lines(self, plan, driver):
        """Las líneas de contrata y personal propio del ambiente que dependen del
        driver (por módulo o por ML de su grupo)."""
        if driver not in ('ml_low', 'ml_high', 'units'):
            return super()._driver_lines(plan, driver)
        lines = self.env['construction.resource.plan.line'].search([
            ('plan_id', '=', plan.id), ('space_task_id', '=', self.task_id.id),
            ('resource_type', 'in', ('contract', 'labor')), ('activity_id', '!=', False)])
        if driver == 'units':
            return lines.filtered(lambda l: l.activity_id.module_level)
        group = 'low' if driver == 'ml_low' else 'high'
        return lines.filtered(lambda l: l.activity_id.ml_based and l.activity_id.ml_group == group)


class ConstructionMeasurementLine(models.Model):
    _inherit = 'construction.measurement.line'

    driver = fields.Selection(selection_add=[
        ('ml_low', 'ML de mueble bajo'),
        ('ml_high', 'ML de mueble alto'),
        ('units', 'Módulos'),
    ], ondelete={'ml_low': 'cascade', 'ml_high': 'cascade', 'units': 'cascade'})
