# -*- coding: utf-8 -*-
from odoo import fields, models


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    # El turno nativo no tiene tarea (especificación): la cuadrilla (W-06,
    # fase 5) lo enlaza con el nivel de la obra y su línea del plan.
    construction_task_id = fields.Many2one(
        'project.task', string='Tarea de obra', index='btree_not_null', check_company=True)
    construction_plan_line_id = fields.Many2one(
        'construction.resource.plan.line', string='Línea del plan', index='btree_not_null',
        check_company=True)
    construction_allocation_ids = fields.One2many(
        'construction.resource.plan.allocation', 'slot_id', string='Asignaciones del plan')
