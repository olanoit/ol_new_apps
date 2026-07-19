# -*- coding: utf-8 -*-
{
    'name': 'PE - Detracciones SPOT (AL)',
    'summary': 'Detracciones SUNAT (SPOT): catálogo 54 administrable con '
               'porcentajes y montos mínimos, cálculo automático en '
               'facturas, depósito/constancia y enlace con el PLE 8.1.',
    'description': """
Detracciones — Sistema de Pago de Obligaciones Tributarias (SPOT)
=================================================================
Completa el soporte nativo de ``l10n_pe_edi`` (que emite el XML UBL con el
bloque «Detraccion» a partir del % del producto) con la capa funcional que
falta:

* **Catálogo 54 administrable** (``l10n_pe.detraction.type``): porcentaje y
  monto mínimo por código, con sincronización a los campos nativos del
  producto (``l10n_pe_withhold_code`` / ``l10n_pe_withhold_percentage``)
  que usa el XML.
* **Cálculo automático en la factura** (ventas y compras): detecta el
  código dominante (mayor %), verifica el monto mínimo (S/ 700 por defecto,
  configurable por código), calcula la detracción redondeada a soles
  enteros (regla SUNAT) y el neto a cobrar/pagar.
* **Tipo de operación EDI automático**: al publicar una factura de venta
  afecta, fija ``1001`` si no se eligió un valor 100x.
* **Depósito y constancia**: wizard que registra el pago de la detracción
  (compras: depósito propio al Banco de la Nación; ventas: cobro de la
  detracción depositada por el cliente) y llena la constancia
  (``l10n_pe_detraction_number/date`` de ``l10n_pe_reports``) que alimenta
  los campos 32-33 del PLE 8.1.

Análisis del módulo v18 ``al_l10n_pe_edi_detraction`` (ce18): se adopta su
catálogo (corrigiendo los porcentajes de los códigos 027/030/040 al 4 %
oficial) y se descarta el cronograma de pagos con re-balanceo manual de
asientos por su complejidad y riesgo contable.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-ACCOUNT/Apps',
    'version': '1.20260719',
    'license': 'LGPL-3',
    'depends': [
        'al_account_base',
        'l10n_pe_edi',
        'l10n_pe_reports',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/detraction_type_data.xml',
        'views/detraction_type_views.xml',
        'views/product_views.xml',
        'views/account_move_views.xml',
        'wizards/detraction_deposit_wizard_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
}
