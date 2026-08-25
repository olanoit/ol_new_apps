# -*- coding: utf-8 -*-
{
    'name': 'Numeración de asientos por secuencia (AL)',
    'summary': 'Secuencia ir.sequence OPCIONAL por diario para controlar la '
               'numeración (serie-correlativo SUNAT) de los comprobantes.',
    'description': """
Numeración de asientos por secuencia — opcional por diario
===========================================================
Adaptación a Odoo 19 del módulo OCA ``account_move_name_sequence``
(Akretion/Vauxoo, AGPL-3), rediseñado como **opt-in por diario**: el
módulo OCA original fuerza la secuencia en TODOS los diarios y desactiva
globalmente el mecanismo nativo; aquí cada diario decide.

* Casilla **"Numerar por secuencia"** en el diario (desactivada por
  defecto): sin marcar, el diario numera exactamente igual que el Odoo
  estándar (incluida la numeración latam por tipo de documento).
* Con la casilla marcada, al publicar cada asiento el número sale de la
  **ir.sequence del diario** (se crea una automáticamente al activar si
  no se elige ninguna). Secuencia separada opcional para notas de
  crédito.
* **Facturación electrónica peruana**: configure el prefijo de la
  secuencia con la serie y relleno 8 — p. ej. prefijo ``F001-`` para
  facturas, ``B001-`` para boletas, ``FC01-`` para NC. El nombre
  resultante (``F001-00000001``) es a la vez el número de documento
  latam (serie-folio SUNAT) que consumen el EDI, el QR y los reportes.
* Implementación ``no_gap`` por defecto: sin huecos de numeración (los
  exige SUNAT); se omite el aviso nativo de "hueco en la secuencia" en
  estos diarios.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNT/Apps',
    'version': '6.20260721',
    'license': 'OPL-1',
    'depends': [
        'account',
        'l10n_latam_invoice_document',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/edi_invoice_series_views.xml',
        'views/account_journal_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
}
