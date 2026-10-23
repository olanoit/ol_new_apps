# Diseño del requerimiento «Vertical Planificación de obra» v1.0 (CREVAL)

Requerimiento: `docs/md/CREVAL_Requerimiento_Desarrollo_Vertical_v1.0.docx` (23-oct-2026).
Este diseño cubre la Parte I (producto). La Parte II (configuración y prueba CREVAL) es
configuración de la base del cliente y no deja datos del cliente en este repositorio.

## Principios

- Todo se activa por configuración. Una orden de contrata **sin condiciones** se comporta
  exactamente como hoy (retención por línea de la tarifa, descuento de material extra,
  liquidación semanal). Las condiciones de contrata son opcionales y se copian a la orden.
- La valorización sigue siendo `construction.contract.settlement`; no hay documento paralelo
  en Compras.
- Los identificadores externos actuales (grupos, menús, acciones) se conservan.

## Módulos

| Módulo | Cambio | Capítulos |
| --- | --- | --- |
| `al_construction_planner` | Grupos en dos ejes y su migración; ajustes de entrada a la ejecución; menús por momento; tablero de obra; tarea de obra con menú Ejecutar; botones en el tablero del proyecto; forma de cálculo de la receta; rótulos de la plantilla de la obra; fuente del APU; equivalencias de unidades; partidas en otra moneda | 4, 5, 6 |
| `al_construction_planner_subcontract` | Condiciones de contrata y esquema de cálculo; valorización (tipo, título, cascada, periodicidad, adicionales, deductivos, adelanto, fondo); deductivos; fondo de garantía y su reporte; liquidación y cierre de la orden; carga inicial; documentos impresos con casillas de firma; resumen y análisis de valorizaciones | 3 |
| `al_construction_planner_subcontract_purchase` | El material extra descontado entra como deductivo en las órdenes con condiciones | 3.7 |
| `al_construction_planner_subcontract_sale` (nuevo, automático) | «Agregar a la orden de contrata» desde el cambio de obra; margen de compra por partida | 3.9, 3.13 |
| `purchase_tier_validation` (OL-THIRD-PARTY) | Copia idéntica de OCA `tier-validation` 19.0 `0b611d7` (versión 19.0.1.0.0), el mismo commit que `base_tier_validation`. Se instala desde Ajustes («Aprobación por niveles de la orden de contrata»); no hace falta un puente: las casillas de firma leen las revisiones de la orden si existen | 3.4, 3.12 |
| `al_report_base` (OL-TOOLS) | Plantilla `report_pe_sign_boxes` de casillas de firma | 3.12 |
| `al_construction_planner_sale` | Importación del presupuesto con secciones a la cotización y de ahí al plan; casillas de firma en la valorización al cliente y en el cambio de obra | 6.4, 3.12 |
| `al_construction_planner_purchase`, `_crew`, `_mrp`, `_furniture`, `_approvals*`, `_production`, `al_construction_attendance` | Grupos de los dos ejes en accesos, menús y controles; entradas del menú Ejecutar y del tablero | 4, 5 |

## Capítulo 5 · grupos en dos ejes

| Eje (privilegio) | Grupo | XMLID | Incluye |
| --- | --- | --- | --- |
| Plan | Consulta | `group_planner_plan_viewer` (nuevo) | Usuario interno |
| Plan | Planificador | `group_planner_plan_planner` (nuevo) | Consulta |
| Plan | Aprueba | `group_planner_plan_approver` (nuevo) | Planificador |
| Ejecución | Reporta avance | `group_planner_progress` (se conserva) | Usuario interno |
| Ejecución | Ejecuta | `group_planner_user` (se conserva) | Reporta avance, Plan: consulta |
| Ejecución | Valida | `group_planner_exec_validator` (nuevo) | Ejecuta |
| Ejecución | Aprueba | `group_planner_exec_approver` (nuevo) | Valida |
| Complemento | Ve montos | `group_planner_amounts` | — |
| Complemento | Ingresos | `group_planner_revenue` | Ejecuta, Ve montos |
| Complemento | Administrador | `group_planner_manager` | Plan: aprueba, Ejecución: aprueba, Ve montos, Ingresos |

