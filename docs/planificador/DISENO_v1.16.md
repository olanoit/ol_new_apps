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
| 2 · Requerimiento de obra y contratas | M114-01 a 05, M116-03 a 06, CR-20, CR-21, CR-24, I-01 a I-09, I-13, D1 a D3 | Desarrollada (bloques 2a, 2b y 2c); por probar en las bases |
| 3 · Cronograma | M115-01 a 06, M116-07, M116-08, CR-25, CR-26 | Desarrollada (bloques 3a y 3b) y aceptada |
| 4 · Hoja de trabajo | M113-01 a 12, M116-09, M116-10, CR-22 b) a g) | Bloques 4a y 4b desarrollados; 4c pendiente |

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

### Pruebas de la etapa 1

`al_construction_planner_suite/tests/test_package_116_stage1.py`.

## Etapa 2 · Requerimiento de obra y contratas

Se entrega en tres bloques, en este orden, para probar cada uno sobre el
anterior. Los tres se prueban juntos en las dos bases antes de la etapa 3.

| Bloque | Contenido |
|---|---|
| 2a · Requerimiento sin plan y asignación | M114-01 a 05, M116-03, M116-04, CR-21, CR-24 con M116-06 |
| 2b · Analítica por nivel y por rubro | M116-05, I-01 a I-09, D1, D2, D3 |
| 2c · Intervenir contrata | CR-20, I-13 |

### Rutas ya existentes que cambian el pedido (se devuelven antes de programar)

1. **M116-03 y M114-02 · ya hay un ajuste.** Ajustes › Requerimiento de obra
   tiene «Requerimiento de obra sin regla» (`res.company.construction_site_request_without_rule`,
   `al_construction_material_request`), con dos valores: «Pasar al jefe de la
   obra» y «Aprobar al enviar». Es la regla 7.4. Propuesta: no crear un ajuste
   nuevo, sino agregar a ese el tercer valor «Material fuera del plan». Hoy la
   base de construcción tiene «Pasar al jefe de la obra» con validación por
   niveles, y la de mobiliario «Aprobar al enviar» con la aplicación
   Aprobaciones: el valor inicial de cada base sale solo.
   Dos precisiones:
   - El ajuste de hoy actúa cuando ninguna regla aplica, con o sin plan. El
     valor nuevo solo cambia el caso «sin plan».
   - Hoy solo funciona con la validación por niveles. Con la aplicación
     Aprobaciones, «Pasar al jefe de la obra» no hace nada. Se completa para
     que los dos motores den el mismo resultado (el paquete lo pide).
2. **M116-06 · no hay marca de «escrito en la partida».** La modalidad de la
   partida (`project.task.construction_execution_mode`) es un campo calculado
   desde la plantilla de ejecución de la receta y editable. No se distingue
   si la escribió alguien o la puso la receta. Propuesta: «escrita en la
   partida» = el campo tiene valor (venga de la receta o de la mano). Lo que
   viene de la actividad o de la etapa no está en ese campo, así que en
   mobiliario el aviso no sale.
3. **M116-05 punto 5 (ingreso por rubro):** configuración, como dice el
   paquete. No se programa.
4. **M114-05:** no hay ruta de configuración que no se haya descartado ya.

### Respuestas que el paquete pide al desarrollo

- **M114-02, punto 5 (validación por niveles):** basta una definición de nivel
  con dominio, siempre que el requerimiento tenga un campo almacenado que diga
  «sin plan». Se agrega `construction_plan_control = 'no_plan'` (ya se muestra
  «Control de plan»). La definición la crea el ajuste, como hoy la regla 7.4.
- **M116-05, rendimiento:** el control de compras recorre las líneas del
  presupuesto de la obra por cada combinación de la OC. Con cuentas por
  partida, una obra de 300 partidas × 4 etapas × 5 tipos de costo puede pasar
  de unas decenas a varios miles de líneas. Con D3 la comparación se hace sobre
  los planes de control, agrupando antes las líneas del presupuesto por esos
  planes: una lectura por OC (`_read_group`) en lugar de una búsqueda por
  combinación. Así no depende del número de cuentas de partida.
- **CR-20, punto 6 (cobro contra el fondo):** la cuota del fondo es un saldo
  por pagar de la factura de la contrata (`move_line_id`). El exceso de
  deductivos se registra como nota de crédito del proveedor y se concilia
  contra esa cuota. Lo que queda de la cuota sigue su devolución. Sin cuenta
  nueva ni asiento manual.

### 2a · Requerimiento sin plan y asignación

Desarrollado. Las tres propuestas de arriba quedaron confirmadas. Detalles de
la implementación:

- La regla de validación por niveles «obra sin plan» la crea y archiva la
  compañía al cambiar el ajuste (`tier.definition.construction_no_plan`),
  revisada por «Planificación de obra: ejecución › Aprueba». Con Aprobaciones,
  la solicitud lleva la marca «Obra sin plan» y el resumen «Material fuera del
  plan (obra sin plan)».
- «Control de plan» del requerimiento muestra «Sin plan» en todo requerimiento
  de obra enviado sin plan vigente, con cualquier valor del ajuste.
- M114-01: las asignaciones de versiones anteriores quedan como historia; la
  regularización solo crea las del plan que se aprueba.
- CR-24 c): si el plan está aprobado, el cambio de modalidad queda anotado en
  el plan para la nueva versión; la asignación no se detiene.

- **M114-01** (`al_construction_planner_purchase`): `_construction_on_approve`
  del plan, después de pasar las asignaciones a la nueva versión. Busca las
  líneas de requerimientos de la obra (aprobados, en proceso o hechos, con
  material, sin asignación en el plan). Escribe el plan en el requerimiento y
  reparte con `_construction_candidate_plan_lines` y `_supply_split`. El
  exceso se registra en `construction.exceed.log` con el motivo «Regularización
  de pedido sin plan». Filtro «Pedidos sin plan» y mensaje en el plan. Corre
  con `sudo()`, justificado: quien aprueba el plan puede no ver los
  requerimientos.
- **M114-02 / M116-03** (`al_construction_planner_approvals` y
  `al_construction_material_request`): con «Material fuera del plan» y sin plan
  vigente, `_construction_approval_info` cuenta cada línea como
  `change = 'material'` al costo del producto. Tipo de cambio «Material fuera
  del plan (obra sin plan)».
- **M114-03 / M116-04** (`construction_material_request_scope.py`): selector
  «Módulo» como último nivel cuando la obra tiene módulos (el límite de seis
  sigue). Campo «Primer nivel de la ruta» en la plantilla de niveles (por
  defecto la unidad de entrega; si no la hay, el primer nivel). La etiqueta del
  nivel va desde ese nivel hasta la tarea, también en la solicitud de
  aprobación.
