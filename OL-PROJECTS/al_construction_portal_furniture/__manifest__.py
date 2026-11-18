# -*- coding: utf-8 -*-
{
    'name': 'Portal de obra: funciones de campo de mobiliario (AL)',
    'summary': 'En el portal de obra, por departamento: recepción de módulos, pedido de '
               'reposición a planta, ambiente medido, avance por sub etapa y avance de la '
               'contrata con su driver.',
    'description': """
Portal de obra: funciones de campo de mobiliario
================================================
Paquete 1.22, etapa 2 (M122-05 a M122-09). Puente entre el portal de obra, el
puente de mobiliario del planificador y la reposición a planta (se instala
solo con los tres). Cada función es una función del perfil de vertical de la
obra: el perfil que no la usa no la ve.

* **Ficha del departamento**: desde «Avance», la etapa actual de cada
  ambiente (la misma del escritorio) y las funciones activas con sus
  contadores.
* **Recepción de módulos por departamento**: el despacho de módulos se recibe
  por departamento y por módulo (rótulo del ETO, tipología y lote): llegó, no
  llegó o llegó dañado con foto. Se valida con lo que llegó; lo que no llegó
  queda en la entrega parcial.
* **Pedir reposición**: ambiente, módulo, cantidad, motivo, qué pasó y foto;
  crea la reposición a planta en borrador.
* **Marcar medido**: uno o varios ambientes en un envío, con fotos o croquis.
* **Avance por sub etapa**: una fila por ambiente y una columna por sub etapa
  de instalación; un envío y una foto registran el saldo de cada línea del
  plan con las reglas del avance de siempre.
* **Avance de la contrata**: por departamento, el driver de cada actividad y
  lo reportado, validado y liquidado; «Esta semana» con lo que pasa a la
  liquidación.

Funciona sin señal, como el resto del portal: cada registro entra a la cola
con su identificador y Odoo no lo duplica si el envío se repite.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_portal_furniture/static/description/icon.png',
    'version': '2.20261117',
    # LGPL-3 como el portal y el planificador de los que depende.
    'license': 'LGPL-3',
    'countries': ['pe'],
    'depends': [
        'al_construction_portal',
        'al_construction_planner_furniture',
        'al_construction_planner_mrp_request',
    ],
    'data': [
        'data/vertical_profile_data.xml',
        'views/vertical_profile_views.xml',
        'views/portal_app_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
    'post_init_hook': 'post_init_hook',
}