- `group_planner_planner` (Planificador anterior) y `group_planner_project_head` (Jefatura)
  salen de la selección y quedan como grupos de compatibilidad: el primero incluye Plan:
  planificador + Ejecución: valida; el segundo, Plan: aprueba + Ejecución: aprueba + Ve montos.
  Conservan sus accesos, de modo que las reglas, rutas y vistas que los citan siguen
  funcionando.
- Los controles del código pasan a los grupos nuevos (`PLAN_*_GROUPS`, `EXEC_*_GROUPS` en
  `models/common.py`). Como los grupos de compatibilidad incluyen a los nuevos, los usuarios
  actuales pasan los mismos controles.
- La migración pasa a cada usuario de los grupos de compatibilidad a los grupos nuevos
  equivalentes (tabla 5.3) y deja vacíos los de compatibilidad, salvo `base.user_admin`. Las
  reglas de validación por niveles que revisaba la jefatura pasan a Plan: aprueba (plan) o
  Ejecución: aprueba (valorizaciones, metrados y material extra). La prueba de la migración
  compara, por usuario, los permisos efectivos de cada modelo antes y después.
- Cada eje se muestra como una selección en Ajustes › Usuarios; los complementos son
  privilegios de una sola opción en la misma sección.

## Capítulo 3 · contratas

### Modelos nuevos

| Modelo | Uso |
| --- | --- |
| `construction.contract.condition` | Condiciones de contrata: adelanto (%, forma de amortizar, monto fijo), fondo de garantía (%, base, días, desde factura o liquidación, requisitos de devolución), periodicidad y corte, tolerancia de avance, documentos requeridos, detalle de líneas, esquema de cálculo |
| `construction.contract.scheme.line` | Fila del esquema (de las condiciones o de la orden): secuencia, concepto, tipo, base, %, signo y reflejo en la factura |
| `construction.contract.requirement` | Catálogo de requisitos de devolución del fondo (vencimiento, acta de recepción, carta de no deuda, sin observaciones de postventa, otros) |
| `construction.contract.document.type` | Catálogo de documentos requeridos para la liquidación |
| `construction.contract.deduction` y `construction.contract.deduction.type` | Deductivo con secuencia por obra, tipo, monto sin IGV, sustento obligatorio, referencia (tarea, cierre de costo de personal, requerimiento) y estados pendiente → en valorización → aplicado / anulado |
| `construction.contract.settlement.summary` | Filas del resumen del periodo (una por concepto del esquema) con contractual, anterior, actual, acumulado y saldo |
| `construction.guarantee.fund` | Una por cuota de fondo de garantía (o de apertura): orden, contratista, obra, monto, vencimiento, estado, devolución retenida con motivo y ticket |
| `construction.contract.order.document` | Documento requerido de la orden con su adjunto |
| `construction.contract.summary.report` | Vista SQL del resumen de valorizaciones por orden |

### Cálculo del resumen

Subtotal costo directo = líneas que no son adicional. Adicionales = líneas de adicional.
Ajustes de precio sobre «costo directo más adicionales» (o la base que diga la fila);
deductivos con su monto; Subtotal = costo directo + adicionales + ajustes − deductivos;
impuestos sobre el subtotal; Total = subtotal + impuestos; adelanto y fondo de garantía
sobre el total o el subtotal según las condiciones; Total a pagar = total − adelanto − fondo.
Cada fila se redondea a la moneda. La secuencia de las filas fija el orden en pantalla y en el
impreso; la base de cada fila fija el cálculo.

### Factura

