# -*- coding: utf-8 -*-
"""Paquete 1.10, M110-01: «Accesorios a pedido desde la orden» reemplaza la
etapa ``assembly`` escrita en el código. Se marca en esa etapa para que
«Pedir accesorios» (M19-02) siga igual en las bases que ya lo usan."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['construction.stage']._construction_mark_assembly_accessories()
