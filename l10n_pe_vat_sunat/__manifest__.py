# -*- coding: utf-8 -*-
{
    'name': "Búsqueda RUC/DNI desde SUNAT",
    'summary': "Consulta y actualización automática de datos de RUC y DNI "
               "desde el portal SUNAT, ApiPerú, Apis.net.pe y JSON-PE. "
               "Padrón de buenos contribuyentes y agentes de retención "
               "con caché diaria.",
    'description': """
Módulo de consulta de RUC/DNI peruanos refactorizado para Odoo 19:

* Patrón Strategy para múltiples proveedores (SUNAT oficial,
  apis.net.pe, apiperu.dev, SUNAT Multi-RUC).
* Capa de servicios (``services/``) desacoplada del modelo ORM —
  testable de forma aislada y reutilizable desde otros módulos.
* HTTP con timeouts y reintentos centralizados.
* Padrón SUNAT (buenos contribuyentes, agentes de retención) con
  caché en BD y sincronización diaria vía ``ir.cron`` — no se
  descargan los ZIP de SUNAT en cada apertura del form.
* Resolución de ubigeo / distrito / ciudad / departamento
  centralizada con fallback robusto.
* Sin credenciales hardcodeadas: los tokens se configuran en
  Ajustes → Compañías → Servicio de Búsqueda.
""",
    'author': "OLANOIT",
    'maintainer': "CRISTÓBAL OCH <olanoit@gmail.com>",
    'website': "https://github.com/olanoit",
    'category': 'OL/Apps',
    'countries': ['pe'],
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'base_vat',
        'contacts',
        'l10n_latam_base',
        'l10n_pe',
    ],
    'external_dependencies': {
        'python': ['requests', 'beautifulsoup4'],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/ir_config_parameter.xml',
        'data/ir_cron.xml',
        'views/l10n_pe_sunat_padron_views.xml',
        'views/res_company_views.xml',
        'views/res_config_settings_views.xml',
        'views/res_partner_view.xml',
    ],
    'installable': True,
    'application': False,
}
