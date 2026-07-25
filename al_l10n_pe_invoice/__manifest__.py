# -*- coding: utf-8 -*-
{
    'name': 'PE - Comprobantes Electrónicos (AL)',
    'summary': 'Presentación del comprobante electrónico: QR SUNAT, monto '
               'en letras, detalle tributario, detracción, cuotas de '
               'crédito, firmas y reportes propios A4 y ticket 80mm.',
    'description': """
Comprobantes electrónicos — SUNAT Perú
========================================
No es solo un reporte: agrega los campos y el detalle tributario que la
representación impresa necesita (``account.move``: detalle
IGV/ISC/IVAP/ICBPER/exoneradas/inafectas, vínculo con la orden de venta,
forma de pago crédito/contado) y los dos formatos de impresión:

* **A4** (``report_cpe_invoice_a4``): encabezado con recuadro SUNAT,
  detalle tributario, bloque de detracción (``al_l10n_pe_detraction``),
  cuotas de crédito y bloque de firmas/cuentas bancarias (configurable).
* **Ticket 80mm** (``report_cpe_ticket``): misma información condensada
  para punto de venta.

Reutiliza el core (``l10n_pe_edi``) en vez de duplicarlo:

* **QR oficial**: ``_l10n_pe_edi_get_extra_report_values()`` extrae del
  XML firmado el QR con el hash de la firma digital que exige SUNAT
  (el QR recalculado a mano del v18 no era conforme) y se renderiza con
  el endpoint nativo ``/report/barcode`` — sin dependencia ``qrcode`` ni
  campos binarios almacenados.
* **Monto en letras**: ``_l10n_pe_edi_amount_to_text()`` (num2words).

El estilo vive en ``static/src/css/report_cpe.css`` (bundles
``web.report_assets_common`` / ``_pdf``), siguiendo el patrón de
``account`` — sin ``<style>`` inline en las plantillas, que usan el
esquema contenedor + ``_document`` de ``account.report_invoice``.

La guía de remisión es un reporte independiente:
ver ``al_l10n_pe_delivery_guide_report``.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-ACCOUNT/Apps',
    'version': '6.20260719',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'sale',
        'l10n_pe_edi',
        'al_account_base',
        'al_l10n_pe_currency',
        'al_l10n_pe_detraction',
    ],
    'data': [
        'data/paper_format_data.xml',
        'views/account_move_views.xml',
        'views/res_company_views.xml',
        'views/res_config_settings_views.xml',
        'views/sale_order_views.xml',
        'reports/cpe_invoice_reports.xml',
        'reports/cpe_ticket_reports.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            'al_l10n_pe_invoice/static/src/css/report_cpe.css',
        ],
        'web.report_assets_pdf': [
            'al_l10n_pe_invoice/static/src/css/report_cpe.css',
        ],
    },
    'installable': True,
    'application': False,
}