| Fila | Reflejo |
| --- | --- |
| Líneas de la valorización | Una línea por línea de la orden con su analítica (como hoy) |
| Ajuste de precio | «Línea de servicio»: línea con la cuenta, los impuestos y la analítica del servicio. «Línea propia»: con la cuenta de la fila |
| Deductivo | «Línea propia»: línea negativa «Deductivo a contrata» con la analítica de la partida y los impuestos del servicio. «Descuento al pago»: no va en la factura; un asiento de la contrata (cuenta por pagar contra la cuenta de deductivos) que se concilia con la factura |
| Adelanto | «Regularización»: línea negativa del producto de anticipo = amortización ÷ (1 + impuesto del anticipo) |
| Fondo de garantía | «Cuota»: la cuenta por pagar se divide en neto (día de pago) y fondo (inicio del plazo + días), por `_compute_needed_terms` |

La detracción (`al_l10n_pe_detraction`) sigue el código del producto del servicio y del
anticipo; separa la cuota mayor (el neto) y convive con la cuota del fondo.

### Valorización

- `settlement_type`: periódica, liquidación o apertura. `number` correlativo por orden y
  título «Valorizado NN - especialidad» (la especialidad de la orden, propuesta desde el
  nivel 1 de sus líneas del plan).
- Con condiciones, la valorización es por orden: una sola abierta por orden y periodo según la
  periodicidad (semanal con el corte de la obra, quincenal 1-15 / 16-fin, mensual a fin de mes
  o al día de corte, al término = solo la liquidación). El periodo empieza el día siguiente al
  fin del anterior de la misma orden. Sin condiciones, todo sigue como hoy (por contrata y
  semana).
- Líneas por línea de la orden y partida (detalle «por partida», el de las condiciones) o por
  línea de la orden (detalle «por actividad», el de hoy). Columnas de contratado, anterior,
  actual, acumulado, % y saldo, opcionales.
- Franja «Revisar antes de aprobar»: metrados escritos a mano, re-trabajos, líneas sobre lo
  contratado más la tolerancia y avances sin fotos.
- Pestañas Avance, Adicionales, Deductivos, Avances incluidos y Validaciones (revisiones de la
  validación por niveles).
- El corte crea la actividad «Preparar valorizado» al responsable de la obra. Un botón en la
  lista genera las de todas las órdenes de una obra que vencen en el corte.

### Orden de contrata

- Pestaña «Condiciones de contrata»: condiciones y esquema copiados, adelanto, ajustes, fondo,
  valorización (periodicidad, próximo corte, tolerancia) y saldos (contractual, valorizado,
  facturado, pagado y saldo con IGV; adelanto otorgado, amortizado y por amortizar; fondo
  retenido y devuelto).
- «Registrar adelanto»: factura de proveedor en borrador con el producto de anticipo de
  Ajustes, base = adelanto % × subtotal contractual sin IGV (costo directo y adicionales con
  sus ajustes de precio, como en el libro: 30 % × 88,000.00 = 26,400.00 + IGV) y la analítica
  de la obra.
- Botones Adelantos, Deductivos y Pagos de la orden.
- Con la orden confirmada, las condiciones solo las cambia el administrador (queda en el
  historial) o una ampliación aprobada.
- El asistente «Asignar contrata» propone las condiciones del contratista (pestaña Compras del
  contacto) o las de Ajustes, muestra los totales según el esquema y elige entre la orden
  abierta del contratista en la obra o una orden nueva.

### Liquidación y cierre

Valorización de tipo liquidación: cantidades finales = acumulado validado, editables a la baja
con motivo; amortiza el saldo del adelanto; consolida deductivos y fondo; muestra el alcance no
ejecutado por línea. «Cerrar orden», con la factura publicada y los documentos requeridos
adjuntos, baja la cantidad de cada línea de la orden a lo recibido (libera el saldo del plan y
el comprometido del presupuesto analítico) y bloquea la orden. El fondo se paga después.

### Carga inicial

Asistente con plantilla Excel (hojas ORDENES y LINEAS): crea la orden confirmada con sus
condiciones y una valorización de apertura aprobada sin efecto contable, con el acumulado por
línea (lo recibido de la orden) y, en la orden, valorizado, facturado, pagado, adelanto otorgado
y amortizado y las cuotas de fondo con sus vencimientos.

## Capítulo 4 · ejecución

