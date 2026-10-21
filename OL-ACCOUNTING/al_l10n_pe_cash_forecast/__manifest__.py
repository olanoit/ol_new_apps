{
    'name': 'PE - Flujo de caja proyectado (AL)',
    'summary': 'Proyección de cobros y pagos por semana o mes desde los saldos de bancos, '
               'las cuentas por cobrar y por pagar, cheques, depósitos a plazo y partidas '
               'manuales, con escenario editable y comparación con lo real.',
    'description': """
Flujo de caja proyectado
========================
* Saldo inicial de bancos y caja disponibles (sin cuentas restringidas como la de
  detracciones del Banco de la Nación ni la cartera de cheques de terceros).
* Ingresos y egresos esperados por semana o mes: cobros y pagos en tránsito, cuentas
  por cobrar y por pagar por vencimiento (incluidas las letras), cheques propios por
  debitar y de terceros en cartera, depósitos a plazo que vencen, detracciones por
  pagar y partidas manuales (planilla, impuestos, préstamos).
* Escenario: la fecha esperada y el importe de cada partida se pueden cambiar y se
  conservan al actualizar. Lo vencido entra en el primer periodo.
* Proyectado frente a real (movimiento de bancos y caja) en los periodos transcurridos.
* Vista pivote y gráfico por periodo y tipo; exportación a Excel.
""",
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-ACCOUNTING/Apps',
    'icon': '/account/static/description/icon.png',
    'version': '1.20261021',
    'license': 'OPL-1',
    'countries': ['pe'],
    'depends': ['al_account_base'],
    'data': [
        'security/ir.model.access.csv',
        'security/cash_forecast_security.xml',
        'views/cash_forecast_views.xml',
        'views/account_journal_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
