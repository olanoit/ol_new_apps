# -*- coding: utf-8 -*-
{
    'name': 'Gantt de Proyectos — Backend (AL)',
    'summary': 'Aplicación de Gantt interactivo dentro del backend de Odoo, '
               'con menú propio y carga perezosa de la librería.',
    'description': """
Gantt de Proyectos — interfaz de backend
========================================
Aplicación propia (``ir.actions.client`` + menú raíz) que renderiza el Gantt de
``project.task`` con dhtmlxGantt, dentro del webclient.

* **No es una vista Gantt heredada**: es un componente OWL propio que monta la
  librería en su contenedor, sin depender de ``web_gantt`` (Enterprise).
* Toda la lectura pasa por ``project.project.get_gantt_data()``, del módulo
  base: aquí no hay lógica de datos ni de seguridad.
* La librería (627 KB) se carga con ``loadJS``/``loadCSS`` **solo al abrir la
  vista**; no entra en el bundle general del backend.
* Selección de proyectos, zoom (día/semana/mes/trimestre) y avisos de datos
  incompletos (tareas sin fecha, resultado truncado).

Versión 1: solo lectura.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECT/Apps',
    'version': '11.20260818',
    'license': 'LGPL-3',
    'depends': [
        'al_project_gantt_base',
        'web',
    ],
    'data': [
        'views/gantt_action.xml',
        'views/project_project_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Adaptador compartido del módulo base (pequeño). La librería NO se
            # declara aquí a propósito: se carga de forma perezosa al montar.
            'al_project_gantt_base/static/src/js/gantt_adapter.js',
            'al_project_gantt_base/static/src/js/gantt_setup.js',
            'al_project_gantt_base/static/src/js/gantt_filters.js',
            'al_project_gantt_base/static/src/js/gantt_editing.js',
            'al_project_gantt_base/static/src/js/gantt_tools.js',
            'al_project_gantt_base/static/src/js/gantt_lightbox.js',
            'al_project_gantt_base/static/src/scss/gantt_common.scss',
            'al_project_gantt_backend/static/src/**/*',
        ],
    },
    'installable': True,
    'application': True,
}
