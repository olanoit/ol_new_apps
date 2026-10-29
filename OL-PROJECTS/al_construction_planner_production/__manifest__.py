# -*- coding: utf-8 -*-
{
    'name': 'Planificación de obra: orden de fabricación del mueble (AL)',
    'summary': 'Accesorios de armado pedidos desde la orden y presupuestado, requerido y '
               'consumido en la orden y en el planificador.',
    'description': """
Planificación de obra: orden de fabricación del mueble
======================================================
Paquete 1.9. Se instala solo con las aprobaciones en fabricación.

* Accesorios de armado (M19-02): el jefe de producción, o quien él asigne, los
  pide desde la orden sobre lo proyectado de sus módulos (sub etapa Armado)
  con su saldo. Sin cambios van directo a los componentes de la orden; un
  cambio de material o de cantidad va a Oficina Técnica por Aprobaciones,
  con el jefe de proyectos como seguidor. Confirmar la orden sin pedir
  accesorios avisa al jefe de proyectos y a Logística.
* Presupuestado frente a real (M19-05): la orden suma lo consumido a lo
  presupuestado y lo requerido, y el informe del planificador lo reparte por
  módulo, mueble, ambiente, piso, obra y etapa.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_planner_production/static/description/icon.png',
    'version': '6.20261027',
    # LGPL-3 como el planificador del que depende (base_tier_validation es AGPL).
    'license': 'LGPL-3',
    'depends': ['al_construction_planner_approvals_mrp'],
    'data': [
        'data/ir_sequence_data.xml',
        'views/construction_accessory_request_views.xml',
        'views/construction_production_analysis_views.xml',
        'views/mrp_production_views.xml',
        'views/menus.xml',
        'security/ir.access.csv',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': True,
}
