# -*- coding: utf-8 -*-
{
    'name': 'Planillas Perú - Asistencia y turnos (AL)',
    'summary': 'Capa peruana sobre planning EE: régimen atípico, monitor de asistencia, tareaje y horas extra.',
    'description': """
Planillas Perú - Asistencia y turnos (AL)
=========================================
Módulo del refactor de planillas v18 → v19 (27 módulos → 5); ver
``docs/planillas/PLAN_MIGRACION_PLANILLAS_V19.md``.

Fase 6 (actual):

* **Turnos PE sobre planning EE** (sin clonar el gantt): tipos de
  turno en el rol nativo, jornada nocturna detectada en la plantilla,
  ciclos atípicos N×M (``l10n_pe.hr.shift.cycle``, D.S. 004-2006-TR)
  con validador legal (promedio semanal ≤ 48 h, tope 12 h/día) y
  generación de ``planning.slot`` TZ-aware.
* **Monitor de asistencia** (``l10n_pe.hr.attendance.monitor``):
  turno planificado vs marcación real, TZ-aware por recurso.
* **Fotocheck**: configuración por compañía + carné QWeb.
* **Tareaje** (``hr.tareaje.manager``): clasificación peruana de
  horas — nocturnidad 22:00-06:00 (art. 8 D.S. 007-2002-TR), HE 25 %
  las 2 primeras horas y 35 % después (art. 10), descanso/feriado
  laborado 100 % (D.Leg. 713) — con parámetros por compañía y volcado
  a la boleta por work entries (respeta el remapeo DLAB del núcleo).

Sustituye al clon de planning EE de ~2 700 líneas de v18
(``hr_assistance_planning``) y a ``hr_attendance_payslip``.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-PLANILLAS/Apps',
    'version': '4.20260802',
    'license': 'LGPL-3',
    'depends': [
        'al_hr_pe',
        'planning',
        'hr_payroll_planning',
        'hr_attendance',
        'hr_payroll_attendance',
        'hr_holidays',
        # El tareaje clasifica el día como feriado leyendo los descansos
        # globales del calendario (`_get_public_holidays`): sin el
        # calendario de feriados peruanos, todo feriado se contaría como
        # jornada ordinaria y no se aplicaría la sobretasa del 100 %.
        'al_hr_pe_public_holidays',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/planning_role_data.xml',
        'views/hr_shift_pe_views.xml',
        'views/hr_attendance_monitor_views.xml',
        'views/hr_fotocheck_views.xml',
        'views/hr_tareaje_views.xml',
        'report/hr_employee_badge.xml',
    ],
    'installable': True,
    'application': False,
}
