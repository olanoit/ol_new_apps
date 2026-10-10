# -*- coding: utf-8 -*-
{
    'name': 'PE - Factoring de facturas (AL)',
    'summary': 'Cesión de facturas a un factor con y sin recurso: asientos de '
               'cesión, desembolso, devengo de intereses, cobro del factor y '
               'recompra, con cuentas del PCGE configurables.',
    'description': """
Factoring de facturas — Perú
============================
Operaciones de factoring sobre las facturas de cliente de Odoo, sin duplicar
la factura ni el cobro:

* **Sin recurso** (el factor asume el riesgo, NIIF 9): la factura se da de
  baja (1212 → 1214 a nombre del factor) y queda pagada; el desembolso
  registra intereses (6734) y comisiones (6391); el retenido se cobra al
  factor.
* **Con recurso**: la factura se reclasifica a 1214 y el adelanto es una
  obligación con el factor (4512); los intereses se devengan desde 3731; si
  el cliente no paga, la recompra devuelve el adelanto y la factura vuelve a
  quedar pendiente.
* Cuentas por modalidad y moneda (PCGE por defecto), número de anotación
  CAVALI, «Ceder a factoring» desde la lista de facturas, pestaña Factoring
  en la factura y menú Perú ▸ Factoring con análisis.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/account/static/description/icon.png',
    'version': '3.20261010',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['account', 'l10n_pe', 'al_account_base'],
    'data': [
        'security/ir.model.access.csv',
        'security/factoring_security.xml',
        'data/ir_sequence_data.xml',
        'views/factoring_views.xml',
        'views/factoring_account_config_views.xml',
        'views/factoring_wizard_views.xml',
        'views/account_move_views.xml',
        'views/menu.xml',
        'data/factoring_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
