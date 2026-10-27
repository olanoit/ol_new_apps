{
    'name': 'Cobranza (AL)',
    'summary': 'Gestión de cobranza: cartera por gestor, gestiones, compromisos de pago, reclamos, cobranza judicial, '
               'calificación de riesgo, bloqueo de crédito, intereses, provisión de cobranza dudosa, '
               'centrales de riesgo, proyección, metas y estado de cuenta.',
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
* **Tablero** nativo de Odoo 19 (hoja de cálculo en la app Tableros): cartera, vencido,
  tramos, gestores, vencimientos, compromisos y cobrado, con filtros por gestor, zona,
  cliente y periodo.
* **Metas** de cobranza por gestor e indicadores del gestor (vencido, DSO, cumplimiento).
* **Estado de cuenta** en PDF y por correo.
* **Notificaciones**: recordatorio de compromisos al cliente, alerta de incumplidos al
  gestor, resumen diario a cada gestor y niveles de seguimiento en español.
* **Calificación de riesgo** (A–D) y **cola de trabajo** del gestor ordenada por prioridad.
* **Bloqueo de crédito** por mora (automático o manual) con liberación del administrador.
* **Reclamos**: los documentos discutidos salen del seguimiento y de las centrales.
* **Protección al consumidor** (art. 62, Ley 29571): horario, fines de semana, feriados y
  recordatorios previos solo con consentimiento.
* **Intereses moratorios** (TEA pactada) en el estado de cuenta y por nota de débito.
* **Provisión y castigo de cobranza dudosa** (art. 21 f y g del Reglamento de la LIR) con
  **expediente de cobranza** en PDF como sustento.
* **Centrales de riesgo**: aviso previo, reporte, retiro al pagar y Excel.
* **Comisiones** de gestores y agencias sobre lo recuperado, con escala por antigüedad de
  la deuda, descuento de cobros revertidos y factura de proveedor de la agencia.
* **Agencias externas**: cartera asignada por fechas; sus usuarios solo ven esos clientes
  y sus documentos, sin entrar a Contabilidad.
* **Cobranza judicial**: proceso por deudor (vía, juzgado, expediente, actuaciones con
  plazos y gastos) que sustenta la provisión y el castigo de la cobranza dudosa.
* **Predicción de la fecha de pago** de cada cuota (historial del cliente o de la
  cartera, atraso que ya lleva, estacionalidad y compromisos), con su confianza y su
  error medido; la usan la cartera («se atrasará») y la proyección.
* **Pago en línea**: enlace y QR para pagar el saldo con las pasarelas activas (Culqi,
  Niubiz, Izipay…) en los avisos y el estado de cuenta; el pago se aplica a las
  facturas más antiguas.

Excluye de la cartera los anticipos (122) y las detracciones por cobrar.
""",
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    'icon': '/al_l10n_pe_collection/static/description/icon.png',
    'version': '12.20261027',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['account_followup', 'account_payment', 'account_reports', 'al_account_base', 'al_report_base', 'mail',
                'spreadsheet_dashboard'],
    'data': [
        'security/collection_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/collection_bucket_data.xml',
        'data/collection_result_data.xml',
        'data/collection_rate_cap_data.xml',
        'data/collection_commission_data.xml',
        'report/statement_report.xml',
        'report/collection_file_report.xml',
        'data/mail_template_data.xml',
        'data/ir_cron_data.xml',
        'views/collection_rate_cap_views.xml',
        'views/collection_dispute_views.xml',
        'views/collection_provision_views.xml',
        'views/collection_bureau_views.xml',
        'data/mail_template_bureau_data.xml',
        'views/collection_config_views.xml',
        'views/collection_action_views.xml',
        'views/collection_promise_views.xml',
        'views/collection_portfolio_views.xml',
        'views/collection_forecast_views.xml',
        'views/collection_target_views.xml',
        'views/collection_commission_views.xml',
        'views/collection_agency_views.xml',
        'views/collection_lawsuit_views.xml',
        'views/collection_dashboard_views.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/statement_send_views.xml',
        'wizard/interest_invoice_views.xml',
        'views/menus.xml',
        'data/collection_dashboard_data.xml',
    ],
    'installable': True,
    'application': True,
}
