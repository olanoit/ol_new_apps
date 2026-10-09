# -*- coding: utf-8 -*-
{
    'name': 'Perú - Libro de Reclamaciones',
    'summary': 'Libro de Reclamaciones físico y virtual conforme al Código del Consumidor y '
               'al D.S. 011-2011-PCM: hoja del Anexo I, constancia por correo, plazo de 15 '
               'días hábiles, respuesta, SIREC y multicompañía.',
    'description': """
Libro de Reclamaciones (Perú)
=============================
Construido desde las normas vigentes a octubre de 2026 (Ley 29571 modificada por
las leyes 31435 y 32495, D.S. 011-2011-PCM y modificatorias hasta el D.S.
101-2022-PCM, D.S. 032-2021-PCM y Directiva SIREC). Requisitos en
``docs/reclamaciones/REQUISITOS_LEGALES.md``.

* **Libros por establecimiento** con código de identificación, dirección y
  numeración correlativa ``000000001-AAAA`` por libro y año.
* **Formulario web** sin registro ni inicio de sesión, adaptado a móvil, con
  validación de los datos sin los cuales la hoja «se tiene por no presentada»,
  adjuntos y protección contra envíos automáticos.
* **Constancia inmediata**: la hoja del Anexo I (D.S. 101-2022-PCM) en PDF,
  con fecha y hora, se envía al correo del consumidor y se puede imprimir.
* **Plazo de 15 días hábiles improrrogables** con el calendario de feriados de
  la compañía, suspensión de hasta 5 días hábiles por oferta de solución a
  distancia, alertas y vencidos.
* **Respuesta** por correo con la hoja completada, recalificación de queja a
  reclamo, solución acordada («ACUERDO ACEPTADO…»).
* **Libro de respaldo** y canales presencial y telefónico.
* **SIREC**: exportación del archivo de carga masiva.
* **Aviso** del Anexo II imprimible y enlace permanente en el pie del sitio web.
* Conservación de 2 años, multicompañía y datos personales solo para el
  equipo de atención.
""",
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-INVOICING/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/helpdesk/static/description/icon.png',
    'version': '7.20261009',
    'license': 'OPL-1',
    'depends': ['mail', 'portal', 'website', 'resource'],
    'data': [
        'security/complaints_book_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'data/mail_templates.xml',
        'report/complaint_report.xml',
        'report/complaint_templates.xml',
        'views/complaint_book_views.xml',
        'views/complaint_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/complaint_sirec_wizard_views.xml',
        'wizard/complaint_settlement_wizard_views.xml',
        'views/menus.xml',
        'views/website_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'al_l10n_pe_complaints_book/static/src/scss/complaints_book.scss',
            'al_l10n_pe_complaints_book/static/src/interactions/complaint_form.js',
        ],
    },
    'installable': True,
    'application': True,
}
