# -*- coding: utf-8 -*-
{
    'name': 'Planificación de obra: producción y requerimiento de obra (AL)',
    'summary': 'Planchas enteras y retazo en el despacho del requerimiento, despacho a la '
               'preproducción de la planta y reposición a planta.',
    'description': """
Planificación de obra: producción y requerimiento de obra
=========================================================
Puente entre la producción del planificador (al_construction_planner_mrp) y
el requerimiento de obra (paquete 1.11). Se instala solo cuando están los dos.

* M111-22: el despacho de una línea indivisible guarda la necesidad y el
  redondeo, se cubre con retazo y la línea cuenta la fracción cubierta; el
  despacho a la preproducción de una planta usa el tipo «Elegir componentes»
  del almacén.
* M111-23: «Pedir reposición a planta»: la obra pide la pieza, la planta la
  fabrica en su tipo de reposición y la despacha a la obra, sin que quien
  pide entre a Fabricación.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_planner/static/description/icon.png',
    'version': '3.20261026',
    # LGPL-3 como el planificador del que depende (base_tier_validation es AGPL).
    'license': 'LGPL-3',
    'depends': ['al_construction_planner_mrp', 'al_construction_planner_purchase'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/replacement_data.xml',
        'views/replacement_request_views.xml',
        'views/construction_material_request_views.xml',
        'views/mrp_production_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
}
