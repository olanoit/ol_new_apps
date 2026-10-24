Historial de cambios — Planificación de obra (AL)
=================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_planner.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 46.20261016 — 24/10/2026

- Corrección CR-03 de la prueba CREVAL del 24-oct: el costo unitario de la línea de receta y de la línea del plan guarda los decimales de «Precio del producto» (el ladrillo a 0.9661 ya no pasa a 0.97) y la receta redondea su costo por unidad una sola vez. Las recetas importadas antes conservan el costo ya redondeado: vuelva a importarlas.

## 45.20261016 — 24/10/2026

- Quien solo tiene «Plan: consulta» ya ve la aplicación Planificación de obra (antes el menú raíz pedía «Reporta avance»).

## 44.20261016 — 23/10/2026

- Al actualizar desde la 42, los menús, acciones y reglas que en la base citaban al Planificador anterior o a la jefatura reciben los grupos nuevos, y las entradas a la ejecución quedan activas como en una instalación nueva.

## 43.20261016 — 23/10/2026

- Requerimiento CREVAL v1.0, capítulo 5: grupos en dos ejes independientes, plan (consulta, planificador, aprueba) y ejecución (reporta avance, ejecuta, valida, aprueba), más los complementos Ve montos, Ingresos y Administrador. El Planificador anterior y la jefatura quedan como grupos de compatibilidad; la migración pasa a cada usuario a los grupos equivalentes sin perder permisos y las reglas de validación de la jefatura a los aprobadores de cada eje.
- Capítulo 4: dos ajustes de entrada a la ejecución (en Planificación de obra y desde Proyectos), menú por momento (Planificación, Ejecución con Personal propio y Abastecimiento), tablero de obra, tarea de obra con su menú Ejecutar, sección Obra en el tablero del proyecto y menú Ejecutar en la tarea de Proyectos.
- Capítulo 6: forma de cálculo en la receta y el plan (cantidad, cuadrilla ÷ rendimiento, % de la mano de obra, % del costo directo de un grupo de partidas), fuente del análisis de precio unitario por obra, rótulos de la plantilla de la obra en campos, filtros y agrupaciones, equivalencias de unidades y partidas en otra moneda.
- 3.12: casillas de firma de los documentos impresos (elaboró, cada nivel de aprobación y conformidad) desde las revisiones de la validación por niveles.

## 42.20261016 — 16/10/2026

- Etapas con sub etapas (v1.8, M18-02 y M18-14): el catálogo de etapas es un árbol numerado («1.1 Armado»); el árbol de recursos, el cronograma y la matriz filtran por etapa padre o sub etapa, el resumen y el control del plan van en ese orden y el cronograma muestra una barra resumen por etapa padre.
- Metrado como función propia (M18-01), separado del avance; **Aplicar el perfil** abre un asistente con la vista previa de lo que cambia, y los niveles de la obra toman los nombres de la plantilla en formularios, árbol y cronograma.
- Panel de recursos por tipo de recurso con subtotales y por etapa (M18-03) y matriz insumo-producto de la selección, en pantalla y en Excel (M18-04).
- Avance en formulario con chatter (M18-11): fotos y documentos, evaluación del supervisor con sus observaciones, validación y rechazo con autor y fecha; el avance de re-trabajo no suma al ejecutado. Cada partida avanza en su propio driver (M18-12).
- Recetas sincronizadas con los Work Items de Ventas (M18-13): aviso de diferencias, asistente para traer o enviar cambios y revisión diaria.
- Políticas de exceso por tipo de recurso en la compañía, la obra y el plan, y registro «Excesos autorizados» con motivo, monto y quién autorizó (M18-05, M18-21).
- Visibilidad de montos (M18-10): el grupo «Planificación de obra: ve montos» (administrador, jefatura e ingresos) ve costos, precios, presupuestos y saldos; sin él, vistas, árbol, cronograma, matriz, paneles y exportaciones muestran cantidades, fechas y avance. Al actualizar, lo reciben los usuarios que ya usaban el planificador.

