"""Genera los TXT/XLSX de referencia desde la base v18 tecport-mtest.

Solo lectura: no se hace commit; los wizards son TransientModel.
Compañía: TECPORT PERU (id 3, RUC 20517256031).
"""
import base64, os, traceback

OUT = '/home/och/odoo/ce19/myodoo/ol_new_apps/docs/tecport/referencia'
COMPANY_ID = 3
PERIODS = [('2026', '03'), ('2026', '01')]

company = env['res.company'].browse(COMPANY_ID)
env = env(user=1, context=dict(env.context, allowed_company_ids=[COMPANY_ID]))
W = env['l10n_pe_reports.accounting.book.wizard']
books = env['l10n_pe_reports.accounting.book'].search([])

os.makedirs(OUT, exist_ok=True)
summary = []

for year, month in PERIODS:
    for book in books:
        label = '%s %s-%s' % (book.code, year, month)
        try:
            wiz = W.create({
                'company_id': COMPANY_ID,
                'accounting_book_id': book.id,
                'year': year,
                'month': month,
                'operation_indicator': '1',
            })
            wiz.action_generate_files()
            wiz.invalidate_recordset()
            got = []
            for fname in sorted(f for f in W._fields if f.startswith('e_binary_')):
                data = wiz[fname]
                if not data:
                    continue
                name = wiz[fname.replace('e_binary_', 'e_filename_')]
                if not name:
                    continue
                raw = base64.b64decode(data)
                sub = os.path.join(OUT, '%s-%s' % (year, month))
                os.makedirs(sub, exist_ok=True)
                with open(os.path.join(sub, name), 'wb') as fh:
                    fh.write(raw)
                lines = raw.count(b'\n') if name.lower().endswith('.txt') else 0
                got.append('%s (%d B%s)' % (name, len(raw), ', %d líneas' % lines if lines else ''))
            summary.append((label, 'OK', got))
            print('  OK  %-14s -> %s' % (label, ' | '.join(got) or 'sin datos'))
        except Exception as e:
            summary.append((label, 'ERROR', [str(e)[:200]]))
            print('  ERR %-14s -> %s: %s' % (label, type(e).__name__, str(e)[:200]))
        finally:
            env.cr.rollback()

print('\n===== RESUMEN =====')
for label, st, got in summary:
    print('%-16s %-6s %s' % (label, st, ' | '.join(got)[:150]))
