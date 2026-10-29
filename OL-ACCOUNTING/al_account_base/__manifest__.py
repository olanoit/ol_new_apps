# -*- coding: utf-8 -*-
{
    'name': 'PE - Base Contabilidad (AL)',
    'summary': 'Personalizaciones genéricas de la localización contable '
               'peruana: glosa en asientos/líneas, menú "Perú" y utilidades '
               'compartidas.',
    'description': """
Base de contabilidad Perú
=========================
Módulo base y liviano del que dependen las demás personalizaciones AL de la
localización peruana. Provee:

* Glosa (`l10n_pe_gloss`) en asientos contables y sus líneas.
* Menú raíz "Perú" y su rama de Configuración.
* Utilidad `account.move.l10n_pe_is_pe()`.
* Sección «Documentación» al final de Ajustes ▸ Perú: URL del sitio de
  documentación de la suite (MkDocs) y accesos a sus secciones
  (documentación para usuarios, novedades, localización y nómina peruanas y
  desarrollador).

Sin código muerto: reemplaza a la versión previa que arrastraba placeholders y
campos sin uso.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-ACCOUNTING/Apps',
    # Ícono propio de la app, con el estilo de Odoo 19 (icon.svg 50×50).
    'icon': '/al_account_base/static/description/icon.png',
    'version': '21.20261029',
    'license': 'OPL-1',
    # El formato de los documentos impresos (encabezado, pie y estilos del
    # comprobante A4) vive en al_report_base, común a toda la suite.
    # l10n_latam_invoice_document: tipo de documento del comprobante modificado
    # de las notas cuyo original no está en Odoo (PLE y SIRE).
    'depends': ['account', 'al_report_base', 'l10n_latam_invoice_document', 'l10n_pe'],
    'data': [
        'security/ir.access.csv',
        'data/l10n_pe_bank_data.xml',
        'views/res_company_views.xml',
        'views/res_config_settings_views.xml',
        'views/account_move_views.xml',
        'views/pe_base_views.xml',
        'views/menu_pe.xml',
        'reports/report_pe_document.xml',
    ],
    'installable': True,
    'application': False,
}