## 33.20261013 — 15/10/2026

- Migración de las bases que ya usaban el planificador (v1.7): una compañía sin perfil con obras o tipologías queda con el perfil «Mobiliario», y sus obras con él, sin cambiar su plantilla, sus parámetros ni sus funciones; una obra sin plantilla conserva el árbol clásico.
- La plantilla de las obras nuevas sale de la compañía (aplicar un perfil la deja con la suya); solo una obra de otro perfil toma la plantilla de ese perfil.
- Las obras sin compañía reciben el perfil «Mobiliario» cuando todas las compañías de la base quedan con él.
- Con el núcleo solo, la obra recibe su cuenta analítica al marcarse como obra: sin ella el plan no se podía aprobar.

## 32.20261013 — 15/10/2026

- Perfiles de vertical (v1.7, M17-05): «Construcción por partidas» y «Mobiliario» reúnen plantilla de niveles, etapas, tipos de recurso, puentes, funciones, parámetros de la compañía y planes analíticos; **Aplicar el perfil** en Ajustes los deja en un paso, la pestaña «Desvíos de la compañía» muestra lo que difiere y **Exportar** / **Importar perfil** los pasan entre bases en JSON.
- Cada obra guarda el perfil con el que nació y toma su plantilla de niveles.
- Operación nativa (M17-08 a M17-11): la compra masiva agrupa por producto, nivel, etapa, partida o receta; la OF sale de cualquier nivel con etapa de producción; la cuadrilla se arma por rol, una fila por persona; los menús que operan otro documento son accesos directos a su aplicación.

## 31.20261013 — 15/10/2026

- Funciones activables (v1.7, M17-06): bloque «Funciones» en Ajustes para el control, el avance y metrados y cada puente (contratas, compras, cuadrillas, presupuesto, ingresos, producción y mobiliario).

## 30.20261013 — 15/10/2026

- Núcleo y puentes (v1.7, M17-07): el núcleo solo depende de Proyecto, el Gantt, la analítica, los productos y las aprobaciones; compras, contratas, cuadrillas, presupuesto, ventas, fabricación y mobiliario pasan a sus módulos `al_construction_planner_*`. La actualización instala todos los puentes y la suite, sin tocar los datos.

## 29.20261013 — 15/10/2026

- Control por nivel (v1.7): análisis por los niveles de la plantilla, línea base contra versión y desvío; destino de la compra masiva en la plantilla y en la obra; metrado por cantidad; portal en cualquier nivel.

## 28.20261013 — 15/10/2026

- Catálogos de etapas y de tipos de recurso (v1.7, M17-02 y M17-03), con el comportamiento «Equipo».
- Niveles libres (M17-01): agrupador, unidad de entrega, nivel con etapas, subnivel y nivel de detalle, con las casillas lleva receta, se mide con metrado, se valoriza o factura y recibe avance.
- Recetas (M17-04): plantillas de ejecución con «Generar desde la receta» e «Importar recetas y niveles» (Excel o Work Items).

## 27.20261013 — 15/10/2026

- La ayuda de la compra masiva ya no menciona el modo «con analítica de la obra», retirado en la v1.6 (M16-02).

## 26.20261013 — 15/10/2026

- Grupo «Planificación de obra: jefatura de proyectos» (v1.6, M16-09): aprueba las reglas de validación del planificador (excesos, liquidaciones, metrados, material extra y la regla del plan), así que funcionan con un reemplazo; el administrador deja de ser el aprobador por defecto. La actualización pasa las reglas existentes a la jefatura y suma a ella a los administradores actuales, que se pueden quitar después.
- Aprobar cambios, confirmar entregas semanales, anular valorizaciones, aprobar excesos de OC y OF y decidir el descuento a la contrata: lo hace la jefatura (o el administrador).
- Grupo «Planificación de obra: asistente de proyectos» (M16-10): crea los requerimientos a obra y los envía a aprobación, sin aprobarlos.
- Avance de armado por el portal (M16-11): las contratas de armado reportan módulo por módulo, probado de punta a punta.

