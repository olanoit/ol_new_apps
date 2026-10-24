# -*- coding: utf-8 -*-
"""Paquete 1.11 (M111-19 C y M111-20 A): Logística aprueba el requerimiento
interno de quien no tiene jefe y todos los usuarios internos pueden hacer
requerimientos internos, como en una instalación nueva."""
from odoo import SUPERUSER_ID, api

from odoo.addons.al_construction_material_request.hooks import setup_package_111_options


def migrate(cr, version):
    setup_package_111_options(api.Environment(cr, SUPERUSER_ID, {}))
