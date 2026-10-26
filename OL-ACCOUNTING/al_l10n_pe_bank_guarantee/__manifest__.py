# -*- coding: utf-8 -*-
{
    'name': 'PE - Cartas fianza (AL)',
    'summary': 'Cartas fianza emitidas por el banco a pedido de la empresa y recibidas de terceros: '
               'vigencia, renovación, liberación y ejecución, comisión, línea de crédito, cuentas de '
               'orden y avisos (plazo del art. 1898 del Código Civil).',
    'description': """
Cartas fianza
=============
* **Emitidas** (fiel cumplimiento, adelanto directo o de materiales, seriedad
  de oferta, pago, aduanera): banco, beneficiario, contrato o proceso, importe,
  vigencia y condiciones (solidaria, irrevocable, incondicional, de realización
  automática, sin beneficio de excusión). Comisión trimestral con mínimo al
  emitir y al renovar (6391), ITF opcional, consumo de la **línea de crédito**
  y fondo en garantía enlazado (Depósitos y garantías).
* **Recibidas** de proveedores y contratistas: aviso antes del vencimiento y
  fecha límite para requerir al banco (vencimiento + 15 días, art. 1898 del
  Código Civil).
* **Renovación** (nueva carta fianza enlazada), **liberación** y **ejecución**
  con su asiento.
* **Cuentas de orden** opcionales (0113/0114 emitidas, 0126/0129 recibidas).
""",
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    # Ícono de la aplicación a la que pertenece (Tesorería).
    'icon': '/al_l10n_pe_treasury/static/description/icon.png',
    'version': '1.20261026',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['al_l10n_pe_treasury'],
    'data': [
        'security/ir.model.access.csv',
        'security/bank_guarantee_security.xml',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'views/bank_guarantee_views.xml',
        'views/res_config_settings_views.xml',
        'wizards/bank_guarantee_wizard_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
