# -*- coding: utf-8 -*-
from odoo import fields, models

APPROVAL_ENGINES = [
    ('tier', 'Validación por niveles'),
    ('approvals', 'Aplicación Aprobaciones'),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Se pasa a Aprobaciones en Ajustes, por compañía: instalar el puente no
    # cambia el flujo de quien ya aprueba por niveles.
    construction_approval_engine = fields.Selection(
        APPROVAL_ENGINES, string='Motor de aprobación', required=True, default='tier',
        help='Dónde se aprueban el plan de recursos y el requerimiento de obra. Lo enviado con '
             'el otro motor termina con su flujo.')
