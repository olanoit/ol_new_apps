# -*- coding: utf-8 -*-
{
    'name': 'PE - Consulta de validez de comprobantes en SUNAT (AL)',
    'summary': 'Consulta integrada de comprobantes de pago de SUNAT para las facturas de '
               'proveedor: de una en una, en lote o al publicar, con aviso o bloqueo.',
    'description': """
Consulta de validez de comprobantes en SUNAT
============================================
Antes de usar el crédito fiscal de una compra, conviene comprobar que el
comprobante existe en SUNAT y que su emisor está activo y habido. Este módulo
usa el servicio web oficial «Consulta integrada de comprobante de pago»:

* **Botón «Validar en SUNAT»** en la factura o nota de crédito de proveedor y
  la misma acción en la lista, para consultar en lote.
* **Resultado en la factura**: válido, válido con observaciones (emisor no
  activo o no habido) o no válido (no existe, anulado o no autorizado), con el
  estado del comprobante, del emisor, de su domicilio y la fecha de consulta.
  Filtros por resultado en la lista de facturas.
* **Al publicar**: consulta y solo avisa en el historial, o además impide
  publicar los comprobantes que SUNAT no da por válidos (Ajustes ▸ Perú).
* **Acción programada** (desactivada por defecto) que consulta las compras
  publicadas de los últimos 60 días aún sin resultado.
* **Credenciales** de API SUNAT del RUC (client ID y client secret), con el
  token renovado solo; si no se configuran, se usan las del SIRE.

Facturas (01), boletas (03), liquidaciones de compra (04), notas de crédito
(07) y de débito (08) y recibos por honorarios (02, código R1 del servicio).
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-ACCOUNTING/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/account/static/description/icon.png',
    'version': '3.20261018',
    'license': 'OPL-1',
    'depends': ['al_account_base', 'l10n_pe'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'data/ir_cron.xml',
        'views/res_config_settings_views.xml',
        'views/account_move_views.xml',
    ],
    # Solo en bases con datos de demostración, en «PE Company» (l10n_pe).
    'demo': ['demo/al_l10n_pe_cpe_validation_demo.xml'],
    'installable': True,
    'application': False,
}
