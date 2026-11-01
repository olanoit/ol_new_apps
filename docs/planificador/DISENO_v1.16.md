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

## Estimación

Días de desarrollo con pruebas automáticas, sin contar las pruebas en las
bases. La etapa 1 tomó uno. Las etapas 3 y 4 están estimadas desde sus
requerimientos; se precisan al diseñarlas.

| Etapa | Días | Lo que más pesa |
|---|---|---|
| 1 · Base común | 1 (hecha) | — |
| 2 · Requerimiento de obra y contratas | 8 a 10 | 2b (analítica, migración, D1 a D3): 4 a 5 · 2c (intervención): 2 a 3 · 2a: 2 |
| 3 · Cronograma | 5 a 6 | M115-04 y 05 (etapa de cada ambiente e informe) y M115-06 con M116-07 (carga semanal) |
| 4 · Hoja de trabajo | 7 a 9 | M113-01 a 04 y M116-09 (contrato de datos, pestaña ERRORES común, importar Excel) y las pestañas nuevas |
| Total | 21 a 26 | |
