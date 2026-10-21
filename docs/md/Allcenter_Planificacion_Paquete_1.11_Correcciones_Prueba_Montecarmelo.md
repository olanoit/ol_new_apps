# Planificación de obra — correcciones de la prueba Montecarmelo (paquete 1.11)

19-oct-2026 · versión 2 (21-oct-2026: resultados del desarrollo y de la prueba) · @Vicente · Para Cristóbal Och

## Objetivo y alcance

Este paquete junta las correcciones que salen de la prueba integral de Montecarmelo después de enviado el paquete 1.10. Se irá completando a medida que avance la prueba. Códigos M111.

Marcas de fuente:
- [V] leído o probado en `newallcenter_dev_1` el 19-oct-2026;
- [C] código leído en `olanoit/ol_new_apps`, rama 19.0: commit `38b5ada` para M111-01 y commit `2ef3210` (paquete 1.10 publicado) desde M111-02;
- [D] decisión de Vicente, con fecha;
- [P] propuesta de la asesoría, por validar;
- [R] resultado del desarrollo y de la prueba, 21-oct-2026 (commit `12b16572`).

| Código | Corrección | Hallazgo | Módulo | Tamaño [P] |
| --- | --- | --- | --- | --- |
| M111-01 | Avances y liquidaciones sin permisos de Nómina | HM-30 | `al_construction_attendance` | Pequeño |
| M111-02 | El asistente «Rechazar» de Aprobaciones no abre (urgente) | HM-43 | `al_construction_planner_approvals` | Pequeño |
| M111-03 | Operación por etapa en las listas que crea el importador | HM-40 | `al_construction_planner_mrp`, `al_construction_planner_furniture` | Mediano |
| M111-04 | Exceso falso por redondeo entre el plan y la lista | HM-41 | `al_construction_planner_furniture`, `al_construction_planner_approvals_mrp` | Mediano |
| M111-05 | Mismo % de exceso en Aprobaciones y en la orden de fabricación | HM-42 | `al_construction_planner_approvals`, `al_construction_planner_approvals_mrp` | Pequeño |
| M111-06 | Cifras de la solicitud cuando el pedido ya tiene líneas del plan asignadas | HM-44 | `al_construction_planner_approvals`, `al_construction_planner_purchase` | Pequeño |
| M111-07 | Vale de despacho del requerimiento para pegar en el bulto | Pedido de Vicente, 20-oct | `al_construction_material_request` | Pequeño |

El tamaño es una estimación de la asesoría para ordenar el trabajo, no un plazo. El plazo lo da Cristóbal.

## Avances y liquidaciones sin permisos de Nómina (M111-01)

Decisión de Vicente del 19-oct-2026: va como requerimiento de desarrollo, en este paquete y no en el 1.10, que ya se envió.

### Qué pasó [V]

- **18-oct:** Annabelees no pudo validar los avances AVN/2026/00001 a 00006 sin el grupo «Nómina: Encargado: gestionar todos los contratos». Se le dio ese grupo como parche temporal.
- **19-oct:** Anderson (produccion@allcenter.pe), que no tiene ningún grupo de Nómina, abrió la liquidación LIQ/2026/00001 y recibió este error:

  > Ocurrió un error al leer el campo project.project.construction_hr_site_ids. No puede acceder a los registros 'Obra de construcción' (l10n_pe.hr.construction.site). Esta operación está permitida para los siguientes grupos: Nómina/Administrador, Nómina/Encargado: gestionar todos los contratos.

### Causa [C]

1. **La pestaña de la liquidación:** la liquidación tiene la pestaña «Avances liquidados» (`al_construction_planner_subcontract/views/construction_settlement_views.xml`, l. 152-155). Usa la lista `al_construction_planner.construction_task_progress_view_list`.
2. **La columna heredada:** `al_construction_attendance` hereda esa lista y le agrega la columna «Con asistencia», `attendance_ok` (`views/contractor_views.xml`, l. 92-101).
3. **Cálculo con los permisos del usuario:** `attendance_ok` es un campo calculado y no guardado (`models/task_progress.py`, l. 9-12). En un campo así, Odoo calcula con los permisos del usuario, porque `compute_sudo` es falso por defecto.
4. **La lectura de la sede:** el cálculo llama a `progress.project_id._construction_site()` (`task_progress.py`, l. 27), que lee `construction_hr_site_ids` (`models/construction_site.py`, l. 106-111).
5. **El permiso que falla:** ese campo apunta al modelo `l10n_pe.hr.construction.site`, definido en `OL-PAYROLL/al_hr_pe_construction/models/hr_construction_masters.py` (l. 385). En dev1 solo pueden leerlo «Nómina: Administrador» y «Nómina: Encargado: gestionar todos los contratos» [V].

Por eso, un usuario sin Nómina recibe el error en estos casos:
- al abrir una liquidación semanal;
- al abrir la lista de avances;
- al abrir el menú «Avances sin asistencia», que filtra por `attendance_ok` (`contractor_views.xml`, l. 103-108).

