# -*- coding: utf-8 -*-
"""Versión 18: tasas del SPP de 2026.

Las afiliaciones globales se cargan con ``noupdate``. Aquí se actualizan la
prima de seguros (1,70 % → 1,37 %) y la remuneración máxima asegurable
(11 981,55 → 12 672,65) solo donde siguen con el valor de origen, para no
pisar lo que la compañía haya ajustado a mano.
"""
from odoo import SUPERUSER_ID, api

XMLIDS = ('membership_AFP_HABIAT', 'membership_AFP_INTEGRA',
          'membership_AFP_PRIMA', 'membership_AFP_PROFUTURO')


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid in XMLIDS:
        membership = env.ref('al_hr_pe.%s' % xmlid, raise_if_not_found=False)
        if not membership:
            continue
        vals = {}
        if round(membership.prima_insurance, 2) == 1.70:
            vals['prima_insurance'] = 1.37
        if round(membership.insurable_remuneration, 2) == 11981.55:
            vals['insurable_remuneration'] = 12672.65
        if vals:
            membership.write(vals)
