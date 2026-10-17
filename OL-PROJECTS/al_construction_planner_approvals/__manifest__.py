# -*- coding: utf-8 -*-
{
    'name': 'Planificación de obra: aprobaciones (AL)',
    'summary': 'Plan de recursos y requerimiento de obra aprobados en la aplicación Aprobaciones, '
               'con tabla de rutas por tramos y aprobadores por grupo.',
    'description': """
Planificación de obra: aprobaciones
===================================
Paquete 1.9, M19-07: las aprobaciones del planificador pasan de la validación
por niveles (OCA) a la aplicación Aprobaciones de Odoo, con lo que a esta le
falta para el flujo de obra:

* documento de origen en la solicitud y botón inteligente en los dos sentidos;
* solicitud creada desde el documento, con sus líneas (material,
  presupuestado, pedido, diferencia, % y soles, tipo de cambio);
* tabla de rutas: tipo de documento, tipo de cambio y tramo de porcentaje o
  monto, con su tipo de aprobación, aprobadores y seguidores; los tramos van
  en escalera (cada tramo inferior aprueba antes);
* aprobadores por usuario o por grupo, con «basta uno» o «todos» por tramo;
* aprobar o rechazar desde el documento, y el resultado vuelve a él.

El motor se elige por compañía en Ajustes. Lo que se envió con la validación
por niveles termina con ese flujo.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_planner/static/description/icon.png',
    'version': '1.20261017',
    # LGPL-3 como el planificador del que depende (base_tier_validation es AGPL).
    'license': 'LGPL-3',
    'depends': ['al_construction_planner_purchase', 'approvals'],
    'data': [
        'security/approval_groups.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'wizards/approval_refuse_wizard_views.xml',
        'views/construction_approval_route_views.xml',
        'views/approval_request_views.xml',
        'views/plan_views.xml',
        'views/material_request_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