En cambio, `distance_m` del avance no falla. También lee la sede, pero es un campo guardado (`al_construction_planner/models/construction_task_progress.py`, l. 101-103), y esos Odoo los calcula como superusuario.

### Corrección

- **`attendance_ok` con `compute_sudo=True`** en `al_construction_attendance/models/task_progress.py`. El valor solo dice si la contrata tuvo personal marcado ese día; no muestra datos de Nómina. La búsqueda `_search_attendance_ok` (l. 29-35) usa el mismo cálculo, así que queda cubierta.
- **Recomendado: `groups` en `construction_hr_site_ids`** con los grupos de Nómina (`hr_payroll.group_hr_payroll_user`). Si un usuario sin Nómina lee la obra completa, por ejemplo al exportar o duplicar, Odoo omite el campo en lugar de dar error. Antes de ponerlo, revisar que `construction_crew_attendance.py` (l. 259), que también lo lee, corra con permisos suficientes.
- **Versión:** en dev1 y en el repositorio, `al_construction_attendance` está en 3.20261016. La novedad va en `docs/fichas/al_construction_attendance.yml` y el `CHANGELOG.md` se genera con `scripts/gen_changelog.py`.

### Configuración de Allcenter después de publicar

Quitarle a Annabelees el grupo «Nómina: Encargado: gestionar todos los contratos», que se le dio solo como parche.

### Criterio de aceptación

- Anderson, sin Nómina, abre LIQ/2026/00001 y ve la pestaña «Avances liquidados» con la columna «Con asistencia», sin error.
- Annabelees, sin Nómina, valida un avance sin error.
- «Avances sin asistencia» abre para un usuario sin Nómina y muestra los mismos registros que para el administrador.
- Un usuario sin Nómina sigue sin poder abrir las sedes de obra de Nómina.

### Prueba automatizada

En `al_construction_planner_suite/tests`, con `PlannerCommon`, se crea un usuario con «Planificación de obra: Usuario» y sin Nómina, más una obra con sede y un avance de contrata. La prueba comprueba que ese usuario:
- lee `attendance_ok`;
- abre una liquidación;
- valida el avance;

y que nada de eso da error de acceso. Archivo propuesto: `test_permissions_v111.py`.

Efecto en Manufactura: ninguno directo. Evita que el jefe de producción y los supervisores necesiten permisos de Nómina para ver el avance de la obra.

## El asistente «Rechazar» de Aprobaciones no abre (M111-02)

Hallazgo de la prueba del paquete 1.10 del 19-oct-2026. Es urgente: mientras no se corrija, en dev1 nadie puede rechazar una solicitud de obra.

### Qué pasó [V]

El 19-oct, al intentar rechazar desde Aprobaciones la solicitud de RQO/2026/00017, el navegador mostró un error del cliente (OwlError) con este detalle:

> EvalError: Can not evaluate python expression: (bool(len(approval_ids) < 2)) — Error: Name 'len' is not defined

### Causa [C]

- **El paquete 1.10 cambió el asistente.** Para el rechazo en bloque (M110-07), el asistente de rechazo pasó de una solicitud (`approval_id`) a varias (`approval_ids`). Commit `2ef3210`, `al_construction_planner_approvals` 3.20261019.
- **La vista usa `len()`.** En `wizards/approval_refuse_wizard_views.xml` (l. 8-9), el campo lleva `invisible="len(approval_ids) &lt; 2"`. Esa expresión la evalúa el navegador, y en Odoo 19 el evaluador del navegador no tiene la función `len`. La vista falla al abrirse.
- **Falla en los dos caminos de rechazo**, porque los dos abren la misma vista:
  - el botón «Rechazar» del formulario de la solicitud (`action_construction_refuse`, `models/approval_request.py`, l. 386-395);
  - la acción «Rechazar» de la lista, para varias solicitudes a la vez.
- **Las pruebas automáticas no lo detectaron**, porque llaman al asistente desde Python y no abren la vista.

### Corrección

- Agregar al asistente un campo calculado `approval_count` (entero, sin guardar) con la cantidad de solicitudes, y usar `invisible="approval_count &lt; 2"`.
- Revisar las demás vistas del paquete 1.10 que usen funciones de Python en `invisible`, `readonly` o `required`, como `len`, `sum` o `any`. En todo el repositorio solo aparece esta (búsqueda de `len(`, `sum(`, `any(`, `all(`, `max(` y `min(` dentro de `invisible`, `readonly`, `required` y `column_invisible` en los XML, commit `2ef3210`, 19-oct).
- Agregar una prueba de vista: un recorrido (tour) o `Form` sobre el asistente que abra la vista con una y con dos solicitudes.

### Criterio de aceptación

