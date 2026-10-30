# -*- coding: utf-8 -*-
{
    'name': 'PE - Retenciones de IGV (AL)',
    'summary': 'Régimen de Retenciones del IGV (R.S. 037-2002/SUNAT): '
               'agente de retención, aplicabilidad con excepciones y '
               'retención del 3% en el pago sobre el marco nativo.',
    'description': """
Régimen de Retenciones del IGV — SUNAT
======================================
Fases 0-5 del plan (``docs/retencion/PLAN_MODULO_al_l10n_pe_retention.md``):

* Configuración en Ajustes ▸ Perú: agente de retención, tasa (3 %), monto
  mínimo (S/ 700) e impuesto de retención en el pago (marco nativo
  ``l10n_account_withholding_tax``).
* Contactos: «Agente de retención» y «Buen contribuyente» del padrón
  SUNAT (``l10n_pe_vat_sunat``), verificados contra el padrón oficial y
  corregibles a mano.
* Aplicabilidad en la factura de proveedor con las excepciones SUNAT:
  monto mínimo, operaciones entre agentes, buenos contribuyentes,
  boletas sin crédito fiscal y operaciones con detracción (SPOT).

Basado en el análisis del proceso completo v17 (``l10n_pe_retention``) y
la referencia CRE del v18 (``al_l10n_pe_edi_withholding``).
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-ACCOUNTING/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/al_l10n_pe_retention/static/description/icon.png',
    'version': '25.20261027',
    'license': 'OPL-1',
    'depends': [
        'al_account_base',
        'l10n_account_withholding_tax',
        'l10n_latam_invoice_document',
        # código SUNAT de los impuestos (IGV) para las excepciones
        'l10n_pe',
        # Firma y envío del CRE con el proveedor electrónico de la compañía
        'l10n_pe_edi',
        # Servicio de envío de CPE (sendBill/sendSummary) sobre l10n_pe_edi 20
        'al_l10n_pe_edi_service',
        # El padrón SUNAT es la fuente de «buen contribuyente» y «agente
        # de retención» del contacto: las dos excepciones al régimen.
        'l10n_pe_vat_sunat',
    ],
    'data': [
        'data/ir_sequence_data.xml',
        'data/cre_reversal_templates.xml',
        'views/res_config_settings_views.xml',
        'views/account_move_views.xml',
        'views/retention_menu_views.xml',
        'views/retention_document_views.xml',
        'views/retention_views.xml',
        'reports/retention_report.xml',
        'security/ir.access.csv',
    ],
    'post_init_hook': 'post_init_hook',
    # Solo en bases con datos de demostración, en «PE Company» (l10n_pe).
    'demo': ['demo/al_l10n_pe_retention_demo.xml'],
    'installable': True,
    'application': False,
}
