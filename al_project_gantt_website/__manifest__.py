# -*- coding: utf-8 -*-
{
    'name': 'Gantt de Proyectos — Website (AL)',
    'summary': 'Página de Gantt en el sitio web, restringida a usuarios '
               'internos autenticados.',
    'description': """
Gantt de Proyectos — interfaz de sitio web
==========================================
Publica el mismo diagrama de Gantt en una página del sitio web (``/gantt``),
pensada para consultarla fuera del backend (pantallas de obra, enlaces
compartidos internamente, tableros).

**Solo usuarios internos.** No es una página pública ni de portal:

* ``auth='user'`` obliga a estar autenticado;
* el controlador rechaza con **403** a los usuarios compartidos
  (portal/público, ``user.share``) y a quien no tenga el grupo del Gantt;
* el endpoint de datos aplica los mismos controles antes de delegar en el
  módulo base.

No reimplementa lógica: los datos salen de ``project.project.get_gantt_data()``
y el render usa el adaptador y la configuración compartidos del módulo base.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECT/Apps',
    'version': '10.20260818',
    'license': 'LGPL-3',
    'depends': [
        'al_project_gantt_base',
        'website',
    ],
    'data': [
        'views/gantt_templates.xml',
        'views/website_menu.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            # Código compartido del módulo base. La librería NO se declara
            # aquí: se carga de forma perezosa al abrir la página.
            'al_project_gantt_base/static/src/js/gantt_adapter.js',
            'al_project_gantt_base/static/src/js/gantt_setup.js',
            'al_project_gantt_base/static/src/js/gantt_filters.js',
            'al_project_gantt_base/static/src/js/gantt_editing.js',
            'al_project_gantt_base/static/src/js/gantt_tools.js',
            'al_project_gantt_base/static/src/js/gantt_lightbox.js',
            'al_project_gantt_base/static/src/scss/gantt_common.scss',
            'al_project_gantt_website/static/src/**/*',
        ],
    },
    'installable': True,
    'application': False,
}
