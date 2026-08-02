# -*- coding: utf-8 -*-
{
    'name': 'PE - Letras de cambio y canje (AL)',
    'summary': 'Canje, refinanciación y gestión de letras de cambio para '
               'clientes y proveedores (Perú).',
    'description': """
Letras de cambio y canje — Perú
================================
Gestión de letras de cambio y canje para la localización peruana:

* **Canje de letras (clientes/proveedores)**: convierte comprobantes
  pendientes en un canje (``l10n_pe.letter``) que reemplaza el saldo por
  cobrar/pagar por una obligación cambiaria. Estados:
  ``draft → checked → redeemed → banked``.
* **Generación masiva de letras**: a partir de un canje, crea N letras
  individuales repartiendo el saldo (total o parcial) según cantidad, fecha
  de vencimiento y rango de días.
* **Tipos de letra** ("En cartera", "Cobranza libre", "Descuento",
  "Protestada"), cada uno enrutado a la cuenta contable configurada por
  tipo de cuenta/letra/moneda.
* **Refinanciación de canjes**, individual o masiva (mismo socio, diario,
  moneda y compañía).
* **Residuales/redondeo** entre el total facturado y el total canjeado.
* **Vinculación de asientos** por referencia y reconciliación de las
  facturas originales al canjear.

Migrado desde ``ol_l10n_pe_account_letter`` (proyecto Inveragro) y
refactorizado al namespace ``l10n_pe.*`` del proyecto: usa el tipo de
cambio compra/venta de ``al_l10n_pe_currency`` en vez del helper multitasa
de ``ol_l10n_pe_account``, y ya no depende de
``ol_l10n_pe_account_withholdings`` ni de ``ol_partner_contact_type`` (no
se usaban en la lógica del módulo).
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-ACCOUNT/Apps',
    'version': '1.20260731',
    'license': 'LGPL-3',
    'depends': [
        'mail',
        'al_account_base',
        'al_l10n_pe_currency',
        'l10n_latam_invoice_document',
    ],
    'data': [
        # Seguridad
        'security/security_group.xml',
        'security/ir.model.access.csv',
        # Wizards
        'wizards/account_refinance_invoice_view.xml',
        'wizards/account_massive_refinance_view.xml',
        # Server actions
        'data/account_letter_server_actions.xml',
        # Vistas
        'views/letter_type_wizard_views.xml',
        'views/letter_massive_views.xml',
        'views/letter_line_views.xml',
        'views/letter_account_config_views.xml',
        'views/letter_views.xml',
        'views/account_move_view.xml',
        'views/account_move_line_view.xml',
        'views/letter_canje_wizard_views.xml',
        'views/menuitem_views.xml',
        # Datos
        'data/document_type_letter.xml',
        'data/ir_sequence_data.xml',
    ],
    'installable': True,
    'application': False,
}
