# -*- coding: utf-8 -*-
{
    'name': 'PE - DUA de importación y costos en destino (AL)',
    'summary': 'La DUA (tipo 50) como documento de compra: IGV e IPM con crédito fiscal, '
               'derechos aduaneros, percepción aduanera y costos en destino del producto.',
    'description': """
DUA de importación
==================
La Declaración Aduanera de Mercancías (DUA/DAM, tipo de documento 50; 52 para la
simplificada) se registra como un documento de compra a nombre de la Aduana:

* Número de la DAM en sus partes (aduana, año, régimen y número), que arman el
  número del documento que leen el PLE y el SIRE de compras.
* Liquidación de la DUA: valor en aduana, ad valorem, ISC y otros derechos; el
  asistente genera las líneas: los derechos como costo en destino y la base
  imponible con el IGV (16 % + IPM 2 %) para el crédito fiscal, compensada
  para que el documento sume lo que se paga a la Aduana.
* Percepción aduanera registrada con al_l10n_pe_perception (si está instalado).
* Facturas del proveedor del exterior y recepciones de inventario vinculadas.
* Costos en destino (stock_landed_costs) con los derechos de la DUA y los gastos
  de aduana (agente, flete, almacén), repartidos por valor, peso, cantidad,
  volumen o en partes iguales.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-ACCOUNTING/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/account/static/description/icon.png',
    'version': '4.20261018',
    'license': 'OPL-1',
    'depends': [
        'al_account_base',
        # l10n_pe_dua_invoice_id: factura del exterior → DUA (PLE de compras).
        'l10n_pe_reports',
        'stock_landed_costs',
        'purchase_stock',
    ],
    'data': [
        'data/product_data.xml',
        'views/account_move_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    # Solo en bases con datos de demostración, en «PE Company» (l10n_pe).
    'demo': ['demo/al_l10n_pe_import_dua_demo.xml'],
    'installable': True,
    'application': False,
}
