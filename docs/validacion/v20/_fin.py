# Cierre: estado por caso, JSON de resultados y commit.
for c in QA['casos']:
    estados = [k['estado'] for k in c['checks']]
    c['estado'] = FAIL if FAIL in estados else (WARN if WARN in estados else (OK if OK in estados else SKIP))
_dir = os.environ['QA_DIR']
with open(os.path.join(_dir, 'resultados', '%s.json' % QA['fase']), 'w') as fh:
    json.dump(QA, fh, ensure_ascii=False, indent=1, default=str)
if os.environ.get('QA_ROLLBACK'):
    env.cr.rollback(); print('\nROLLBACK (QA_ROLLBACK)')
else:
    env.cr.commit(); print('\nCOMMIT')
_tot = {}
for c in QA['casos']:
    _tot[c['estado']] = _tot.get(c['estado'], 0) + 1
print('RESUMEN %s: %s' % (QA['fase'], _tot))