- Dos ajustes (grupos técnicos implícitos de `base.group_user`, como las funciones):
  «Ejecución en Planificación de obra» y «Ejecución desde Proyectos». Los dos activos al
  instalar.
- Menús por momento: los menús nuevos (Planificación, Ejecución › Personal propio y
  Abastecimiento, Informes › Contratas) se recolocan al cargar el menú
  (`ir.ui.menu.load_menus`) según el ajuste; los XMLID actuales no cambian. Con el ajuste
  apagado se ve el menú actual con los nombres nuevos.
- Tablero de obra: formulario propio de la vertical sobre `project.project` con su acción;
  cada puente agrega sus botones con contador.
- Tarea de obra: formulario propio sobre `project.task` con los rótulos de la plantilla y el
  menú Ejecutar; la misma lista de acciones aparece en la tarea de Proyectos con su ajuste.
- Tablero del proyecto: los botones de la obra se agregan con `_get_stat_buttons` y una
  extensión de la plantilla del panel los agrupa bajo «Obra».
- Devengado de lo aprobado y no facturado: como la aprobación recibe en la orden, el asiento
  de devengo nativo de Compras («Asiento de gastos devengados») lo calcula con su analítica.

## Capítulo 6 · receta y plan

- Forma de cálculo en la línea de receta y del plan: cantidad por unidad, cuadrilla ÷
  rendimiento (personas × horas de la jornada ÷ rendimiento), % de la mano de obra de la
  partida o % del costo directo de un grupo de partidas (mismo padre, mismo nivel 1 u obra).
  Las líneas por porcentaje no generan requerimientos ni compras y se recalculan al cambiar
  su base.
- Fuente del APU en la obra: Work Items de la venta (por defecto) o libro Excel.
- Rótulos: campo «Rótulo» en la línea de la plantilla; los rótulos salen de la plantilla de la
  obra (no solo de la compañía), en campos, filtros, agrupaciones, impresos e importación.
- Importación del presupuesto: asistente en la cotización (sección por nivel 1, subsección
  por nivel 2, partidas como líneas), tabla de equivalencias de unidades, aviso de duplicados
  antes de crear; de la cotización se crean los niveles y partidas del plan.
- Partidas en otra moneda: la línea de receta y la del plan llevan moneda y precio en esa
  moneda; el control se lleva en la moneda de la obra con el tipo de cambio de cada
  documento y la diferencia de cambio aparte del desvío de precio; la compra masiva agrupa
  por moneda.

## Desvíos y decisiones de implementación

| Punto | Implementado | Motivo |
| --- | --- | --- |
| 5.3 «los usuarios conservan exactamente sus permisos» | Nadie pierde permisos (prueba de la migración); el grupo «Usuario» pasa a ser «Ejecuta» y gana los asistentes de ejecución (asignar contrata y cuadrilla, pedir material) | La tabla 5.2 define «Ejecuta» con esas acciones y la 5.3 le asigna los usuarios de «Usuario»; el XMLID se conserva |
| Revisores de la validación por niveles | Las reglas citan Plan: aprueba o Ejecución: aprueba; los revisores son los miembros directos y quienes los tienen por otro grupo (jefatura, administrador) | El administrador incluye Ejecución: aprueba (tabla 5.2); antes solo revisaba la jefatura (v1.6, M16-09) |
| 3.9 «vuelve a aprobación por la diferencia» | Marca «Ampliación por aprobar» en la orden y el botón «Aprobar ampliación» (Ejecución: aprueba); el adicional no se valoriza hasta entonces | La validación por niveles de OCA no reabre una orden confirmada |
| 3.13 «Resumen de valorizaciones … aprobación del programa de pagos» | El impreso firma Elaboró (quien imprime) y deja Aprobó en blanco | El programa de pagos no tiene hoy una aprobación con revisiones |
| 3.6 «el anticipo nativo de compras de Odoo 19» | Producto de anticipo propio | El anticipo nativo no regulariza en la factura del valorizado |
| 6.3 «rótulos en impresos» | Campos, filtros y agrupaciones con la plantilla de la obra del contexto; el impreso agrupa por el nivel 1 con su nombre | La etiqueta de un campo no puede variar por registro en una lista con varias obras |