- **M114-04:** la línea manual con etapa y material toma la distribución con la
  misma función del plan (`_apply_analytic_rules`, con tipo `material`). Lo
  escrito a mano manda. En 2b suma las cuentas de nivel sin código aparte.
- **M114-05** (`replacement_request.py`, `_construction_replacement_bom`): si
  el almacén de la lista es el del tipo de reposición de Ajustes, usa ese tipo.
- **CR-21** (`schedule_action.js`, `res.users`): el último plan abierto se
  guarda por usuario. El menú abre ese plan; si no hay, el último aprobado o en
  ejecución que el usuario tocó; si tampoco, el primero. El selector agrupa por
  obra, primero la del plan abierto, con versión y estado.
- **CR-24 con M116-06** (`plan_contract_wizard.py`):
  - a) si nada de la selección queda por asignar, el asistente no abre y avisa
    con la contrata y el número de líneas, sugiriendo «Intervenir contrata»;
  - b) lista lo omitido por contrata, incluidas las líneas sin saldo;
  - c) aviso de modalidad solo con «Personal propio» escrito en la partida
    (ver arriba); al confirmar, la modalidad se guarda en la partida, en una
    nueva versión si el plan está aprobado.

### 2b · Analítica por nivel y por rubro

- **Plantilla de niveles:** cada línea de la plantilla lleva «Plan analítico»
  (vacío = no va a la analítica) y «Modo de la cuenta»: Catálogo, Mixto o Por
  obra.
- **Cuenta de la tarea:** campo `construction_analytic_account_id` en la tarea.
  Al crear la tarea de un nivel con plan, se crea o enlaza la cuenta:
  - Por obra: código «obra-código de la tarea», sigue el nombre de la tarea.
  - Catálogo: la cuenta elegida en la hoja; nunca se crea desde el título.
  - Mixto: la del catálogo si la fila la trae; si no, por obra.
  - Al archivar la tarea, la cuenta se archiva solo si ninguna otra la usa.
- **Hoja:** columnas «Especialidad (catálogo)» y «Sub-especialidad (catálogo)»
  en el libro de APU y presupuesto (las que quedaron pendientes de M116-11).
  El envío las lleva a la ruta de cada fila.
- **Distribución:** `_apply_analytic_rules` suma a la obra y a las reglas las
  cuentas de los niveles de la ruta de la línea y, en mobiliario, la cuenta
  Rubro de la familia de la tipología. La correspondencia familia → cuenta
  Rubro va en Ajustes › Planificación de obra. Todo lo que hereda la
  distribución del plan la recibe sin cambios propios.
- **Rótulo:** «Partida de costo» de la regla analítica pasa a «Tipo de costo».
- **I-01:** `stock.move._get_analytic_distribution` devuelve la distribución
  del requerimiento cuando el movimiento es de una línea de requerimiento de
  obra y su destino es la ubicación de la obra. En cualquier otro movimiento
  sale enseguida. El gancho de apuntes deja de adivinar la etapa en ese caso.
  Se corrige el comentario de `al_construction_material_request/models/stock_move.py`.
- **D1** (`al_construction_planner_mrp`, `_construction_stage_distribution`):
  cada clave se reparte entre cuentas Rubro en proporción al material
  planificado de los ambientes de la orden, por familia.
- **D2** (`al_construction_attendance`, `labor_cost_allocation.py`): el cierre
  reparte cada persona por los jornales ejecutados de `construction.crew.day`
  (`kind = 'executed'` con línea del plan), con la distribución de cada línea.
  Lo que no tiene turno queda como hoy. La pestaña de horas muestra el reparto.
- **D3** (`al_construction_planner_budget`): ajuste «Planes que controla el
  presupuesto». La compra y el presupuesto se reducen a esos planes antes de
  comparar. Sin ajuste, como hoy.
- **I-05 a I-09:** sin código. El planificador no pone cuenta de destino en las
  cuentas que crea (I-05); los planes de nivel quedan opcionales (I-06).
- **Migración** (`al_construction_planner`, script de la versión): crea las
  cuentas de las tareas existentes de los niveles con plan, recalcula la
  distribución de las líneas de plan abiertas y regenera el presupuesto nativo
  de los planes aprobados o en ejecución. No toca apuntes contabilizados. Sin
  plan en ningún nivel, no hace nada.

### 2b · Implementación

Desarrollado. Detalles:

- Plantilla de niveles: «Plan analítico» y «Modo de la cuenta» por nivel.
  La tarea guarda su cuenta (`construction_analytic_account_id`); la propia
  (`construction_analytic_own`) sigue el nombre y se archiva con la tarea si
  nadie más la usa. El código por obra es «cuenta de la obra-número de la
  partida».
- La hoja: columnas «Especialidad (catálogo)» y «Sub-especialidad
  (catálogo)» al final de PRESUPUESTO; el valor se busca por código o por
  nombre en el plan del nivel. Un valor sin cuenta queda avisado en la
  cotización y el nivel sigue su modo (mixto: cuenta por obra).
- Rubro: «Rubros (analítica)» en Configuración del plan
  (`construction.rubro.account`, en el puente de mobiliario). El núcleo deja
  los ganchos `_construction_extra_analytic_accounts` (línea) y
  `_construction_rubro_account` (tarea).
- I-01: `al_construction_material_request` depende ahora de
  `project_stock_account` para que su distribución mande sobre la del
  proyecto en el traslado a la obra.
- D3: `res.company.construction_budget_control_plan_ids`, en Ajustes junto a
  «Control de consumo».
- Punto 7 (obras ya cargadas): botón «Aplicar analítica a las obras» en la
  plantilla de niveles. Al actualizar el módulo ningún nivel tiene plan
  todavía, así que la migración se hace después de configurar, con el botón.

### 2c · Intervenir contrata

- Asistente nuevo `construction.contract.intervention.wizard`
  (`al_construction_planner_subcontract`). Botón en la OC de contrata
  confirmada y en el Cronograma (partidas de una sola orden), para
  «ejecución › Aprueba».
- Preliquidación por partida (nodo con APU): contratado, ejecutado validado,
  valorizado, saldo, cantidad nueva y comprometido que se libera. Sin asiento.
- Al confirmar:
  - cada línea intervenida de la OC baja a lo recibido, y la asignación del
    plan a lo hecho (lo mismo que hace «Cerrar orden», por línea);
  - la línea del plan queda sin contrata y con saldo para «Asignar contrata»;
  - las cuotas del fondo pasan a «Devolución retenida» con el motivo
    «Contrata intervenida» (`sudo()` justificado);
  - la OC queda «Intervenida»: rechaza avance nuevo en esas partidas y acepta
    deductivos.
