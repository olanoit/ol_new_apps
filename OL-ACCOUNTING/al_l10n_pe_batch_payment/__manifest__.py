# -*- coding: utf-8 -*-
{
    'name': 'PE - Pagos masivos a proveedores (AL)',
    'summary': 'Lotes de pago a proveedores con el archivo TXT de BCP, BBVA, Interbank, '
               'Scotiabank y Banco de la Nación: cuenta o CCI del proveedor, controles y '
               'totales del archivo.',
    'description': """
Pagos masivos a proveedores
===========================
Sobre los lotes de pago de Odoo (Enterprise), un método de pago «Pago masivo
(TXT de banco peruano)» que genera el archivo de pago a proveedores del banco
del diario:

* Formato por banco (BCP, BBVA, Interbank, Scotiabank, Banco de la Nación),
  elegido en el banco; códigos del servicio y de la empresa en el diario.
* Cuenta del proveedor: la del mismo banco o, si es de otro banco, su CCI de
  20 dígitos (validado).
* Controles al validar el lote: formato y cuenta de cargo del diario, cuenta y
  CCI del proveedor, moneda de la cuenta igual a la del lote (soles y dólares
  van en lotes distintos), documento del proveedor y depósitos de detracción
  fuera del banco comercial.
* Archivo con el nombre del banco, la moneda, el diario y el lote; número de
  registros y total guardados en el lote y el archivo adjunto en su historial.

Los bancos entregan la especificación de sus archivos a cada empresa
afiliada: valide el primer archivo con el banco antes de pagar.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-ACCOUNTING/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/al_l10n_pe_batch_payment/static/description/icon.png',
    'version': '6.20261027',
    'license': 'OPL-1',
    'depends': ['account_batch_payment', 'al_account_payments', 'l10n_pe'],
    'data': [
        'data/account_payment_method_data.xml',
        'views/views.xml',
    ],
    # Solo en bases con datos de demostración, en «PE Company» (l10n_pe).
    'demo': ['demo/al_l10n_pe_batch_payment_demo.xml'],
    'installable': True,
    'application': False,
}
