# -*- coding: utf-8 -*-
"""Marcar las unidades de un contrato (v1.5, M15-05): todas, pisos pares o
impares, las de unos agrupadores (torres A y C) o una lista."""
import re

from odoo import fields, models


class ConstructionContractUnitWizard(models.TransientModel):
    _name = 'construction.contract.unit.wizard'
    _description = 'Marcar unidades del contrato'

    contract_id = fields.Many2one('construction.contract', string='Contrato', required=True)
    project_id = fields.Many2one(related='contract_id.project_id', string='Obra')
    mode = fields.Selection(
        [('all', 'Todas las unidades'), ('even', 'Pisos pares'), ('odd', 'Pisos impares'),
         ('groups', 'De unos agrupadores'), ('list', 'Una lista')],
        string='Marcar', required=True, default='all')
    group_ids = fields.Many2many(
        'project.task', 'construction_contract_unit_wizard_group_rel', string='Agrupadores',
        domain="[('project_id', '=', project_id), ('construction_level', 'in', ('group', 'floor'))]",
        help='Torres, etapas o pisos: se marcan todas las unidades que tienen debajo.')
    task_ids = fields.Many2many(
        'project.task', 'construction_contract_unit_wizard_task_rel', string='Unidades',
        domain="[('project_id', '=', project_id), ('construction_level', '=', 'apartment')]")
    replace = fields.Boolean(
        string='Reemplazar las marcadas', default=True,
        help='Sin marcar: se suman a las que ya tiene el contrato.')

    @staticmethod
    def _floor_number(floor):
        """Número del piso por su nombre: «Piso 05» → 5, «P-12» → 12."""
        numbers = re.findall(r'\d+', floor.name or '')
        return int(numbers[-1]) if numbers else None

    def _selected_units(self):
        self.ensure_one()
        Task = self.env['project.task']
        units = Task.search([('project_id', '=', self.project_id.id),
                             ('construction_level', '=', 'apartment')])
        if self.mode in ('even', 'odd'):
            parity = 0 if self.mode == 'even' else 1
            return units.filtered(
                lambda u: self._floor_number(u.construction_floor_task_id) is not None
                and self._floor_number(u.construction_floor_task_id) % 2 == parity)
        if self.mode == 'groups':
            return Task.search([('id', 'child_of', self.group_ids.ids),
                                ('construction_level', '=', 'apartment')])
        if self.mode == 'list':
            return self.task_ids
        return units

    def action_apply(self):
        self.ensure_one()
        units = self._selected_units()
        if not self.replace:
            units |= self.contract_id.task_ids
        self.contract_id.task_ids = units
        return {'type': 'ir.actions.act_window_close'}
