# -*- coding: utf-8 -*-
"""Datos mínimos para ver el Gantt en una base de desarrollo.

Uso:

    .venv/bin/python odoo-bin shell -c cfg/my/pe.cfg -p 19799 --gevent-port 19798 \
        < myodoo/ol_new_apps/docs/gantt/pruebas/seed_gantt_demo.py

Crea dos proyectos con el prefijo «[DEMO Gantt]», tareas jerárquicas con
dependencias e hitos. Es idempotente: si ya existen, los borra y los rehace.

Para eliminarlos:

    env['project.project'].search([('name', 'like', '[DEMO Gantt]')]).unlink()
    env.cr.commit()
"""
from datetime import datetime, timedelta

PREFIX = '[DEMO Gantt]'
BASE = datetime(2026, 9, 7, 8, 0, 0)  # lunes

field_map = env['al.gantt.field.map'].get_map()
START = field_map['date_start']
END = field_map['date_end']
print(f"Mapeo de campos detectado: {field_map}")

old = env['project.project'].search([('name', 'like', PREFIX)])
if old:
    print(f"Eliminando {len(old)} proyecto(s) de demostración anteriores")
    old.with_context(active_test=False).unlink()


def dates(offset_days, duration_days):
    values = {}
    start = BASE + timedelta(days=offset_days)
    if START:
        values[START] = start
    if END:
        values[END] = start + timedelta(days=duration_days)
    return values


def make_task(project, name, offset, duration, parent=None, **extra):
    values = {'name': name, 'project_id': project.id}
    values.update(dates(offset, duration))
    if parent:
        values['parent_id'] = parent.id
    values.update(extra)
    return env['project.task'].create(values)


# ---------------------------------------------------------------------------
# Proyecto 1 — obra, con jerarquía de tres niveles y cadena de dependencias
# ---------------------------------------------------------------------------
building = env['project.project'].create({
    'name': f'{PREFIX} Edificio A',
    'allow_milestones': True,
    'privacy_visibility': 'employees',
})

expedientes = make_task(building, 'Expediente técnico', 0, 10)
licencia = make_task(building, 'Licencia de construcción', 10, 15, parent=expedientes)
planos = make_task(building, 'Planos estructurales', 0, 8, parent=expedientes)

obra = make_task(building, 'Obra gruesa', 25, 60)
excavacion = make_task(building, 'Excavación', 25, 12, parent=obra)
cimentacion = make_task(building, 'Cimentación', 37, 20, parent=obra)
estructura = make_task(building, 'Estructura', 57, 28, parent=obra)

acabados = make_task(building, 'Acabados', 85, 40)
instalaciones = make_task(building, 'Instalaciones eléctricas', 85, 20, parent=acabados)
pintura = make_task(building, 'Pintura', 105, 20, parent=acabados)

entrega = make_task(building, 'Entrega de obra', 125, 0)  # duración 0 => hito

# Cadena de dependencias fin-comienzo.
licencia.depend_on_ids = [(6, 0, planos.ids)]
excavacion.depend_on_ids = [(6, 0, licencia.ids)]
cimentacion.depend_on_ids = [(6, 0, excavacion.ids)]
estructura.depend_on_ids = [(6, 0, cimentacion.ids)]
instalaciones.depend_on_ids = [(6, 0, estructura.ids)]
pintura.depend_on_ids = [(6, 0, instalaciones.ids)]
entrega.depend_on_ids = [(6, 0, pintura.ids)]

# Estados variados, para ver los colores configurables.
planos.state = '1_done'
expedientes.state = '03_approved'
excavacion.state = '02_changes_requested'
pintura.state = '04_waiting_normal'

env['project.milestone'].create([
    {'name': 'Licencia obtenida', 'project_id': building.id,
     'deadline': (BASE + timedelta(days=25)).date(), 'is_reached': True},
    {'name': 'Casco terminado', 'project_id': building.id,
     'deadline': (BASE + timedelta(days=85)).date()},
])

# Casos límite que el contrato debe manejar:
make_task(building, 'Tarea sin fecha de inicio', 40, 5, **{START: False} if START else {})
env['project.task'].create({'name': 'Tarea sin fechas', 'project_id': building.id})

# ---------------------------------------------------------------------------
# Proyecto 2 — plano, para probar la vista multiproyecto
# ---------------------------------------------------------------------------
erp = env['project.project'].create({
    'name': f'{PREFIX} Migración ERP',
    'allow_milestones': True,
    'privacy_visibility': 'employees',
})
analisis = make_task(erp, 'Análisis de brechas', 0, 15)
datos = make_task(erp, 'Migración de datos', 15, 25)
capacitacion = make_task(erp, 'Capacitación', 40, 10)
salida = make_task(erp, 'Salida en vivo', 50, 0)
datos.depend_on_ids = [(6, 0, analisis.ids)]
capacitacion.depend_on_ids = [(6, 0, datos.ids)]
salida.depend_on_ids = [(6, 0, capacitacion.ids)]

env.cr.commit()
print(f"Creados: {building.name} ({len(building.task_ids)} tareas), "
      f"{erp.name} ({len(erp.task_ids)} tareas)")
