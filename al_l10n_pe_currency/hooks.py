# -*- coding: utf-8 -*-
"""Comprueba las cuentas de diferencia de cambio del plan peruano.

La localización oficial ya las asigna al cargar el plan contable
(``income_currency_exchange_account_id: chart776`` y
``expense_currency_exchange_account_id: chart676`` en ``template_pe.py`` de
``l10n_pe``), de modo que en una instalación normal no hay nada que hacer.
Esto es solo una red de seguridad para una compañía cuyo plan se cargara de
forma incompleta: sin esas cuentas, Odoo no puede registrar la ganancia o
pérdida al conciliar una factura en moneda extranjera con un cobro a otro tipo
de cambio, y el ajuste se pierde sin aviso.

Cuentas del PCGE:

* **676** Diferencia de cambio — pérdida.
* **776** Diferencia en cambio — ganancia.

**Ojo:** ambos campos de ``res.company`` dependen de la compañía activa, igual
que ``account.account.code``. Leerlos o escribirlos sin ``with_company``
devuelve vacío y, peor, un ``write`` en el contexto equivocado los borra.
"""
import logging

_logger = logging.getLogger(__name__)

# Prefijo del PCGE → campo de la compañía. Se busca por prefijo porque el plan
# desarrolla el código a distinta longitud según la versión (676, 6760000…).
EXCHANGE_ACCOUNTS = {
    'expense_currency_exchange_account_id': '676',
    'income_currency_exchange_account_id': '776',
}


def _l10n_pe_assign_exchange_accounts(env):
    """Rellena las cuentas de diferencia de cambio que falten.

    Devuelve las compañías en las que hizo falta actuar; vacío es lo normal.
    """
    repaired = env['res.company']
    companies = env['res.company'].search([]).filtered(
        lambda company: company.chart_template == 'pe')
    for company in companies:
        # Todo el trabajo se hace en el contexto de la compañía: es la única
        # forma de leer y escribir estos campos correctamente.
        target = company.with_company(company)
        values = {}
        for field, prefix in EXCHANGE_ACCOUNTS.items():
            if target[field]:
                continue
            account = env['account.account'].with_company(company).search([
                ('company_ids', 'in', company.id),
                ('code', '=like', '%s%%' % prefix),
            ], order='code', limit=1)
            if account:
                values[field] = account.id
        if values:
            target.write(values)
            repaired |= company
            _logger.info(
                'al_l10n_pe_currency: cuentas de diferencia de cambio '
                'asignadas en %s (%s)',
                company.display_name,
                ', '.join(
                    '%s=%s' % (field, env['account.account'].browse(
                        account_id).with_company(company).code)
                    for field, account_id in values.items()))
    return repaired


def post_init_hook(env):
    _l10n_pe_assign_exchange_accounts(env)