## Fases

| Fase | Contenido |
| --- | --- |
| F1 | Capítulo 5 (grupos y migración) |
| F2 | 3.2, 3.4 a 3.8 y 3.10 (condiciones, valorización, adelanto, deductivos, fondo, periodicidad) |
| F3 | 3.9, 3.11, 3.14 y la aprobación por niveles de la orden |
| F4 | 3.12 y 3.13 (impresos con firmas y reportes) |
| F5 | Capítulo 4 |
| F6 | Capítulo 6 |
| F7 | Documentación (MkDocs, ACEPTACION.md, fichas) y respuesta 12.3 |

## Respuesta de Desarrollo (12.3)

Esfuerzo en días de desarrollo con pruebas. Las fechas son de entrega en la base de pruebas,
sujetas al despliegue.

| Requerimiento | Capítulo | Prioridad | Esfuerzo (días) | Fecha comprometida | Observación |
| --- | --- | --- | --- | --- | --- |
| Nomenclatura y menús de contratas | 3.2 | Alta | 0.5 | 06-nov-2026 | Solo nombres; XMLID sin cambio |
| Condiciones de contrata y esquema de cálculo | 3.4 | Alta | 3 | 06-nov-2026 | Sin condiciones la orden se comporta como hoy |
| Valorización de contrata | 3.5 | Alta | 4 | 06-nov-2026 | Por orden con condiciones; por contrata y semana sin ellas |
| Adelanto y amortización | 3.6 | Alta | 2 | 06-nov-2026 | Producto de anticipo propio: el anticipo nativo de Compras de Odoo 19 no regulariza en la factura del valorizado |
| Deductivos | 3.7 | Alta | 2 | 06-nov-2026 | El material extra pasa a ser un tipo de deductivo |
| Fondo de garantía | 3.8 | Alta | 2.5 | 06-nov-2026 | Cuotas por `_compute_needed_terms`; reporte propio |
| Adicionales de la contrata | 3.9 | Alta | 1.5 | 11-nov-2026 | Puente nuevo con Ventas; la diferencia la aprueba Ejecución: aprueba |
| Periodicidad | 3.10 | Alta | 1.5 | 06-nov-2026 | — |
| Liquidación de contrata | 3.11 | Alta | 2.5 | 11-nov-2026 | — |
| Documentos impresos y casillas de firma | 3.12 | Alta | 3 | 13-nov-2026 | Con `al_report_base`; el cargo sale del puesto del empleado si existe |
| Reportes de contratas | 3.13 | Media | 3 | 13-nov-2026 | Vista SQL del resumen |
| Carga inicial | 3.14 | Media | 2 | 11-nov-2026 | Plantilla Excel descargable |
| Aprobación por niveles de la orden de contrata | 3.4 | Alta | 1 | 11-nov-2026 | `purchase_tier_validation` 19.0.1.0.0 (OCA, commit 0b611d7) |
| Ejecución en la vertical y desde Proyectos, con ajustes | 4 | Alta | 5 | 17-nov-2026 | Menús recolocados al cargar, sin duplicar XMLID |
| Grupos en dos ejes | 5 | Alta | 4 | 04-nov-2026 | Grupos actuales como compatibilidad; migración con prueba de permisos efectivos |
| Herramientas en % de la mano de obra | 6.1 | Alta | 2 | 19-nov-2026 | — |
| Fuente del análisis de precio unitario | 6.2 | Alta | 1 | 19-nov-2026 | — |
| Nombres de niveles | 6.3 | Alta | 1 | 19-nov-2026 | — |
| Importación con secciones | 6.4 | Alta | 3 | 19-nov-2026 | — |
| Partidas en dólares | 6.5 | Media | 3 | 19-nov-2026 | — |
| Módulos del Gantt ALTA | 7 | Media | 1 | 20-nov-2026 | Instalación y prueba en la base de pruebas |
| Configuración CREVAL | 9 | Alta | 2 | 20-nov-2026 | Parte II, en la base del cliente |
