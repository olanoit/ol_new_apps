# -*- coding: utf-8 -*-
from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _construction_moment_moves(self):
        """Menú por momento (CREVAL v1.0, 4.3): la asistencia pasa a la sección
        Personal propio de Ejecución."""
        p = 'al_construction_attendance.'
        return super()._construction_moment_moves() + [
            (p + 'menu_planner_attendance_own', 'al_construction_planner.menu_planner_exec_staff', 20),
            (p + 'menu_planner_contractor_workers', 'al_construction_planner.menu_planner_exec_staff', 30),
            (p + 'menu_planner_attendance_contractor', 'al_construction_planner.menu_planner_exec_staff', 35),
            (p + 'menu_planner_progress_no_attendance', 'al_construction_planner.menu_planner_exec_staff', 40),
            (p + 'menu_planner_labor_cost_allocation', 'al_construction_planner.menu_planner_exec_staff', 50),
        ]

    @api.model
    def _construction_moment_names(self):
        p = 'al_construction_attendance.'
        return dict(super()._construction_moment_names(), **{
            p + 'menu_planner_attendance_own': self.env._('Asistencia de personal propio'),
            p + 'menu_planner_attendance_contractor': self.env._('Asistencia de contratas'),
        })
