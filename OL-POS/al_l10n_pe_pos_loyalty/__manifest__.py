# -*- coding: utf-8 -*-
{
    'name': 'Perú - Tarjetas de regalo y monedero en el TPV (AL)',
    'summary': 'La venta de tarjetas de regalo y recargas del monedero no lleva comprobante y su '
               'canje es una forma de pago: la boleta o factura sale con el IGV completo.',
    'description': """
Tarjetas de regalo y monedero electrónico con el criterio de SUNAT
==================================================================
Según el Informe SUNAT 097-2010, vender una tarjeta de regalo o recargar el
monedero no es una venta de bienes: no lleva IGV ni comprobante, y el
comprobante se emite cuando el cliente la canjea por productos.

- **Venta de la tarjeta o recarga**: no entra en la boleta ni en la factura.
  Una venta que solo lleva tarjetas o recargas sale con ticket, sin
  comprobante electrónico. El importe queda como deuda con el cliente en la
  cuenta de pasivo de la compañía (496 Ingresos diferidos, configurable).
- **Canje**: el vale no rebaja el precio de los productos. La boleta o
  factura lleva el importe completo con su IGV, y el vale la paga desde la
  cuenta de pasivo, como cualquier otra forma de pago.
- El ticket del TPV muestra lo mismo que el comprobante: el canje entre los
  pagos y la tarjeta vendida como importe fuera del comprobante.

Se instala solo con el comprobante electrónico del TPV y los programas de
fidelización del TPV.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-POS/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/al_l10n_pe_pos_loyalty/static/description/icon.png',
    'version': '2.20261027',
    'license': 'OPL-1',
    'depends': ['al_l10n_pe_edi_pos', 'pos_loyalty'],
    'data': [
        'data/voucher_setup_data.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'al_l10n_pe_pos_loyalty/static/src/app/**/*',
        ],
        'web.assets_tests': [
            'al_l10n_pe_pos_loyalty/static/tests/tours/**/*',
        ],
    },
    'installable': True,
    'auto_install': True,
    'application': False,
}
