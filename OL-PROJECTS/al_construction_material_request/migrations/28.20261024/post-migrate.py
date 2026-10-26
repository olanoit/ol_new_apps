# -*- coding: utf-8 -*-
"""CREVAL, 7.4: las compañías que ya existían siguen aprobando al enviar el
requerimiento de obra al que no le aplica ninguna regla (como hasta ahora);
«Pasar al jefe de la obra» se elige en Ajustes."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['res.company'].search([]).write({'construction_site_request_without_rule': 'approve'})
