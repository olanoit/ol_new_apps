# -*- coding: utf-8 -*-
{
    'name': 'Industria: Mobiliario a medida (AL)',
    'summary': 'Fábrica de muebles a medida para obras: tipologías con módulos y piezas, lista de materiales, órdenes de fabricación, metrado, despacho e instalación por torre, piso y departamento.',
    'description': """
Industria: Mobiliario a medida
==============================
Contratas de mobiliario que fabrican e instalan cocinas, closets y muebles de baño en proyectos inmobiliarios.

Paquete de industria al estilo de los de Odoo: instala las aplicaciones y los
módulos de la suite que usa el rubro y deja la base configurada (categorías,
etiquetas, opciones de inventario y la actividad CIIU 3100 de la
compañía). Lo que se configura por compañía está en Ajustes ▸ Usuarios y
compañías ▸ Industrias.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-INDUSTRIES/Apps',
    'icon': '/al_industry_furniture/static/description/icon.png',
    'version': '1.20261017',
    # LGPL-3 como el planificador que instala (base_tier_validation es AGPL).
    'license': 'LGPL-3',
    'depends': [
        'al_industry_base',
        'al_construction_planner_suite',
    ],
    'data': [
        'data/al_industry_data.xml',
        'data/furniture_data.xml',
    ],
    'demo': [
        'demo/furniture_demo.xml',
    ],
    'installable': True,
    'application': True,
}
