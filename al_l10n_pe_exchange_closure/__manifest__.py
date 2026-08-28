# -*- coding: utf-8 -*-
{
    'name': 'PE - Cierre de tipo de cambio (AL)',
    'summary': 'Ajuste mensual por diferencia de cambio de las partidas '
               'monetarias en moneda extranjera: T.C. compra para activos y '
               'T.C. venta para pasivos (art. 61 LIR / art. 34 Reglamento).',
    'description': """
Cierre de tipo de cambio — Perú
================================
Genera el asiento mensual de ajuste por diferencia de cambio de las cuentas
de balance denominadas en moneda extranjera, según la norma peruana:

* **Art. 34.d del Reglamento de la LIR**: las partidas que originan
  **activos** se ajustan al **T.C. promedio ponderado compra** y las que
  originan **pasivos** al **T.C. promedio ponderado venta** publicados por
  la SBS/SUNAT a la fecha del balance.
* **Art. 61 de la LIR / NIC 21**: la diferencia de cambio de partidas
  monetarias es resultado computable del ejercicio (676 pérdida / 776
  ganancia), no una provisión reversible.

Cómo funciona
-------------
1. Se marcan las cuentas de balance en el plan contable como *cierre de
   T.C. sin detalle* (consolidado por cuenta) o *con detalle* (por socio).
2. Cada mes se crea un cierre, se trae el T.C. de la fecha de balance y se
   calcula.
3. El ajuste de cada grupo es::

       ajuste = saldo_ME_acumulado × T.C._cierre − saldo_MN_contabilizado

   Al usar **saldos acumulados** (todos los apuntes publicados hasta la
   fecha de cierre, incluidos los ajustes de cierres anteriores y las
   diferencias de cambio realizadas que genera Odoo al conciliar), el
   cálculo es auto-corrector: nunca duplica ni omite el ajuste de meses
   previos y no necesita histórico paralelo de saldos.
4. La contrapartida va a las cuentas nativas de diferencia de cambio de la
   compañía (776 ganancia / 676 pérdida), con una línea por cada
   distribución analítica distinta.

Distribución analítica
----------------------
La diferencia de cambio de una factura cae en el mismo centro de costo que
la factura: cada renglón hereda la analítica de los apuntes que forman su
saldo (para las cuentas de balance, la de las líneas de ingreso o gasto de
sus documentos), ponderada por importe. Solo se distribuye la línea de
resultado: si la línea de balance llevara la misma distribución, su apunte
analítico saldría con signo contrario y ambos se anularían.

Diferencias frente al módulo v18 ``al_exchange_rate_closure``
-------------------------------------------------------------
* Se elimina el modelo de "saldos anteriores" (``tc_close_acc_line_all``) y
  su recálculo mes a mes: el saldo acumulado ya lo resuelve.
* Se elimina el cron que cancelaba automáticamente asientos publicados de
  diferencia de cambio (riesgo contable).
* Se agrupa con ``_read_group`` en vez de cargar todos los apuntes del año
  en campos Many2many almacenados.
* Se busca el diario por configuración de compañía, no por el código
  literal ``CTC``; y las cuentas por ``id``, no por ``code`` (en Odoo 19 el
  código de cuenta depende de la compañía).
* Contrapartida separada en ganancia y pérdida en vez de una sola neta.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'countries': ['pe'],
    'category': 'OL-ACCOUNT/Apps',
    'version': '2.20260828',
    'license': 'OPL-1',
    'depends': [
        'al_account_base',
        'al_l10n_pe_currency',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/account_account_views.xml',
        'views/account_move_views.xml',
        'views/exchange_closure_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
}
