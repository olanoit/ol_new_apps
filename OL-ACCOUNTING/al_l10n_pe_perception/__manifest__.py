# -*- coding: utf-8 -*-
{
    'name': 'PE - Percepciones del IGV (AL)',
    'summary': 'Régimen de percepciones del IGV: comprobante de percepción electrónico '
               '(tipo 40) como agente, percepciones que nos cobran para el F.V. 621 y '
               'resumen del F.V. 697.',
    'description': """
Percepciones del IGV
====================
Régimen de percepciones del IGV (Ley 29173 y R.S. 058-2006/SUNAT; combustibles,
R.S. 128-2002/SUNAT) para empresas peruanas.

Como agente de percepción:

* Bienes sujetos en el producto (Apéndice 1 de la Ley 29173, numerales con
  consumidor final hasta S/ 100, gas licuado y combustibles).
* Cálculo en la factura de venta: 2 % general; 0,5 % si el comprobante da
  crédito fiscal y el cliente es agente de percepción; 1 % en combustibles.
  Exclusiones: cliente agente de retención o entidad exceptuada (con
  comprobante que da crédito fiscal), consumidor final, operaciones con
  detracción (SPOT) y combustible a otro agente o consumidor final.
* La factura informa la operación 2001, el cargo de percepción (catálogo 53:
  51, 52 o 53) y el monto total con la percepción; el PDF lleva la leyenda
  «Operación sujeta a percepción del IGV».
* Comprobante de percepción electrónico (tipo 40, serie P001) por cada cobro,
  uno por tasa, desde el pago o desde las facturas: factor de seis decimales
  sobre el monto cobrado, tipo de cambio de la fecha de cobro, asiento contra
  la cuenta del IGV percibido, XML UBL 2.0 firmado y enviado por el operador
  de la compañía y reversión (resumen RR), con el mismo motor que el
  comprobante de retención.
* Análisis por periodo con la base cobrada (casilla 502) y las percepciones
  efectuadas (casilla 401) del F.V. 697.

Percepciones que nos cobran:

* Registro del comprobante de percepción del proveedor, de la percepción
  consignada en la factura (numeral 10.6) o de la percepción a la importación
  (DUA), con su asiento al IGV percibido y la cuenta por pagar.
* «Registrar percepción» desde la factura de proveedor.
* Análisis por periodo para aplicarlas en el F.V. 621.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-ACCOUNTING/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/account/static/description/icon.png',
    'version': '3.20261012',
    'license': 'OPL-1',
    'depends': [
        # Motor del comprobante electrónico (l10n_pe.retention.edi.mixin),
        # agente de percepción del contacto y padrones de SUNAT.
        'al_l10n_pe_retention',
        # Leyenda de la percepción en el comprobante impreso A4.
        'al_l10n_pe_invoice',
        # Formato común de los documentos impresos.
        'al_report_base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'reports/perception_report.xml',
        'views/res_config_settings_views.xml',
        'views/product_views.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'views/perception_views.xml',
        'views/perception_received_views.xml',
        'views/perception_menus.xml',
    ],
    # Solo en bases con datos de demostración, en «PE Company» (l10n_pe).
    'demo': ['demo/al_l10n_pe_perception_demo.xml'],
    'installable': True,
    'application': False,
}