- Desde el formulario de una solicitud pendiente, «Rechazar» abre el asistente, pide el motivo y rechaza.
- Desde la lista, con dos solicitudes marcadas, Acciones › «Rechazar» abre el asistente con las dos y rechaza solo las que le tocan al usuario.
- Con una solicitud ya aprobada cuyo documento siguió, rechazar da el aviso de M110-08 («El documento … ya siguió con la aprobación…»), no un error del navegador. El aviso ya funciona en el servidor: se comprobó en dev1 el 19-oct llamando al rechazo de la solicitud de RQO/2026/00017.

Efecto en Manufactura: el jefe de producción y la jefatura pueden volver a rechazar excesos de órdenes de fabricación y pedidos de accesorios.

## Prueba del paquete 1.10 con la obra ZZMONTEC2-41-26

Decisión de Vicente del 19-oct-2026: los cuatro hallazgos siguientes van como requerimiento en este paquete. Salen de la obra de prueba «ZZMONTEC2-41-26 MONTECARMELO PRUEBA 1.10» (piso 3, plan PLR/2026/00004), corrida en dev1 el 19-oct con el commit `2ef3210`.

## Operación por etapa en las listas que crea el importador (M111-03)

### Qué pasó [V]

Las listas de fabricación que crea el importador para la obra nueva no tienen operaciones. Por eso las órdenes de corte (PPD/MO/00036 a 00048) y de armado (BRE/MO/00031 a 00043) no generaron órdenes de trabajo ni pasaron por ninguna estación. En la primera obra (ZZMONTEC-40-26) las órdenes de armado BRE/MO/00006 a 00017 sí tuvieron orden de trabajo, con listas preparadas antes del paquete 1.10.

### Causa [C]

`_construction_write_bom` (`al_construction_planner_furniture/models/construction_stage_bom.py`, l. 93-127) crea la lista con producto, secuencia, tipo de operación y obra, y escribe solo los componentes. Su comentario dice que «las operaciones y lo demás puesto a mano se conservan», pero en una lista nueva no hay nada puesto a mano. La etapa no tiene ningún campo de estación (búsqueda de `workcenter` en `al_construction_planner_mrp` y `al_construction_planner_furniture`, sin resultados).

### Corrección [P]

- **Estación por defecto en la etapa:** campo nuevo en `al_construction_planner_mrp`, junto a la planta y la categoría de M110-01, por compañía: «Estación de la etapa» (`mrp.workcenter`), más «Minutos por unidad» como tiempo estándar (puede ser 0).
- **Operación al crear la lista:** si la lista no tiene operaciones y la etapa tiene estación, `_construction_write_bom` crea una operación con el nombre de la etapa («Producción de piezas», «Armado»), esa estación y ese tiempo. Si la lista ya tiene operaciones, no las toca.
- **Listas ya creadas:** una acción «Completar operaciones» en la obra, o la misma regla al volver a importar, para las obras de prueba que ya existen.
- **Configuración de Allcenter después de publicar:** etapa 1.1 con la estación de corte de Puente Piedra y etapa 1.2 con la de armado de Breña (Azcona o Castrovirreyna, a decidir por Producción).

### Criterio de aceptación

- Obra nueva importada: al confirmar la orden de armado, ella y su orden de corte tienen una orden de trabajo en la estación de su etapa.
- Una lista con operaciones puestas a mano conserva las suyas al volver a importar.
- Una etapa sin estación crea la lista sin operaciones, como hoy.

Efecto en Manufactura: el corte y el armado vuelven a aparecer en las estaciones y en la planificación de planta, con tiempos para medir la carga.

## Exceso falso por redondeo entre el plan y la lista (M111-04)

### Qué pasó [V]

Las órdenes de corte PPD/MO/00036 (cocina C07) y PPD/MO/00045 (cocina C09) salieron «excede» sin que nadie cambiara nada. Ejemplo en C07: el material 3103002 tiene 0.21 en el plan y 0.23 en la lista. La lista suma las 11 cantidades por módulo sin redondear (0.2327); el plan las redondea a 0.01 por módulo y luego suma. Las dos órdenes generaron solicitudes de exceso (46 y 47) por diferencias de céntimos.

### Causa

La lista y el plan calculan la misma cantidad por caminos distintos y redondean en momentos distintos [V, comparación de cantidades en dev1]. El punto exacto donde el plan redondea por módulo no se ubicó en esta revisión; queda para Cristóbal.

### Corrección [P]

- **Recomendado: una sola fuente.** La cantidad de cada componente en la lista de la etapa sale de las mismas cantidades por módulo que usa el plan, ya redondeadas, sumadas por tipología. Así plan y lista coinciden por construcción.
- **Alternativa:** el control de exceso de la orden ignora diferencias menores o iguales al redondeo acumulado (número de módulos × media unidad del redondeo del plan). Es más simple pero deja dos números distintos a la vista.

### Criterio de aceptación

