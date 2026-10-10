# Planificación de obra (AL)

Guía funcional: [GUIA_FUNCIONAL.md](GUIA_FUNCIONAL.md)

Planificador de recursos de obra según la especificación v1.4
([`docs/planificador/ESPECIFICACION_v1.4.md`](../../docs/planificador/ESPECIFICACION_v1.4.md)).
Diseño técnico, equivalencias de nombres y plan de fases:
[`docs/planificador/DISENO_TECNICO.md`](../../docs/planificador/DISENO_TECNICO.md).

## Estado

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Jerarquía de la obra, tipologías, actividades y tarifas, etapa de consumo, plan de recursos y «Generar plan» (P-01 básica, P-04, P-12, P-14) | hecha |
| 2 | Árbol del plan OWL (P-02) | hecha |
| 2 (resto) | Resumen por etapa (P-03), aplicar costo (W-12), aprobación con tier validation, replanificación | pendiente |
| 3-8 | Requerimientos, contratas, avances y liquidaciones, producción, ingresos, cronograma con recursos | pendiente |

## Modelos

- `construction.labor.activity` / `construction.labor.rate`: actividades con su
  driver (und, ML, módulo) y tarifas por obra y contrata. Prioridad: obra y
  contrata › obra › contrata › base › precio de la actividad.
- `construction.typology` (+ `.module`, `.activity`): plantilla de un ambiente.
- `construction.resource.plan` / `.line`: plan por obra con versiones; las
  líneas guardan sus ancestros (piso, departamento, ambiente, módulo) para
  acumular con `_read_group` sin recursión.
- `project.task`: `construction_level` y ancestros `construction_*_task_id`
  (calculados y almacenados), datos del módulo y `construction_unit_state`.
- `mrp.bom.line`: `construction_consumption_stage`.

## Árbol de recursos (P-02)

Acción de cliente OWL `al_construction_planner.plan_tree`
(`static/src/plan_tree/`), en **Obras ▸ Árbol de recursos** y en el botón
«Árbol de recursos» del plan.

- Carga por niveles: `construction.resource.plan.get_tree_nodes(parent_key,
  filters)` con `'root'` (la obra), `'p'` (pisos) o el id de una tarea. Cada
  nodo trae módulos, ML, material, contrata, total, cantidades de driver y
  estado del módulo; lo acumulado sale de un `_read_group` por el ancestro
  almacenado de la línea (`floor/apartment/space/module_task_id`).
- Selección en cascada (`selection.js`): se guardan solo los nodos marcados
  de más arriba; el servidor los expande con `child_of`
  (`get_selection_summary`). Desmarcar un hijo deja a los padres en parcial.
- Barra de selección: módulos, ambientes, ML y montos, más los botones de los
  asistentes W-02 a W-08 que estén instalados (`get_tree_actions`; reciben
  `construction_selection_keys` y `construction_selection_task_ids` en el
  contexto).
- Panel lateral: recursos de la selección por actividad, producto o rol, con
  driver, acumulado (fase 5), monto y contrata.
- Filtros: etapa, tipo de recurso, estado del módulo y contrata (o «sin
  asignar»); medida en soles, cantidad de driver o avance.
- Permisos: lectura del plan (`check_access`) y reglas de compañía del plan y
  de las tareas.

Rendimiento (`tools/planner_tree_benchmark.py`, 20 pisos, 153 departamentos,
1,257 módulos, 7,800 líneas; mejor de 5, en el servidor):

| RPC | ms |
|---|---|
| `get_tree_nodes('root')` – obra | 19.3 |
| `get_tree_nodes('p')` – 20 pisos | 24.8 |
| `get_tree_nodes(piso)` – departamentos | 15.1 |
| `get_tree_nodes(ambiente)` – módulos | 7.7 |
| `get_tree_nodes('p')` con filtro de material | 22.7 |
| `get_selection_summary` de un piso | 37.2 |
| `get_selection_summary` de 10 pisos | 64.6 |
| `get_selection_summary` de la obra | 39.5 |

## Generar plan (`construction.plan.generate.wizard`)

1. Ambientes elegidos (vacío = todos los de la obra).
2. Crea las tareas de módulo faltantes desde la plantilla (no duplica: si el
   ambiente ya tiene módulos, empareja por código y avisa los que faltan).
3. Armado: una línea por módulo a la tarifa vigente de la obra.
4. Actividades por ambiente: en el ambiente; las de ML bajan al módulo cuando
   la tipología tiene anchos (cantidad = ancho / 1000).
5. Materiales: de la BOM de los módulos si la tienen; si no, de la BOM de la
   tipología. Etapa = etapa de consumo de la línea; costo vacío (lo escribe el
   planificador), salvo el ya escrito en el plan.
6. «Reemplazar» borra antes solo las líneas generadas de esos ambientes.

## Datos demo y pruebas

```bash
.venv/bin/python odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
  < myodoo/ol_new_apps/OL-PROJECTS/al_construction_planner/tools/planner_demo_data.py
```

Piso 05 (Dptos 501 a 508): 66 módulos, 41.33 ML, S/ 6,642.91 de material,
S/ 2,301.53 de contrata, S/ 8,944.44 en total; el script lo comprueba.

Tests: `--test-tags /al_construction_planner` (30 tests, con el tour
`al_construction_planner_plan_tree` del árbol).

Rendimiento del árbol con volumen tipo MOMEN (deshace todo al terminar):

```bash
.venv/bin/python odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http \
  < myodoo/ol_new_apps/OL-PROJECTS/al_construction_planner/tools/planner_tree_benchmark.py
```

## Licencia

LGPL-3: depende de `base_tier_validation` (AGPL-3, OCA).
