# -*- coding: utf-8 -*-
{
    'name': 'Planillas Perú - Documentos y bancos (AL)',
    'summary': 'Boleta de pago, certificados, contratos y archivos TXT de pago masivo bancario.',
    'description': """
Planillas Perú - Documentos y bancos (AL)
=========================================
Módulo del refactor de planillas v18 → v19 (27 módulos → 5); ver
``docs/planillas/PLAN_MIGRACION_PLANILLAS_V19.md``.

Fase 7 (actual):

* **Boleta de pago QWeb** (D.S. N° 001-98-TR): 3 columnas
  Ingresos/Descuentos/Aportes del empleador con códigos SUNAT,
  suspensiones T21, neto en letras; envío por correo con PDF adjunto
  y confirmación de recepción con token HMAC (``database.secret``).
* **Certificados y cartas**: certificado de trabajo, carta de
  disposición de CTS y certificado de rentas de 5ta categoría
  (wizards multi-empleado desde la ficha del empleado).
* **Contratos**: plantillas por compañía (``l10n_pe.hr.contract.template``)
  renderizadas sobre ``hr.version`` con placeholders ``{{...}}``
  (sin Jinja2); régimen de prueba LPCL Art. 10.
* **TXT de pago masivo bancario** (``hr.automate.multipayment``):
  haberes y CTS en los formatos propietarios BCP, BBVA, Interbank,
  Scotiabank y BanBif (paridad byte a byte con v18), desde lotes de
  boletas, quincena, CTS, gratificaciones y vacaciones.

Sustituye a ``hr_voucher``, ``hr_certificate_letter``,
``hr_print_contract`` y ``hr_automate_multipayment`` de v18
(``hr_contract_history`` no se porta: versionado nativo).
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-PLANILLAS/Apps',
    'version': '6.20260816',
    'license': 'LGPL-3',
    'depends': ['al_hr_pe_benefits'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/bank_codes_data.xml',
        'report/hr_payslip_voucher_report.xml',
        'data/payroll_structure_report_data.xml',
        'report/hr_certificates_report.xml',
        'report/hr_contract_report.xml',
        'report/hr_fifth_certificate_report.xml',
        'data/mail_template_boleta.xml',
        'views/hr_payslip_voucher_views.xml',
        'views/hr_certificates_views.xml',
        'views/hr_contract_template_views.xml',
        'views/hr_multipayment_views.xml',
        'data/contract_template_data.xml',
    ],
    'installable': True,
    'application': False,
}
