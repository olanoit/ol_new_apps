# -*- coding: utf-8 -*-
{
    'name': 'Portal de obra: caja chica y entrega a rendir (AL)',
    'summary': 'El residente registra en el portal de obra los comprobantes que paga con su '
               'caja chica o entrega a rendir, los rinde y ve su saldo, sin ficha de empleado.',
    'description': """
Portal de obra: caja chica y entrega a rendir
=============================================
Paquete 6, CR-55. Puente entre el portal de obra y las entregas a rendir y
cajas chicas de *al_l10n_pe_cash_fund* (se instala solo con los dos). El
fondo es del contacto del residente: sirve igual para un trabajador en
planilla y para un locador sin ficha de empleado, sin pasar por Gastos.

* **Registrar un comprobante**: foto, tipo de comprobante, RUC del emisor,
  número, fecha, monto, la obra y la partida o los gastos generales de la
  obra. Se crea la factura del proveedor en borrador, con la analítica de la
  obra y la foto, para que Contabilidad la revise.
* **Rendir**: el residente elige sus comprobantes y arma la rendición del
  fondo en borrador.
* **Su saldo**: entregado, rendido, aprobado y por rendir.
* Contabilidad revisa los comprobantes, los publica y confirma la rendición
  en el escritorio, como hoy.

Funciona sin señal: cada registro entra a la cola del portal.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    'icon': '/al_construction_portal_cash_fund/static/description/icon.png',
    'version': '1.20261107',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['al_construction_portal', 'al_l10n_pe_cash_fund'],
    'data': [
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
}