- Tipo de deductivo nuevo «Defecto de la contrata intervenida».
- Liquidación final con «Liquidar orden», como hoy. Si los deductivos superan
  lo que queda por pagar, la diferencia va contra el fondo con una nota de
  crédito conciliada contra las cuotas, de la más antigua a la más nueva.
- Historial de contratas en el nodo con APU: orden, desde, hasta, cantidad y
  estado.

Desarrollado. Detalles de la implementación:

- La intervención queda guardada (`construction.contract.intervention`, con
  su preliquidación por partida y las cuotas retenidas): botón
  «Intervenciones» en la orden y menú Contratas › Intervenciones.
- La preliquidación va por línea de la orden. Con condiciones «por partida»
  cada línea es una partida; si la orden agrupa por actividad, la línea
  muestra sus partidas e intervenirla interviene todas.
- «Lo ejecutado» es lo valorizado o, si hay avance validado aún sin
  valorizar, ese: la liquidación final lo paga y la contrata que entra no
  vuelve a recibirlo.
- No se interviene con avance de la contrata reportado sin validar, ni con
  fecha anterior a su último avance validado.
- El avance guarda su contrata (antes era la de la línea del plan): el de la
  contrata que sale sigue siendo suyo y entra a su liquidación final; el
  nuevo es de la que entra.
- Una cuota ya retenida por otro motivo conserva el suyo y no se libera con
  la liquidación final.
- Liquidación final: si los deductivos dejarían el pago en negativo, entran a
  la factura los que lo dejan en cero y el resto («Deductivos contra el
  fondo») va a una nota de crédito del proveedor en borrador. Al publicarla
  contabilidad, se concilia con las cuotas del fondo de la más antigua a la
  más nueva, queda en el historial de cada cuota y se levanta la retención.
  Sin exceso, la retención se levanta al aprobar la liquidación. Con
  deductivos «descontados al pago» el exceso no se resuelve solo: se pide
  registrarlos en su línea de la factura.

### Pruebas de la etapa 2

- `al_construction_planner_suite/tests/test_package_116_stage2.py`: M114-01 a
  04, M116-03 (los dos motores), M116-04, M116-05, I-01, D1, D2, D3, CR-24.
- `al_construction_planner_subcontract/tests/test_contract_intervention.py`:
  CR-20 e I-13.
- `al_construction_planner_mrp_request`: M114-05.
- Prueba de interfaz del selector del Cronograma (CR-21).

## Etapa 3 · Cronograma

Se entrega en dos bloques. Los dos se prueban juntos en las dos bases antes de
la etapa 4.

| Bloque | Contenido |
|---|---|
| 3a · Barra, panel y nombres largos | M115-01, M115-02, M115-03, M116-08 con CR-25, CR-26 |
| 3b · Etapa de cada ambiente y carga semanal | M115-04 con M116-02, M115-05, M115-06 con M116-07 |

### Rutas ya existentes que cambian el pedido (se devuelven antes de programar)

1. **M115-04 punto 5 · el color de la etapa ya existe.** `construction.stage`
   tiene «Color en el cronograma» (`color`), que se edita en Configuración ›
   Etapas. Las barras de etapa y de etapa padre del Cronograma ya lo usan
   (`stage_colors` en `gantt_data.py`, `color` de cada fila en
   `schedule_action.js`). Hoy todas las etapas tienen el mismo azul porque
   nadie lo cambió. Propuesta: no se programa el color. Los colores por
   defecto del pedido se ponen en Configuración › Etapas de cada base, como
   configuración. El desarrollo no los escribe en las bases existentes; solo
   los trae una base nueva (datos `noupdate`). Pendiente, Medido y Entregado
   no son etapas: llevan gris, azul y verde fijos en el puente de mobiliario.
2. **M116-07 punto 2 · la obra no tiene calendario propio.** En Odoo 19
   `project.project.resource_calendar_id` es un cálculo desde la compañía, no
   un campo de la obra. Los días hábiles salen de la compañía
   (`_construction_is_site_day`, I-14), sin código nuevo. La semana sale de la
   obra (`_construction_period`, la misma de la liquidación, CR-10).
3. **M115-01 criterio 3 · el nombre de la acción se puede cambiar, pero la
   actualización del módulo lo vuelve a escribir.** El botón leerá el nombre
   de la acción, como se pide. Un nombre cambiado a mano en la base vuelve al
   del módulo en la siguiente actualización (las acciones no son
   `noupdate`). Para que un nombre propio se conserve, se cambia con su
   traducción (Ajustes › Traducciones), que la actualización no pisa. Es lo
   que se propone documentar.
4. **CR-26 · el ajuste «Producción» nombra la Fabricación.** El interruptor
   de Ajustes que instala Fabricación dice «Órdenes de fabricación desde el
   plan». Es la única pantalla de construcción que la nombra a propósito,
   porque es la que la instala. Propuesta: se queda como está y es la
   excepción del criterio.

### Diseño

**M115-01 · nombres desde la acción.** `TREE_ACTIONS` queda con xmlid, ícono
y grupo de barra; `get_tree_actions` devuelve el nombre de la acción (con la
traducción del usuario). Nombres nuevos en las acciones, títulos y botones
finales de los asistentes de compras (`al_construction_planner_purchase`) y
fabricación (`al_construction_planner_mrp`), como en la tabla del pedido. El
mensaje y la lista que deja el asistente de fabricación siguen diciendo
«Órdenes de fabricación».

**M115-02 · filas por tipo de acción.** El Gantt base acepta `group` y
`groupLabel` en cada botón de `extraToolbarButtons`. Sin ningún botón con
grupo, la barra queda como hoy. Con grupos, una fila por grupo con su
etiqueta a la izquierda; el contador «n fila(s) marcada(s) · Quitar» queda en
la primera. Grupos: Consultar (Insumo-producto), Programar (compra masiva,
materiales para obra, fabricación) y Ejecutar (asignar contrata, intervenir
contrata, asignar cuadrilla, registrar avance, cambiar fechas). «Intervenir
contrata» (etapa 2) va en Ejecutar. El Árbol de recursos usa las mismas filas.

**M115-03 · panel ampliable.** Borde arrastrable de 280 a 720 px (doble clic,
320), guardado en `localStorage`; botón «Ampliar / Reducir» (320 ↔ 640); con
480 px o más, columnas Contrata o proveedor, Plan (cantidad y unidad),
Ejecutado S/ y Saldo S/; «Pantalla completa» abre el mismo resumen en un
diálogo con la opción «Por etapa». Las columnas en soles siguen el permiso de
montos de hoy. `get_selection_summary` agrega el monto ejecutado por recurso
(hoy trae la cantidad ejecutada).

