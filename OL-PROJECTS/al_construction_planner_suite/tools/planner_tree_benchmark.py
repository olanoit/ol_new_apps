# -*- coding: utf-8 -*-
"""Rendimiento del árbol de recursos (P-02) con volumen tipo MOMEN.

Parte de los datos demo (piso 05) y añade pisos hasta llegar a ~20 pisos,
153 departamentos y ~1,263 módulos; regenera el plan (~7,800 líneas o más) y
mide los RPC del árbol. Todo se deshace al final (rollback): no deja datos.

Ejecutar con:
  odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http < planner_tree_benchmark.py
"""
import time
from pathlib import Path

script = Path(odoo.modules.get_module_path('al_construction_planner')) / 'tools' / 'planner_demo_data.py'
quiet = {'env': env, 'print': lambda *a, **k: None}
exec(script.read_text().replace('env.cr.commit()', ''), quiet)
project, plan, typologies, node = quiet['project'], quiet['plan'], quiet['typologies'], quiet['node']
codes = sorted(typologies)

# 20 pisos: 13 con 8 departamentos y 7 con 7 = 153 departamentos.
apartments = 8
for number in range(1, 21):
    if number == 5:
        continue
    floor = node(f'Piso {number:02d}', 'floor')
    per_floor = 8 if number <= 13 else 7
    for n in range(1, per_floor + 1):
        apt = node(f'Dpto {number}{n:02d}', 'apartment', floor)
        node('Cocina', 'space', apt, construction_typology_id=typologies[codes[(n - 1) % 8]].id)
        apartments += 1

t0 = time.perf_counter()
env['construction.plan.generate.wizard'].create({'plan_id': plan.id}).action_generate()
env.flush_all()
generate = time.perf_counter() - t0
# El generador demo da ~3.4 líneas por módulo; MOMEN ronda las 7,800 líneas:
# se completan con copias manuales de líneas existentes.
missing = 7800 - plan.line_count
if missing > 0:
    env['construction.resource.plan.line'].create(
        plan.line_ids[:missing].copy_data())
    env.flush_all()
Task = env['project.task']
modules = Task.search_count([('project_id', '=', project.id), ('construction_level', '=', 'module')])
print(f'Volumen: {apartments} departamentos, {modules} módulos, {plan.line_count} líneas '
      f'(generación {generate:.1f} s)')


def timed(label, func, repeat=5):
    env.invalidate_all()
    best = None
    for _i in range(repeat):
        env.invalidate_all()
        t0 = time.perf_counter()
        result = func()
        elapsed = (time.perf_counter() - t0) * 1000
        best = elapsed if best is None else min(best, elapsed)
    print(f'{label:<45} {best:8.1f} ms')
    return result


root = timed('get_tree_nodes(root) – obra', lambda: plan.get_tree_nodes('root'))
floors = timed('get_tree_nodes(p) – 20 pisos', lambda: plan.get_tree_nodes('p'))
floor = next(f for f in floors if f['name'] == 'Piso 05')
apts = timed('get_tree_nodes(piso) – departamentos', lambda: plan.get_tree_nodes(floor['key']))
space = Task.search([('parent_id', '=', int(apts[0]['key']))], limit=1)
timed('get_tree_nodes(ambiente) – módulos', lambda: plan.get_tree_nodes(str(space.id)))
timed('get_tree_nodes(p) filtrado (material)',
      lambda: plan.get_tree_nodes('p', {'resource_types': ['material']}))
timed('get_selection_summary(piso)', lambda: plan.get_selection_summary([floor['key']]))
timed('get_selection_summary(10 pisos)',
      lambda: plan.get_selection_summary([f['key'] for f in floors[:10]]))
summary = timed('get_selection_summary(obra)', lambda: plan.get_selection_summary(['p']))
print('Obra:', root[0]['modules'], 'módulos,', root[0]['ml'], 'ML, S/', root[0]['total'],
      '·', len(summary['resources']), 'recursos en el panel')
env.cr.rollback()
