# -*- coding: utf-8 -*-
{
    'name': 'PE - Reportes financieros (AL)',
    'summary': 'Estados financieros peruanos sobre el motor de informes de '
               'Odoo: 3.19, hoja de trabajo (formatos 1 y 2), cierre del '
               'ejercicio con la cascada de la clase 8 y EEFF por centro de '
               'costo.',
    'description': """
Reportes financieros — Perú
===========================
Módulo que reúne los estados financieros peruanos de la suite, definidos como
informes contables de Odoo (``account.report``): se filtran por fechas, se
comparan con periodos anteriores, se despliegan hasta el apunte y se exportan
a PDF y XLSX con las herramientas estándar.

* **3.19 Estado de Cambios en el Patrimonio Neto** (PCGE), migrado del módulo
  v18 ``al_l10n_pe_reports`` y corregido:

  * el patrimonio sale en positivo, como en el Balance;
  * componentes del PCGE vigente: 50 Capital, 51 Acciones de inversión,
    52 Capital adicional, 56 Resultados no realizados, 57 Excedente de
    revaluación, 58 Reservas y 59 Resultados acumulados (el v18 usaba las
    cuentas 53, 54 y 55, que no existen, y tomaba la 57 como dividendos);
  * el resultado del ejercicio sale de las cuentas de resultados, así que el
    informe cuadra con o sin asiento de cierre (en el v18 salía en cero
    hasta cerrar el ejercicio);
  * los asientos de diarios con naturaleza **Cierre** no cuentan y los de
    **Apertura** del periodo forman el saldo inicial;
  * líneas editables para cambios de políticas, corrección de errores,
    aportes, distribuciones y subsidiarias, con su nota.

  Sin ajustes editables, el saldo final coincide con el patrimonio del
  Balance a la misma fecha.

* **Hoja de trabajo** formato 1 (sumas, saldos, balance, resultados por
  naturaleza y por función) y formato 2 (además saldos iniciales y
  movimientos), con el resultado del ejercicio que iguala cada par de
  columnas y filtro por centro de costo.

* **Cierre del ejercicio** (Perú ▸ Contabilidad ▸ Cierre del mes): asientos
  en borrador que cancelan la clase 9 contra la 79, determinan los saldos
  intermediarios de gestión (80 a 85), el resultado (89) y lo llevan a la 59,
  según reglas editables; opcionalmente cierran y reabren las cuentas de
  balance. Al publicar, concilia la reapertura con el cierre.

* El **Balance** y el **Estado de resultados** peruanos no cuentan los
  asientos de cierre y tienen filtro por centro de costo.

* Menú **Perú ▸ Informes ▸ Estados financieros** con el Balance, el Estado de resultados,
  el 3.19 y la hoja de trabajo; el 3.19 aparece también en Contabilidad ▸ Informes.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-ACCOUNTING/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/al_l10n_pe_financial_reports/static/description/icon.png',
    'version': '5.20261028',
    'license': 'OPL-1',
    'depends': [
        'account_reports',
        'l10n_pe',
        'l10n_pe_reports',
        'al_account_base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/l10n_pe_closing_rule_security.xml',
        'data/l10n_pe_closing_rule_data.xml',
        'data/report_equity_changes.xml',
        'data/report_worksheet.xml',
        'data/report_variants.xml',
        'wizard/l10n_pe_year_closing_wizard_views.xml',
        'views/l10n_pe_closing_rule_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
}
