Historial de cambios — Planificación de obra (AL)
=================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_planner.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 19.20261012 — 12/10/2026

- Menús organizados como Contabilidad: de 8 menús principales a Obras (obras y tareas, plan de recursos, cronograma), Ejecución (avance y contratas), Abastecimiento, Ingresos, Informes (plan, cronograma valorizado, compras) y Configuración (plan de obra, aprobaciones y Gantt); se quita el menú repetido «Precios de compra».

## 18.20261011 — 11/10/2026

- Más rápido con obras grandes: la tabla de valorizaciones previstas de la obra y el control de las líneas al generar ya no reúnen las líneas de una en una.

## 17.20261011 — 11/10/2026

- Generar el plan valida la compañía de las líneas por lotes: en una obra de 7.800 líneas ahorra cerca de 20 segundos.

## 16.20261011 — 11/10/2026

- Generar el plan crea las actividades por metro lineal de la obra con el ML bajo y alto de la tipología cuando los módulos no traen ancho (con ETO siguen bajando al módulo).
- Las fechas del calendario de ingresos y de las liquidaciones también evitan los feriados nacionales de Perú (pe.public.holiday); los feriados se leen una vez por transacción.
- Servicio con «Crea una obra»: al confirmar la venta, el proyecto queda marcado como obra y con su orden de venta del contrato; una obra marcada después toma su venta de origen.
- Obras ▸ Obras se abre dentro de Planificación de obra.
- «Solicitar aprobación» resume cada producto o actividad una vez, con sus líneas y departamentos; la importación ya no muestra un instante «no es un libro Excel válido».

## 15.20261011 — 11/10/2026

- Con el planificador instalado, la aplicación Gantt deja de mostrarse en el menú: el Gantt de todos los proyectos está en Cronograma ▸ Gantt de proyectos y sus colores por estado en Configuración ▸ Colores del Gantt. Al desinstalar el planificador, la aplicación Gantt vuelve a aparecer.

## 14.20261011 — 11/10/2026

- La valorización impresa usa el formato común de los documentos de la suite (el del comprobante A4, módulo al_report_base): recuadro R.U.C./tipo/número con el estado, datos de obra y contrato, partidas con los totales al pie (entregado, confirmado, por valorizar, amortización, fondo de garantía y neto a cobrar), conformidad del cliente y firmas.

## 13.20261011 — 11/10/2026

- Modo oscuro: el panel de recursos del cronograma (P-15) toma el fondo del tema; el diagrama y su barra lo heredan del Gantt de proyectos.

## 11.20261011 — 11/10/2026

- Importar maestro y ETO (fase 12, W-15): libro Excel con catálogo de actividades, tipologías, plantilla de módulos, actividades por ambiente, BOM con etapa y árbol de la obra, o solo con el ETO (código y ancho real de cada módulo).
- Vista previa sin escribir nada con conteos por hoja y advertencias (BOM sin etapa con su monto, productos que no existen o sin costo, productos repetidos, actividades o tipologías desconocidas, ambientes del ETO que no existen, decimales de más); importación idempotente.
- «Generar plan» usa el ancho real del módulo del ETO para la instalación y la limpieza por ML.
- Plantilla vacía y libros de ejemplo de una obra genérica (maestro y ETO) para descargar desde el asistente.

## 10.20261010 — 10/10/2026

- Cronograma valorizado (fase 11, P-22): por obra y semana, costo, ingreso devengado, margen, valorización confirmada, facturado y cobrado en plan (líneas repartidas en los días hábiles de su etapa y calendario de P-21) y real (ejecutado, entregas, valorizaciones, facturas y cobros conciliados), con curva S, fondo de garantía al cierre, Excel, pivote y gráfico.
- Inicio de la aplicación (P-01) como acción por defecto: obras con plan, planificado, saldo, avance, próximo hito y estado, y «Pendientes de hoy» por grupo con su lista filtrada.
- Supervisores de obra en el proyecto: el supervisor ve en su inicio solo los avances y liquidaciones por validar de sus obras.
- Menú «Reportes» (cronograma valorizado, su análisis, control de saldo y precios de compra) y «Cobranza de la obra» en Ingresos.

## 9.20261010 — 10/10/2026

- Calendario e ingresos de la obra (fase 10, P-21): OV del contrato, valorización cada n semanas o en fechas fijas, plazos de presentación, confirmación, factura y cobro, adelanto y fondo de garantía, con valores por defecto en Ajustes y tabla de valorizaciones previstas corridas al siguiente día hábil.
- Entrega semanal (P-19): una por obra y semana, creada por la acción programada del día de liquidación y confirmada por la Jefatura; avance valorizado de la partida con material consumido, ingreso devengado sin redondear el avance, costo y margen.
- Valorización con el cliente (P-20): W-13 con las entregas confirmadas hasta el corte, envío con PDF, observaciones con fecha y autor, conformidad obligatoria (W-14) y lo no confirmado por valorizar.
- «Crear factura» desde la OV con la cantidad entregada al % acumulado confirmado y la valorización en la factura; no se publica por encima de lo confirmado.

## 8.20261010 — 10/10/2026

- Precios de compra del producto (fase 9, P-16): compras confirmadas de una ventana editable en soles al tipo de cambio de su fecha, con ponderado, mediana, desviación, medias móviles de 4 semanas y 3 meses, resumen por semana, mes y proveedor y gráfico semanal con las compras atípicas.
- «Aplicar costo» (W-12) suma la media móvil de 4 semanas y se abre desde P-16 con la base elegida.
- Crear producto desde el plan (W-11, P-17): código de familia más correlativo asignado al guardar, productos parecidos antes de crear, producto activo marcado con el plan y actividad a Logística.
- Abastecimiento de la obra (P-18): necesidad por semana de la etapa, stock, OC abiertas, cantidad a comprar, costo del plan y último precio con alerta; la compra masiva sale con los productos marcados.
- Alertas de abastecimiento (precio sobre el plan, necesidad sin OC a una semana, sin proveedor) y umbral de la alerta de precio en Ajustes.

