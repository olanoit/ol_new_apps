# -*- coding: utf-8 -*-
{
    'name': 'Planillas Perú - Núcleo (AL)',
    'summary': 'Localización peruana de nómina: tablas PLAME/AFP, campos '
               'laborales en hr.version, reglas salariales SUNAT y '
               'exportadores PLAME/AFPNet.',
    'description': """
Planillas Perú — Núcleo de la localización
===========================================
Refactor a Odoo 19 de la suite v18 ``al_hr_payroll`` (27 módulos → 5),
según ``docs/planillas/PLAN_MIGRACION_PLANILLAS_V19.md``.

Este núcleo aporta (por fases):

* **Fase 0 (actual)**: esqueleto + PoC — campos laborales peruanos en
  ``hr.version`` (régimen laboral, CUSPP, tipo de comisión AFP) visibles
  en la ficha y verificados con una nómina calculando sobre ellos.
* Fase 1: tablas maestras PLAME (TABLA 08/15/17/21), AFP/ONP, EsSalud,
  periodos, UIT/RMV por año fiscal, ``hr.main.parameter`` por compañía.
* Fase 2: reglas salariales peruanas, snapshot de versión en la boleta,
  exportadores PLAME (.rem/.jor/.snl/.toc) y AFPNet como adjuntos.

Multicompañía por diseño: ``_check_company_auto``, reglas por compañía y
cero códigos hardcodeados (ver plan §5).
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-PLANILLAS/Apps',
    'version': '12.20260901',
    'license': 'OPL-1',
    'depends': [
        'hr_payroll',
        'hr_payroll_account',
        'l10n_latam_base',
        'l10n_pe',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/hr_worker_type.xml',
        'data/hr_situation.xml',
        'data/hr_reasons_leave.xml',
        'data/hr_suspension_type.xml',
        'data/hr_social_insurance.xml',
        'data/hr_contributions.xml',
        'data/hr_membership.xml',
        'data/l10n_latam_identification_type_data.xml',
        'data/hr_uit_data.xml',
        'data/hr_salary_rule_category_data.xml',
        'data/hr_payroll_structure_type_data.xml',
        'data/hr_payroll_structure_data.xml',
        'data/hr_work_entry_type_data.xml',
        'data/hr_payslip_input_type_data.xml',
        'data/hr_salary_rule_data.xml',
        'data/hr_tregistro_catalogs.xml',
        'data/l10n_pe.hr.occupation.csv',
        'data/l10n_pe.hr.education.institution.csv',
        'data/l10n_pe.hr.education.career.csv',
        'data/hr_dependent_data.xml',
        # Primero: define el menú «Perú» y sus grupos, de los que
        # cuelgan los menús declarados en los demás archivos.
        'views/menus.xml',
        'views/hr_catalogs_views.xml',
        'views/hr_dependent_views.xml',
        # Antes que hr_tregistro_views.xml: define la vista de lista
        # «hr_version_list_view_inherit_pe» de la que aquél hereda.
        'views/hr_version_views.xml',
        'views/hr_tregistro_views.xml',
        'views/hr_period_views.xml',
        'views/hr_main_parameter_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_payslip_views.xml',
        # El último: reorganiza el árbol de «Configuración ▸ Perú».
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
}