- En una obra importada de nuevo, ninguna orden de corte ni de armado sale «excede» sin cambios de material o cantidad.
- La pestaña «presupuestado frente a requerido» muestra la misma cantidad en las dos columnas para el 3103002 de C07.
- Un exceso real de una unidad sigue marcándose.

Efecto en Manufactura: el jefe de producción solo recibe solicitudes de exceso cuando de verdad se pide de más.

## Mismo % de exceso en Aprobaciones y en la orden de fabricación (M111-05)

### Qué pasó [V]

La solicitud de la orden PPD/MO/00036 mostraba en la lista de Aprobaciones «Exceso %» 9.52 %, mientras la orden mostraba 0 % y un monto de S/ 0.06. Quien aprueba ve un número que no es el de la orden.

### Causa [C]

- **La orden** calcula según la base de la compañía (`construction_production_margin_basis`). Con «por orden», el % es el monto del exceso entre el presupuesto total de la orden (`al_construction_planner_approvals_mrp/models/mrp_production.py`, l. 144-152). En dev1 la compañía tiene «por orden» y margen 5 %.
- **La solicitud** toma siempre el mayor % de sus líneas: `construction_excess_pct = max(lines.mapped('construction_diff_pct'))` (`al_construction_planner_approvals/models/approval_request.py`, l. 99-100), sin mirar la base de la compañía.

### Corrección [P]

- El «Exceso %» de la solicitud lo da el documento de origen, con su propia regla. Para la orden de fabricación es su `construction_excess_pct`; para el requerimiento, el que ya calcula `_construction_approval_info`.
- El mayor % por línea puede seguir visible en el detalle de cada línea de la solicitud.

### Criterio de aceptación

- Con base «por orden», la solicitud de PPD/MO/00036 muestra el mismo % que la orden.
- Con base «por material», muestra el mayor % de las líneas, como la orden.

Efecto en Manufactura: el jefe de producción y la jefatura deciden con el mismo número que ve la planta.

## Cifras de la solicitud cuando el pedido ya tiene líneas del plan asignadas (M111-06)

### Qué pasó [V]

- **Primer pedido, RQO/2026/00017:** 74 tornillos 4x30 para instalación. La solicitud mostró presupuestado 54, ya pedido 0, saldo 54, pedido 74 y exceso 20 (37.04 %). Correcto.
- **Segundo pedido, RQO/2026/00018:** el mismo material otra vez. El exceso salió bien (20), pero las demás cifras no: presupuestado 30, ya pedido 50, saldo −20 y 66.67 %. Lo correcto es presupuestado 54, ya pedido 74, saldo −20 y el % sobre 54.

### Causa [C]

`_construction_approval_info` (`al_construction_planner_approvals/models/construction_material_request.py`, l. 46-110) calcula las cifras sobre `_construction_candidate_plan_lines`. Ese método devuelve solo las líneas del plan ya asignadas al pedido cuando las hay, y solo si no hay ninguna busca todas las del mismo material bajo su nivel (`al_construction_planner_purchase/models/construction_material_request.py`, l. 230-246; con etapa, `construction_material_request_scope.py`, l. 401-409). El segundo pedido ya tenía asignada una línea de 30, así que «presupuestado» quedó en 30 y «ya pedido» salió de restar el saldo a esas 30.

### Corrección [P]

- Para las cifras de la solicitud (presupuestado, ya pedido, saldo y %), usar siempre todas las líneas del plan del mismo material bajo el nivel y la etapa del pedido, tengan o no asignación.
- El cálculo del exceso (`_construction_get_excess`) se queda como está: ya da el número correcto.

### Criterio de aceptación

- Se repite la prueba: RQO/2026/00017 por 74 y luego RQO/2026/00018 por 20 del mismo material y etapa. La segunda solicitud muestra presupuestado 54, ya pedido 74, saldo −20, pedido 20, exceso 20 y 37.04 %.
- Un pedido sin asignaciones muestra lo mismo que hoy.

Efecto en Manufactura: ninguno directo. Quien aprueba materiales de instalación ve cuánto se pidió en total contra lo presupuestado.

## Vale de despacho del requerimiento (M111-07)

Pedido de Vicente del 20-oct-2026, ajustado el mismo día. Lo nativo se configura y se desarrolla un vale para pegar en el bulto. El vale muestra todo el requerimiento y, en cada producto, cuánto se despachó y cuánto falta, para que el capataz que recibe en obra sepa que lo demás está en proceso.

### Cómo trabaja el almacenero con lo nativo [V]

- **Los despachos le llegan por requerimiento.** Al procesar el requerimiento:
  - lo disponible en el origen sale en una transferencia «Despacho a obra» en estado «Listo»;
  - lo que falta comprar queda en otra transferencia «En espera de otra operación».

  Ejemplo en dev1, RQO/2026/00023 (AFFINITY-25-26): BRE/DO/00016 «Listo», con 100 tapatornillos, y BRE/DO/00017 «En espera», con 50 burletes que dependen del requerimiento de compra PR00005.