## 7.20261010 — 10/10/2026

- Cronograma con recursos (fase 8, P-15): el Gantt de proyectos con pisos, departamentos y ambientes y, debajo de cada ambiente, sus etapas (producción, armado, instalación, acabado) enlazadas; monto, avance y contrata en la rejilla y barra clara si la etapa no tiene contrata ni cuadrilla.
- Etapas del ambiente con fechas: se crean al generar el plan (y con «Crear etapas del cronograma» en los planes ya generados); contrata, cuadrilla, monto y avance salen de sus líneas.
- Casillas con selección en cascada, panel con los recursos de la selección y los botones de los asistentes W-02 a W-08 con ella; carga semanal por contrata y etapa debajo del diagrama.
- Arrastrar una etapa desplaza la fecha de necesidad de sus líneas y avisa a Logística de los requerimientos y OC desfasados; «Cambiar fechas» también mueve las etapas.

## 6.20261010 — 10/10/2026

- Control y personal propio (fase 7, P-13): estado de la línea y montos de control (comprometido, real, saldo, % ejecutado) guardados, filtrables y agrupables; pestaña «Control» del plan y «Análisis de control» en pivote y gráfico.
- La OC con analítica de la obra se contrasta al confirmarla con el presupuesto analítico de su combinación según la política del plan (W-10).
- «Asignar cuadrilla» (W-06): turnos por obrero y semana con la tarea y la línea del plan; las horas registradas suben el ejecutado y el real, los turnos sin horas son el comprometido.
- «Cambiar fechas» (W-08): desplaza n días o lleva a una fecha nueva la selección por etapas, recalcula la fecha de necesidad y avisa a Logística con una actividad en los requerimientos y OC desfasados.
- Revertir un avance validado baja el estado del módulo; los botones del árbol «Asignar cuadrilla» y «Cambiar fechas» quedan activos.

## 5.20261010 — 10/10/2026

- Contratas (fase 5, P-05 a P-07 y P-09): «Asignar contrata» con tarifa vigente, monto y retención por actividad; pone la contrata en las líneas y suma el alcance a la OC de servicio de la contrata en la obra.
- Avance reportado (AVN) por driver con fotos obligatorias, «Registrar avance» con el saldo por módulo o ambiente y la tolerancia del plan, y «Avances por validar» por obra, contrata y semana.
- Ejecutado, liquidado y avance de cada línea; avance valorizado de los niveles en el árbol y en la pestaña «Recursos y avance» de la tarea; estado del módulo automático.
- Liquidación semanal (fase 6, P-08): LIQ por contrata, obra y semana con acción programada en el día de liquidación, aprobación de la jefatura, recepción en la OC y factura con vencimiento el día de pago; «Pagada» con la factura pagada.
- Semana de la obra configurable (inicio, liquidación y pago) con valores por defecto en Ajustes; feriados al día hábil anterior; el plan no se cierra con liquidaciones pendientes.

## 4.20261010 — 10/10/2026

- Asignaciones y compras (fase 4, P-10 y P-11): cada documento generado desde el plan guarda qué parte corresponde a cada línea; lo comprado, despachado y consumido se reparte por fecha de necesidad.
- Pedido, comprado, despachado, consumido, saldo, comprometido, real y estado calculado de cada línea (excedida, completa, en compra, parcial, planificada).
- Asistentes «Compra masiva» (con analítica de la obra o stock general), «Requerimiento de obra» (por ambiente, departamento o piso) y «Orden de fabricación» (por piso o selección desde la BOM), en la barra del árbol y en el plan.
- Control de exceso al solicitar la aprobación del requerimiento de obra y al confirmar la OF, según la política del plan, con justificación y revisión adicional de la jefatura (W-10).
- Menú «Abastecimiento»; las asignaciones abiertas pasan a la versión nueva y el plan no se cierra con documentos abiertos.

## 3.20261010 — 10/10/2026

- Línea base (fase 3, P-03): flujo del plan con «Solicitar aprobación», aprobación por niveles (reglas de aprobación), rechazo a borrador y cierre.
- La aprobación crea el presupuesto analítico (una línea por combinación de cuentas), congela los montos y deja la versión anterior en «Reemplazado».
- Asistentes «Aplicar costo» (último precio, ponderado de 3 o 6 meses o manual, con su fecha) y «Nueva versión» (todo o solo saldos, con motivo).
- Pestaña «Resumen por etapa» y menú «Análisis del plan» con pivote y gráfico.

## 2.20261010 — 10/10/2026

- Árbol de recursos (fase 2, P-02): obra › piso › departamento › ambiente › módulo cargado por niveles, con módulos, ML y montos de cada nivel.
- Selección en cascada con barra de resumen y panel de recursos acumulados de la selección; filtros por etapa, tipo de recurso, estado del módulo y contrata.
- Botón «Árbol de recursos» en el plan; el menú «Árbol de la obra» pasa a llamarse «Tareas de la obra».

## 1.20261010 — 10/10/2026

- Primera versión (fase 1): niveles de obra en las tareas, tipologías con módulos, actividades y lista de materiales, actividades y tarifas de contrata, etapa de consumo en la BOM, plan de recursos con versiones y el asistente «Generar plan» con vista previa y advertencias.
- Ícono propio en el menú principal: edificio de pisos con las barras de su plan.
