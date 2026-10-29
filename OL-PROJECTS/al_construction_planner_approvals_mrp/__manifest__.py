# -*- coding: utf-8 -*-
{
    'name': 'Planificación de obra: aprobaciones en fabricación (AL)',
    'summary': 'Exceso de la orden de fabricación frente a lo presupuestado: el jefe de '
               'producción lo aprueba dentro de su margen y, por encima, va a Aprobaciones.',
    'description': """
Planificación de obra: aprobaciones en fabricación
=================================================
Paquete 1.9, M19-04. Se instala solo con las aprobaciones del planificador y
el puente de producción.

* La orden de fabricación compara, por material, lo presupuestado en el plan
  (sus ambientes, etapas de fabricación) con lo requerido en sus
  componentes: diferencia en cantidad, en % y en soles, y el total.
* Dentro del margen del jefe de producción (Ajustes), él aprueba el exceso en
  la orden: queda quién, cuándo y el motivo.
* Por encima, «Solicitar aprobación» crea la solicitud en Aprobaciones según
  la tabla de rutas (documento «Orden de fabricación», tramos en escalera).
* Con un exceso pendiente la orden no empieza: no registra producción, no
  consume ni inicia órdenes de trabajo.
* Toda diferencia queda registrada en la orden; lo que sale por debajo de lo
  presupuestado no pide aprobación.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_planner_approvals_mrp/static/description/icon.png',
    'version': '8.20261027',
    # LGPL-3 como el planificador del que depende (base_tier_validation es AGPL).
    'license': 'LGPL-3',
    'depends': ['al_construction_planner_approvals', 'al_construction_planner_mrp'],
    'data': [
        'security/production_groups.xml',
        'wizards/excess_approve_wizard_views.xml',
        'views/mrp_production_views.xml',
        'views/res_config_settings_views.xml',
        'security/ir.access.csv',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
}
