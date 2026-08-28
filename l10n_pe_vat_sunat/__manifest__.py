# -*- coding: utf-8 -*-
{
    'name': "Búsqueda RUC/DNI desde SUNAT",
    'summary': "Consulta y actualización automática de datos de RUC y DNI "
               "desde el portal SUNAT, ApiPerú, Apis.net.pe y JSON-PE. "
               "Padrón de buenos contribuyentes y agentes de retención "
               "con caché diaria.",
    'description': """
Consulta de RUC/DNI peruanos **configurable por datos** (Odoo 19):

* Cada compañía define un One2many de **conexiones** de API
  (``l10n_pe.api.connection``) con su prioridad; la consulta usa la
  primera que responda y hace fallback en cascada.
* Por cada conexión se **mapea dinámicamente** cada atributo de la
  respuesta a un campo de Odoo (``l10n_pe.api.field.mapping``): agregar
  una API nueva es configuración, no código.
* Motor unificado: normaliza toda respuesta a ``dict`` (JSON REST o
  resultado de scraper SUNAT) y aplica el mismo mapeo. Soporta rutas con
  puntos, plantillas de concatenación y transformaciones.
* Scrapers SUNAT (oficial/multi) como engine especial; APIs REST/JSON
  totalmente configurables.
* Padrón SUNAT (buenos contribuyentes, agentes de retención) con caché
  en BD y sincronización diaria vía ``ir.cron``.
* Resolución de ubigeo / distrito / ciudad / departamento configurable
  por conexión.
""",
    'author': "OLANOIT",
    'maintainer': "CRISTÓBAL OCH <olanoit@gmail.com>",
    'website': "https://github.com/olanoit",
    'category': 'OL-ACCOUNT/Apps',
    'countries': ['pe'],
    'version': '7.20260828',
    'license': 'OPL-1',
    'depends': [
        'base',
        'base_vat',
        'contacts',
        'l10n_latam_base',
        'l10n_pe',
        'al_account_base',
    ],
    'external_dependencies': {
        'python': ['requests', 'beautifulsoup4'],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/l10n_pe_api_connection_views.xml',
        'views/l10n_pe_sunat_padron_views.xml',
        'views/res_company_views.xml',
        'views/res_config_settings_views.xml',
        'views/res_partner_view.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
}
