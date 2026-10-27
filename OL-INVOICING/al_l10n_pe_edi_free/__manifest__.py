{
    'name': 'PE - Operaciones gratuitas en el CPE (AL)',
    'summary': 'Facturas y boletas con transferencias gratuitas (retiros, bonificaciones, '
               'muestras): impuesto gratuito exonerado o inafecto, leyenda 1002, contado '
               'y validación de las reglas SUNAT al publicar.',
    'description': """
Operaciones gratuitas en el comprobante electrónico
====================================================
Odoo 19 (``l10n_pe_edi``) ya informa los ítems gratuitos con precio 0, el valor
referencial (código de precio 02) y el total 9996, y trae el grupo «18% Free
Group» para los retiros gravados (afectación 11-16), con el IGV asumido al
gasto. Contrastado con las reglas de validación de SUNAT (26.08.2026), le
falta:

* **Gratuitas exoneradas o inafectas** (afectación 21 y 31-37): grupo
  «Gratuito exonerado/inafecto» que deja el ítem en 0 en el asiento; con el
  «0% Gra» solo, el ítem se cobraba.
* **Afectación 37** (transferencia gratuita inafecta) tratada como gratuita en
  el XML.
* **Leyenda 1002** puesta (y quitada) sola según haya ítems gratuitos.
* **Forma de pago**: una factura de total 0 sale al contado.
* **Validación al publicar** de las reglas 3110, 3111, 2641/3224 y del ítem
  gratuito que se cobra.
* Botón **Transferencia gratuita** que convierte la factura entera.
""",
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-INVOICING/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/al_l10n_pe_edi_free/static/description/icon.png',
    'version': '2.20261027',
    'license': 'OPL-1',
    'countries': ['pe'],
    # El XML de una factura con ítems gratuitos y pagados lo corrige
    # al_l10n_pe_edi_downpayment_discount (totales con la leyenda 1002).
    'depends': ['l10n_pe_edi', 'al_l10n_pe_edi_downpayment_discount'],
    'data': [
        'views/account_move_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
