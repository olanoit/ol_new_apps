# -*- coding: utf-8 -*-
{
    'name': 'Formato común de documentos impresos (AL)',
    'summary': 'El formato del comprobante A4 para todos los documentos '
               'impresos de la suite: encabezado, pie, estilos y papel.',
    'description': """
Formato común de documentos impresos
====================================
Un solo formato, el del comprobante electrónico A4, para todos los documentos
PDF de la suite (comprobantes, boletas de pago, certificados, contratos,
requerimientos, valorizaciones, kárdex, libro de reclamaciones, Gantt):

* Encabezado: logo, datos de la compañía y recuadro con R.U.C., tipo y número.
* Pie en cada página: compañía, contacto, fecha de impresión y «Página X de Y».
* Hoja de estilos en blanco y negro (prefijo ``pe-doc-``): tablas de datos y
  de detalle, totales, secciones, textos justificados, importes destacados y
  firmas.
* Formatos de papel A4 vertical y horizontal sin el encabezado de Odoo.
* Plantilla ``al_report_base.report_pe_page``: página completa (article,
  encabezado, cuerpo y pie) en una sola llamada.

Solo depende de ``web``: lo usan módulos de contabilidad, planillas,
inventario y proyectos sin arrastrar dependencias entre ellos.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-TOOLS/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/al_report_base/static/description/icon.png',
    'version': '3.20261027',
    'license': 'OPL-1',
    'depends': ['web'],
    'data': [
        'data/report_paperformat_data.xml',
        'reports/report_pe_document.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            'al_report_base/static/src/css/report_pe_document.css',
        ],
        'web.report_assets_pdf': [
            'al_report_base/static/src/css/report_pe_document.css',
        ],
    },
    'installable': True,
    'application': False,
}
