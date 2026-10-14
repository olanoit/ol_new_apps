# -*- coding: utf-8 -*-
{
    'name': 'PE - Cliente por RUC/DNI en el TPV (AL)',
    'summary': 'En la lista de clientes del TPV, un RUC o DNI que no está registrado se crea '
               'en un clic con los datos de SUNAT/RENIEC y queda elegido para la venta.',
    'description': """
Cliente por RUC o DNI en el punto de venta
==========================================
El cajero escribe el RUC o el DNI en la búsqueda de clientes. Si no está
registrado, el botón **Crear desde SUNAT** consulta el documento con las
conexiones de ``l10n_pe_vat_sunat`` y crea el cliente con su nombre o razón
social, la dirección y el ubigeo, listo para emitir la factura o la boleta.

* Valida el formato (8 dígitos del DNI; 11 del RUC con su dígito
  verificador) antes de consultar: no gasta consultas de pago en errores de
  tipeo.
* Si el documento ya existe pero no estaba cargado en la caja, lo trae en vez
  de duplicarlo.
* El formulario completo de cliente del TPV ya consulta SUNAT al escribir el
  documento (onchange de ``l10n_pe_vat_sunat``); este módulo agrega el atajo
  desde la búsqueda.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-POS/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/point_of_sale/static/description/icon.png',
    'version': '1.20261014',
    'license': 'OPL-1',
    'depends': [
        'point_of_sale',
        'l10n_pe_pos',
        'l10n_pe_vat_sunat',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'al_pos_pe_partner_lookup/static/src/overrides/partner_list/partner_list.js',
            'al_pos_pe_partner_lookup/static/src/overrides/partner_list/partner_list.xml',
        ],
    },
    'installable': True,
    'application': False,
}
