# -*- coding: utf-8 -*-
{
    'name': 'PE - Arrendamientos NIIF 16 (AL)',
    'summary': 'Contratos de alquiler como arrendatario según NIIF 16: pasivo por '
               'arrendamiento a valor presente, activo por derecho de uso con su '
               'depreciación y cuotas del arrendador contra el pasivo.',
    'description': """
Arrendamientos NIIF 16
======================
Alquileres de oficinas, almacenes y equipos tomados en arrendamiento:

* Contrato con arrendador, plazo, cuota mensual (al inicio o al final del
  periodo), tasa incremental de endeudamiento, costos directos iniciales e
  incentivos.
* Pasivo por arrendamiento = valor presente de las cuotas; activo por derecho
  de uso = pasivo + cuotas pagadas por adelantado + costos directos −
  incentivos. Tabla por el método del interés efectivo.
* Al confirmar: asiento de reconocimiento inicial, **activo** en
  ``account_asset`` (depreciación lineal en el plazo) y **pasivo** en
  ``account_loans`` (interés y capital de cada cuota, reclasificación a
  corto plazo), enlazados por un grupo de activos.
* «Registrar cuota»: factura del arrendador contra el pasivo (IGV y
  detracción los maneja la localización).
* Corto plazo (12 meses o menos) o bajo valor: exentos de NIIF 16, la cuota
  va a gasto de alquiler.

Requiere Odoo Enterprise (``account_asset`` y ``account_loans``).
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    # Ícono nativo de la app a la que pertenece (como las l10n de Odoo).
    'icon': '/account/static/description/icon.png',
    'version': '1.20261010',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['account_asset', 'account_loans', 'al_account_base'],
    'data': [
        'security/ir.model.access.csv',
        'security/lease_security.xml',
        'data/ir_sequence_data.xml',
        'views/lease_views.xml',
        'views/account_move_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
