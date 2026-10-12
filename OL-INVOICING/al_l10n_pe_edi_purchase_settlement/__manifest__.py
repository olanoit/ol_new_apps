# -*- coding: utf-8 -*-
{
    'name': 'PE - Liquidación de compra electrónica (AL)',
    'summary': 'Liquidación de compra electrónica (tipo 04) a personas '
               'naturales sin RUC: XML UBL 2.1 firmado y enviado, retención '
               'del IGV y del impuesto a la renta, PDF y reversión.',
    'description': """
Liquidación de compra electrónica — SUNAT
==========================================
El comprador emite la liquidación de compra (tipo 04) cuando compra a
personas naturales sin RUC productos primarios agropecuarios, de pesca
artesanal, madera, productos silvestres, oro de minería artesanal,
artesanía o desperdicios (Reglamento de Comprobantes de Pago, art. 6,
num. 1.3; R.S. 097-2012/SUNAT, capítulo XI, incorporado por la
R.S. 244-2019/SUNAT).

* Diario de compras propio con serie ``L###`` y numeración correlativa.
* Retención del IGV (formulario 1662) y del impuesto a la renta (1,5 %, o
  4 % en el oro; nada hasta S/ 700) con impuestos negativos del plan
  peruano: el proveedor recibe el importe total neto.
* XML ``SelfBilledInvoice`` (anexo 6) firmado y enviado con el operador
  electrónico de la compañía (IAP, SUNAT directo, Digiflow y otros
  operadores que sigan el contrato de ``l10n_pe_edi``, p. ej. Factory HKA).
* Resumen diario de reversiones (anexo 17) para revertir una liquidación
  aceptada dentro de los siete días calendario.
* Representación impresa con el formato común de la suite.
* Aviso del límite de 75 UIT de ventas del vendedor en el año.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-INVOICING/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/account/static/description/icon.png',
    'version': '2.20261012',
    'license': 'OPL-1',
    'depends': [
        # Páginas «Facturación PE», ajustes y menús de la app Perú
        'al_account_base',
        # Formato común de los documentos impresos
        'al_report_base',
        # Firma, envío y resúmenes con el operador electrónico de la compañía
        'l10n_pe_edi',
    ],
    'data': [
        'data/ir_sequence_data.xml',
        'data/lce_templates.xml',
        'views/res_config_settings_views.xml',
        'views/account_journal_views.xml',
        'views/product_template_views.xml',
        'views/account_move_views.xml',
        'reports/purchase_settlement_report.xml',
    ],
    'post_init_hook': 'post_init_hook',
    # Solo en bases con datos de demostración, en «PE Company» (l10n_pe).
    'demo': ['demo/al_l10n_pe_edi_purchase_settlement_demo.xml'],
    'installable': True,
    'application': False,
}
