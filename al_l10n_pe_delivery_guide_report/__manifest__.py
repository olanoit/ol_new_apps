# -*- coding: utf-8 -*-
{
    'name': 'PE - Reporte de Guía de Remisión Electrónica (AL)',
    'summary': 'Representación impresa propia de la guía de remisión '
               'electrónica remitente (SUNAT) para stock.picking.',
    'description': """
Reporte de guía de remisión electrónica — SUNAT Perú
=====================================================
Reemplaza el reporte estándar de entrega por una representación impresa
propia de la Guía de Remisión Electrónica Remitente: datos del traslado,
remitente/destinatario, detalle de bienes agrupado por producto (con
series/lotes), datos del transportista/vehículo y QR de SUNAT.

Basado en el análisis del módulo v18 ``al_l10n_pe_edi`` (ce18): se separa
del módulo de reportes de factura (``al_l10n_pe_invoice``) para que
ambos sean instalables de forma independiente, y se descarta el método
propio de obtención del QR (``_l10n_pe_edi_get_qr``): el core v19
(``l10n_pe_edi_stock``) ya trae uno idéntico.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-INVENTORY/Apps',
    'version': '5.20260828',
    'license': 'OPL-1',
    'depends': [
        'stock',
        'l10n_pe_edi_stock',
        'al_account_base',
    ],
    'data': [
        'views/stock_picking_views.xml',
        'views/menu.xml',
        'reports/guia_remision_reports.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            'al_l10n_pe_delivery_guide_report/static/src/css/report_guia.css',
        ],
        'web.report_assets_pdf': [
            'al_l10n_pe_delivery_guide_report/static/src/css/report_guia.css',
        ],
    },
    'installable': True,
    'application': False,
}
