# -*- coding: utf-8 -*-
"""«Ambiente medido» desde el portal de obra (paquete 1.22, M122-07).

El escritorio exige el grupo interno de personal de obra
(``_construction_check_supervisor``). El servicio del portal comprueba antes
que la persona es capataz u oficina técnica de la obra y llama al mismo
asistente con una marca del servidor; aquí se vuelve a comprobar que la
persona está en el portal de la obra de cada ambiente."""
from odoo import models

#: Marca del servidor (se compara por identidad): un contexto con el mismo
#: nombre enviado por el cliente no vale.
PORTAL_MEASURE = object()


class ProjectTask(models.Model):
    _inherit = 'project.task'

    def _construction_check_supervisor(self):
        if self and self.env.context.get('construction_portal_measure') is PORTAL_MEASURE:
            # sudo: la persona del portal no lee el personal del portal.
            members_sudo = self.env['construction.portal.member'].sudo().search([
                ('user_id', '=', self.env.uid), ('active', '=', True),
                ('role', '!=', 'contractor'), ('project_id', 'in', self.project_id.ids)])
            if set(members_sudo.project_id.ids) == set(self.project_id.ids):
                return
        return super()._construction_check_supervisor()