**M116-08 y CR-25 · nombres largos.** Ajuste de la compañía «Ancho máximo de
los nombres» (`construction_name_max_width`, 360 px). La interfaz lo recibe
con la sesión y lo pone en una variable CSS. Una clase común
(`o_cp_wrap_names`) hace el salto de línea con ese ancho máximo en: los
encabezados de fila del Análisis de control (pivote) y de los informes de la
vertical, las listas de líneas del plan y el panel de M115-03. Las vistas de
Odoo fuera de la vertical no cambian: la clase solo se pone en las vistas del
planificador.

**CR-26 · textos de mobiliario.** Las ayudas del núcleo que nombran la orden
de fabricación o la planta pasan a hablar de producción en taller. Las
ayudas, filtros y textos propios de Fabricación pasan al puente
`al_construction_planner_mrp` (redefinen la ayuda del campo o heredan la
vista), así solo se ven con Fabricación instalada. El tipo «Producción» no
cambia.

**M115-04 con M116-02 · etapa actual y plazo.**

- Campo almacenado en el ambiente (la tarea con etapas,
  `construction.space.stage.space_task_id`): `construction_current_stage`, una
  selección con los estados de la obra en este orden: Pendiente, Medido, las
  etapas hoja del catálogo por su secuencia y Entregado. Lleva
  `construction_current_stage_progress` y `construction_current_partner_id`
  (contrata de esa etapa), también almacenados.
- Se recalcula con un método explícito
  (`_construction_refresh_current_stage`). Lo llaman la validación o el
  rechazo de un avance, el cambio de fechas de una etapa, la marca «Ambiente
  medido» y el estado del módulo. El avance de la etapa es un cálculo sobre
  las líneas del plan: no hay dependencia que el ORM pueda seguir sola.
- Árbol 1, etapa actual. Los estados Pendiente, Medido y Entregado solo
  existen si el perfil de la obra mide sus ambientes (M116-02); si no, solo
  etapas.
  1. Todas las etapas al 100 % y todos los módulos entregados: Entregado. Sin
     estados de mobiliario: la última etapa al 100 %.
  2. Si no, la primera etapa (por secuencia) con avance menor a 100 %. Si
     es la primera de todas y su avance es 0: Medido si el ambiente está
     medido, Pendiente si no. Si no, esa etapa con su %.
- Árbol 2, plazo, sobre la etapa actual (cálculo no almacenado, porque
  depende de hoy, con búsqueda para el filtro):
  1. Avance 100 %: terminado.
  2. Sin fechas: sin fechas.
  3. Fin vencido: atrasada «n d» (rojo).
  4. Inicio pasado y avance 0: en riesgo «debía iniciar dd/mm» (ámbar).
  5. Avance esperado por días hábiles transcurridos menos el avance real
     mayor que el margen: en riesgo (ámbar). Margen en Ajustes, 20 puntos.
  6. Si no: a tiempo.
- Cronograma, filas «Etapas»: columnas «Etapa actual» (distintivo con
  nombre, % y color; borde punteado y «por iniciar» con 0 %; mini barra con
  los estados) y «Plazo» (punto y texto). Pisos y departamentos: cuántos
  ambientes hay en cada etapa y el peor plazo. Filtros nuevos: «Etapa
  actual» (varias) y «Solo atrasados o en riesgo».

**M115-05 · informe «Etapa de los ambientes».** Acción nativa en Informes
sobre los ambientes: cuadro dinámico, gráfico de barras apiladas y lista.
Para agrupar por los dos primeros niveles de la plantilla de la obra (piso y
departamento en mobiliario, especialidad y sub-especialidad en CREVAL), la
tarea guarda sus ancestros de nivel 1 y 2
(`construction_level1_task_id`, `construction_level2_task_id`). Columnas por
la etapa actual (en el orden de la selección), medida: número de ambientes.
Agrupaciones guardadas: por departamento, tipología y contrata. Lo ve quien
ve el Cronograma.

**M115-06 con M116-07 · carga semanal.**

- Semanas de la obra (`_construction_period`) y días hábiles de la compañía.
  Cada semana trae su rango («jue 5 – mié 11 nov»).
- Modos: Planificado, Ejecutado y Plan vs ejecutado (por defecto).
  Ejecutado: avances validados por su fecha, contrata (o rol) y etapa, con el
  filtro de etapas.
- Filas por etapa con subtotal y color; «Sin asignar» pasa a «Por asignar».
  Montos sin decimales; semana actual resaltada; columnas Plan total, Plan a
  la fecha, Ejecutado y % a la fecha; fila «Diferencia ejecutado − plan».
- Colores del %: verde desde 95, ámbar desde 70, rojo debajo. Los dos
  umbrales en Ajustes.
- El permiso es el de hoy: solo «ve montos».

### 3a · Implementación

Desarrollado. Detalles:

- `TREE_ACTIONS` guarda xmlid, ícono y grupo; `get_tree_actions` devuelve el
  nombre de la acción y la etiqueta del grupo; `get_tree_action_groups` da el
  orden de las filas. «Insumo-producto» va en Consultar.
- Gantt base (`al_project_gantt_backend`): `toolbarButtonRows` arma las filas
  con `groupToolbarButtons`; el contador de la selección queda en la primera.
  El Árbol de recursos pinta las mismas filas.
- Panel: el ancho vive en `localStorage`
  (`al_construction_planner.schedule_panel_width`). Con 480 px o más, o en
  pantalla completa, salen las columnas completas. `get_selection_summary`
  agrega `amount_executed` y `amount_balance` por recurso y por etapa (avances
  validados, sin retrabajos), solo para contratas y personal propio, y los
  oculta a quien no ve montos.
- Nombres largos: `res.company.construction_name_max_width` (360 px), en la
  sesión (`ir.http.session_info`) y en la variable CSS
  `--o-cp-name-max-width`. La clase `o_cp_wrap_names` está en las vistas
  dinámicas del planificador y sus puentes y en las listas de líneas del plan
  (columnas `o_cp_name`).
- CR-26: el núcleo dice «producción en taller»; el puente de Fabricación
  redefine las ayudas de `kind`, `production_consumption`, `behavior` y de
  las cantidades de la línea del plan, y trae el filtro «Orden de
  fabricación» de las asignaciones.

### 3b · Implementación

Desarrollado. Detalles:

- `construction_space_current_stage.py` (núcleo): campos guardados de la
  etapa actual en la tarea, plazo calculado con búsqueda, ancestros de nivel 1
  y 2, y `_construction_refresh_current_stage`. Lo llaman
  `_refresh_control` de las líneas del plan (avances, versiones, acción
  programada), las etapas del ambiente (crear, fechas, borrar) y la escritura
  de los campos de `_construction_current_stage_trigger_fields` (estado del
  módulo; el puente de mobiliario agrega «Ambiente medido»).