- **Favoritos configurados el 20-oct en dev1** para Lady Silva y Crisanto:
  - «Pendientes por requerimiento», en «Requerimientos de obra › Requerimientos › Materiales pedidos». Es la vista de trabajo del almacenero (decisión de Vicente, 20-oct). Está como favorito predeterminado: al abrir el menú van directo a una fila por producto, agrupada por requerimiento, con pedido, a despachar, a comprar, recibido en obra y «Situación». Toma las líneas no completas de requerimientos «Aprobado» y «En proceso».
  - «Despacho a obra por requerimiento», en la lista de transferencias: despachos a obra abiertos de Breña y Puente Piedra, agrupados solo por requerimiento. Vicente lo vio en pantalla el 20-oct y pidió quitar la separación por estado. En esa lista cada fila es una transferencia: Odoo no muestra ahí una fila por producto.
  - «Requerimientos por despachar», en la lista de requerimientos: requerimientos «Aprobado» y «En proceso».
- **Del despacho al requerimiento.** En la transferencia, el enlace «Requerimiento de obra» (pestaña «Logística PE») abre el requerimiento. En su pestaña de materiales cada producto muestra «A despachar», «A comprar», «Recibido en obra» y «Situación».

### Por qué el vale actual no sirve para el bulto [V] [C]

«Imprimir vale» (`report/construction_material_request_report.xml`) se probó con RQO/2026/00023.

Lo que ya trae:
- cada material con «A despachar» y «A comprar»: tapatornillos 100 a despachar, burletes 50 a comprar;
- las transferencias BRE/DO/00016 y BRE/DO/00017;
- el requerimiento de compra PR00005.

Lo que no sirve para pegar en el bulto:
- **Imprime montos:** «Valor estimado S/ 393,50».
- **Imprime stock interno:** «Disponible al procesar 68,943.50».
- **No dice qué va en el bulto** ni cuánto se despachó antes.
- **No imprime la «Situación»** de cada producto.
- **Solo se imprime desde el requerimiento**, no desde el despacho que prepara el almacenero.

El «Recibo de entrega» nativo de Odoo tampoco alcanza. Solo lista como pendiente lo que quedó en la misma transferencia (`stock/report/report_deliveryslip.xml` de Odoo 19, l. 181-196), y lo que espera compra va en otra transferencia.

### Corrección [P]

Un reporte nuevo, «Vale de despacho», en `al_construction_material_request`, con el formato común de `al_report_base` (el mismo encabezado del vale actual). Hecho en el módulo; no desde la base.

**Dónde se imprime**
- **En la transferencia con «Requerimiento de obra»:** Imprimir › «Vale de despacho». Es el uso principal: acompaña ese bulto.
- **En el requerimiento:** botón «Imprimir vale de despacho». Sin transferencia de referencia, no lleva la columna «En este bulto».
- Si se marcan varias transferencias del mismo requerimiento en la lista, sale un vale por transferencia.

**Diseño del documento** (A4 vertical, sin precios ni montos)

1. **Encabezado**, igual que el vale actual: datos de la compañía, título «Vale de despacho», N.º del requerimiento y transferencia que acompaña (por ejemplo «Bulto BRE/DO/00016»).
2. **Datos del envío**, en dos columnas:
   - obra (código y nombre) y ubicación de obra;
   - solicitado por, fecha del requerimiento y fecha requerida;
   - almacén de origen y fecha de despacho (la de validación; si no está validada, la de impresión).
3. **Tabla de materiales: todas las líneas del requerimiento**, también las que no van en este bulto. Columnas:

| Columna | Contenido |
| --- | --- |
| Ítem | Correlativo |
| Material | Código y nombre; debajo, en letra chica, piso, ambiente o tarea si la línea los tiene |
| Unidad | Unidad de la línea |
| Pedido | `product_qty` |
| Despachado antes | Movimientos hechos de la línea hacia la obra en otras transferencias (`qty_dispatched` menos lo de esta transferencia) |
| En este bulto | Cantidad de la línea en esta transferencia: lo preparado si aún no se valida, lo hecho si ya se validó. En negrita |
| Pendiente | Pedido − despachado antes − en este bulto; nunca menor que 0 |
| Situación | Texto corto en palabras, ver abajo |

   **Texto de la columna «Situación»**, a partir de la situación de la línea y sus documentos:
   - «Completo» si no queda pendiente;
   - «Va completo en este bulto» si este bulto cierra la línea;
   - «Por despachar · BRE/DO/00017» si está reservado en otra transferencia;
   - «En compra · PR00005» y, si ya hay orden de compra, «· OC P000xx · llega dd/mm» con la fecha prevista;
   - «Cancelado» si la línea se anuló.

   Las filas que no van en este bulto van en gris claro, para que el capataz vea primero lo que recibe.
