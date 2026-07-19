# -*- coding: utf-8 -*-
{
    'name': 'PE - Libros Electrónicos PLE (AL)',
    'summary': 'Completa los libros electrónicos PLE de SUNAT no cubiertos '
               'por la localización oficial: Libro 7 (Activos Fijos), '
               '4.1 (Retenciones LIR), 9.1/9.2 (Consignaciones), '
               'complementos del Libro 3 (3.8/3.9/3.19/3.23), Libro 10 '
               '(Costos) y formatos simplificados (5.2/5.4, 8.3, 14.2).',
    'description': """
Libros Electrónicos PLE — SUNAT Perú
====================================
Genera los archivos TXT del PLE que la localización oficial (CE + EE) no
cubre. Plan completo en ``docs/ple/PLAN_MODULO_al_l10n_pe_ple.md``.

Fase actual:

* Motor común PLE (nomenclatura de archivos, serialización ``|``, validador
  de estructura según el Anexo 2 de SUNAT).
* Wizard de exportación en el menú **Perú ▸ Libros PLE** (libros anuales y
  mensuales).
* **Libro 7 — Registro de Activos Fijos**: formatos 7.1 (revaluados y no
  revaluados), 7.3 (diferencia de cambio) y 7.4 (arrendamiento financiero),
  con datos SUNAT capturados en la ficha del activo (``account.asset``).
* **PLE 4.1 — Retenciones Art. 34 e)/f) LIR**: captura mensual editable e
  importable (sin nómina peruana en Odoo).
* **PLE 9.1/9.2 — Registro de Consignaciones**: albaranes marcados como
  consignación (6 clases), con saldo inicial por producto/contraparte.
* **Libro 3 — complementos**: 3.8 inversiones mobiliarias (captura), 3.9
  intangibles (automático desde activos cuenta ``34…``), 3.19 cambios en el
  patrimonio neto (captura por rubro tabla 34) y 3.23 notas a los EEFF
  (PDF incluido en el ZIP con nombre oficial).
* **Libro 10 — Registro de Costos** (anual): 10.1 costo de ventas, 10.2
  elementos del costo mensual, 10.3 costo de producción por proceso
  (tabla 21) y 10.4 centros de costos, con captura editable/importable
  (sin ``mrp``).
* **Formatos simplificados 5.2/5.4, 8.3 y 14.2** (excluyentes con los
  completos): habilitados por la bandera «Libros PLE simplificados» en
  Ajustes ▸ Perú; generados desde los asientos/facturas publicados.

Los formatos ya cubiertos por ``l10n_pe_reports`` / ``l10n_pe_reports_lib`` /
``l10n_pe_reports_stock`` (1.1/1.2, libro 3, 5.1/5.3/6.1, 8.1/8.2, 12.1/13.1,
14.1) NO se reimplementan.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-ACCOUNT/Apps',
    'version': '3.20260719',
    'license': 'LGPL-3',
    'depends': [
        'al_account_base',
        'account_asset',
        'l10n_pe_reports',
        'l10n_pe_reports_stock',
        'l10n_pe_reports_lib',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/account_asset_views.xml',
        'views/ple_withholding_views.xml',
        'views/ple_investment_views.xml',
        'views/ple_cost_views.xml',
        'views/stock_picking_views.xml',
        'views/res_config_settings_views.xml',
        'wizards/ple_export_wizard_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
}
