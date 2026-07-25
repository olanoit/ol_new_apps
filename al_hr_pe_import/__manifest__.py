# -*- coding: utf-8 -*-
{
    'name': 'Planillas Perú - Importadores Excel (AL)',
    'summary': 'Framework de importación Excel (openpyxl) con lotes, progreso '
               'en vivo y reporte de errores por fila para toda la suite de '
               'planillas Perú.',
    'description': """
Planillas Perú - Importadores Excel (AL)
========================================
Módulo del refactor de planillas v18 → v19 (27 módulos → 6); ver
``docs/planillas/PLAN_MIGRACION_PLANILLAS_V19.md``.

Fase 8 — módulo de CIERRE de la suite: sus plantillas de importación
cruzan todos los dominios (núcleo, beneficios, asistencias, contable,
reportes), por eso depende de los cinco módulos ``al_hr_pe_*``.

Port de ``al_hr_payroll_import`` v18 (el mejor módulo del set):

* **Mixin** ``al.import.payroll.mixin``: carga de ``.xlsx``/``.xlsm``
  con openpyxl (sin xlrd ni auto-pip), detección de hojas, fila de
  inicio configurable, procesamiento por lotes con commit por lote,
  manejo de errores por fila con sugerencia de corrección, reporte
  xlsx de resultados y **plantilla Excel descargable** generada con
  openpyxl.
* **Progreso en vivo**: modelo ``al.import.payroll.progress`` +
  widget OWL con polling; la importación corre en un hilo con cursor
  propio y el avance se publica con un cursor dedicado.
* **Importadores portados de v18**: asistencias (``hr.attendance``,
  con zona horaria) y reglas salariales (``hr.salary.rule``).
* **Plantillas nuevas por dominio** (sustituyen a ``hr_importers`` y
  ``hr_vacation_import`` v18, veredictos #15/#20 = D):

  - Inputs de boletas (``hr.payslip`` de un lote, novedades por
    documento + código de input).
  - Récord vacacional (saldos iniciales de ``hr.vacation.rest``).
  - Adelantos (``hr.advance``).
  - Datos PE de la versión del empleado (campos PLAME de
    ``hr.version``).

Multicompañía: ``company_id`` en wizards y progreso, ``check_company``
y regla de registro por compañía en el historial.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-PLANILLAS/Apps',
    'version': '2.20260722',
    'license': 'LGPL-3',
    'depends': [
        'al_hr_pe',
        'al_hr_pe_benefits',
        'al_hr_pe_account',
        'al_hr_pe_attendance',
        'al_hr_pe_reports',
    ],
    'external_dependencies': {
        'python': ['openpyxl'],
    },
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/import_payroll_progress_views.xml',
        'wizards/hr_attendance_import_wizard_views.xml',
        'wizards/hr_salary_rule_import_wizard_views.xml',
        'wizards/hr_payslip_input_import_wizard_views.xml',
        'wizards/hr_vacation_rest_import_wizard_views.xml',
        'wizards/hr_advance_import_wizard_views.xml',
        'wizards/hr_version_import_wizard_views.xml',
        'views/hr_attendance_views.xml',
        'views/hr_salary_rule_views.xml',
        'views/import_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'al_hr_pe_import/static/src/js/import_payroll_list_view.js',
            'al_hr_pe_import/static/src/js/hr_attendance_list_view.js',
            'al_hr_pe_import/static/src/js/hr_salary_rule_list_view.js',
            'al_hr_pe_import/static/src/xml/hr_attendance_list_buttons.xml',
            'al_hr_pe_import/static/src/xml/hr_salary_rule_list_buttons.xml',
            'al_hr_pe_import/static/src/components/import_progress/import_progress.js',
            'al_hr_pe_import/static/src/components/import_progress/import_progress.xml',
        ],
    },
    'installable': True,
    'application': False,
}
