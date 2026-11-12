# -*- coding: utf-8 -*-
from odoo import api, models

G = 'al_construction_planner.group_planner_feature_'


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _construction_moment_moves(self):
        """Menú por momento (CREVAL v1.0, 4.3): la asistencia pasa a la sección
        Personal propio de Ejecución."""
        p = 'al_construction_attendance.'
        q = 'al_construction_planner.'
        return super()._construction_moment_moves() + [
            (p + 'menu_planner_attendance_own', q + 'menu_planner_exec_staff', 20),
            (p + 'menu_planner_progress_no_attendance', q + 'menu_planner_exec_staff', 40),
            (p + 'menu_planner_labor_cost_allocation', q + 'menu_planner_exec_staff', 50),
            # Paquete 1.20, M120-01: el personal de contratas va a Contratas y
            # los dos controles semanales a su sección; la carpeta Asistencia
            # queda vacía y no se muestra.
            (p + 'menu_planner_contractor_workers', q + 'menu_planner_contract_staff', 10),
            (p + 'menu_planner_attendance_contractor', q + 'menu_planner_contract_staff', 20),
            (p + 'menu_planner_installation_board', q + 'menu_planner_exec_control', 10),
            (p + 'menu_planner_labor_weekly_control', q + 'menu_planner_exec_control', 20),
            # M120-02: las sedes en «Portal y asistencia».
            (p + 'menu_planner_sites', q + 'menu_planner_config_portal', 10),
        ]

    @api.model
    def _construction_moment_names(self):
        p = 'al_construction_attendance.'
        return dict(super()._construction_moment_names(), **{
            p + 'menu_planner_attendance_own': self.env._('Asistencia de personal propio'),
            p + 'menu_planner_attendance_contractor': self.env._('Asistencia de contratas'),
        })

    @api.model
    def _construction_feature_menus(self):
        """Paquete 1.20, M120-07: el control semanal de instalación (mobiliario)."""
        p = 'al_construction_attendance.'
        return super()._construction_feature_menus() + [
            (p + 'menu_planner_installation_board', G + 'installation_board'),
        ]
