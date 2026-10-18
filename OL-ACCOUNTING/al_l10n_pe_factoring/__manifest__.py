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
* **Con recurso**: la factura sigue pendiente a nombre del cliente (NIIF 9) y
  el adelanto es una obligación con el factor (4512); los intereses se
  devengan desde 3731; si el cliente no paga, la recompra devuelve el
  adelanto y la factura sigue pendiente.
* Factura negociable (DU 013-2020): conformidad expresa o presunta,
  anotación en CAVALI, monto neto pendiente de pago sin detracción ni
  retención; cobros parciales; comisión facturada por el factor; pérdida del
  retenido (sin recurso); diferencia de cambio de la obligación (con recurso).
* Contratos por factor (adelanto, TEA, comisión, línea de crédito y límite
  por cliente) con simulación de la liquidación; revisión previa de las
  facturas; desembolsos parciales; prórroga; cobro recibido por la empresa y
  transferencia al factor; notificación al cliente (PDF y correo); archivo de
  la cesión para el factor.
* Factura negociable en la factura: conformidad (presunta automática a los 8
  días), anotación en CAVALI e historial de eventos con orden validado.
* CAVALI: paquete para Factrack, importación de estados y servicios web
  configurables con registro de envíos.
* Cuentas por modalidad y moneda (PCGE por defecto), «Ceder a factoring»
  desde la lista de facturas, pestaña Factoring en la factura y menú
  Perú ▸ Clientes ▸ Factoring con análisis y costo financiero.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/account/static/description/icon.png',
    'version': '9.20261018',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['account', 'l10n_pe', 'al_account_base', 'al_report_base'],
    'external_dependencies': {'python': ['xlsxwriter', 'openpyxl', 'requests']},
    'data': [
        'security/ir.model.access.csv',
        'security/factoring_security.xml',
        'data/ir_sequence_data.xml',
        'views/factoring_views.xml',
        'views/factoring_contract_views.xml',
        'reports/factoring_notice_report.xml',
        'views/factoring_account_config_views.xml',
        'views/factoring_wizard_views.xml',
        'views/account_move_views.xml',
        'views/menu.xml',
        'data/factoring_data.xml',
    ],
    # Solo en bases con datos de demostración, en «PE Company» (l10n_pe).
    'demo': ['demo/al_l10n_pe_factoring_demo.xml'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
