# -*- coding: utf-8 -*-
{
    'name': 'PE - Depósitos a plazo y garantías (AL)',
    'summary': 'Depósitos a plazo, fondos en garantía y depósitos en garantía '
               'entregados: apertura, devengo mensual de intereses (TEA), '
               'vencimiento, cancelación, renovación y liberación con sus asientos.',
    'description': """
Depósitos a plazo y garantías
=============================
Lleva el dinero inmovilizado de la empresa con su contabilidad:

* **Depósito a plazo** (PCGE 1062): capital, TEA, base de 360 o 365 días,
  plazo y vencimiento; devengo mensual de intereses (1631 / 7721) automático
  y cancelación o renovación (con o sin capitalizar los intereses).
* **Fondo en garantía** (1071): dinero retenido por el banco (p. ej. respaldo
  de una carta fianza), con intereses si los genera y liberación total o
  parcial.
* **Depósito en garantía entregado** (1643): p. ej. la garantía del alquiler
  de una oficina o un almacén, que se recupera al terminar el contrato.

Aviso (actividad) unos días antes del vencimiento (o de la vigencia de la
garantía), renovación automática opcional y cuentas configurables por tipo y
moneda. Además:

* **ITF** (Ley 28194) opcional en la apertura, la cancelación y la liberación.
* **Penalidad** por cancelación anticipada (cuenta propia o menor ingreso).
* **Garantías** con su finalidad (carta fianza, alquiler, contrato), el
  beneficiario, el documento garantizado y su vigencia.
* **Moneda extranjera**: aviso si las cuentas no están marcadas para el
  cierre de tipo de cambio de la suite.
* Reportes de **cartera vigente** e **intereses devengados** por mes.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/account/static/description/icon.png',
    'version': '2.20261010',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['account', 'l10n_pe', 'al_account_base'],
    'data': [
        'security/ir.model.access.csv',
        'security/term_deposit_security.xml',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'views/term_deposit_views.xml',
        'views/term_deposit_account_config_views.xml',
        'views/term_deposit_wizard_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu.xml',
        'data/term_deposit_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
