# -*- coding: utf-8 -*-
{
    'name': 'Industria: Constructora (AL)',
    'summary': 'Constructora lista para planificar y ejecutar obras: plan de recursos por partidas, requerimientos de obra, compras, contratas, cuadrillas, presupuesto, valorización, aprobaciones y planilla de construcción civil.',
    'description': """
Industria: Constructora
=======================
Constructoras y contratistas generales que planifican por disciplina, subpartida y partida, con contratas y personal de construcción civil.

Paquete de industria al estilo de los de Odoo: instala las aplicaciones y los
módulos de la suite que usa el rubro y deja la base configurada (categorías,
etiquetas, opciones de inventario y la actividad CIIU 4100 de la
compañía). Lo que se configura por compañía está en Ajustes ▸ Usuarios y
compañías ▸ Industrias.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-INDUSTRIES/Apps',
    'icon': '/al_industry_construction/static/description/icon.png',
    'version': '3.20261027',
    # LGPL-3 como el planificador que instala (base_tier_validation es AGPL).
    'license': 'LGPL-3',
    'depends': [
        'al_industry_base',
        'al_construction_planner_purchase',
        'al_construction_planner_subcontract_purchase',
        'al_construction_planner_crew',
        'al_construction_planner_budget',
        'al_construction_planner_sale',
        'al_construction_planner_approvals',
        'al_construction_attendance',
        'al_hr_pe_construction',
    ],
    'data': [
        'data/al_industry_data.xml',
        'data/construction_data.xml',
    ],
    'demo': [
        'demo/construction_demo.xml',
    ],
    'installable': True,
    'application': True,
}
