# -*- coding: utf-8 -*-
{
    'name': 'Planillas Perú - Contabilización (AL)',
    'summary': 'Asientos de planilla y beneficios sociales con distribución analítica opcional por compañía.',
    'description': """
Planillas Perú - Contabilización (AL)
=====================================
Módulo del refactor de planillas v18 → v19 (27 módulos → 5); ver
``docs/planillas/PLAN_MIGRACION_PLANILLAS_V19.md``.

Fase 5 (actual):

* **Asiento de planilla por lote** (opt-in): agregación por ORM de las
  líneas de boleta en cargos/abonos por cuenta de la regla, detalle por
  trabajador (``employee_move_line`` nativo) y bloque AFP por la cuenta
  de la afiliación (``hr.membership``, ``company_dependent``); asistente
  con previsualización y ajuste por redondeo. Sustituye a la vista SQL
  ``payslip_run_move`` v18 y sus 4 variantes.
* **Asientos de beneficios sociales**: CTS, gratificación, liquidación
  de cese y provisiones por ORM (``account.move.create``).
* **Distribución analítica opcional** por compañía
  (``hr.main.parameter.detail_analytic``) con el JSON nativo
  ``analytic_distribution`` (regla > versión); elimina el modelo v18
  ``hr.analytic.distribution``.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-PLANILLAS/Apps',
    'version': '3.20260816',
    'license': 'LGPL-3',
    'depends': ['al_hr_pe_benefits', 'hr_payroll_account'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'wizard/hr_payslip_run_move_wizard.xml',
        'wizard/hr_benefits_move_wizard.xml',
        'views/hr_payslip_run_move_views.xml',
        'views/hr_benefits_move_views.xml',
    ],
    'installable': True,
    'application': False,
}
