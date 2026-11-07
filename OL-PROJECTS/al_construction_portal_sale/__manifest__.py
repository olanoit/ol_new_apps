# -*- coding: utf-8 -*-
{
    'name': 'Portal de obra: cambios del cliente (AL)',
    'summary': 'El residente registra en el portal de obra el cambio que pide el cliente, con '
               'fotos y su firma en la pantalla, y el cliente recibe la constancia en PDF.',
    'description': """
Portal de obra: cambios del cliente
===================================
Paquete 6, CR-53. Puente entre el portal de obra y los cambios de obra del
puente de Ventas del planificador (se instala solo con los dos):

* el residente registra en el celular el cambio que pide el representante del
  cliente: descripción, partidas afectadas o partida nueva, adicional o
  deductivo, metrado estimado, fotos, nombre y cargo de quien lo pide y su
  firma con el dedo;
* se crea el cambio de obra en «Borrador», con el residente como autor; lo
  valoriza y lo lleva a aprobación el coordinador en el escritorio, como hoy;
* al llegar a Odoo, el contacto del cliente de la obra recibe la constancia en
  PDF con la descripción, las fotos y la firma.

Funciona sin señal: el cambio entra a la cola del portal y la constancia sale
cuando llega a Odoo.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_portal_sale/static/description/icon.png',
    'version': '1.20261107',
    # LGPL-3 como el portal y el puente de Ventas del planificador.
    'license': 'LGPL-3',
    'countries': ['pe'],
    'depends': ['al_construction_portal', 'al_construction_planner_sale', 'al_report_base'],
    'data': [
        'report/change_record_report.xml',
        'views/construction_change_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
}
