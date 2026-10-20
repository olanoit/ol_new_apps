# Parte de al_l10n_pe_sire. Ver LICENSE del repositorio para detalles.
{
    'name': 'Perú - SIRE (RVIE / RCE)',
    'summary': 'Conciliación con el Sistema Integrado de Registros Electrónicos de SUNAT',
    'description': """
Sistema Integrado de Registros Electrónicos (SIRE) — SUNAT Perú
===============================================================
Descarga la propuesta del Registro de Ventas e Ingresos Electrónico (RVIE) y del
Registro de Compras Electrónico (RCE) vía la API REST de SUNAT, la compara con los
comprobantes registrados en Odoo y genera los archivos de reemplazo (TXT) y de
trabajo (XLSX).

* Solicitud de propuesta, consulta de ticket y descarga por API (OAuth2 + clave SOL).
* Carga manual del TXT exportado desde SUNAT Operaciones en Línea.
* Comparación por CAR SUNAT con campos configurables y detalle de diferencias.
* Exportación XLSX (hojas SIRE y Sistema) y TXT de reemplazo con nombre oficial.
* Envío a SUNAT por API: aceptación de la propuesta, carga del reemplazo (TUS) y
  registro del preliminar; la generación del registro se completa en el portal.
* Validación al publicar: cada comprobante pasa por las reglas del registro
  (RUC, DNI, serie, nota sin documento, boleta sobre S/ 700, IGV) al publicarse.
* Roles: el aprobador SIRE envía, cierra y reabre (con motivo); el contable prepara.
* Bitácora de cada llamada a la API (90 días) y prueba de conexión.
""",
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-ACCOUNTING/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/account/static/description/icon.png',
    'version': '22.20261012',
    'license': 'OPL-1',
    'depends': [
        'al_account_base',
        'l10n_pe_edi',
    ],
    'external_dependencies': {
        'python': ['xlsxwriter', 'requests'],
    },
    'data': [
        'security/sire_security.xml',
        'security/ir.model.access.csv',
        'data/sire_compare_fields.xml',
        'data/sire_cron.xml',
        'data/res_country_sire.xml',
        'views/account_move_views.xml',
        'views/sire_compare_field_views.xml',
        'views/sire_rce_views.xml',
        'views/sire_rvie_views.xml',
        'views/sire_operation_views.xml',
        'views/sire_line_views.xml',
        'views/res_country_views.xml',
        'views/sire_api_log_views.xml',
        'wizard/sire_action_wizard_views.xml',
        'wizard/sire_reopen_wizard_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
}