## 25.20261013 — 15/10/2026

- Material extra con aprobación de la jefatura (v1.6, M16-05 y M16-07): todo requerimiento marcado como extra pasa por la regla «Material extra: jefatura de proyectos», esté o no dentro del plan.
- Pedido de material extra desde el portal (M16-06): el capataz de la contrata elige piso o ambiente, material del plan, cantidad, motivo y foto; queda un requerimiento en borrador, sin reservar stock, con una actividad al responsable de la obra.
- Corrección: la línea de retención de la factura de la liquidación podía quedar con importe 0 en el asiento (la sincronización de v19 no la recalculaba junto con las líneas de la OC); ahora la factura cuadra con el neto.
- Descuento a la contrata (M16-08): al aprobar el extra, la jefatura decide descontarlo a una contrata; su siguiente liquidación semanal en la obra lo resta del neto y la factura lleva una línea negativa a la cuenta configurada en Ajustes.

## 24.20261013 — 14/10/2026

- Metrado del ambiente (v1.6, M16-03): el supervisor registra la medida real en ML de mueble bajo, ML de mueble alto y módulos frente a lo planificado; el planificador muestra la diferencia en cantidad y en soles. «Generar metrados» crea los de un piso entero y las medidas se cargan en una lista editable o por Excel.
- Aprobación del metrado (M16-04): un metrado con diferencia pasa por la validación por niveles de la jefatura de proyectos, y la orden de fabricación de ese ambiente espera la aprobación.

## 23.20261013 — 14/10/2026

- La compra masiva entra siempre como stock general (v1.6, M16-02): se retiró el modo «con analítica de la obra»; el comprado sube en las líneas del plan y el costo cae a la obra al consumir.
- El comprado de las líneas del plan cuenta solo la parte de cada solicitud en la orden de compra consolidada, no la línea entera.

## 22.20261013 — 13/10/2026

- Ícono propio de la app «Planificación de obra» con el estilo de Odoo 19: icon.svg de 50×50 con formas planas y la paleta de Odoo, e icon.png de 100×100 sin fondo.

## 21.20261013 — 13/10/2026

- «Nombre de la obra» en la orden de venta: la obra creada desde la venta se llama «<referencia del cliente> <nombre de la obra>» y toma la referencia como código de obra.
- Etapas de tarea con «Exige foto de evidencia»: la tarea no pasa a esa etapa sin un adjunto.

## 20.20261013 — 13/10/2026

- Paquete de mejoras v1.5. Plantilla de niveles por obra (agrupadores como torre o etapa, unidad, ambiente, mueble y módulo) con tipo de unidad; árbol, cronograma e importador con niveles variables.
- Ritmo de programación al generar el plan (pisos por semana o semanas por piso), etapas encadenadas por días hábiles de la obra y fechas acumuladas en ambiente, unidad y piso.
- Tipologías completas: familia, variantes, otros nombres por documento, muebles con sus ML (actividades por ML por mueble) y variantes por unidad (color, no lleva, metrado distinto).
- Contratos de obra con condiciones, unidades cubiertas, documentos habilitantes y hitos de cobro por unidad (plantillas 80/15/5 y otras); valorización por hitos.
- Producto de servicio por actividad, tramos de pago con avance ponderado, reglas analíticas de etapa y partida, presupuesto por obra › etapa › partida y etapa y partida completadas en los apuntes reales.
- Portal de la contrata (P-23 a P-25): obras asignadas, registro de avance con foto y ubicación, historial de avances y liquidaciones.
- Adicionales, deductivos y rehacer con regla de precio según el estado de la unidad, llevados al plan aprobado y a su presupuesto; dependencias de terceros que bloquean avances y fechas de la etapa en el cronograma (P-32).
- Pestaña «Planificación» en la obra con margen planificado, devengado y contable, y accesos al árbol y al cronograma.
- Validaciones de datos: tipologías y ambientes repetidos, unidades que no corresponden a su piso y avances posiblemente duplicados.

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