- Etapa sin contratas ni personal propio (la producción en taller de
  mobiliario): no tiene avance que medir. Una etapa de fabricación queda
  terminada cuando todos los módulos del ambiente salieron de producción;
  cualquier etapa sin líneas queda terminada si una etapa siguiente ya tiene
  avance. Sin esta regla, el ambiente quedaría siempre en su primera etapa.
- Colores de Pendiente, Medido y Entregado: fijos en el núcleo (gris, azul y
  verde), junto a la lista de estados; los nombres siguen en el puente de
  mobiliario (M116-02).
- Cronograma: el payload trae `construction.space_states`, y en cada tarea
  `current` (ambiente) o `current_counts` y `worst` (ancestros). Filtros
  `construction_current_stages` y `construction_only_late`: el ambiente y sus
  ancestros.
- Carga semanal: `get_schedule_load` mantiene `weeks`, `rows`, `totals` y
  `total`, y agrega `week_ends`, `current_week`, `groups`, `executed` por
  fila, `executed_totals`, `diff`, `plan_to_date`, `executed_total`, `pct` y
  `thresholds`. «Sin asignar» pasa a «Por asignar».
- Informe: Informes › Cronograma › Etapa de los ambientes (lo ve
  «Planificación de obra: usuario»).

### Ajustes nuevos (Ajustes › Planificación de obra)

| Ajuste | Por defecto | Requerimiento |
|---|---|---|
| Ancho máximo de los nombres | 360 px | M116-08, CR-25 |
| Margen de «en riesgo» | 20 puntos | M115-04 |
| Carga semanal: verde desde / ámbar desde | 95 % / 70 % | M115-06 |

Son de la compañía. En las bases existentes toman el valor por defecto; no se
cambia nada más.

### Pruebas de la etapa 3

- `al_construction_planner_suite/tests/test_package_116_stage3.py`: M115-01
  (nombre de la acción, grupo de avance), M115-04 (una rama de cada árbol con
  fecha fija), M115-05, M115-06 con M116-07 (dos semanas pasadas con avances
  validados y uno reportado, una futura; semana de jueves y de viernes).
- `al_construction_planner/tests/test_profiles_v17.py`: CR-26, ayudas con y
  sin Fabricación.
- Pruebas de interfaz en `al_construction_planner/static/tests/`: barra en
  filas, panel ampliable y nombres largos.

## Etapa 4 · Hoja de trabajo

Se entrega en tres bloques, en el orden que propone el paquete 1.13: primero
lo que asegura el envío, después lo que permite cargar las obras desde la
hoja y al final la experiencia de planificación. Los tres se prueban juntos en
las dos bases. La programación empieza cuando la etapa 3 esté aceptada.

| Bloque | Contenido |
|---|---|
| 4a · Envío seguro y convención común | M116-09, M113-01, M113-02, M113-03, CR-22 b) a g) |
| 4b · Cargar la obra desde la hoja | M113-04, M113-05, M113-06, M116-10 |
| 4c · Planificar en la hoja | M113-07 a M113-12 |

### Rutas ya existentes que cambian el pedido (se devuelven antes de programar)

1. **M113-06 punto 3 · el desplegable nativo ya busca al escribir.** La
   validación por lista o por rango de la hoja de Odoo 19 ofrece sus valores
   en el editor de la celda y los filtra por coincidencia aproximada mientras
   se escribe (proveedor `dataValidation` de `autoCompleteProviders`, con
   `fuzzySearchKey`, en `addons/spreadsheet/.../o_spreadsheet.js`). Propuesta:
   no se programa el buscador del panel. Escribir parte del nombre en la celda
   «Producto» basta, y cumple el criterio «el producto se elige escribiendo
   parte del nombre» de M116-09.
2. **M113-10 punto 4 · las fechas por piso ya se ponen en el planificador.**
   «Cambiar fechas» (W-08) del Árbol de recursos lleva la selección (un piso,
   varios pisos) a una fecha nueva o la desplaza n días, y el Cronograma mueve
   las etapas de cada ambiente arrastrando la barra. Propuesta: el maestro no
   lleva una pestaña de fechas por piso. PROGRAMA queda como pre-plan en la
   hoja y solo escribe Inicio y Fin en OBRA. El ritmo por piso se lleva al
   plan con esas dos herramientas, ya generado el plan.
3. **M113-03 · el menú del presupuesto en la hoja de mobiliario.** En dev1 las
   cuatro hojas de trabajo tienen `construction_sheet_kind = furniture`, y el
   código vigente solo muestra ese menú en las de presupuesto. Lo observado el
   30-oct no se reproduce con el código de hoy; probablemente eran recursos
   anteriores en la caché del navegador. Al revisarlo encontré otra causa
   real, que sí se corrige en 4a: el puente de mobiliario decide el tipo de
   hoja con `profile.code != 'construction'`
   (`al_construction_planner_spreadsheet_furniture/models/project_project.py`).
   Los perfiles «Construcción PROF 4» a «PROF 6» de la etapa 1 tienen otro
   código, así que en una base con los dos puentes una obra de construcción
   abriría la hoja de mobiliario. Hoy no pasa en creval-dev porque ahí no está
   el puente de mobiliario. Propuesta: el perfil tiene un campo «Hoja de
   trabajo» (presupuesto y plan / maestro de mobiliario), que traen los
   perfiles de cada vertical. Así no queda una condición por código de perfil.
4. **M113-07 puntos 2 y 8 · lo que la hoja nativa no hace.** Un enlace de la
   hoja abre una dirección o una pestaña, pero no ejecuta una opción del menú.
   Tampoco hay forma nativa de poner un conteo en el nombre de la pestaña. Por
   eso «Validar» y «Enviar» quedan en INICIO como texto que dice dónde está la
   opción, y los conteos van en INICIO, como prevé el pedido.
5. **M116-10 punto 3 · las actividades y tarifas por ML son configuración.**
   La actividad tiene «Se mide por ML» y «Grupo ML», y la lista de tarifas
   tiene la familia «Closet y cajones». Con el grupo nuevo, las actividades
   de instalación y limpieza de closets, baños, lavanderías y ductos se crean
   en el catálogo (o en la hoja CATALOGO) con «Grupo ML: Mueble completo», y
   su tarifa va en la lista de su familia. El desarrollo solo agrega el grupo
   y lo suma; no crea actividades.
6. **Duda del 1.13 · la BOM con módulo no se cuenta dos veces.** Al generar el
   plan, si algún módulo de la tipología tiene receta, la BOM de la tipología
   no se usa (`plan_generate_wizard.py`, `sources = … [] if recipe_modules`).
   El material no se duplica. Pero de ahí sale un **quinto caso de pérdida
   silenciosa**: en una tipología con recetas por módulo, las filas de BOM
   *sin* «Módulo» llegan a la BOM de la tipología y el plan no las usa.
   Propuesta: se agrega a M113-01 como aviso `bom_without_module`, con la hoja
   y la fila. En «Validar» cuenta como error.

