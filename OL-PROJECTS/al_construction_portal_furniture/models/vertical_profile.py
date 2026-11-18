# -*- coding: utf-8 -*-
"""Funciones de campo de mobiliario del portal de obra (paquete 1.22, etapa
2). Son funciones del perfil de vertical, con el mecanismo de M122-01: el
portal las lee del perfil de la obra (o del de su compañía) y cada servicio
las vuelve a comprobar. No llevan grupo ni menú: solo existen en el portal."""
from odoo import api, fields, models

#: Campos del perfil que agrega este puente.
PORTAL_FIELDS = ('portal_module_reception', 'portal_replacement', 'portal_measure',
                 'portal_stage_progress', 'portal_contractor_units')


class ConstructionVerticalProfile(models.Model):
    _inherit = 'construction.vertical.profile'

    portal_module_reception = fields.Boolean(
        string='Portal: recibir módulos por departamento',
        help='En «Recepción» del portal de obra, el despacho de módulos se recibe por '
             'departamento y por módulo.')
    portal_replacement = fields.Boolean(
        string='Portal: pedir reposición',
        help='La obra pide desde el portal la reposición a planta de un módulo, con foto.')
    portal_measure = fields.Boolean(
        string='Portal: marcar medido',
        help='El capataz o la oficina técnica marcan desde el portal los ambientes medidos.')
    portal_stage_progress = fields.Boolean(
        string='Portal: avance por sub etapa',
        help='El avance de instalación se reporta por ambiente y sub etapa del departamento, '
             'con un solo envío.')
    portal_contractor_units = fields.Boolean(
        string='Portal: avance de la contrata por departamento',
        help='La contrata ve por departamento el driver de cada actividad y lo reportado, '
             'validado y liquidado.')

    @api.model
    def _portal_furniture_enable_defaults(self):
        """Enciende las cinco funciones en el perfil Mobiliario. Lo llaman la
        instalación del puente y sus datos (una sola vez: después manda lo
        que elija cada cliente en el perfil)."""
        profile = self.env.ref('al_construction_planner.profile_furniture',
                               raise_if_not_found=False)
        if profile:
            profile.write({name: True for name in PORTAL_FIELDS})
        return True