4. **Resumen bajo la tabla**, en una línea: «En este bulto: 1 de 2 materiales. Pendientes: 1 (en compra).»
5. **Pie:**
   - «Despachado por» (nombre del almacenero y firma);
   - «Recibido por» (nombre del capataz, firma, fecha y hora);
   - nota fija: «Este vale acompaña el bulto. Los pendientes se enviarán en otro despacho.»

**Ejemplo con RQO/2026/00023**, impreso desde BRE/DO/00016 antes de validar:

| Ítem | Material | Unidad | Pedido | Despachado antes | En este bulto | Pendiente | Situación |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [3200018] TAPATORNILLO BLANCO | Unidades | 100 | 0 | **100** | 0 | Va completo en este bulto |
| 2 | [31051499] BURLETE AUT. 5X10X5MT | m | 50 | 0 | 0 | 50 | En compra · PR00005 |

### Criterio de aceptación

- **Desde BRE/DO/00016:** el vale de RQO/2026/00023 sale como el ejemplo, sin montos y sin stock disponible.
- **Después de recibir la compra:** BRE/DO/00017 queda «Listo». Su vale muestra los tapatornillos con «Despachado antes» 100 y «Completo», y los burletes con «En este bulto» 50, pendiente 0.
- **Desde el requerimiento:** el vale sale sin la columna «En este bulto».
- **Sin requerimiento:** la opción no aparece en transferencias que no tienen «Requerimiento de obra».
- **El vale actual** («Vale de requerimiento de obra») no cambia.

Efecto en Manufactura: ninguno directo. La obra sabe qué le falta recibir sin llamar al almacén.

## Resultado del desarrollo y de la prueba (21-oct-2026) [R]

Las siete correcciones están desarrolladas en el commit `12b16572` (rama 19.0), publicado y desplegado el 21-oct en `newallcenter_dev_1`, `newallcenter_dev_2` y `creval_dev_1`, con respaldo previo de cada base. Pruebas automáticas: 415 en verde en la base de desarrollo (planificador con sus puentes, asistencia, hoja de cálculo y requerimiento de obra).

### Qué se hizo en cada corrección

| Código | Cómo quedó | Desvío de la propuesta |
| --- | --- | --- |
| M111-01 | «Con asistencia» se calcula sin los permisos del usuario. Las sedes de obra llevan los grupos de Nómina: quien no tiene Nómina lee o exporta la obra sin ese campo. | Además, quien marca una obra sin tener Nómina ya puede crearle su sede automática (fallaba por el mismo permiso). La prueba está en `al_construction_attendance/tests/test_permissions_v111.py`, no en la suite. |
| M111-02 | El asistente usa `approval_count` en lugar de `len()`. Una prueba nueva revisa que ninguna vista del planificador use en `invisible`, `readonly` o `required` una función que el navegador no evalúa. | La prueba de vista es esa revisión de todas las vistas más un `Form` del asistente con una y con dos solicitudes, no un recorrido en el navegador. |
| M111-03 | «Estación de la etapa» y «Minutos por unidad» por compañía en Configuración › Etapas. Al importar, la lista por etapa sin operaciones recibe una con el nombre de la etapa, esa estación y ese tiempo. La obra tiene el botón «Completar operaciones». | Ninguno. |
| M111-04 | Se tomó la opción recomendada: la lista suma las cantidades por módulo ya redondeadas como el plan. | Ninguno. El punto donde el plan redondea es la precisión de «Cantidad» de la línea del plan, una línea por módulo. |
| M111-05 | El documento de origen da el «Exceso %» al crear la solicitud. Las solicitudes anteriores conservan el mayor % de sus líneas. | Para un plan de recursos, la solicitud muestra 0 % (decisión de Vicente del 21-oct-2026). Lo que sube frente a la versión que reemplaza sigue eligiendo los tramos de la tabla de rutas. |
| M111-06 | Las cifras de la solicitud salen de todas las líneas del plan del material bajo el nivel y la etapa del pedido. El cálculo del exceso no cambia. | Ninguno. |
| M111-07 | Reporte «Vale de despacho» con las columnas y los textos de «Situación» propuestos. Se imprime desde la transferencia (solo si tiene requerimiento) y desde el requerimiento (botón «Imprimir vale de despacho», en proceso o hecho). | El texto «Pendiente» aparece cuando la línea no tiene transferencia ni compra. El resumen separa los pendientes por tipo: «Pendientes: 2 (1 en compra, 1 por despachar).» |

### Configuración hecha en dev1 y dev2 (21-oct)

- **M111-01:** en dev1 se le quitó a Annabelees el grupo «Nómina: Encargado: gestionar todos los contratos». En dev2 ya no lo tenía. Con su usuario se comprobó que lee los avances y abre LIQ/2026/00001 sin error.
- **M111-03:**
  - etapa 1.1 con «Producción de piezas · Puente Piedra» y etapa 1.2 con «Armado · Azcona», las dos con 60 minutos por unidad;
  - se tomó Azcona porque es la estación que Producción puso a mano en las listas de ZZMONTEC-40-26 (falta que Producción lo confirme);
  - si se elige Castrovirreyna 2.º piso, se cambia la etapa 1.2 y también la operación de cada lista que ya la tiene.
