{
    'name': 'Cobranza (AL)',
    'summary': 'Gestión de cobranza: cartera por gestor, gestiones, compromisos de pago, proyección '
               'de cobranza, metas, indicadores, estado de cuenta y notificaciones.',
    'description': """
Cobranza
========
Aplicación de cobranza sobre el seguimiento nativo de Odoo (account_followup), cuyo
responsable es el **gestor de cobranza** del cliente:

* **Cartera** por gestor y zona con antigüedad, tramos y compromiso vigente.
* **Gestiones** (llamada, visita, correo, WhatsApp, SMS, carta) con su resultado y la
  próxima acción del gestor.
* **Compromisos de pago** evaluados solos al vencer: cumplido, parcial o incumplido.
* **Proyección de cobranza** por semanas o meses: compromiso, atraso promedio del cliente
  y probabilidad por antigüedad; proyectado frente a lo cobrado; tabla dinámica y Excel.
* **Metas** de cobranza por gestor y **tablero** de indicadores (vencido, DSO, cumplimiento).
* **Estado de cuenta** en PDF y por correo.
* **Notificaciones**: recordatorio de compromisos al cliente, alerta de incumplidos al
  gestor, resumen diario a cada gestor y niveles de seguimiento en español.

Excluye de la cartera los anticipos (122) y las detracciones por cobrar.
""",
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    'icon': '/al_l10n_pe_collection/static/description/icon.svg',
    'version': '1.20261021',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['account_followup', 'account_reports', 'al_account_base', 'al_report_base', 'mail'],
    'data': [
        'security/collection_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/collection_bucket_data.xml',
        'data/collection_result_data.xml',
        'report/statement_report.xml',
        'data/mail_template_data.xml',
        'data/ir_cron_data.xml',
        'views/collection_config_views.xml',
        'views/collection_action_views.xml',
        'views/collection_promise_views.xml',
        'views/collection_portfolio_views.xml',
        'views/collection_forecast_views.xml',
        'views/collection_target_views.xml',
        'views/collection_dashboard_views.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/statement_send_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
}
