# -*- coding: utf-8 -*-
{
    'name': 'Gantt de Proyectos — Base (AL)',
    'summary': 'Capa de datos, mapeo de campos, seguridad y librería Gantt '
               'compartidas por las interfaces de Gantt (backend y website).',
    'description': """
Gantt de Proyectos — Módulo base
================================
Módulo *sin interfaz de usuario*: contiene todo lo que comparten las dos UIs de
la suite (``al_project_gantt_backend`` y ``al_project_gantt_website``).

* **Capa de datos única** (``al.gantt.data``, expuesta como
  ``project.project.get_gantt_data()``): devuelve proyectos, tareas,
  dependencias e hitos ya normalizados, en un formato **neutral** respecto de la
  librería de renderizado. Es el único punto de acceso a datos: ninguna UI
  consulta el ORM por su cuenta.
* **Mapeo de campos configurable** (``al.gantt.field.map``): detecta si la
  instancia tiene fechas de planificación (``planned_date_begin``, que aporta
  ``project_enterprise``) o solo ``date_deadline``, y permite sobreescribir la
  detección con el parámetro de sistema ``al_gantt.field_map`` (JSON).
* **Colores por estado configurables** (``al.gantt.state.color``), por compañía
  o globales — nada de colores incrustados en el código.
* **Seguridad centralizada**: grupos «Usuario/Administrador de Gantt», ACL y
  reglas de registro de los modelos propios. La visibilidad de proyectos y
  tareas se apoya en las reglas nativas de ``project`` (se lee **sin**
  ``sudo()``), en lugar de duplicarlas.
* **Librería dhtmlxGantt 10.0.1 (MIT)** vendorizada en ``static/lib/`` y
  **adaptador JS** compartido que traduce el formato neutral al de la librería.
  El base no declara la librería en ningún *bundle*: cada UI la carga de forma
  perezosa al montar su vista.

Versión 1: solo lectura. Los puntos de escritura están definidos en el contrato
(``editable``) pero desactivados.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECT/Apps',
    'version': '13.20260818',
    'license': 'LGPL-3',
    'depends': [
        'project',
    ],
    'data': [
        'security/gantt_groups.xml',
        'security/ir.model.access.csv',
        'security/gantt_rules.xml',
        'data/gantt_state_color_data.xml',
        'report/gantt_report.xml',
        'report/gantt_report_templates.xml',
        'views/gantt_state_color_views.xml',
    ],
    'installable': True,
    'application': False,
}