### Diseño

**Clave interna de columna (M116-09 punto 3, CR-22 d).** La hoja de Odoo 19
no tiene notas de celda ni rangos con nombre, y una fila técnica arriba
correría todas las fórmulas, tablas dinámicas y referencias de las hojas ya
creadas. Se usa una pestaña oculta `_CLAVES`, con una fila por columna leída:
pestaña, clave y `=COLUMN(<pestaña>!<celda del encabezado>)`. La hoja
actualiza esa referencia cuando el usuario inserta, mueve o borra columnas, y
renombrar el encabezado no la cambia. Una columna borrada da `#REF` y se
informa como «falta la columna obligatoria».
- Al enviar, el servidor cambia el encabezado de cada columna leída por su
  clave antes de armar el libro.
- Los dos importadores ya reconocen el encabezado por su texto. El de
  mobiliario ya acepta la clave; al del presupuesto (`COLUMNS`) se le agrega
  la clave como un alias más.
- El libro .xlsx importado directo sigue leyéndose por encabezado, como hoy.

**Pestaña ERRORES común (M116-09 punto 4, M113-03).** Está en
`al_construction_planner_spreadsheet`.
- Columnas: Hoja, Fila, Columna, Mensaje, Tipo (Error / Aviso) e «Ir».
- «Ir» es `HYPERLINK` a la pestaña, nativo; si el enlace admite celda, va a la
  celda.
- Arriba, una fila de estado: «Validada el [fecha] · N errores · M avisos».
- Cada vertical entrega sus filas con el mismo formato: el presupuesto desde
  `_parse` y el mobiliario desde `_analyze`.
- Para el mobiliario, el análisis guarda además una lista
  `issues` (hoja, fila, columna, mensaje, tipo). Los avisos de texto de la
  vista previa del asistente no cambian.

**Colores y producto (M116-09 puntos 1 y 2, CR-22 f y g).**
- Colores en las dos plantillas: amarillo `#FFF2CC` para el dato y gris
  `#D9D9D9` para la fórmula. El verde del mobiliario desaparece.
- El producto se muestra «nombre · unidad · código». El código calculado lee
  el último tramo después de « · ». En la hoja de presupuesto, INSUMOS lleva
  la columna calculada «Para elegir», con el mismo formato.
- «Traer de Odoo» del presupuesto escribe:
  - el nombre del producto sin el código;
  - la unidad en español;
  - la etapa por su nombre.
- APU y APU_DETALLE llevan la receta por nombre con el código al final, y la
  primera fila y las primeras columnas quedan inmovilizadas.

**Sin `N()` (CR-22 c).** La función no existe en la hoja de Odoo 19 (no está
en el registro de funciones de `o_spreadsheet.js`). La plantilla del
presupuesto pasa a `IFERROR(VALUE(x),0)`. Una migración reescribe esas
fórmulas en las hojas ya creadas, en los datos y en la última foto, sin perder
las revisiones (como la migración `5.20261016`).

**Rendimiento en APU (CR-22 e).** «Traer de Odoo» escribe el rendimiento por
día y las horas por jornada que la receta guarda en sus líneas por cuadrilla.
Sin horas, usa las de la compañía. El envío ya recalcula la mano de obra por
cuadrilla cuando hay rendimiento.

**Hojas ya creadas (CR-22 b y f, M116-09).** Una migración por módulo:
- agrega «Costo unitario sin APU» donde falta, y «Traer de Odoo» la llena para
  las partidas sin receta (D1);
- pasa a gris los encabezados de fórmula;
- crea `_CLAVES`.

Agrega o cambia formato; no borra datos del usuario.

**Contrato de datos (M113-01).** Los cinco casos van en `_analyze` de
`master_import_v18.py`:
- `module_unknown`: BOM o PIEZAS con un módulo que no está en MODULOS de su
  tipología, ni en el libro ni en la obra;
- `piece_product_unknown`: tablero que no existe y no está en PRODUCTOS NUEVOS;
- `obra_date_invalid`: la fecha no se puede leer. Además, `_apply_obra` acepta
  el número de serie de la hoja (días desde el 30-dic-1899), «AAAA-MM-DD» y
  «DD-MM-AAAA»;
- error de fila en ARBOL: trae Agrupador y la plantilla de la obra no tiene
  niveles de agrupador. Lleva el mensaje del pedido;
- `bom_without_module`: el caso nuevo de la ruta 6.

También: «Tipo de módulo» escrito ya no deja vacío el tipo especial. El tipo
especial se deduce del nombre aunque la fila traiga «Especial». Desde la hoja,
los casos 1, 2, 4 y 5 son errores y bloquean el envío. En el asistente directo
siguen siendo avisos. La vista previa cuenta las piezas y las líneas que no se
importarán.

**Solo las pestañas del maestro (M113-02).** `collectSheets(model, names)`
recoge solo las pestañas pedidas y corta en la última fila con datos antes de
leer celda por celda (`getSheetZone` más la última fila no vacía). La lista
llega en `_get_spreadsheet_metadata`:
- mobiliario: `SHEETS` más `_CLAVES`;
- presupuesto: `BOOK_SHEETS` más `_CLAVES`.

**Menú del mobiliario (M113-03).** «Planificación de obra» con `isVisible:
isFurniture` y las opciones del pedido en su orden. La de 4b y las de 4c
aparecen con su bloque.
- «Validar» llama a `action_construction_validate_furniture(sheets)`. Arma el
  libro como el envío, ejecuta `_analyze` sin escribir y devuelve las filas de
  ERRORES.
- «Enviar al planificador» valida primero. Con errores no abre el asistente:
  lleva a ERRORES y dice cuántos hay.
- La opción de Archivo se queda.

**Importar Excel a la hoja (M113-04).** Asistente transitorio
`construction.spreadsheet.import.wizard` en el puente de la hoja de
mobiliario.
- Campos: archivo; modo (reemplazar / agregar al final); las tres opciones
  del pedido; y la revisión por pestaña antes de escribir (filas, columnas
  reconocidas, columnas extra y resultado de `_analyze`).
- El servidor lee el libro con `_read_workbook` y devuelve las filas por
  clave.
- El cliente escribe con `UPDATE_CELL` en la columna de cada clave, que busca
  en `_CLAVES`, no por posición. No toca las columnas calculadas.
- El código del producto del archivo se convierte en el texto de «Producto».
  La categoría se llena con la del producto si el archivo no la trae.
