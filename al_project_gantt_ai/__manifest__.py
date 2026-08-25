# -*- coding: utf-8 -*-
{
    'name': 'Gantt de Proyectos — Asistente IA (AL)',
    'summary': 'Panel de chat opcional para consultar el diagrama de Gantt y '
               'recibir propuestas de cambio que el usuario revisa y aplica.',
    'description': """
Gantt de Proyectos — asistente de IA
====================================
Añade un panel de chat lateral al diagrama de Gantt del backend. Permite
**preguntar** sobre el cronograma que se está viendo y recibir **propuestas de
cambio** concretas (mover fechas, reasignar, renombrar, ajustar avance).

Principios de diseño
--------------------
* **La IA nunca escribe en Odoo.** El modelo solo devuelve propuestas; el
  usuario las revisa una a una y las aplica con un botón. La escritura pasa por
  ``project.project.apply_gantt_changes()``, es decir por los permisos reales de
  cada tarea, igual que si se arrastrara la barra a mano.
* **Solo se envía lo que se ve, resumido.** Nombre, fechas, estado, avance,
  dependencias y (opcional) personas asignadas de las tareas visibles. Nunca
  descripciones, adjuntos, mensajes ni datos de clientes.
* **Proveedor configurable**: Anthropic (Claude), OpenAI o DeepSeek, con enlace
  directo a donde cada uno crea su clave. La clave se guarda como parámetro del
  sistema y **nunca** llega al navegador.
* **Opcional de verdad**: sin clave configurada, el botón del panel no aparece y
  el Gantt funciona exactamente igual que sin este módulo.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECT/Apps',
    'version': '2.20260817',
    'license': 'OPL-1',
    'depends': [
        'al_project_gantt_backend',
    ],
    'data': [
        'views/res_config_settings_views.xml',
        'views/gantt_ai_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'al_project_gantt_ai/static/src/js/**/*',
            'al_project_gantt_ai/static/src/xml/**/*',
            'al_project_gantt_ai/static/src/scss/**/*',
        ],
    },
    'external_dependencies': {
        # `requests` viene con Odoo; se declara por claridad, no añade nada nuevo.
        'python': [],
    },
    'installable': True,
    'application': False,
}
