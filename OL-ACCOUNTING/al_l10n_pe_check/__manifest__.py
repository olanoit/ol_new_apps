# -*- coding: utf-8 -*-
{
    'name': 'PE - Cheques recibidos y girados (AL)',
    'summary': 'Cartera de cheques de terceros y cheques propios sobre el módulo nativo de '
               'Odoo: diarios y cuentas del PCGE, emisor con RUC o DNI y plazo de '
               'presentación de la Ley de Títulos Valores.',
    'description': """
Cheques recibidos y girados
===========================
Adapta a Perú la gestión de cheques nativa de Odoo (``l10n_latam_check``):
cartera de cheques de terceros (recepción, depósito, endoso a un proveedor,
rechazo y devolución) y cheques propios girados (diferidos, anulación).

* **Diarios y cuentas del PCGE** al instalar el plan peruano o este módulo:
  «Cheques de terceros» (1033001 Cheques de terceros en cartera), «Cheques
  rechazados» (1689001) y el método «Cheques propios» en los diarios de banco
  (1049001 Cheques girados en circulación).
* **Emisor** con RUC (dígito verificador), DNI de 8 dígitos o carné de
  extranjería: Odoo solo aceptaba RUC.
* **Plazo de presentación** (Ley 27287, Ley de Títulos Valores): 30 días desde
  la fecha del cheque o, si es de pago diferido, desde la fecha de pago. La
  cartera muestra el vencimiento y avisa al depositar un cheque vencido o un
  diferido que aún no se puede cobrar.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/al_l10n_pe_check/static/description/icon.png',
    'version': '3.20261027',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['l10n_latam_check', 'l10n_pe', 'al_account_base'],
    'data': [
        'views/l10n_latam_check_views.xml',
        'views/l10n_latam_payment_mass_transfer_views.xml',
    ],
    # Solo en bases con datos de demostración, en «PE Company» (l10n_pe).
    'demo': ['demo/al_l10n_pe_check_demo.xml'],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
