# -*- coding: utf-8 -*-
"""Destinos por compañía raíz, como el código de la cuenta en Odoo 19.

- Carga y «Desactivar destinos» de la cuenta: el valor que tenía pasa a cada
  compañía raíz de la cuenta (campos company_dependent).
- Cada línea de reparto pasa a la compañía raíz donde su cuenta trabaja con
  destinos (clase 6 en 6→9, clase 9 en 9→6, con el código de esa raíz); si
  aplica a varias raíces, se duplica.
- Cada raíz queda con su diario «GA» y la cuenta de carga que más usaban sus
  cuentas (o la 791 del plan).
- Las sucursales toman el sentido y la carga de su raíz (campos delegados).
"""
from collections import Counter

from odoo import SUPERUSER_ID, api
from odoo.tools import SQL, sql


def _move_old_values(env):
    cr = env.cr
    if not sql.column_exists(cr, 'account_account', 'l10n_pe_load_account_id_v8'):
        return
    cr.execute(SQL("""SELECT id, l10n_pe_load_account_id_v8, l10n_pe_no_destiny_v8
                        FROM account_account
                       WHERE l10n_pe_load_account_id_v8 IS NOT NULL
                          OR l10n_pe_no_destiny_v8"""))
    for account_id, load_id, no_destiny in cr.fetchall():
        account = env['account.account'].browse(account_id)
        for root in account.company_ids.root_id:
            vals = {'l10n_pe_no_destiny_store': bool(no_destiny)}
            if load_id:
                vals['l10n_pe_load_account_store'] = load_id
            account.with_company(root).write(vals)
    for column in ('l10n_pe_load_account_id_v8', 'l10n_pe_no_destiny_v8'):
        cr.execute(SQL("ALTER TABLE account_account DROP COLUMN IF EXISTS %s",
                       SQL.identifier(column)))


def _sync_branches(env, fnames):
    """Copia a cada sucursal los campos del RUC, padres antes que hijas."""
    Company = env['res.company']
    for branch in Company.search([('parent_id', '!=', False)], order='parent_path'):
        branch.write({
            fname: Company._fields[fname].convert_to_write(branch.parent_id[fname], branch)
            for fname in fnames
        })


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _move_old_values(env)

    Destiny = env['l10n_pe.account.destiny'].with_context(active_test=False)
    roots = env['res.company'].search([('parent_id', '=', False)])
    prefix_of = {c.id: '6' if c.l10n_pe_dest_type == '6a9' else '9' for c in roots}
    for line in Destiny.search([]):
        account = line.parent_account_id
        targets = [root for root in (account.company_ids.root_id or roots)
                   if (account.with_company(root).code or '').startswith(prefix_of.get(root.id, '6'))]
        if not targets:
            line.company_id = line.company_id.root_id
            continue
        line.company_id = targets[0]
        for root in targets[1:]:
            if not Destiny.search_count([('company_id', '=', root.id),
                                         ('parent_account_id', '=', account.id),
                                         ('dest_account_id', '=', line.dest_account_id.id)]):
                line.copy({'company_id': root.id})

    for root in roots:
        vals = {}
        if not root.l10n_pe_destination_journal_id:
            journal = env['account.journal'].search(
                [('code', '=', 'GA'), ('company_id', '=', root.id)], limit=1)
            if journal:
                vals['l10n_pe_destination_journal_id'] = journal.id
        if not root.l10n_pe_destination_load_account_id:
            accounts = Destiny.search([('company_id', '=', root.id)]).parent_account_id
            used = Counter(account.with_company(root).l10n_pe_load_account_id.id
                           for account in accounts
                           if account.with_company(root).l10n_pe_load_account_id)
            if used:
                vals['l10n_pe_destination_load_account_id'] = used.most_common(1)[0][0]
            else:
                load = env['account.account'].with_company(root).search(
                    [('code', '=like', '791%')], limit=1)
                if load:
                    vals['l10n_pe_destination_load_account_id'] = load.id
        if vals:
            root.write(vals)
    _sync_branches(env, ['l10n_pe_dest_type', 'l10n_pe_destination_load_account_id'])
