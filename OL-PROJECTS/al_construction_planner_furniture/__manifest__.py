# -*- coding: utf-8 -*-
{
    'name': 'Planificación de obra: rubro mobiliario (AL)',
    'summary': 'Tipologías de mueble con módulos, piezas, método de unión y lista de materiales, '
               'productos por módulo, receta real y despacho a obra, e importación del maestro, '
               'del ETO y de la proyección de materiales.',
    'description': """
Planificación de obra: rubro mobiliario
=======================================
Puente del planificador de obra (paquete 1.7, M17-07): el núcleo
(al_construction_planner) solo depende de Proyectos, el Gantt de la suite y
las aprobaciones por niveles; cada función que opera en otra aplicación de
Odoo vive en su puente y se activa desde Ajustes.

Tipologías de mueble con módulos, metros lineales y lista de materiales, generar plan desde la tipología e importación del maestro y del ETO.

Paquete 1.8 (M18-15 a M18-20, M17-15, M17-18 a M17-20):

* Modelo del mueble: tipo de mueble (bajo, alto, torre, isla, completo),
  módulo estándar o especial y método de unión propuesto por reglas.
* Catálogo de actividades de contrata con listas de tarifas por familia y
  versiones por obra; las líneas de contrata salen de las piezas del módulo.
* Un producto por módulo con su lista de materiales y lote por departamento;
  envíos de planta a obra.
* Metrado como receta real del mueble, versus con lo planificado y
  autorización de la jefatura sobre el umbral.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_planner_furniture/static/description/icon.png',
    'version': '15.20261029',
    # LGPL-3 como el planificador del que depende (base_tier_validation es AGPL).
    'license': 'LGPL-3',
    'depends': ['al_construction_planner_mrp'],
    'data': [
        'data/furniture_catalog_data.xml',
        'data/module_product_data.xml',
        'wizards/plan_generate_wizard_views.xml',
        'wizards/master_import_wizard_views.xml',
        'wizards/projection_import_wizard_views.xml',
        'views/construction_typology_views.xml',
        'views/real_recipe_views.xml',
        'views/plan_views.xml',
        'views/project_views.xml',
        'views/furniture_catalog_views.xml',
        'views/space_measured_views.xml',
        'views/site_dispatch_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
        'security/ir.access.csv',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
