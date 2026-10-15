# Planificación de obra — diseño técnico del paquete 1.7 (configurabilidad)

Requerimiento: [`docs/md/Planificación de obra — requerimiento de configurabilidad (paquete 1.7).md`](../md/Planificación%20de%20obra%20—%20requerimiento%20de%20configurabilidad%20%28paquete%201.7%29.md).
Parte de la versión 27 del planificador (paquete 1.6 completo). Fecha: 15/10/2026.

## 1. Principio: catálogos configurables sobre comportamientos fijos

El código del planificador tiene que saber *qué hacer* con una etapa o un
recurso (lanzar una OF, asignar una contrata, comprar), pero no *cómo se
llaman* ni *cuántos hay*. Por eso cada lista cerrada se parte en dos:

| Lista de hoy | Catálogo configurable (datos) | Comportamiento fijo (código) |
|---|---|---|
| Etapas (`STAGES`, 13 campos) | `construction.stage`: nombre, código, orden, etapa anterior, plantilla y nivel del que cuelga, duración por defecto | `kind`: fabricación, campo o control, y «consume en la orden de fabricación» |
| Tipos de recurso (`RESOURCE_TYPES`, 5 campos) | `construction.resource.type`: nombre, código, abastecimiento | `behavior`: material, servicio, equipo, contrata, personal propio, producción |
| Niveles (funciones fijas y 19 vínculos con nombre) | líneas de `construction.level.template` con nombre libre y casillas de comportamiento | ruta almacenada `construction_path` y nivel superior; las funciones de mueble quedan para el rubro mobiliario |

Compatibilidad con Allcenter: los campos `stage` siguen guardando el
**código** de la etapa (la columna no cambia), pero su lista sale del catálogo
(`selection` dinámica). Las etapas actuales son registros del catálogo con los
mismos códigos (`production`, `assembly`, `installation`, `finishing`): los
datos existentes, los dominios, el árbol, el cronograma y las pruebas siguen
igual. Comprobado en `odoo/addons/base/models/ir_model.py:1757`: al dejar de
reflejar una selección fija, Odoo no aplica `ondelete` a campos del módulo
(solo a extensiones `selection_add` y campos manuales), así que la
actualización no vacía la columna.

Con el tipo de recurso pasa lo mismo: `resource_type` sigue siendo el
comportamiento (con `equipment` nuevo) y `resource_type_id` apunta al
catálogo. Elegir el tipo del catálogo fija el comportamiento; crear una línea
solo con el comportamiento (como hacen hoy los asistentes) le pone el tipo por
defecto de ese comportamiento.

## 2. Decisiones abiertas del requerimiento (propuesta)

| Decisión | Propuesta | Motivo |
|---|---|---|
| Fuente de la receta para constructoras (M17-04) | Receta propia del planificador (plantilla de ejecución), que se escribe a mano, se importa desde Excel o se copia desde un Work Item. La copia es en un solo sentido y se puede repetir; no hay sincronización | Los Work Items son modelos `x_` del paquete de industria (`construction_developer`, 303 en `construccion_dev_1`): no se puede depender de ellos en Python ni garantizar sus campos. Copiar evita que un cambio de la industria rompa el plan aprobado |
| Destino por defecto de la compra masiva en Construcción por partidas (M17-14) | Configurable por plantilla y por obra; el perfil de construcción arranca con «directo a la obra» y mobiliario con «stock general» | La constructora compra por obra con su analítica (planes Proyecto, Disciplina, Partida en `construccion_dev_1`) |
| Semana de contratas y valorización del perfil de construcción | Se deja con los valores de la compañía (lunes a domingo, liquidación y pago editables) y valorización por avance de partida, marcados «por validar» en el perfil | Hay que validarlo con CREVAL y Montegrande; el perfil se puede reaplicar |
| Orden de entrega | Estructura (fases 26 a 28) › control por nivel y generalizaciones 1.6 (29) › núcleo con puentes (30) › interruptores (31) › perfiles (32) › operación nativa y menús (33) › obras de prueba por rubro (34) | Los perfiles activan interruptores y puentes, así que van después de ellos. Las generalizaciones van antes del corte: el núcleo no puede quedarse con lo que solo sirve al mueble (metrado en ML, portal por piso o ambiente) |
| Numeración y nombres | M17-01 a M17-17 como en el requerimiento; puentes `al_construction_planner_<función>` (§4) | Sigue la convención del repositorio |

## 3. Fases

