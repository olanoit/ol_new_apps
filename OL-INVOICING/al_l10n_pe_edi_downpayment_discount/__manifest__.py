# -*- coding: utf-8 -*-
{
    'name': 'PE - Anticipos y descuentos globales en el CPE (AL)',
    'summary': 'Corrige el XML UBL 2.1 de SUNAT con anticipos y descuentos globales: '
               'anticipos exonerados e inafectos, un anticipo por comprobante, '
               'descuentos de partes no gravadas y notas de crédito sin bloqueos.',
    'description': """
Anticipos y descuentos globales en el comprobante electrónico
=============================================================
La localización de Odoo 19 (``l10n_pe_edi``) ya emite ``PrepaidPayment``, el
cargo ``04`` y el descuento global ``02``. Este módulo corrige lo que SUNAT
rechaza, verificado contra las reglas de validación oficiales (26.08.2026):

* **Anticipos exonerados e inafectos** con su código (``05``/``06``), no ``02``.
* **Un anticipo, una referencia**: una ``AdditionalDocumentReference`` y un
  ``PrepaidPayment`` por comprobante de anticipo, con su tipo (factura/boleta).
* **Descuento global de partes exoneradas o inafectas** repartido entre sus
  ítems como descuento de línea ``00``.
* **Notas de crédito y débito** de facturas con anticipos, descuento global o
  descuento de línea: se publican y el XML informa el valor neto por ítem.
* **Ítems gratuitos junto a ítems pagados** (muestra médica o bonificación
  con la compra, leyenda 1002): total de impuestos y valor de venta de lo
  pagado; el nativo los ponía en 0 y SUNAT rechazaba (3294).
* **Líneas sin producto** (descuento de una nota de crédito, intereses de una
  nota de débito): unidad ``ZZ`` del catálogo 03; sin ella SUNAT rechaza por
  ``unitCode`` vacío (2883, 2138, 2188).

El asiento contable no cambia: todo ocurre al generar el XML.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-INVOICING/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/al_l10n_pe_edi_downpayment_discount/static/description/icon.png',
    'version': '6.20261027',
    'license': 'OPL-1',
    'countries': ['pe'],
    # sale: los anticipos nacen del asistente de facturación del pedido
    # (líneas ``is_downpayment``) y los enlaza ``_get_downpayment_lines``.
    'depends': ['l10n_pe_edi', 'sale'],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
