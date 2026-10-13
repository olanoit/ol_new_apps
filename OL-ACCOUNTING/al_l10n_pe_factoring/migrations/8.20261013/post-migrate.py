# -*- coding: utf-8 -*-
from odoo.tools import SQL
from odoo.tools.sql import column_exists


def migrate(cr, version):
    if not column_exists(cr, 'l10n_pe_factoring_line', 'legacy_conformity_state'):
        return
    cr.execute(SQL("""
        UPDATE account_move m
           SET l10n_pe_cavali_number = COALESCE(m.l10n_pe_cavali_number, l.legacy_cavali_number),
               l10n_pe_cavali_date = COALESCE(m.l10n_pe_cavali_date, l.legacy_cavali_date),
               l10n_pe_conformity_state = CASE WHEN m.l10n_pe_conformity_state IS NULL
                                                 OR m.l10n_pe_conformity_state = 'pending'
                                               THEN COALESCE(l.legacy_conformity_state, 'pending')
                                               ELSE m.l10n_pe_conformity_state END,
               l10n_pe_conformity_date = COALESCE(m.l10n_pe_conformity_date, l.legacy_conformity_date),
               l10n_pe_negotiable_state = CASE WHEN l.legacy_cavali_number IS NOT NULL
                                                 AND COALESCE(m.l10n_pe_negotiable_state, 'none') = 'none'
                                               THEN 'registered'
                                               ELSE COALESCE(m.l10n_pe_negotiable_state, 'none') END
          FROM l10n_pe_factoring_line l
         WHERE l.move_id = m.id
    """))
    # Tenedor y fecha de pago de las anotadas; transferidas si están en una
    # operación ya cedida.
    cr.execute(SQL("""
        UPDATE account_move m
           SET l10n_pe_negotiable_holder_id = c.partner_id,
               l10n_pe_negotiable_due_date = COALESCE(m.l10n_pe_negotiable_due_date, m.invoice_date_due)
          FROM res_company c
         WHERE c.id = m.company_id AND m.l10n_pe_negotiable_state = 'registered'
           AND m.l10n_pe_negotiable_holder_id IS NULL
    """))
    cr.execute(SQL("""
        UPDATE account_move m
           SET l10n_pe_negotiable_state = 'transferred', l10n_pe_negotiable_holder_id = f.factor_id
          FROM l10n_pe_factoring_line l
          JOIN l10n_pe_factoring f ON f.id = l.factoring_id
         WHERE l.move_id = m.id AND m.l10n_pe_negotiable_state = 'registered'
           AND l.state = 'assigned' AND f.factor_id IS NOT NULL
           AND m.l10n_pe_conformity_state IN ('accepted', 'presumed')
    """))
    cr.execute(SQL("UPDATE account_move SET l10n_pe_conformity_state = 'pending' "
                   "WHERE l10n_pe_conformity_state IS NULL AND move_type = 'out_invoice'"))
    cr.execute(SQL("UPDATE account_move SET l10n_pe_negotiable_state = 'none' "
                   "WHERE l10n_pe_negotiable_state IS NULL AND move_type = 'out_invoice'"))
    # Las facturas ya desembolsadas en versiones anteriores (sin desembolso parcial).
    cr.execute(SQL("""
        UPDATE l10n_pe_factoring_line l
           SET disbursed = TRUE, disbursement_date = f.disbursement_date
          FROM l10n_pe_factoring f
         WHERE l.factoring_id = f.id AND f.disbursement_date IS NOT NULL
    """))
    for column in ('cavali_number', 'cavali_date', 'conformity_state', 'conformity_date'):
        cr.execute(SQL('ALTER TABLE l10n_pe_factoring_line DROP COLUMN IF EXISTS %s',
                       SQL.identifier('legacy_%s' % column)))