| Fase | Requerimientos | Contenido |
|---|---|---|
| 26 | M17-02, M17-03 | Catálogos de etapas y de tipos de recurso; selección dinámica en los 13 campos de etapa; `resource_type_id` y comportamiento equipo; las reglas que dependían de códigos (OF con producción y armado, contrata en instalación) pasan al `kind` de la etapa |
| 27 | M17-01 | Niveles libres: casillas de comportamiento en el nivel, nivel genérico, `construction_path` y nivel superior almacenados en la tarea y la línea; el árbol, el cronograma y el importador leen la plantilla |
| 28 | M17-04 | Plantilla de ejecución (receta por unidad del nivel con rendimiento, cuadrilla y etapa), importación Excel y copia desde Work Items; «Generar plan» desde la receta; la tipología de mueble queda como extensión |
| 29 | M17-13 a M17-17 | Control por cualquier nivel (niveles 1 a 6 en la línea, línea base y desvío), destino de la compra masiva, metrado en la unidad del nivel, material extra y avance por portal en cualquier nivel |
| 30 | M17-07 | Núcleo con dependencias mínimas y puentes; script de migración que instala los puentes que la base ya usa y reasigna sus `ir.model.data` |
| 31 | M17-06 | Interruptores `module_*` en Ajustes y visibilidad de menús, botones del árbol y asistentes |
| 32 | M17-05 | Perfiles de vertical (datos), aplicar, desvíos, exportar e importar; perfiles Construcción por partidas y Mobiliario |
| 33 | M17-08 a M17-12 | Operación en la aplicación nativa y tabla de clasificación de menús |
| 34 | Casos de prueba | Obras de prueba por rubro, documentación y criterios de aceptación |

Cada fase se cierra con la batería completa en verde (hoy 260 pruebas), sin
cambiar las cifras de las pruebas del paquete 1.6 ni de `ACEPTACION.md`.

## 4. Núcleo y puentes (fase 30)

| Módulo | Depende de | Contenido |
|---|---|---|
| `al_construction_planner` (núcleo) | `al_project_gantt_base`, `al_project_gantt_backend`, `base_tier_validation`, `analytic`, `product` | Plantillas, catálogos de etapas y tipos de recurso, recetas, árbol, plan de recursos y línea base, asignaciones (base), cronograma, avances, metrado, dependencias de terceros, control de la línea, inicio |
| `al_construction_planner_mrp` | núcleo, `project_mrp` | OF desde el plan, etapa de consumo de la BOM, espera del metrado, asignación «Orden de fabricación» |
| `al_construction_planner_purchase` | núcleo, `al_construction_material_request`, `purchase_request` | Compra masiva, requerimiento de obra, abastecimiento, precios de compra, aplicar costo, crear producto, asignaciones de compra masiva y requerimiento |
| `al_construction_planner_subcontract` | núcleo, `purchase`, `portal` | Asignar contrata y OC de servicio, liquidación semanal, portal de la contrata |
| `al_construction_planner_subcontract_purchase` (automático) | contratas, compras | Material extra desde el portal y su descuento a la contrata |
| `al_construction_planner_crew` | núcleo, `project_forecast`, `hr_timesheet` | Asignar cuadrilla, turnos, horas como real |
| `al_construction_planner_budget` | núcleo, `account_budget_purchase` | Presupuesto analítico al aprobar, control de la OC, completar la analítica de los apuntes |
| `al_construction_planner_sale` | núcleo, `sale_project`, `al_report_base` | Calendario e ingresos, contratos con hitos, cambios de obra, entrega semanal, valorización, cronograma valorizado, márgenes de la obra |
| `al_construction_planner_furniture` | `al_construction_planner_mrp` | Tipología de mueble (familia, módulos, ML, BOM), generar plan desde la tipología, importar maestro y ETO |
| `al_construction_planner_suite` | todos los puentes | Instala el perfil mobiliario completo y reúne las pruebas de integración |

El núcleo deja ganchos que cada puente extiende: tipos de asignación
(`_kind_fields`, `_get_document_state`, `_get_document_totals`), montos de la
mano de obra (`_get_driver_amounts`, `_get_labor_amounts`), aprobación y
cierre del plan (`_construction_on_approve`, `_construction_lines_added`,
`_construction_on_close`, `_construction_check_closable`), pendientes e hitos
del inicio, metros lineales del árbol y drivers del metrado.

Migración (`al_construction_planner/migrations/30.20261013/pre-migrate.py`):
una base con el planificador instala todos los puentes en la misma pasada,
les pasa los xmlid de sus registros, modelos y campos y vuelve a cargar las
vistas. `al_construction_planner_spreadsheet` pasa a depender de mobiliario y
`al_construction_attendance` de contratas y cuadrillas.
