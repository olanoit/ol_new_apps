# -*- coding: utf-8 -*-
{
    'name': 'PE - OSE The Factory HKA (AL)',
    'summary': 'The Factory HKA como Operador de Servicios Electrónicos: facturas, '
               'boletas, notas, bajas, comprobantes de retención (CRE) y su '
               'reversión, con funciones que se activan en Ajustes.',
    'description': """
OSE The Factory HKA
===================
Añade **The Factory HKA** a los operadores de la facturación electrónica
peruana de Odoo (``l10n_pe_edi``), junto a IAP, SUNAT y Estela.

* Credenciales y WSDL de demostración y producción por compañía, en
  *Ajustes ▸ Contabilidad ▸ Facturación electrónica peruana*.
* Firma, envío (``sendBill``), consulta del CDR (``getStatusCdr``) y
  comunicaciones de baja (``sendSummary`` / ``getStatus``) con los servicios
  de ``l10n_pe_edi``: el mismo flujo, mensajes y adjuntos que los demás
  operadores.
* El nombre del archivo lleva el número con 8 dígitos, como exige HKA.
* **Comprobantes de retención (CRE)** de ``al_l10n_pe_retention`` por HKA
  (desactivable: entonces van directo a SUNAT con la clave SOL).
* **Reversión del CRE** (resumen de reversiones RR) desde el pago:
  ``sendSummary`` y consulta del ticket con ``getStatus`` (desactivable).

Migrado de los módulos 17.0 ``al_ose_factory_hka`` y
``al_ose_factory_hka_retention``, unificados.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-INVOICING/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/account/static/description/icon.png',
    'version': '1.20261009',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['l10n_pe_edi', 'al_l10n_pe_retention'],
    'data': [
        'data/ir_sequence_data.xml',
        'data/cre_reversal_templates.xml',
        'views/res_config_settings_views.xml',
        'views/account_payment_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
