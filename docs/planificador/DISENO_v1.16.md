# Diseño del paquete 1.16 · planificación de obra consolidado

Fuente: «Requerimiento · paquete 1.16 · Planificación de obra consolidado, en
cuatro etapas» (31-oct-2026). Reúne los paquetes 1.13 (hoja de trabajo de
mobiliario), 1.14 (pedido sin plan), 1.15 (Cronograma) y el paquete 3 de
construcción (CR-19 a CR-26), con once requerimientos de armonización
(M116-01 a M116-11) y la revisión de integración con la suite (I-01 a I-17,
D1 a D3). Los nombres de obra, montos y usuarios de las pruebas no se copian.

Reglas comunes: [`ARQUITECTURA_COMUN.md`](ARQUITECTURA_COMUN.md).

## Etapas

| Etapa | Contenido | Estado |
|---|---|---|
| 1 · Base común | CR-23, CR-22 a), CR-19 con M116-01, M116-02, M116-11 | Desarrollada (este documento) |
| 2 · Requerimiento de obra y contratas | M114-01 a 05, M116-03 a 06, CR-20, CR-21, CR-24, I-01 a I-09, I-13, D1 a D3 | Pendiente |
| 3 · Cronograma | M115-01 a 06, M116-07, M116-08, CR-25, CR-26 | Pendiente |
| 4 · Hoja de trabajo | M113-01 a 12, M116-09, M116-10, CR-22 b) a g) | Pendiente |

Cada etapa se prueba en las bases de desarrollo de las dos verticales antes de
empezar la siguiente.

## Etapa 1

### CR-23 · Nueva versión sin líneas duplicadas

- «Reemplazar lo generado» (`construction.plan.recipe.wizard`) borra las líneas
  con origen «Receta» y también las copias «Replanificación» cuya primera línea
  de la cadena (`previous_line_id` hasta el principio) vino de una receta
  (`_construction_root_source`, `_construction_recipe_generated`). Las manuales
  y sus copias se conservan.
- La línea regenerada hereda la línea anterior de la copia que reemplaza (misma
  tarea, comportamiento, producto, actividad y etapa), así que al aprobar la
  versión las asignaciones y los avances pasan a ella
  (`_transfer_to_new_version`, sin cambios).
- El envío de la hoja de presupuesto usa el mismo modo «Reemplazar»: ya no borra
  las copias de líneas manuales.

### CR-22 a) · Actividad archivada en el envío

`construction.labor.activity._construction_get_by_code(code, company, project)`
busca también entre las archivadas y reactiva la que encuentra. Si su etapa no
es del perfil de la obra, toma la etapa por defecto del perfil. La usan el
importador de recetas y el libro de APU y presupuesto.

### M116-01 (CR-19) · Etapas según el perfil de la obra

- El dato no cambia: los campos `stage` siguen guardando el código.
- Ruta nativa para filtrar: el widget `filterable_selection` de Odoo 19 con
  `whitelist_fname`. El mixin `construction.stage.offer.mixin` da el campo
  `construction_stage_codes` (las etapas activas del perfil de la obra; sin obra
  o sin perfil con etapas, las activas del catálogo). La etapa ya guardada se
  sigue mostrando aunque esté archivada o sea de otro perfil.
- Lo usan la línea del plan, la línea de la receta, la actividad, la línea del
  cambio de obra, «Asignar contrata» y la línea del requerimiento de obra.
- Ayudas de etapa con la obra: `_production_codes`, `_consumption_code`,
  `_field_codes`, `_offered_stages`, `_default_code` y `_check_project_code`
  (`construction_stage.py`). Cierra C-02.
- «Generar plan» de mobiliario elige entre las etapas del perfil de la obra
  (`stage_ids`), sin lista fija. Cierra C-03.
- Importadores (recetas, libro de APU, maestro): una etapa de otro perfil es
  error de la fila; una etapa vacía toma la por defecto del perfil
  (`construction.vertical.profile.default_stage_id`, o la primera de campo).
- Las listas de etapas de las dos hojas de trabajo son las del perfil de la obra.

### M116-02 · Estados del ambiente y «Medido»

- Nombres configurables por compañía en Ajustes › Planificación de obra › Obra:
  Pendiente, Medido y Entregado (`al_construction_planner_furniture`).
- `project.project._construction_space_state_labels()` los devuelve solo si el
  perfil de la obra mide sus ambientes (función «Metrado» del perfil); si no,
  vacío. Los consume la etapa actual de cada ambiente del Cronograma (M115-04,
  etapa 3).

### M116-11 · Profundidad libre y APU en cualquier nivel

- Plantilla: opción «APU en cualquier nivel» (`apu_any_level`) y función
  «Subnivel de obra» (`work_sublevel`), repetible debajo del nivel con etapas y
  disponible solo con la opción. No se mezcla con Subnivel ni Nivel de detalle.
  Tope: 6 niveles debajo de la obra. La validación corre también al crear o
  cambiar un nivel suelto.
- Tarea: «Lleva APU» (`construction_has_apu`). Con la opción, se enciende con
  la receta y el envío lo marca en las filas con precio; sin ella, es el nivel
  con etapas (mobiliario no cambia). Un nodo con APU no puede tener debajo otro
  con APU.
- I-10: con la opción, `construction_space_task_id` de la tarea (y
  `space_task_id` de la línea) es el nodo con APU más cercano de la ruta: los
  puentes que lo leen no cambian. Las etapas del cronograma, el metrado y la
  reprogramación validan «Lleva APU».
- I-11: el portal de contratas filtra por «Lleva APU» cuando la plantilla tiene
  la opción; si no, por «Recibe avance» del nivel.
- Control: el análisis agrupa hasta el nivel más profundo de la plantilla. El
  árbol de recursos suma cada nodo por su ruta y marca «APU».
- I-12: el libro de APU y presupuesto acepta filas de título (ítem y nombre, sin
  APU, unidad, metrado ni costo). La ruta de cada partida sale de su código
  (`budget_code_levels`: `1.01.01` o `1.0101`) y se guarda en la línea de venta
  (`construction_budget_path`). La cotización conserva sección y subsección; los
  títulos más profundos van en la descripción. El envío crea un nodo por cada
  elemento de la ruta en el nivel de su profundidad y el nodo con APU con su
  receta, metrado y línea de venta. Una fila más profunda que la plantilla
  detiene el envío sin crear nada.
- Datos: «Construcción PROF 3» (el perfil `profile_construction`, ahora
  Especialidad (N1) › Sub-especialidad (N2) › Partida (N3)) y PROF 4 a PROF 6,
  creados por `_construction_ensure_depth_profiles` solo si no existe ya un
  perfil o una plantilla con ese nombre o código. Son `noupdate`: en una base
  existente no se cambia nada de lo que ya tiene.

### Queda para las etapas siguientes

- Columnas «Especialidad (catálogo)» y «Sub-especialidad (catálogo)» de la hoja
  y las cuentas analíticas por nivel: van con M116-05 (etapa 2).
- Convención común de las dos hojas (colores, producto, lectura por clave):
  M116-09 (etapa 4).

### Configuración en las bases existentes

- Las plantillas de construcción creadas a mano necesitan marcar «APU en
  cualquier nivel» para que el APU deje de estar fijo en la partida.
- La subpartida que hoy usa «Subnivel» o «Nivel de detalle» pasa a «Subnivel de
  obra» cuando se configure.
- El perfil de cada compañía que debe filtrar etapas necesita sus etapas en el
  perfil; un perfil sin etapas ofrece todo el catálogo, como antes.

## Pruebas

`al_construction_planner_suite/tests/test_package_116_stage1.py`.
