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

    # Control de las líneas del plan: los turnos son el comprometido del
    # personal propio (horas aún no registradas).
    _CONTROL_FIELDS = {'start_datetime', 'end_datetime', 'allocated_hours', 'resource_id'}

    def write(self, vals):
        res = super().write(vals)
        if self._CONTROL_FIELDS & set(vals):
            self._construction_sync_allocations()
            self.env['construction.resource.plan.allocation']._refresh_for_documents(
                'slot_id', self)
        return res

    def _construction_sync_allocations(self):
        """Lo pedido del personal propio son las horas de sus turnos: la
        asignación sigue a las horas del turno (en la unidad de la línea si se
        mide en horas)."""
        hour = self.env.ref('uom.product_uom_hour')
        # sudo: quien mueve el turno (Planificación) no edita el plan; solo
        # se actualiza la cantidad de la asignación de su propio turno.
        for allocation_sudo in self.sudo().construction_allocation_ids:
            line = allocation_sudo.plan_line_id
            qty = hour._compute_quantity(allocation_sudo.slot_id.allocated_hours,
                                         line.product_uom_id) if line._is_hour_based() else 0.0
            if line.product_uom_id.compare(qty, allocation_sudo.qty_allocated):
                allocation_sudo.qty_allocated = qty

    def unlink(self):
        # Las asignaciones se borran en cascada en la base: las líneas se
        # leen antes y se actualizan después.
        lines = self.sudo().construction_allocation_ids.plan_line_id
        res = super().unlink()
        lines._refresh_control()
        return res
