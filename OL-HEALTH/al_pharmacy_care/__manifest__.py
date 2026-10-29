# -*- coding: utf-8 -*-
{
    'name': 'Farmacia: tratamientos crónicos y recompra (AL)',
    'summary': 'Tratamientos crónicos por paciente: días cubiertos por cada compra (también de '
               'equivalentes), recordatorio de recompra con WhatsApp o correo, adherencia (PDC) y '
               'aviso en la caja al elegir al cliente.',
    'description': """
Farmacia: tratamientos crónicos y recompra
==========================================
Entrega E5 de las mejoras (docs/farmacia/MEJORAS_PROCESOS.md).

* Tratamiento por paciente y medicamento: unidades por día, inicio,
  posología, responsable y estado (activo, en pausa, terminado). Se crea a
  mano o desde una receta.
* Cada compra del paciente en la caja o por pedido de venta, del
  medicamento o de un equivalente intercambiable, suma días cubiertos: fecha
  «cubierto hasta», próxima recompra y días de atraso.
* Recordatorio diario: actividad para el responsable los días antes que
  indique la compañía, mensaje listo para WhatsApp y correo opcional al
  paciente.
* Adherencia: proporción de días cubiertos (PDC) de los últimos 180 días;
  menos de 80 % es no adherente.
* En la caja: al elegir al cliente, aviso de los tratamientos que toca
  reponer y botón para agregarlos al pedido (con la presentación y la receta
  que pida cada producto).
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-HEALTH/Apps',
    'icon': '/al_pharmacy_care/static/description/icon.png',
    'version': '2.20261027',
    'license': 'OPL-1',
    'depends': ['al_pharmacy_prescription', 'al_pharmacy_pos', 'sale'],
    'data': [
        'data/pharmacy_care_data.xml',
        'views/pharmacy_treatment_views.xml',
        'security/ir.access.csv',
    ],
    'demo': ['demo/pharmacy_care_demo.xml'],
    'assets': {
        'point_of_sale._assets_pos': [
            'al_pharmacy_care/static/src/app/**/*',
        ],
        'web.assets_tests': [
            'al_pharmacy_care/static/tests/tours/**/*',
        ],
    },
    'installable': True,
    'application': False,
}
