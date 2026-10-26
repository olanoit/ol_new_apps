# -*- coding: utf-8 -*-
{
    'name': 'Portal de obra (AL)',
    'summary': 'Portal instalable y sin señal para capataces, contratas y oficina técnica: '
               'avance con fotos, parte diario, cuadrilla y tareo, requerimientos, recepción, '
               'devolución y valorizaciones, sobre servicios JSON versionados.',
    'description': """
Portal de obra
==============
Requerimiento CREVAL v1.0, 4.11. Capataces, contratas y personal de oficina
técnica sin licencia registran desde el celular o la tablet lo que hoy llega
por WhatsApp:

* **Ingreso**: usuario y clave con sesión larga, o el QR de la obra con el
  nombre de la persona y su PIN de 4 dígitos (tres errados bloquean).
* **Aplicación web instalable** (manifiesto y service worker) que trabaja sin
  señal: guarda los datos de la obra y deja cada registro en una cola con sus
  fotos comprimidas; Odoo no duplica un envío repetido y vuelve a validar sus
  reglas al recibirlo.
* **Pantallas**: mis partidas y registrar avance (metrado o %, fotos, GPS,
  re-trabajo), parte diario, cuadrilla y tareo (tablet), requerimientos con
  catálogo de partida, EPP y útiles (con kits), recepción con faltantes,
  devolución al almacén y, para la contrata, sus valorizaciones y pagos.
* **Servicios JSON versionados** (/construction/api/v1): los mismos para una
  aplicación nativa futura.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_planner/static/description/icon.png',
    'version': '4.20261025',
    # LGPL-3 como el planificador del que depende (base_tier_validation es AGPL).
    'license': 'LGPL-3',
    'countries': ['pe'],
    'depends': [
        'al_construction_planner_subcontract',
        'al_construction_material_request',
        'al_construction_attendance',
        'al_construction_planner_crew',
        'stock',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/portal_security.xml',
        'views/portal_app_templates.xml',
        'views/portal_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