- Los códigos desconocidos quedan como texto y se agregan a PRODUCTOS NUEVOS.
- Las columnas extra van a la derecha, con encabezado gris. Las pestañas que no
  son del maestro se copian.
- Antes de escribir guarda una versión. Si faltan filas, amplía la hoja: las
  filas del archivo más 10 %.
- Al terminar ejecuta «Validar» y deja un mensaje en la obra.
- «Descargar formato de carga» reutiliza `action_download_template`.

**Filas (M113-05).** `construction_spreadsheet_rows` pasa a 0 = «Automático»
y se ve en la ficha de la obra, junto a «Hoja de trabajo». En automático la
hoja nace con 300 filas y la importación la amplía.

**Elegir materiales (M113-06).**
- **Listas:** «Grupo de categoría», «Categoría» (ruta corta «ACCESORIOS /
  OTROS») y «Producto», las tres con validación nativa.
- **Ajuste nuevo:** «Categoría raíz de materiales de la hoja». Sin él, todas
  las categorías menos las excluidas.
- **Rendimiento:** la validación nativa por rango exige una referencia fija;
  no admite un rango calculado con `INDEX` o `MATCH` (`isValueInRange`,
  `rangeReference`). Por eso `_LISTAS` tiene dos bloques:
  - una fila por categoría con su `FILTER`: menos de 100 en total;
  - una fila por fila de datos, con `INDEX(…, MATCH(categoría), 0)` sobre el
    bloque de categorías, sin `FILTER`. La regla de cada celda «Producto»
    apunta a su fila, como hoy.
  - El ancho de `_LISTAS` sale de la categoría con más productos. Hoy son 60
    columnas, y una categoría más grande se corta.
- **Materiales de la obra:** van primero en la lista de su categoría
  (`VSTACK` con `UNIQUE`; las dos son nativas).
- **Columnas calculadas:** «Unidad del producto (calc.)» y «Costo unitario
  (calc.)».
- **Formato condicional:** rojo para el código fuera del maestro y ámbar para
  el costo 0.
- **«Reemplazar un material…»:** va en 4c, con el panel.

**ML de mueble completo (M116-10).**
- `ML_GROUPS` suma `('full', 'Mueble completo')`.
- La tipología tiene «ML de mueble completo» (`ml_full`) y «ML total» (bajo +
  alto + completo).
- La generación del plan, la medición, el árbol de recursos y la plantilla
  tratan «Mueble completo» como un grupo más.
- Las actividades por ML de ese grupo toman los ML de los módulos de ese
  grupo.
- El formato de carga y la conversión del 1.13 ponen «Mueble completo» a los
  muebles completos. Los zócalos siguen en «Sin ML».

**Planificar en la hoja (4c).**
- **INICIO (M113-07):** la primera pestaña, con fórmulas sobre las pestañas
  del maestro.
  - Estado de la hoja, ruta de 8 pasos con su semáforo, indicadores, dos
    gráficos y «Lo que falta».
  - El ML que muestra es el total de M116-10.
- **Panel «Planificación» (M113-08):** `sidePanelRegistry`.
  - Muestra la pestaña activa, la ayuda de la columna (de `SHEETS`) y los
    enlaces a Odoo.
  - Acciones que guardan versión antes de escribir: copiar piso, asignar
    tipología, numerar ambientes repetidos, crear variante, reemplazar un
    material y ver ficha.
  - Clic derecho en la celda (`cellMenuRegistry`).
- **FICHA (M113-09):** fórmulas y una acción para escribir el precio en
  VENTA. «‹ Anterior» y «Siguiente ›» son acciones del panel.
- **PROGRAMA (M113-10):**
  - Entradas, matriz piso × semana con formato condicional e indicadores.
  - La semana empieza el día de la obra (`_construction_period`), con la
    regla de M116-07.
  - Solo Inicio y Fin pasan a OBRA (ruta 2).
- **CONTROL y «Traer de Odoo» (M113-11):**
  - Campo `spreadsheet_id` en el asistente del maestro, para guardar la
    versión al importar.
  - Estado de la hoja en `documents.document`: borrador / importada /
    validada / enviada, con fecha y versión.
  - «Traer de Odoo» del mobiliario y CONTROL por piso, con un método que
    entrega los conteos del planificador (muebles, módulos a armar y ML total).
- **Ficha de la obra (M113-12):** botón inteligente con la versión y el
  estado; bloque «Hoja de trabajo» de solo lectura, salvo las filas.

### 4a · Implementación

- **Tipo de hoja:** `construction.vertical.profile.construction_spreadsheet_kind`
  (`al_construction_planner_spreadsheet`), con exportación e importación del
  perfil. El puente de mobiliario marca el perfil Mobiliario
  (`_construction_set_furniture_sheet`, sin pisar lo que ajustó la base) y deja
  el maestro solo para las obras sin perfil.
- **Menú:** la barra de la hoja de Odoo 19 muestra todos los menús raíz, sin
  mirar su `isVisible` (`menu.children` es una función y su `length` nunca es
  0). Esa era la causa de lo visto en dev1. Queda un solo menú «Planificación
  de obra» y cada opción es visible según el tipo de hoja. En una hoja que no
  es del planificador, el menú solo dice dónde abrirla.
- **Claves:** `models/sheet_keys.py` (`_CLAVES`, `apply_keys`). El envío y
  «Validar» aplican las claves antes de armar el libro. Al libro de
  presupuesto se le agregó la clave como un alias más de cada columna.
- **«Traer de Odoo» del presupuesto:** escribe INSUMOS, APU y APU_DETALLE por
  clave (de `_CLAVES` o, en una hoja anterior, por el encabezado) y no pisa las
  columnas de fórmula.
- **ERRORES:** fila de estado, encabezados en la fila 2 y «Ir» con
  `HYPERLINK("o-spreadsheet://<pestaña>")`. La hoja de Odoo no enlaza a una
  celda, solo a la pestaña.
- **M113-01:** el análisis del importador guarda `issues` (hoja, fila,
  columna, mensaje, tipo). Avisos nuevos: `module_unknown`,
  `piece_product_unknown`, `bom_without_module`, `obra_date_invalid` y
  `group_without_levels`. `obra_date` lee el número de serie de la hoja y las
  fechas como texto. Con «Tipo de módulo: Especial» escrito, el tipo especial
  sale del nombre. La vista previa cuenta las piezas.
- **CR-22 g, parcial:**
  - Hecho:
    - INSUMOS tiene «Para elegir» («tipo · nombre · unidad · código»);
    - APU_DETALLE elige el insumo con una lista sobre esa columna, y «Código
      del insumo» es una fórmula;
    - «Traer de Odoo» escribe nombres sin código, unidades en español y la
      etapa por su número y nombre;
    - encabezado y dos primeras columnas inmovilizados.
  - Queda para 4b:
    - INSUMOS y APU siguen con el código en la columna A, porque las fórmulas
      de APU_DETALLE y PRESUPUESTO lo buscan con `VLOOKUP`;
    - la receta por nombre en APU_DETALLE y la banda de color por receta.
