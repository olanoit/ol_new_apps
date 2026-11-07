# -*- coding: utf-8 -*-
"""El residente del portal valida y rechaza avances de su obra (paquete 6,
CR-49) sin el grupo interno «Ejecución: valida». El servicio del portal
comprueba antes que la persona es residente de la obra y llama a los mismos
métodos del escritorio con este contexto; el autor queda como su usuario."""
from odoo import models


class ConstructionTaskProgress(models.Model):
    _inherit = 'construction.task.progress'

    def _check_validator(self):
        projects = self.env.context.get('construction_portal_resident_projects')
        if projects and set(self.project_id.ids) <= set(projects):
            # sudo: el miembro del portal no lee el personal del portal.
            residents = self.env['construction.portal.member'].sudo().search([
                ('user_id', '=', self.env.uid), ('role', '=', 'resident'),
                ('active', '=', True), ('project_id', 'in', self.project_id.ids)])
            if set(residents.project_id.ids) == set(self.project_id.ids):
                return
        return super()._check_validator()
