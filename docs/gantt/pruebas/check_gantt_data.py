# -*- coding: utf-8 -*-
"""Verificación funcional del contrato de datos del Gantt (módulo base).

Uso:

    .venv/bin/python odoo-bin shell -c cfg/my/pe.cfg -p 19799 --gevent-port 19798 \
        < myodoo/ol_new_apps/docs/gantt/pruebas/check_gantt_data.py

Llama a ``project.project.get_gantt_data()`` **como un usuario real** (no como
superusuario) y resume la respuesta: mapeo detectado, conteos, casos límite,
dependencias y número de consultas SQL.
"""
import json

user = env.ref('base.user_admin')
Project = env['project.project'].with_user(user)

demo = Project.search([('name', 'like', '[DEMO Gantt]')])
print(f"Usuario: {user.name} · proyectos de demostración: {len(demo)}")

payload = Project.get_gantt_data(project_ids=demo.ids)

print("\n--- Mapeo de campos ---")
print(json.dumps(payload['field_map'], indent=2, ensure_ascii=False))

print("\n--- Meta ---")
print(json.dumps(payload['meta'], indent=2, ensure_ascii=False))

print("\n--- Conteos ---")
print(f"proyectos={len(payload['projects'])} tareas={len(payload['tasks'])} "
      f"enlaces={len(payload['links'])} hitos={len(payload['milestones'])} "
      f"colores={len(payload['colors']['states'])}")

print("\n--- Casos límite ---")
inferred = [task['name'] for task in payload['tasks'] if task['start_is_inferred']]
milestones = [task['name'] for task in payload['tasks'] if task['is_milestone']]
orphans = [task['name'] for task in payload['tasks'] if task['orphaned']]
print(f"inicio inferido: {inferred}")
print(f"tareas-hito (duración 0): {milestones}")
print(f"huérfanas: {orphans}")
print(f"sin fecha (excluidas): {payload['meta']['undated_count']}")

print("\n--- Muestra de tarea ---")
sample = next((task for task in payload['tasks'] if task['user_ids'] or task['state'] != '01_in_progress'),
              payload['tasks'][0])
print(json.dumps(sample, indent=2, ensure_ascii=False))

print("\n--- Cadena de dependencias ---")
names = {task['id']: task['name'] for task in payload['tasks']}
for link in payload['links'][:10]:
    print(f"  {names.get(link['source'], link['source'])} -> "
          f"{names.get(link['target'], link['target'])} [{link['type']}]")

print("\n--- Filtros ---")
done = Project.get_gantt_data(project_ids=demo.ids, options={'states': ['1_done']})
print(f"states=['1_done'] -> {len(done['tasks'])} tarea(s)")
undated = Project.get_gantt_data(project_ids=demo.ids, options={'include_undated': True})
print(f"include_undated -> {len(undated['tasks'])} tarea(s)")
limited = Project.get_gantt_data(project_ids=demo.ids, options={'limit': 5})
print(f"limit=5 -> {len(limited['tasks'])} tarea(s), truncated={limited['meta']['truncated']}, "
      f"total={limited['meta']['total']}")

print("\n--- Consultas SQL de una llamada completa ---")
env.invalidate_all()
before = env.cr.sql_log_count if hasattr(env.cr, 'sql_log_count') else None
import time
start = time.time()
Project.get_gantt_data(project_ids=demo.ids)
elapsed = (time.time() - start) * 1000
print(f"tiempo: {elapsed:.0f} ms" + (
    f" · consultas: {env.cr.sql_log_count - before}" if before is not None else ""))