- **Migraciones:**
  - `al_construction_planner_spreadsheet` 9.20261101:
    - quita `N()`;
    - agrega «Costo unitario sin APU» al final de PRESUPUESTO si falta;
    - pinta de gris los encabezados de fórmula;
    - crea `_CLAVES`.
  - `al_construction_planner_spreadsheet_furniture` 4.20261101: pasa el verde a
    gris y los encabezados de datos a amarillo, y crea `_CLAVES`.
  - En los datos y en la última foto, sin perder revisiones.
- **Pruebas:**
  - `al_construction_planner_spreadsheet/tests/test_package_116_stage4.py`;
  - `al_construction_planner_spreadsheet_furniture/tests/test_package_116_stage4.py`,
    con el recorrido `al_construction_furniture_sheet_menu`.
  - Corren en `test_pe_creval`: la base del núcleo no tiene Documentos.

### 4b · Implementación

- **M116-10:**
  - `ML_GROUPS` suma «Mueble completo» (`full`) y `ML_COUNTED` reúne los
    grupos que cuentan.
  - La tipología tiene `ml_full` y `ml_total`; además, `_ml_of_group` da a
    cada actividad por ML los metros de su grupo.
  - Lo usan el plan, la medición (driver «ML de mueble completo»), el árbol de
    recursos (ML del ambiente = total), el importador y las listas de la hoja.
  - Las actividades y tarifas de closets, baños, lavanderías y ductos son
    configuración.
- **M113-06:**
  - Las columnas son «Grupo de categoría», «Categoría» (ruta corta) y
    «Producto», con validación nativa, que filtra al escribir.
  - REFERENCIAS calcula para cada producto el grupo, la ruta corta, el último
    nivel y si está dentro de la raíz.
  - `_LISTAS` tiene una fila por grupo y por categoría con su `FILTER`, y
    cuatro filas por fila de datos con `INDEX/MATCH`. Con 8 000 filas son 33
    `FILTER` y unos 16 MB de hoja; el tiempo de apertura se mide en dev1.
  - BOM muestra «Unidad del producto (calc.)» y «Costo unitario (calc.)».
  - Formato condicional: rojo para el código fuera del maestro y de PRODUCTOS
    NUEVOS, ámbar para el costo 0.
  - Ajuste nuevo: «Categoría raíz de materiales de la hoja». Rige para las
    hojas nuevas.
- **M113-05:** «Filas de la hoja de trabajo» queda en la pestaña
  Planificación de la obra, con 0 = automático. La hoja guarda con cuántas
  filas nació (`construction_sheet_rows`).
- **M113-04:** asistente `construction.spreadsheet.import.wizard`.
  - El servidor lee el libro, prepara las filas por clave y convierte el
    producto en «nombre · unidad · código». Los códigos nuevos van a PRODUCTOS
    NUEVOS.
  - Guarda una versión antes de escribir y entrega las filas al cerrarse
    (`infos`).
  - La hoja escribe en el navegador y, si no alcanzan las filas, pide
    `construction_sheet_extension`: las mismas fórmulas, listas y marcas de la
    plantilla para las filas nuevas, y los rangos de RESUMEN.
  - Al terminar, valida y deja un mensaje en la obra.
  - Las hojas anteriores a este bloque no se amplían (sus listas tienen otro
    orden) y lo avisan.
- **Escrituras agrupadas:** cada dispatch de la hoja es una revisión que
  viaja sola al servidor. Las escrituras masivas (importar, ampliar, Traer de
  Odoo, ERRORES, Actualizar insumos) van en un comando `AL_CONSTRUCTION_BATCH`,
  que un complemento de la hoja (`featurePluginRegistry`) despacha en
  revisiones de 2 000 comandos.
- **Pendiente para 4c:**
  - materiales de la obra primero en la lista y «Reemplazar un material» (van
    con el panel);
  - de CR-22 g: receta por nombre en APU_DETALLE, banda de color por receta y
    el código al final en INSUMOS y APU.
- **Pruebas:**
  - `al_construction_planner_suite/tests/test_package_116_stage4.py`
    (mueble completo en el plan);
  - `al_construction_planner_spreadsheet_furniture/tests/test_package_116_stage4b.py`
    (listas, ampliación y asistente), con el recorrido
    `al_construction_furniture_sheet_import`, que sube un libro, amplía de 10 a
    17 filas y comprueba que el servidor guardó lo escrito.

### Pruebas de la etapa 4

- `al_construction_planner_suite/tests/test_package_116_stage4.py`:
  - un libro con los cinco casos de M113-01 (avisos en el asistente, errores
    en «Validar» y la obra sin datos parciales);
  - encabezado renombrado y columna obligatoria borrada (`_CLAVES`), en las
    dos hojas;
  - fechas de OBRA como número y como texto;
  - ML de mueble completo en la tipología y en una actividad por ML;
  - asistente «Importar Excel a la hoja» (lectura y análisis);
  - migración de una hoja de presupuesto anterior (sin `N(`, con la columna
    D1, encabezados grises).
- Pruebas JS de la hoja: escritura del asistente de importación, `collectSheets`
  con la lista de pestañas, ERRORES con «Ir».
- Prueba de punta a punta del 1.13 en dev1 con el libro de la obra de prueba
  de mobiliario: la corre ALTA, con la autorización que ya dio Vicente.

## Estimación

Días de desarrollo con pruebas automáticas, sin contar las pruebas en las
bases. La etapa 1 tomó uno. Las etapas 3 y 4 están estimadas desde sus
requerimientos; se precisan al diseñarlas.

| Etapa | Días | Lo que más pesa |
|---|---|---|
| 1 · Base común | 1 (hecha) | — |
| 2 · Requerimiento de obra y contratas | 8 a 10 | 2b (analítica, migración, D1 a D3): 4 a 5 · 2c (intervención): 2 a 3 · 2a: 2 |
| 3 · Cronograma | 6 a 7 | 3a: 2 (panel ampliable 1) · 3b: 4 a 5 (etapa actual con sus disparadores 2, carga semanal 1.5, informe 0.5) |
| 4 · Hoja de trabajo | 8 a 10 | 4a (claves de columna, ERRORES común, cinco casos de M113-01, migraciones de las hojas): 3 · 4b (importar Excel a la hoja, listas por categoría, mueble completo): 3 a 3.5 · 4c (INICIO, panel y acciones, FICHA, PROGRAMA, CONTROL): 2.5 a 3.5 |
| Total | 23 a 28 | |
