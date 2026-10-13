# -*- coding: utf-8 -*-
{
    'name': 'Sedes, marcación y costo de personal de obra (AL)',
    'summary': 'Sedes de obra con ubicación y horario, quiosco de marcación para personal '
               'propio y de contratas, asistencia diaria y costo de la planilla por obra, '
               'etapa y partida.',
    'description': """
Sedes, marcación y costo de personal de obra
============================================
Une el planificador de obra con la sede de obra de la planilla (v1.5, fases 17
y 18):

* **Sede con ubicación**: coordenadas, radio, hora límite de ingreso y etapa
  por defecto (obra → instalación, planta → producción); cada obra y cada área
  es una sede.
* **Quiosco de la sede**: una página para la tablet de la obra donde el
  personal propio y el de las contratas marca ingreso y salida con su
  documento o PIN, sin usuario; valida la hora límite y la distancia de la
  tablet a la sede.
* **Personal de contratas**: no entra a la planilla ni al T-Registro; su
  marcación avisa si el SCTR está vencido.
* **Marcación propia**: distancia, fuera de rango y fuera de hora calculados
  desde la sede.
* **Asistencia diaria** de la obra y avances de contratas sin asistencia ese
  día (para revisión).
* **Cierre de costo de personal** (P-29): cada mes, horas de marcación por
  sede por el costo por hora del trabajador, contra lo planificado de
  personal propio; al publicarlo crea los apuntes analíticos con la obra, la
  etapa de la sede y MODF.
* **Costo de personal por sede**: la distribución analítica de la planilla
  lleva, además de la cuenta de la obra, la etapa de la sede y la partida de
  mano de obra fija (MODF), y se contrasta con el presupuesto de la obra.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_planner/static/description/icon.png',
    'version': '2.20261013',
    # LGPL-3 como el planificador del que depende (base_tier_validation es AGPL).
    'license': 'LGPL-3',
    'countries': ['pe'],
    'depends': ['al_construction_planner', 'al_hr_pe_construction', 'hr_attendance',
                'hr_hourly_cost'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'views/construction_site_views.xml',
        'views/contractor_views.xml',
        'views/hr_attendance_views.xml',
        'views/kiosk_templates.xml',
        'views/portal_templates.xml',
        'views/res_config_settings_views.xml',
        'views/labor_cost_allocation_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
}
