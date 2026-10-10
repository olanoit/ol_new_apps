# -*- coding: utf-8 -*-
"""Saldo del plan para los documentos de abastecimiento (fase 4): cuánto
queda por pedir en un grupo de líneas, cómo se reparte un pedido entre ellas
y si lo excede."""
from datetime import date

from odoo import models

from .construction_resource_plan_allocation import distribute


class ConstructionResourcePlanLine(models.Model):
    _inherit = 'construction.resource.plan.line'

    def _product_uom(self):
        self.ensure_one()
        return self.product_id.uom_id or self.product_uom_id

    def _qty_to_product_uom(self, qty):
        self.ensure_one()
        uom = self._product_uom()
        if self.product_uom_id and uom and self.product_uom_id != uom:
            return self.product_uom_id._compute_quantity(qty, uom, rounding_method='HALF-UP')
        return qty

    def _qty_from_product_uom(self, qty):
        self.ensure_one()
        uom = self._product_uom()
        if self.product_uom_id and uom and self.product_uom_id != uom:
            return uom._compute_quantity(qty, self.product_uom_id, rounding_method='HALF-UP')
        return qty

    def _supply_sorted(self):
        return self.sorted(lambda l: (l.date_needed or date.max, l.id))

    def _supply_balance(self, own_allocations=None):
        """{línea: saldo por pedir en la UdM del producto} sin contar las
        asignaciones del propio documento (``own_allocations``)."""
        own_allocations = own_allocations or self.env['construction.resource.plan.allocation']
        result = {}
        for line in self:
            own = own_allocations.filtered(lambda a: a.plan_line_id == line)
            requested = line.qty_requested - sum(a._get_requested_qty() for a in own)
            result[line] = line._qty_to_product_uom(line.qty_planned - requested)
        return result

    def _supply_split(self, qty, own_allocations=None, balance=None):
        """Reparte ``qty`` (UdM del producto) entre las líneas por fecha de
        necesidad hasta su saldo; el exceso va a la última. Devuelve
        {línea: cantidad en la unidad de la línea}."""
        ordered = self._supply_sorted()
        if balance is None:
            balance = ordered._supply_balance(own_allocations)
        shares = distribute(qty, [(line, balance[line]) for line in ordered])
        return {line: line._qty_from_product_uom(share) for line, share in shares.items()}

    def _supply_check(self, qty, own_allocations=None):
        """(saldo, tolerancia, exceso) de pedir ``qty`` contra estas líneas, en
        la UdM del producto. Sin líneas, todo es exceso (fuera de plan)."""
        balance = sum(self._supply_balance(own_allocations).values())
        tolerance = sum(line._qty_to_product_uom(line._get_tolerance_qty()) for line in self)
        return balance, tolerance, qty - balance
