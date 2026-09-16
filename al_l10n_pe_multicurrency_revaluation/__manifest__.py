# -*- coding: utf-8 -*-
{
    'name': 'PE - T.C. compra/venta en ganancias y pérdidas no realizadas',
    'summary': 'Revalúa cada cuenta con el tipo de cambio SUNAT de compra o '
               'de venta en el informe de ganancias/pérdidas de moneda no '
               'realizadas, y muestra el T.C. aplicado en cada línea.',
    'description': """
T.C. compra/venta en ganancias y pérdidas no realizadas
=======================================================
Extiende el informe de Enterprise **Ganancias/pérdidas de moneda no
realizadas** para compañías peruanas:

* Cada cuenta que puede tener saldos en moneda extranjera indica si se
  revalúa con el **T.C. compra** o el **T.C. venta** de SUNAT (campos
  ``rate_purchase`` / ``rate_sale`` de ``al_l10n_pe_currency``). Sin
  tipo de cambio para la fecha, la cuenta usa el genérico del informe.
* Nueva columna **T.C.** con el tipo de cambio aplicado, en soles por unidad
  de moneda extranjera (``S/ 3.750``); queda en blanco en los totales que
  mezclan tipos de cambio distintos.
* La cabecera de cada moneda se muestra como ``USD (1 USD = S/ 3.750)``.
* El asiento de ajuste cita en cada línea el T.C. realmente aplicado.

Para las demás compañías el informe queda exactamente como el nativo (sin
columna T.C.).

Diferencias frente al módulo v18 ``mblz_l10n_pe_multicurrency_revaluation``
----------------------------------------------------------------------------
* No copia la consulta SQL de Enterprise: ejecuta la original una vez por
  grupo de cuentas (genérico, compra y venta), cada una con su dominio y sus
  tasas, y suma los resultados.
* Compra y venta se leen del mismo registro de tasa (``al_l10n_pe_currency``)
  en lugar de dos registros con ``exchange_rate``.
* El campo se llama ``l10n_pe_revaluation_rate_type`` para no chocar con el
  de ``al_l10n_pe_exchange_closure``, que tiene otro significado.
* Las cuentas de ingresos y gastos no muestran el campo: el informe nunca las
  revalúa.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'Accounting/Localizations',
    'version': '1.20260916',
    'license': 'OPL-1',
    'depends': [
        'account_reports',
        'al_account_base',
        'al_l10n_pe_currency',
    ],
    'data': [
        'data/account_report_multicurrency_revaluation.xml',
        'views/account_account_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
}
