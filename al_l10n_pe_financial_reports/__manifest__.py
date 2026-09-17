# -*- coding: utf-8 -*-
{
    'name': 'PE - Reportes financieros (AL)',
    'summary': 'Estados financieros peruanos sobre el motor de informes de '
               'Odoo: 3.19 Estado de Cambios en el Patrimonio Neto, junto al '
               'Balance y el Estado de resultados, en la app Perú.',
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

* Menú **Perú ▸ Estados financieros** con el Balance, el Estado de resultados
  y el 3.19; el 3.19 aparece también en Contabilidad ▸ Informes.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-ACCOUNT/Apps',
    'version': '1.20260917',
    'license': 'OPL-1',
    'depends': [
        'account_reports',
        'l10n_pe',
        'al_account_base',
    ],
    'data': [
        'data/report_equity_changes.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
}
