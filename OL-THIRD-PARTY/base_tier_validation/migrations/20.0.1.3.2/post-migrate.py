# -*- coding: utf-8 -*-
"""Odoo 20: el ícono del tipo de actividad es un nombre de Material Symbols.

El dato va en noupdate: se corrige el «fa-bell» de las bases ya instaladas
(si alguien lo cambió a mano, se respeta)."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    activity_type = env.ref(
        'base_tier_validation.mail_act_tier_validation_reminder',
        raise_if_not_found=False)
    if activity_type and activity_type.icon == 'fa-bell':
        activity_type.icon = 'notifications'