- **M111-04:** se rehicieron las listas de ZZMONTEC-40-26 y de ZZMONTEC2-41-26 en dev1 y de ZZMONTEC-40-26 en dev2, con la misma regla que el importador. Antes se simuló sin guardar:
  - en cada obra cambiaron 16 líneas, todas por redondeo (como mucho 0.02);
  - el 3103002 de C07 pasó de 0.23 a 0.21, lo mismo que el plan;
  - las listas con operaciones puestas a mano las conservaron.

### Criterios de aceptación

| Código | Criterio | Resultado |
| --- | --- | --- |
| M111-01 | Sin Nómina se abre la liquidación con «Avances liquidados», se valida un avance y «Avances sin asistencia» muestra lo mismo que al administrador; las sedes siguen cerradas | **Cumple** (prueba automática; en dev1 y dev2 con el usuario de Annabelees) |
| M111-02 | Rechazar desde el formulario y desde la lista; aviso de M110-08 con una solicitud ya aprobada | **Cumple** en las pruebas automáticas; en dev1 se verificó que la vista ya no usa `len()`. En la E-03 no hubo excesos, así que no se rechazó nada en pantalla |
| M111-03 | Órdenes de armado y de corte con orden de trabajo en su estación; lista con operaciones a mano conservada; etapa sin estación, lista sin operaciones | **Cumple** (prueba automática y E-03 en dev1 y dev2: 27 de 27 órdenes con su orden de trabajo) |
| M111-04 | Ninguna orden «excede» sin cambios; el 3103002 de C07 igual en las dos columnas; un exceso real de una unidad se sigue marcando | **Cumple** (E-03: 0 excesos en 54 órdenes; 3103002 de C07: 0.21 y 0.21. El exceso real está cubierto por prueba automática) |
| M111-05 | Con base «por orden», la solicitud muestra el % de la orden; con «por material», el mayor de las líneas | **Cumple** (prueba automática). En la E-03 ninguna orden pidió aprobación |
| M111-06 | RQO por 74 y luego por 20: presupuestado 54, ya pedido 74, saldo −20, exceso 20 y 37.04 % | **Cumple** en dev1 con RQO/2026/00017 y 00018, en dev2 con RQO/2026/00007 y 00008 (ver «Prueba de M111-06 en dev1 y dev2») y en prueba automática |
| M111-07 | Vale desde BRE/DO/00016 como el ejemplo; después de la compra; desde el requerimiento sin «En este bulto»; solo en transferencias con requerimiento; el vale actual no cambia | **Cumple** (prueba automática; en dev1 el vale de RQO/2026/00023 desde BRE/DO/00016 da «Va completo en este bulto» para los tapatornillos y «En compra · PR00005» para los burletes, sin montos) |

### Prueba E-03 repetida (21-oct)

El piso 3 de cada obra ya estaba fabricado y despachado. Por eso se copió como «Piso 04», con los Dptos 401 a 403, sus 14 ambientes y sus 60 módulos en «Planificado». Luego se generó una versión nueva del plan, que aprobó Annabelees, y la versión anterior quedó «Reemplazado».

| Paso | dev1 · ZZMONTEC2-41-26 | dev2 · ZZMONTEC-40-26 |
| --- | --- | --- |
| Plan | PLR/2026/00006 (v2) | PLR/2026/00007 (v2)¹ |
| Órdenes en una corrida | 14 de corte (PPD/MO/00049 a 00062) y 13 de armado (BRE/MO/00044 a 00056) | 14 de corte (PPD/MO/00015 a 00028) y 13 de armado (BRE/MO/00014 a 00026) |
| Excesos al confirmar | 0 | 0 |
| Órdenes de trabajo | 27, en su estación, terminadas | 27, en su estación, terminadas |
| Traslados Puente Piedra → Breña | PPD/OUT/00225 a 00237, BRE/IN/02156 a 02168, BRE/PC/00044 a 00056 | 13 salidas, 13 recepciones y 13 preparaciones, hechas |
| Despacho por departamento | BRE/DO/00018 a 00020 y PPD/DO/00004 (closet CL01B) | BRE/DO/00004 a 00006 y PPD/DO/00002 (closet CL01B) |
| Módulos | 60 «En obra» | 60 «En obra» |
| Aprobación en bloque | Nada que aprobar | Nada que aprobar |

¹ En dev2, 19 líneas del segundo módulo de closet (MCL02) no tenían costo, porque el plan anterior de dev2 es de antes de la corrección de los closets. Se les puso el costo del plan de dev1: corredera 55 cm (3105222) 9.08, corredera 45 cm (3105412) 7.70 y melamina blanco fantasía (3101161) 72.43.

