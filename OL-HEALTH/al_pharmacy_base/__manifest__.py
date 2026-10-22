# -*- coding: utf-8 -*-
{
    'name': 'Farmacia: maestro farmacéutico (AL)',
    'summary': 'Maestro farmacéutico: principio activo y equivalentes, registro sanitario, '
               'condición de venta, presentaciones con precio propio, turnos del químico '
               'farmacéutico y libro de ocurrencias.',
    'description': """
Farmacia: maestro farmacéutico
==============================
Núcleo de la suite de farmacias y boticas (docs/farmacia/PLAN_FARMACIA.md).

* Producto farmacéutico: composición (principio activo DCI, concentración),
  forma farmacéutica y vía, equivalentes intercambiables, registro sanitario
  con su vencimiento, titular y laboratorio, condición de venta, tipo
  (genérico en DCI, genérico de marca, innovador), empresa vinculada,
  cadena de frío, ubicación en estante y ficha clínica.
* Presentaciones de venta (caja, blíster, frasco) con precio propio; su
  unidad «Caja x 100» se crea sola y se agrega a los empaques del producto.
* Establecimiento: función y colegiatura de los empleados, director técnico
  por local, turnos de químicos farmacéuticos y libro de ocurrencias que
  solo admite asientos nuevos (Manual BPOF, RM 554-2022/MINSA).
* Ajustes por compañía: venta sin receta (bloquear o avisar), sin Q.F. en
  turno (avisar o bloquear) y días de aviso de vencimientos.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-HEALTH/Apps',
    'icon': '/al_pharmacy_base/static/description/icon.png',
    'version': '4.20261022',
    'license': 'OPL-1',
    'depends': ['product', 'uom', 'stock', 'product_expiry', 'hr', 'mail', 'al_report_base'],
    'data': [
        'security/pharmacy_groups.xml',
        'security/ir.model.access.csv',
        'security/pharmacy_security.xml',
        'data/pharmacy_data.xml',
        'views/pharmacy_catalog_views.xml',
        'views/product_template_views.xml',
        'views/pharmacy_establishment_views.xml',
        'views/res_config_settings_views.xml',
        'report/pharmacy_logbook_report.xml',
    ],
    'demo': ['demo/pharmacy_demo.xml'],
    'installable': True,
    'application': False,
}
