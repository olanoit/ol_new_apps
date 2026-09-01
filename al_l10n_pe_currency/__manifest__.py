# -*- coding: utf-8 -*-
{
    'name': 'Tipo de cambio Perú (SUNAT)',
    'summary': 'Tipo de cambio SUNAT (compra/venta) para USD/PEN desde cuatro '
               'fuentes —SUNAT, BCRP, Decolecta y apis.net.pe—, con '
               'actualización diaria, registro manual coherente y '
               'visualización del T.C. aplicado en facturas en moneda '
               'extranjera.',
    'description': """
Tipo de cambio Perú — refactor Odoo 19
======================================
* Tasas de **compra y venta** de SUNAT en ``res.currency.rate`` (Odoo nativo
  solo maneja una tasa única), que se mantienen **coherentes con la tasa
  nativa**: registrar la venta recalcula ``rate`` y viceversa, de modo que la
  ficha nunca dice dos cosas distintas.
* Cuatro fuentes, todas con compra y venta:

  * **SUNAT** — TXT oficial, gratuito y sin token, solo del día publicado;
    es la del cron diario.
  * **BCRP** — series históricas del sistema bancario SBS (las que SUNAT toma
    para efectos tributarios), gratuitas, sin token y con el rango completo en
    una sola consulta.
  * **Decolecta** — tipo de cambio de SUNAT por fecha; reutiliza el token de
    la conexión configurada en ``l10n_pe_vat_sunat``.
  * **apis.net.pe** — alternativa histórica, con token.

* **Elección de compra o venta por comprobante**: cada factura lleva su tipo
  de cambio, propuesto desde el criterio configurado para compras y ventas, y
  la elección **cambia el importe en soles** (se engancha en
  ``_get_expected_currency_rate_at``). Por defecto se usa la venta, que es lo
  que manda el Reglamento de la Ley del IGV.
* Muestra en las facturas en moneda extranjera el **tipo de cambio aplicado,
  su fecha y si fue compra o venta**.
* Módulo autónomo: se eliminó la dependencia ``al_base_mixin`` (los campos de
  filtro de fechas viven en el propio asistente).
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'Accounting/Localizations',
    'version': '5.20260901',
    'license': 'OPL-1',
    'depends': ['account', 'al_account_base'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'security/ir.model.access.csv',
        'data/decimal_precision.xml',
        'data/res_currency_data.xml',
        'data/cron_data.xml',
        'wizard/create_exchange_rate_wizard.xml',
        'views/res_currency_views.xml',
        'views/account_move_views.xml',
        'views/account_payment_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
}