Frente a la corrida del 19-oct: aquella dio excesos falsos de céntimos en el corte de las cocinas y ninguna orden de trabajo. Esta no dio excesos, y las 54 órdenes pasaron por su estación.

### Prueba de M111-06 en dev1 y dev2 (21-oct)

**dev1.** 
RQO/2026/00017 (74 tornillos 4x30 para instalación, ya aprobada) no se tocó. RQO/2026/00018 seguía «Por aprobar» con la solicitud del 19-oct, calculada antes de la corrección. Se pasó a borrador, lo que canceló esa solicitud, y se volvió a enviar con el mismo usuario.

| Cifra | Solicitud del 19-oct | Solicitud del 21-oct | Criterio |
| --- | --- | --- | --- |
| Presupuestado | 30 | 54 | 54 |
| Ya pedido | 50 | 74 | 74 |
| Saldo | −20 | −20 | −20 |
| Pedido | 20 | 20 | 20 |
| Exceso | 20 | 20 | 20 |
| Exceso % | 66.67 | 37.04 | 37.04 |

- El pedido sigue con una sola línea del plan asignada (20 unidades); las cifras salen de las 7 líneas del material bajo su nivel y su etapa.
- La solicitud usa el plan PLR/2026/00006 (v2), que reemplazó a PLR/2026/00004 en la E-03: las asignaciones pasaron a la v2 y las cifras no cambian.
- La solicitud quedó pendiente, a cargo de Kevin Jimenez o Annabelees León.

**dev2.** No tenía RQO/2026/00017 ni 00018: la prueba del 19-oct se hizo solo en dev1. Se armó el mismo caso en ZZMONTEC-40-26: tornillos 4x30 (3105097) para la instalación de la cocina del Dpto 301, con 54 presupuestados en 7 líneas del plan PLR/2026/00007.

| Cifra | RQO/2026/00007 (74) | RQO/2026/00008 (20) | Criterio del segundo |
| --- | --- | --- | --- |
| Presupuestado | 54 | 54 | 54 |
| Ya pedido | 0 | 74 | 74 |
| Saldo | 54 | −20 | −20 |
| Exceso | 20 | 20 | 20 |
| Exceso % | 37.04 | 37.04 | 37.04 |
| Estado | Aprobado por Annabelees | Pendiente (Annabelees) | |

- RQO/2026/00008 tiene asignada una sola línea del plan; sus cifras salen de las 7 líneas del nivel.
- Los números 00005 y 00006 los consumió una simulación previa sin guardar, porque la numeración no se revierte.

### Decidido el 21-oct-2026 [D]

- **% de la solicitud del plan:** muestra 0 %. Con la primera versión de M111-05 mostraba lo que sube frente a la versión vigente: 99.93 % en la v2 de la E-03, que agrega un piso entero. Corregido en `al_construction_planner_approvals` 5.20261021.

### Para decidir

- **Estación de armado de Breña:** Azcona o Castrovirreyna 2.º piso, a confirmar por Producción.

## Fuentes

- **Base `newallcenter_dev_1`**, 19-oct-2026:
  - error de acceso de Anderson al abrir LIQ/2026/00001, en la captura enviada por Vicente;
  - permisos de acceso del modelo `l10n_pe.hr.construction.site`;
  - grupos de los usuarios Anderson y Annabelees;
  - versión instalada de `al_construction_attendance`.
- **Repositorio `olanoit/ol_new_apps`, commit `38b5ada`:** `al_construction_attendance`, `al_construction_planner_subcontract`, `al_construction_planner` y `al_hr_pe_construction`.
- **Error del asistente de rechazo** en dev1, 19-oct-2026, captura enviada por Vicente; repositorio en el commit `2ef3210`.
- **Prueba del paquete 1.10 en dev1**, 19-oct-2026: obra ZZMONTEC2-41-26, plan PLR/2026/00004, órdenes PPD/MO/00036 y 00045, requerimientos RQO/2026/00017 y 00018 y sus solicitudes de aprobación.
- **Repositorio en el commit `2ef3210`:** `al_construction_planner_furniture`, `al_construction_planner_approvals`, `al_construction_planner_approvals_mrp` y `al_construction_planner_purchase`.
- **Caso de prueba integral Montecarmelo:** hallazgos HM-30 y HM-40 a HM-44.
- **Vale de despacho (M111-07):** pedido de Vicente del 20-oct-2026 y su ajuste del mismo día; vale de RQO/2026/00023 impreso en dev1; RQO/2026/00023 y sus transferencias en dev1; grupos de Lady Silva; `al_construction_material_request` en el repositorio; `stock/report/report_deliveryslip.xml` de Odoo 19 (github.com/odoo/odoo, rama 19.0).
- **Resultados (21-oct-2026):** commit `12b16572`; pruebas automáticas en la base de desarrollo; configuración y prueba E-03 en `newallcenter_dev_1` y `newallcenter_dev_2`, con respaldos del 21-oct previos a cada cambio.
