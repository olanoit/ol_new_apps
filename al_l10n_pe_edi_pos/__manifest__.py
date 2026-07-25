# -*- coding: utf-8 -*-
{
    'name': 'PE - Comprobantes Electrónicos en el TPV (AL)',
    'summary': 'Boleta/Factura electrónica desde el punto de venta: selector '
               'de tipo de documento, diario por tipo y ticket con formato '
               'CPE SUNAT.',
    'description': """
Comprobantes electrónicos en el punto de venta — SUNAT Perú
============================================================
Lleva la facturación electrónica peruana a la caja:

* **Selector Boleta/Factura** en la pantalla de pago (diálogo de
  selección, boleta por defecto). La factura exige cliente con RUC.
* **Diario por tipo de documento**: cada TPV configura su diario de
  boletas y su diario de facturas (series B###/F###); la factura
  contable se crea en el diario del tipo elegido.
* **Toda venta se factura**: al cobrar se marca la orden "a facturar"
  automáticamente, de modo que siempre se emite un CPE.
* **Ticket con formato CPE**: el recibo del TPV replica el diseño del
  ticket 80mm de ``al_l10n_pe_invoice`` (encabezado RUC, tipo y número
  de documento, desglose IGV, importe en letras y QR de representación
  impresa según R.S. 018-2005/SUNAT).

Basado en el análisis del módulo v18 ``al_l10n_pe_edi_pos``
(farmaniacos) portado a la arquitectura OWL/data-model de Odoo 19.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-POS/Apps',
    'version': '6.20260721',
    'license': 'LGPL-3',
    'depends': [
        'point_of_sale',
        'l10n_pe_pos',
        'l10n_pe_edi',
        'l10n_pe_edi_pos',
        'al_l10n_pe_invoice',
        'al_account_move_name_sequence',
    ],
    'data': [
        'views/res_config_settings_views.xml',
        'views/pos_order_views.xml',
        'views/account_move_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'al_l10n_pe_edi_pos/static/src/app/utils/pe_doc_utils.js',
            'al_l10n_pe_edi_pos/static/src/overrides/pos_store.js',
            'al_l10n_pe_edi_pos/static/src/app/doc_type_popup/doc_type_popup.js',
            'al_l10n_pe_edi_pos/static/src/app/doc_type_popup/doc_type_popup.xml',
            'al_l10n_pe_edi_pos/static/src/overrides/pos_order.js',
            'al_l10n_pe_edi_pos/static/src/overrides/order_payment_validation.js',
            'al_l10n_pe_edi_pos/static/src/overrides/payment_screen.js',
            'al_l10n_pe_edi_pos/static/src/overrides/payment_screen.xml',
            'al_l10n_pe_edi_pos/static/src/overrides/order_receipt.js',
            'al_l10n_pe_edi_pos/static/src/overrides/order_receipt.xml',
            'al_l10n_pe_edi_pos/static/src/overrides/receipt_screen.xml',
            'al_l10n_pe_edi_pos/static/src/overrides/order_receipt.scss',
        ],
    },
    'installable': True,
    'application': False,
}
