# Requerimiento de desarrollo · Correcciones de la vertical Planificación de obra

**Versión:** 1.2 · 26-oct-2026 (1.1: agrega la corrección 8, CR-18; 1.2: re-prueba del almacén, decisión D5 sobre material dañado y separación por vertical)
**Para:** Cristóbal Olano (Desarrollo)
**De:** Vicente Catacora (ALTA Latam)
**Origen:** re-prueba del 25-oct-2026 en la base de pruebas creval-dev, con los módulos de construcción actualizados ese día a las 11:18 (hora de Lima)
**Documentos relacionados:**
- *Requerimiento de desarrollo · Vertical Planificación de obra v1.0*: capítulo 12 (correcciones), sección 4.11 (portal de obra) y tabla 13.3 (fechas).
- *Prueba integral v1.1*, hoja «E14 Re-prueba 25-oct»: el paso a paso de cada prueba.

---

## 0. Alcance y reglas generales

### 0.1 Qué cubre
Ocho correcciones de la vertical que siguen abiertas después de la re-prueba:

| N° | Corrección | Vertical | Módulo principal (indicativo) | Prioridad | Depende de |
|---|---|---|---|---|---|
| 1 | Movimientos de almacén y devoluciones de obra (CR-16) | Ambas; Mobiliario: puente de Fabricación | `al_stock_base`, `al_construction_material_request`, `al_construction_planner_purchase`, `al_construction_portal` | Alta | — |
| 2 | Valorización al cliente por avance validado de la partida (CR-01) | Ambas; la base de valorización se elige por obra | `al_construction_planner_sale` | Alta | — |
| 3 | Decisiones del validador al actualizar la valorización de la contrata (CR-15) | Ambas | `al_construction_planner_subcontract` | Alta | — |
| 4 | Redondeo único entre valorización y factura (CR-11) | Ambas | `al_construction_planner_subcontract` | Media | 3 |
| 5 | Partida legible en el portal de obra (CR-17) | Ambas | `al_construction_portal` | Media | — |
| 6 | Porcentaje del costo directo de un nivel elegido (CR-05) | Ambas | `al_construction_planner` | Media | — |
| 7 | Ajustes menores del portal de obra | Ambas | `al_construction_portal`, `al_construction_material_request` | Baja | 5 |
| 8 | Hoja de trabajo de presupuesto y plan (CR-18) | Ambas: a), b) y e); Construcción: c), d) y D1 a D4; Mobiliario: verificar su hoja | `al_construction_planner_spreadsheet`, `al_construction_planner_sale` | Alta | — |

Los módulos de la columna «Módulo principal» se dedujeron de dónde aparecen los campos en la base; Desarrollo confirma cuál corresponde.

**Columna «Vertical».** Se deduce de la lista de módulos de creval-dev.
- **Ambas:** el cambio va en un módulo compartido (el núcleo o un puente genérico) y debe funcionar con y sin los módulos de mobiliario.
- **Construcción:** comportamiento propio de las obras por partidas. Se activa por el perfil de la obra o por un ajuste.
- **Mobiliario:** el cambio va en los puentes de mobiliario. En creval-dev esos puentes están sin instalar: `al_construction_planner_furniture`, `_mrp`, `_mrp_request`, `_production`, `_sale_furniture`, `_spreadsheet_furniture`, `_approvals_mrp` y `al_industry_furniture`.

### 0.2 Reglas que aplican a todo
- **Funcionalidad genérica.** Nada del desarrollo debe depender de un cliente: no se usan nombres, formatos ni valores de CREVAL. Todo lo que es una regla de negocio queda como ajuste configurable.
- **Coherencia entre verticales.** Cada corrección dice qué aplica a ambas verticales y qué a cada una. Lo compartido no puede romper la otra vertical; lo propio de una vertical va en su puente o se activa por ajuste, sin duplicar en un puente lo que ya resuelve el núcleo o Odoo estándar.
- **Primero lo nativo.** Antes de pedir desarrollo se revisa si Odoo estándar lo resuelve con configuración (ubicaciones, tipos de operación, reglas de automatización, campos nativos). Cada corrección separa lo que es configuración de lo que es desarrollo.
- **Construcción separada de mobiliario.** La vertical de construcción usa un abastecimiento simple: el requerimiento va referenciado a su partida y a su centro de costo, el almacén despacha a la ubicación de la obra y la obra recibe o devuelve. La lógica de mobiliario (fabricación, plancha entera, cadena de plantas) vive en sus módulos puente y no debe ejecutarse cuando esos módulos o Fabricación no están instalados.
- **Datos existentes.** Cada corrección indica si hace falta un script de migración para los registros ya creados.
- **Pruebas.** Cada corrección trae sus criterios de aceptación. Se prueban en creval-dev con datos marcados «PRUEBA ALTA».
- **Entrega.** Versión nueva del módulo (número y fecha en el manifiesto), nota de cambios por corrección y aviso en el grupo de Desarrollo cuando esté instalado en creval-dev.

### 0.3 Entorno y datos de referencia (creval-dev)

| Dato | Valor |
|---|---|
| Obra de prueba | 096-26 BOSCH (proyecto 12), plan de recursos 10, cotización PPTO 096-26 (venta 1) |
| Obra de prueba para crear datos | PRUEBA ALTA · Obra demo de contratas (proyecto 11) |
| Contrata | EDIFICACIONES Y CONSTRUCCIONES MYFLA S.A.C., orden P00011 |
| Almacén | Almacén CREVAL (WH): Almacén Central, Proyectos (una sububicación por obra, con su «Dañados») y Bajas. Regla de automatización «Alerta: material dañado en obra» |
| Hoja de trabajo | Documento 49 (libro de PPTO 096-26); copia de prueba S00003 (venta 3) con el proyecto 16 y el documento 54 |
| Portal | QR activo en la obra 096-26; usuarios de prueba «PRUEBA ALTA · Capataz de obra» y «PRUEBA ALTA · Supervisor MYFLA» |

---

## 1. Movimientos de almacén y devoluciones de obra (CR-16)

### 1.1 Situación

**Prueba del 25-oct (mañana).** Validar cualquier movimiento de inventario fallaba con `'stock.move' object has no attribute 'raw_material_production_id'`. Pasaba en la recepción `WH/IN/00001` y en el ajuste de inventario. En creval-dev no hay ningún módulo de fabricación ni de mobiliario instalado.

**Re-prueba del 25-oct (22:20 a 23:00).** Con `al_construction_planner_purchase` 19.0.15.20261026, instalado a las 21:04:

| N° | Criterio | Resultado | Evidencia |
|---|---|---|---|
| 1 | Recepción de compra sin Fabricación | Cumple | `WH/IN/00004` de `P00031` |
| 2 | Ajuste de inventario | Cumple | Cemento almacenable, 10 bls en Almacén Central (después se revirtió) |
| 3 | Requerimiento → despacho listo y visible en el portal | Cumple | `RQO/2026/00003` (12 bls desde el portal): `WH/OBRA/00006` listo con 10, `WH/OBRA/00007` en espera de 2 y `PR00002` por 2 |
| 4 | Recepción parcial en el portal | Cumple | 8 de 10 con foto; orden parcial `WH/OBRA/00008` por 2; la nota de faltante quedó en el historial |
| 5 | Devolución desde el portal | No cumple | Ver debajo |
| 6 | Analítica y partida en la compra que nace del requerimiento | No cumple | La línea de `PR00002` lleva la analítica 096-26 al 100 %; la línea de `P00032` quedó con analítica vacía, sin partida y con precio 0 |
| 7 | «Devolver» en newallcenter-dev2 | No probado | Otra base |

Detalle del criterio 5:
- **«En buen estado»** creó `WH/INT/00001` (obra → Almacén Central) como traslado interno suelto. No tiene requerimiento, obra, analítica ni movimiento de origen (`origin_returned_move_id`).
- **«Dañado»** creó el desecho `SP/00001`, validado en el acto, hacia la ubicación virtual «Inventory adjustment».
- Después de las dos devoluciones, la línea del plan (cemento, partida 12.0101) sigue con **«Despachado» 8**. El stock de la obra sí bajó de 8 a 6.

Observaciones menores:
- Después de recibir, «Devolución» del portal mostró «No hay material en la obra» hasta pulsar «Actualizar».
- El requerimiento se aprobó solo, como en el punto 7.4.

### 1.2 Decisiones de diseño (25 y 26-oct)
**D5. Material dañado en obra.**
- Lo dañado no sale de la obra. Se mueve a la sububicación «Dañados» de la ubicación de esa obra, y su costo se queda en la obra y en la partida.
- Al validarse ese movimiento se programa una actividad «Analizar material dañado» para el gestor del proyecto y para el grupo de Logística. Ellos deciden si va a pérdida, si se recupera o si se traslada a gastos generales de la obra.
- La baja definitiva (desecho) es un paso posterior y aparte, que hace Logística.

**Devolución en buen estado.** Es una devolución del despacho, enlazada a él. Al validarse en Almacén Central, baja lo despachado a la partida.

### 1.3 Qué es configuración nativa y qué es desarrollo
Comprobado en creval-dev el 26-oct.

| Necesidad | Tipo | Detalle |
|---|---|---|
| Sububicación «Dañados» por obra | Configuración nativa | Ubicación interna hija de la ubicación de la obra. Creada en creval-dev para 096-26 (id 30) y para la obra de prueba 16 (id 31). |
| Crear «Dañados» al crear la obra | Desarrollo menor | La vertical ya crea la ubicación de cada obra nueva; que cree también su hija «Dañados», con nombre configurable en Ajustes. |
| Alerta de análisis | Configuración nativa | Regla de automatización (módulo estándar `base_automation`, instalado el 26-oct) «Alerta: material dañado en obra», sobre `stock.picking`: al pasar a Hecho con destino «Dañados», programa la actividad para el gestor del proyecto y para los usuarios del grupo «Requerimientos de obra / Logística». Probada con `WH/INT/00002`. Usa una acción de código de servidor; es configuración, no módulo. |
| Botón «Dañado» del portal | Desarrollo | Hoy crea un desecho validado. Debe crear un traslado de la obra a su «Dañados», validado por quien recibe en obra o por Logística, con la foto y el motivo. |
| Botón «En buen estado» del portal | Desarrollo | Debe usar el mecanismo nativo de devolución (`stock.return.picking`) sobre el despacho recibido, para conservar el movimiento de origen, la obra, el requerimiento y la partida. Probado en nativo: `WH/OBRA/00009` → `WH/OBRA/00010` guarda el origen y vuelve a Almacén Central. |
| «Despachado» del plan | Error | Debe ser lo despachado validado menos lo devuelto validado al almacén (movimientos con `origin_returned_move_id`). Lo que pasa a «Dañados» sigue dentro de la obra y no baja lo despachado. |
| Costo analítico por obra con «Analytic Costs» del tipo de operación (nativo, `project_stock_account`) | No sirve como está | Probado en la obra 16: el despacho de 2 bls sumó +42.37 y la devolución de 1 bls sumó otros +21.19, cuando debía restar. La vertical sigue con su propia analítica de obra en el movimiento (`construction_analytic_distribution`). La opción se dejó desactivada. |
| Analítica en la compra desde el requerimiento | Desarrollo menor sobre nativo | La compra tiene el campo nativo «Proyecto» (`project_purchase`). El paso de solicitud a compra debe llenarlo con la obra, para que Odoo ponga su analítica en las líneas, y copiar la partida (`construction_task_id`) de la línea del requerimiento. Para un requerimiento interno, la analítica es la de gastos generales de la obra. |

### 1.4 Por vertical

**Ambas verticales** (módulos compartidos: `al_stock_base`, `al_construction_material_request`, `al_construction_planner_purchase`, `al_construction_portal`):
- validar recepción, ajuste, despacho y devolución sin Fabricación instalada;
- devolución en buen estado por el mecanismo nativo y «Despachado» neto de devoluciones;
- «Dañados» por obra, con su alerta y sin desecho inmediato (D5);
- analítica y partida en la compra que nace del requerimiento.

**Mobiliario** (módulos puente: `al_construction_planner_mrp`, `al_construction_planner_mrp_request`, `al_construction_planner_production`, `al_construction_planner_furniture`):
- toda referencia a campos de Fabricación (`raw_material_production_id`, `production_id`, `bom_line_id`, etc.) vive en un puente que depende de `mrp`; si no se puede mover, se protege con `if '<campo>' in self._fields`;
- el asistente «Devolver» de `al_stock_base` (heredado el 24-oct) propone como destino la ubicación de origen del movimiento y no aplica reglas de mobiliario en construcción;
- en creval-dev, sin mobiliario instalado, `stock.move` ya tiene campos de mobiliario como `construction_rounding_qty` («Redondeo a plancha entera»). Desarrollo confirma si deben pasar al puente de mobiliario.

**Construcción:** nada propio en esta corrección. El flujo simple de 1.5 es el comportamiento por defecto cuando los puentes de mobiliario no están instalados.

### 1.5 Flujo que debe funcionar

| Paso | Operación | Origen → destino | Referencias que conserva |
|---|---|---|---|
| Compra | Recepción | Proveedores → Almacén Central | Requerimiento, partida y analítica de la obra en la línea de compra |
| Despacho | Despacho a obra | Almacén Central → Proyectos/‹obra› | Requerimiento, partida y analítica |
| Recepción en obra | Validación del despacho por el capataz (portal) o el residente | — | Lo recibido; el faltante queda como orden parcial |
| Devolución en buen estado | Devolución del despacho | Proyectos/‹obra› → Almacén Central | Movimiento de origen, partida y requerimiento; baja «Despachado» |
| Material dañado | Traslado interno | Proyectos/‹obra› → Proyectos/‹obra›/Dañados | Partida y foto; actividad de análisis; el costo sigue en la obra |
| Baja definitiva | Desecho, por decisión de Logística | Proyectos/‹obra›/Dañados → ubicación de desecho | Motivo y responsable |

### 1.6 Datos existentes
- No requiere migración.
- Registros de prueba: `P00031`, `WH/IN/00004`, `WH/OBRA/00005`, `WH/OBRA/00006`, `WH/INT/00001`, `SP/00001` y, en la obra 16, `WH/OBRA/00009`, `WH/OBRA/00010` y `WH/INT/00002`. Están hechos y no se anulan.
- Anulados: `RQO/2026/00003`, `PR00002`, `P00032`, `WH/OBRA/00007` y `WH/OBRA/00008`.
- El cemento volvió a consumible, con stock 0.

### 1.7 Criterios de aceptación
1. Sin Fabricación instalada, la recepción de una compra se valida sin error. *Cumple desde 19.0.15.*
2. El ajuste de inventario se aplica sin error. *Cumple.*
3. Un requerimiento de obra aprobado y procesado genera el despacho; con stock, queda listo y el capataz lo ve en **Recepción** del portal. *Cumple.*
4. Al recibir en el portal menos de lo enviado, se valida lo recibido y el resto queda como orden parcial. *Cumple.*
5. «En buen estado» en el portal crea la devolución del despacho (con movimiento de origen) hacia Almacén Central; al validarla, «Despachado» de la línea del plan baja en esa cantidad.
6. «Dañado» en el portal crea el traslado a Proyectos/‹obra›/Dañados; al validarse, el gestor del proyecto y Logística reciben la actividad «Analizar material dañado», y «Despachado» no cambia.
7. Una obra nueva nace con su sububicación «Dañados».
8. La compra generada desde un requerimiento lleva la obra en «Proyecto», su analítica en las líneas y la partida.
9. En newallcenter-dev2, el asistente **Devolver** funciona en Despacho a obra y en Recepciones, y la hoja y el flujo de mobiliario siguen como hoy.

---

## 2. Valorización al cliente por avance validado de la partida (CR-01)

### 2.1 Situación
- **Configuración de la prueba** (la obra quedó luego como estaba): en la obra 096-26 se usó «Base de la valorización» = **Avance validado de la partida** (`project.project.construction_valuation_basis = 'progress'`) y «Orden de venta del contrato» = `PPTO 096-26`.
- **Preparar valorización** con corte al 30-set-2026 creó `VAL/2026/00002` (anulada) con 378 líneas, una por línea de venta, y los roles correctos.
- **Todas las líneas tienen 0** en `pct_rule`, `progress_period`, `progress_delivered` y `amount_delivered`.
- Ejemplo: la partida 3.0302 (tarea 540, línea de venta 52) tiene avance validado de 158.9 de 158.9 m² y `construction_progress_pct = 1`, pero su línea de valorización (id 42) sale en 0.
- Con «Entregas semanales», el asistente no trae ninguna línea.

### 2.2 Diseño funcional
**Base «Avance validado de la partida»**
- El **% acumulado propuesto** (`pct_rule`) de cada línea de venta de rol Partida es el avance físico validado de su partida a la fecha de corte:
  - por defecto, `Σ cantidad validada con fecha ≤ corte ÷ cantidad presupuestada de la partida`;
  - opcional por ajuste de la obra: el avance valorizado de la tarea (`construction_progress_pct`), que pondera contrata y personal propio.
- Solo cuentan los avances validados, no los reportados ni los rechazados, y los re-trabajos no suman.
- Se calculan en cada línea:
  - **% periodo** = % acumulado − % acumulado confirmado en la valorización anterior;
  - **Monto del periodo** = % periodo × precio de la línea de venta.
- El usuario puede escribir otro % en `pct_manual`. Se guardan el motivo, quién lo escribió y cuándo (los campos ya existen), y la línea queda marcada «Manual».

**Gastos generales, imprevistos, utilidad y descuento** (líneas con `construction_line_role` distinto de Partida)
- Se valorizan en proporción: % del periodo de la línea = monto del periodo de las partidas ÷ costo directo total de las partidas de la venta. El costo directo puede ser de toda la venta o de la especialidad, según un ajuste.

**Condiciones del contrato**
- La amortización del adelanto, el fondo de garantía y la detracción salen de las condiciones del contrato de obra, sin hitos ni tipologías.

**Factura**
- **Crear factura** genera la factura desde la valorización confirmada: una línea por partida con avance en el periodo, más las de gastos generales, utilidad y descuento, y las de amortización y fondo de garantía según las condiciones.

### 2.3 Orden de venta del contrato
La ayuda del campo `construction_sale_order_id` dice «Una línea por partida (cantidad 1)». Para la base «Avance validado de la partida»:
- Debe poder usarse la misma cotización de la obra con cantidades por metrado. La línea se valoriza por porcentaje: el precio de la línea es su subtotal y la cantidad no importa.
- Si se mantiene la regla de «cantidad 1», el sistema debe ofrecer generar esa orden de contrato a partir de la cotización. Hoy no lo ofrece, y sin ella **Preparar valorización** falla con «Falta el valor requerido para el campo Orden de venta del contrato».

### 2.4 Interfaz
- **En el asistente Preparar valorización:**
  - mostrar la base de la valorización (solo lectura, tomada de la obra);
  - con base «Avance validado de la partida», llenar «Monto por partida» con las líneas que tengan avance en el periodo, cada una con % acumulado, % periodo y monto.
- **En la valorización:** columnas Partida, Precio, % anterior, % periodo, % acumulado, % escrito, Motivo y Monto, más el resumen de adelanto, fondo de garantía, detracción y neto.

### 2.5 Datos existentes
No requiere migración.

### 2.6 Criterios de aceptación
1. Con base «Avance validado de la partida» y corte al 30-set, la valorización de la obra 096-26 muestra la 3.0302 con 100 % acumulado y su monto completo.
2. Una partida con avance validado parcial muestra ese %. Una partida sin avance no entra o aparece con 0.
3. El % escrito a mano guarda motivo, usuario y fecha, y el siguiente «Actualizar entregas» o «Preparar» no lo borra.
4. Gastos generales, utilidad y descuento se valorizan en la proporción del costo directo del periodo.
5. La factura generada tiene el mismo total que la valorización.

---

## 3. Decisiones del validador al actualizar la valorización de la contrata (CR-15)

### 3.1 Situación
Prueba en `LIQ/2026/00066` (anulada), contrata MYFLA, semana del 28-ago al 3-set:
1. Avances validados: `AVN/2026/00155`, normal, 2 m² en 3.0303; y `AVN/2026/00156`, re-trabajo, 2 m² en 3.0302.
2. **Actualizar avances** (`construction.contract.settlement.action_refresh`): la línea del re-trabajo entra con `qty_settle = 0`. Correcto.
3. Se marca `rework_paid = True` con `rework_pay_reason`: la línea pasa a S/ 64.48 y `rework_paid_by` guarda el usuario. Correcto.
4. **Actualizar avances** otra vez: la línea se vuelve a crear (pasa del id 267 al 269) con `rework_paid = False`, sin motivo y sin usuario.

### 3.2 Causa probable
`action_refresh` borra y vuelve a crear las líneas (`line_ids`) en vez de actualizarlas.

### 3.3 Diseño de la corrección
`action_refresh` actualiza las líneas existentes en vez de reemplazarlas:
- **Clave de la línea:** valorización + línea de la orden (`purchase_line_id`) + partida (`task_id`) + marca de re-trabajo. Desarrollo puede usar la clave que ya tenga la línea.
- **Para cada clave:**
  - si existe, se actualizan solo los campos que vienen del avance (`progress_ids`, `qty_period`, `qty_cumulative`, `pct_validated`, `qty_settled_before`, etc.);
  - si no existe, se crea;
  - si ya no tiene avances, se elimina, salvo que tenga una decisión del validador; en ese caso queda en 0 y con un aviso.
- **Decisiones del validador que se conservan:**
  - `rework_paid`, `rework_pay_reason` y `rework_paid_by`;
  - `pct_manual`, `manual_reason`, `is_manual`, `manual_user_id` y `manual_date`;
  - `qty_final` y `final_reason`.
- **Aviso:** si cambió la cantidad del avance de una línea que tiene una decisión, la línea muestra un aviso visible («El avance cambió desde la decisión del …») y la decisión se mantiene hasta que el validador la confirme o la quite.
- **Deductivos:** se mantiene lo que ya funciona: se conservan los del periodo (CR-09).

### 3.4 Datos existentes
No requiere migración.

### 3.5 Criterios de aceptación
1. Con un re-trabajo marcado para pagar con su motivo, dos «Actualizar avances» seguidos conservan el pago, el motivo, el usuario y el monto.
2. Un % escrito a mano con su motivo se conserva al actualizar.
3. Si se agrega un avance nuevo a la misma partida, la línea suma la cantidad y conserva la decisión, con el aviso.
4. Si se rechaza el avance de una línea con decisión, la línea queda en 0 con aviso y no se borra.
5. Los deductivos siguen conservándose al actualizar.

---

## 4. Redondeo único entre valorización y factura (CR-11)

### 4.1 Situación
La tarifa de la línea ya tiene 4 decimales (`price_unit`, dígitos 16,4), pero el Valorizado 01 de MYFLA (`LIQ/2026/00010`) no cuadra con la factura del proveedor `F E001-00000561`:

| Concepto | Valorización | Factura | Diferencia |
|---|---|---|---|
| Subtotal | 18,613.35 | 18,613.34 | 0.01 |
| Total con IGV | 21,963.75 | 21,963.74 | 0.01 |
| Neto a su cuenta | 19,986.56 | 19,986.55 | 0.01 |

### 4.2 Diseño de la corrección
- **Línea:** `amount = round(qty_settle × price_unit, 2)` una sola vez. La tarifa no se redondea antes de multiplicar.
- **Totales:** suma de los `amount` de las líneas, sin volver a calcular desde los precios. Lo mismo para deductivos, IGV, fondo de garantía y detracción, cada uno redondeado una vez en su base.
- **Factura** que se genera desde la valorización:
  - el precio de cada línea es la tarifa con sus 4 decimales;
  - si el redondeo de Odoo por línea da un total distinto, se agrega una línea de ajuste de redondeo, de cuenta configurable y con máximo S/ 0.05, para que la factura sea igual a la valorización;
  - la diferencia queda visible en la valorización.
- **Factura del proveedor registrada a mano:** si el total difiere de la valorización vinculada, aparece un aviso con la diferencia.

### 4.3 Criterios de aceptación
1. Una valorización con tarifas de 4 decimales genera una factura cuyo subtotal, IGV y total son iguales a los de la valorización.
2. El portal de la contrata muestra el mismo neto que la factura.

---

## 5. Partida legible en el portal de obra (CR-17)

### 5.1 Situación
En **Avance**, **Requerimientos** y **Cuadrilla y tareo**, el portal muestra la ruta interna del árbol (`task_path`) en vez de la partida:

| Se ve | Debería verse |
|---|---|
| `520/543/544/` | `3.04.01 Trabajo de pintura látex…` |
| `919/920/921/` | `12.0101 Concreto f'c=210…` |

### 5.2 Diseño de la corrección
- Los servicios JSON del portal (`/construction/api/v1/…`) devuelven por cada línea:
  - `task_code`: código de la partida;
  - `task_name`: nombre de la partida;
  - `parent_label`: código y nombre del nivel superior, la sub-especialidad;
  - `role_label`: rol o actividad, por ejemplo «Operario (personal propio)».
- **En pantalla:**
  - línea 1: código + nombre de la partida, cortado a dos líneas;
  - línea 2: sub-especialidad y actividad, en texto secundario;
  - la ruta interna no se muestra.
- **Búsqueda:** el buscador de Avance y Requerimientos busca por código y por nombre de partida.
- **Compatibilidad:** se sube la versión del servicio (`v1` → `v1.1`) o se agregan los campos sin quitar los anteriores, para no romper la cola sin señal de los celulares que ya tienen el portal instalado.

### 5.3 Criterios de aceptación
1. En Avance, Requerimientos y Cuadrilla y tareo no aparece ninguna ruta interna.
2. Buscar «3.04.01» o «pintura» encuentra la partida.
3. Un registro guardado sin señal antes de la actualización se envía bien después.

---

## 6. Porcentaje del costo directo de un nivel elegido (CR-05)

### 6.1 Situación
En la receta R14 de la obra 096-26 (`construction.execution.template.line` id 132) se configuró y luego se volvió a como estaba:
- `calc_method = 'pct_group'`;
- `calc_pct = 2`;
- `calc_scope = 'task'` (Nivel elegido);
- `calc_task_id` = 3 ARQUITECTURA.

Resultados:
- `amount_unit` salió S/ 141.20, que es el 2 % del costo de la propia línea (S/ 7,060.03), y no el 2 % del costo directo de Arquitectura.
- Al volver `calc_method` a `qty`, `amount_unit` siguió en 141.20 hasta que se cambió `qty`: el compute no depende de `calc_method` ni de `calc_scope`.

### 6.2 Diseño de la corrección
- **En la receta**, una línea con «% del costo directo de un grupo de partidas» no tiene un monto propio: depende de la obra.
  - `amount_unit` = 0 y se muestra «Se calcula en el plan».
  - El total de la receta muestra «más 2 % del costo directo de ‹nivel›».
- **En el plan** (generación y recálculo):
  - **monto de la línea** = `calc_pct` % × costo directo planificado del nivel elegido;
  - el costo directo del nivel es la suma de las líneas del plan de todas las partidas debajo de `calc_task_id`;
  - no cuentan las líneas calculadas por porcentaje (para evitar circularidad) ni las de gastos generales, utilidad y descuento;
  - se recalcula al cambiar el plan de ese nivel.
- **Dependencias del compute:** `amount_unit` depende de `calc_method`, `calc_pct`, `calc_scope`, `calc_task_id`, `qty`, `price_unit`, `productivity` y `crew_size`.
- **Importación de recetas:** el libro de recetas acepta una columna «Nivel del porcentaje» con el código de la especialidad o sub-especialidad.

### 6.3 Relacionado: suministro del cliente (CR-06)
La marca `is_client_supply` ya existe en la receta y en la línea del plan. Falta:
- que el catálogo de requerimientos del portal y el asistente «Traer materiales del plan» excluyan las líneas marcadas;
- que la aprobación del plan acepte costo 0 en esas líneas;
- que la recepción en obra de lo entregado por el cliente actualice `qty_client_received`.

### 6.4 Criterios de aceptación
1. En una versión nueva del plan de la obra 096-26 con R14 en «Nivel elegido» = 3 ARQUITECTURA al 2 %, la línea vale el 2 % del costo directo planificado de Arquitectura.
2. Al cambiar la cantidad de una partida de Arquitectura, la línea de R14 se recalcula.
3. Volver la línea a «Cantidad por unidad» recalcula el monto en el momento.
4. Con el televisor de R08 marcado como suministro del cliente:
   - el plan se aprueba con su costo 0;
   - el televisor no aparece en el catálogo del portal;
   - su recepción en obra suma a «Recibido del cliente».

---

## 7. Ajustes menores del portal de obra

| N° | Pantalla | Situación | Qué se pide | Criterio de aceptación |
|---|---|---|---|---|
| 7.1 | Parte diario | «Trabajos del día» no mostró el avance `AVN/2026/00157` registrado ese día porque estaba por validar. | Mostrar todos los avances del día de la obra con su estado (Reportado o Validado). | El parte del día lista los avances reportados y validados de ese día. |
| 7.2 | Cuadrilla y tareo | Cada partida aparece una vez por rol (operario, peón…) sin decir el rol, con la ruta interna. | Encabezado de columna con código de partida y rol; agrupar por partida si hay más de un rol. | Cada columna dice partida y rol. |
| 7.3 | Requerimientos | El requerimiento interno `RQO/2026/00002` (EPP y útiles) queda con `project_id` vacío; solo lleva la analítica de gastos generales. | Guardar la obra en `project_id` aunque el tipo sea interno, para que aparezca en la obra y en sus reportes. | El requerimiento interno pedido desde el portal aparece en la obra. |
| 7.4 | Requerimientos | El requerimiento de obra `RQO/2026/00001` se aprobó solo al enviarlo, porque no hay ninguna regla de validación para requerimientos de obra. | Que el comportamiento sin regla sea configurable: aprobación automática o pasar al aprobador por defecto de la obra. Por defecto, pasar al residente. | Con la opción «Pasar al residente», el requerimiento enviado desde el portal queda «Por aprobar» con el residente como aprobador. |

---

## 8. Hoja de trabajo de presupuesto y plan (CR-18)

### 8.1 Situación
Prueba del 25-oct-2026 entre las 20:20 y las 21:05, pasos E14.24 a E14.27 de la prueba integral.

| Paso | Qué pasó | Evidencia |
|---|---|---|
| Abrir la hoja | Odoo vuelve al inicio con «The spreadsheet you're trying to access doesn't exist, has been deleted, or you don't have the necessary permissions to view it». `GET /spreadsheet/data/documents.document/49` responde 200 con la hoja completa. El error está en el navegador: `TypeError: content.startsWith is not a function` en `CellPlugin.createCell`. Hay 564 celdas guardadas como número JSON: INSUMOS 49, APU_DETALLE 140 y PRESUPUESTO 375. | Documento 49; se repite en el documento 51 (375 celdas) |
| Validar plantilla | 29 errores «La unidad … no tiene equivalencia (hoja LISTAS)» para Hours, Units, Days y gal (US): INSUMOS 22 filas y APU 7. Son unidades de Odoo que escribe la propia hoja; el maestro `construction.uom.alias` solo tiene la forma escrita (UND, hh, día, gal). | Pestaña ERRORES del documento 49 |
| Enviar: presupuesto, cotización sin obra | Sin obra, la hoja nace solo con PRESUPUESTO; INSUMOS, APU, APU_DETALLE y PLAN vacíos. El asistente avisa «0 insumos, 0 APU y 375 partidas; costo directo real S/ 0,00» y deja enviar. Las 375 partidas quedan en 0; gastos generales (S/ 51,861.67), utilidad (S/ 45,378.96) y descuento (−S/ 186,103.11) no se recalculan; la cotización queda en −S/ 88,862.48. | Venta 3 (S00003), copia en borrador de PPTO 096-26 |
| Enviar: presupuesto y plan | Con una obra de prueba y el libro de 096-26: «Plan PLR/2026/00012 · v1: 17 partidas con su receta», 73 líneas, 17 recetas y 445 tareas. En la cotización, 358 de 375 partidas quedan en 0: solo las 17 con receta tienen precio (S/ 42,460.99). La cotización queda en −S/ 46,401.49. | Venta 3, proyecto 16, `construction.resource.plan` PLR/2026/00012, documento 54 |

Otras diferencias con la sección 6.7 del requerimiento de la vertical:
- La pestaña PRESUPUESTO tiene 16 columnas (hasta «Costo real»). El libro 6.6 tiene 22: faltan metrado ofertado, costo unitario ofertado, precio unitario, costo ofertado, parcial de venta y reserva por holguras.
- La pestaña OBRA nace con gastos generales, imprevistos, utilidad y descuento vacíos, aunque la cotización los tiene.
- La vista previa del envío solo da conteos; no muestra qué cambia en cada partida.

**Riesgo:** enviado desde PPTO 096-26 (confirmada, S/ 559,408.37), el envío habría dejado en 0 los precios de 358 partidas de un contrato firmado.

### 8.2 Correcciones
- **a) Celdas como texto.** Al generar la hoja y al escribir con «Traer de Odoo» o «Actualizar insumos», el contenido de cada celda se guarda como cadena (formato de o-spreadsheet). El número 12.5 se guarda como `"12.5"`.
- **b) Unidades.** Una unidad es válida si coincide con «Escrito como» de una equivalencia o con el nombre de una unidad de Odoo (`uom.uom`) de la misma compañía.
- **c) Columnas de PRESUPUESTO.** Las mismas del libro 6.6, en el mismo orden, más la columna nueva de 8.3 D1. Datos del presupuestador en amarillo; fórmulas en gris.

| Col. | Columna | Tipo | Fórmula |
|---|---|---|---|
| A | Ítem | Dato | — |
| B | Especialidad | Dato | — |
| C | Sub-especialidad | Dato | — |
| D | Partida | Dato | — |
| E | Código del APU | Dato (opcional) | — |
| F | Costo unitario sin APU | Dato (nuevo, 8.3 D1) | — |
| G | Unidad | Dato, o fórmula si hay APU | Unidad del APU |
| H | Modalidad de ejecución | Dato | — |
| I | Metrado real | Dato | — |
| J | Holgura de metrado (%) | Dato | — |
| K | Holgura de metrado (cantidad) | Dato | — |
| L | Metrado ofertado | Fórmula | I × (1 + J) + K |
| M | Costo unitario | Fórmula | Costo del APU si hay código; si no, F |
| N | Holgura de costo (%) | Dato | — |
| O | Holgura de costo (monto) | Dato | — |
| P | Costo unitario ofertado | Fórmula | M × (1 + N) + O |
| Q | Margen (%) | Dato | — |
| R | Margen (monto) | Dato | — |
| S | Precio unitario | Fórmula | P × (1 + Q) + R |
| T | Costo real | Fórmula | I × M |
| U | Costo ofertado | Fórmula | L × P |
| V | Parcial de venta | Fórmula | L × S |
| W | Reserva por holguras | Fórmula | U − T |

- **d) OBRA.** «Traer de Odoo» llena gastos generales, imprevistos, utilidad y descuento (%) desde las líneas de la cotización con esos roles.
- **e) Vista previa y guardas del envío.**
  - La vista previa lista cada partida con precio y metrado actuales y nuevos, y marca en rojo las que bajan a 0 o cambian más de un porcentaje configurable (por defecto 20 %).
  - Con costo directo 0, «Enviar» queda deshabilitado con el aviso «El costo directo de la hoja es 0».
  - Si al terminar el costo directo de la cotización no es igual al de la hoja (±0.01), el envío se revierte e informa la diferencia (regla ya escrita en 6.7).

### 8.3 Diseño decidido
Decisiones tomadas por ALTA el 25-oct-2026.

**D1. Partida sin receta.**
- La receta es opcional. Si la partida no tiene «Código del APU», el presupuestador escribe su «Costo unitario sin APU» (columna F).
- Si tiene código, F no se usa y el costo sale de la receta.
- Sin código y sin costo, «Validar» marca el error «Partida ‹ítem›: sin código de APU ni costo unitario» y el envío no procede. Nunca se envía un 0 por falta de dato.
- «Traer de Odoo» llena F, para las partidas sin receta, con el `price_unit` actual de la línea. Así, una cotización que vino de otro sistema (por ejemplo S10, solo con precio por partida) va y vuelve sin perder precios.

**D2. Precio de la línea y recálculo.** Cada columna va a un campo de la línea de la cotización:

| Columna de la hoja | Campo de `sale.order.line` |
|---|---|
| Ítem | `construction_budget_item` |
| Metrado ofertado | `product_uom_qty` |
| Precio unitario | `price_unit` |
| Metrado real | `construction_qty_real` |
| Holgura de metrado (%) / (cantidad) | `construction_qty_slack_pct` / `construction_qty_slack` |
| Costo unitario | `construction_cost_apu` |
| Holgura de costo (%) / (monto) | `construction_cost_slack_pct` / `construction_cost_slack` |
| Costo unitario ofertado | `construction_cost_offered` |
| Margen (%) / (monto) | `construction_margin_pct` / `construction_margin_amount` |
| Costo real | `construction_amount_real` |
| Costo ofertado | `construction_amount_offered` |
| Reserva por holguras | `construction_amount_reserve` |

En cada envío al presupuesto se recalculan las líneas que no son partidas, con los porcentajes de OBRA:
- **gastos generales, imprevistos y utilidad** = % × suma del «Parcial de venta» de las partidas;
- **descuento** = % × (partidas + gastos generales + imprevistos + utilidad).

Es la misma base que hoy tiene PPTO 096-26: 8 % y 7 % sobre S/ 648,270.85 de partidas, y el descuento (S/ 186,103.11) sobre S/ 745,511.48.
- El descuento equivale a 24.963145 %, pero el nombre de la línea dice 24.9631 %. Con ese porcentaje de 4 decimales saldría S/ 186,102.78, es decir S/ 0.33 de diferencia.
- Por eso, el porcentaje de OBRA se guarda con 6 decimales, o el descuento se ingresa como monto y la hoja calcula el porcentaje.
- El nombre de cada línea muestra su porcentaje. Cada monto se redondea una sola vez (CR-11).

**D3. Cotización confirmada.**
- Con la cotización en estado «Orden de venta» (o bloqueada), «Enviar al planificador: presupuesto» queda deshabilitado con el aviso «La cotización está confirmada: los cambios de precio o metrado ofertado van por cambio de obra».
- «Enviar al planificador: presupuesto y plan» sigue disponible. Actualiza recetas, modalidad, metrado real, costo unitario, costo real y reserva, y crea la nueva versión del plan con su motivo.
- Ese envío no modifica `price_unit`, `product_uom_qty` ni las líneas de gastos generales, imprevistos, utilidad y descuento.
- Si la hoja trae un precio o un metrado ofertado distinto al de la cotización, la vista previa lo lista como «Va por cambio de obra» y no lo aplica.

**D4. Cotización sin obra.**
- La hoja de una cotización sin obra nace con todas sus pestañas. «Traer de Odoo» carga:
  - en INSUMOS, los productos de construcción con su costo vigente;
  - en APU y APU_DETALLE, la biblioteca de recetas sin obra (`construction.execution.template` con `project_id` vacío; hoy 5 en creval-dev).
- El envío al presupuesto guarda las recetas que usan las partidas como recetas de la cotización (campo nuevo en la receta: cotización de origen). No modifica la biblioteca.
- Al crear la obra desde la cotización, las recetas de la cotización se copian a la obra una sola vez. Desde ahí, «Enviar al plan» trabaja con las recetas de la obra, como hoy.
- La obra tiene el ajuste «Fuente del análisis de precio unitario» con la opción «Work Items de la venta». Desarrollo confirma si es este mismo camino; si lo es, se usa, sin depender de los módulos de mobiliario.

### 8.4 Datos existentes
- **Documentos ya creados.** Script de migración que convierte a texto las celdas numéricas de todo documento con `construction_sheet_kind`. En creval-dev, los documentos 49, 51 y 54 ya se convirtieron a mano.
- **Cotizaciones que vinieron de otro sistema.** Como PPTO 096-26, con los campos `construction_*` en 0: no requieren migración; D1 las cubre al traerlas a la hoja.
- **Registros de prueba** que ALTA archiva al cerrar la re-prueba:
  - venta 3 (S00003);
  - proyecto 16 «PRUEBA ALTA · Envío al planificador 25-oct», con su plan PLR/2026/00012 y 445 tareas;
  - documentos 51 (ya archivado) y 54;
  - equivalencias de unidad 28 a 31, creadas para seguir la prueba antes de la corrección b).

### 8.5 Criterios de aceptación
1. Una hoja nueva, con obra y sin obra, abre en el navegador; ninguna celda queda guardada como número.
2. «Validar plantilla» en el libro de 096-26, con las equivalencias 28 a 31 archivadas, da 0 errores.
3. Sobre una copia en borrador de PPTO 096-26: «Traer de Odoo» y luego «Enviar al planificador: presupuesto», sin cambios en la hoja. Las 375 partidas, sus cantidades, gastos generales, utilidad, descuento y total quedan iguales: S/ 559,408.37 ± 0.01.
4. Una partida sin código de APU y con F vacía da el error de D1 en ERRORES, y el envío no procede.
5. Con costo directo 0, «Enviar» está deshabilitado.
6. Gastos generales de 8 % a 10 % en OBRA y envío: la línea vale el 10 % de las partidas, el descuento se recalcula sobre la nueva base y el total cuadra.
7. Con PPTO 096-26 confirmada: «presupuesto» deshabilitado con su aviso. «Presupuesto y plan» crea la nueva versión del plan sin cambiar `price_unit` ni `product_uom_qty`; un precio cambiado en la hoja aparece como «Va por cambio de obra».
8. Cotización nueva sin obra:
   - «Traer de Odoo» carga insumos y las recetas de la biblioteca;
   - el envío guarda las recetas usadas en la cotización;
   - al crear la obra desde la cotización, la obra tiene esas recetas;
   - «Enviar al plan» crea el plan.
9. La vista previa lista por partida el precio actual y el nuevo, y marca las que bajan a 0.
10. Sin los módulos de mobiliario instalados, todo lo anterior funciona.

### 8.6 Por vertical
- **Ambas** (`al_construction_planner_spreadsheet`):
  - a) celdas como texto;
  - b) unidades de Odoo válidas en la validación;
  - e) vista previa por partida y bloqueo con costo directo 0.

  Lo mismo aplica a la hoja de mobiliario (`al_construction_planner_spreadsheet_furniture`): Desarrollo verifica que no guarde celdas numéricas y que su envío tenga las mismas guardas.
- **Construcción** (libro de partidas y APU del 6.6):
  - c) columnas de PRESUPUESTO;
  - d) porcentajes de OBRA;
  - D1 a D4.
- **Mobiliario:** su hoja de tipologías, muebles y módulos sigue igual que hoy. D3 (cotización confirmada) es una regla de venta y también aplica a mobiliario; Desarrollo confirma si su hoja envía a la cotización.

---

## 9. Lo que ya funciona (no requiere cambios)

- **Almacén sin Fabricación (CR-16, criterios 1 a 4):** recepción, ajuste de inventario, despacho desde el requerimiento y recepción parcial en el portal (19.0.15).
- **Asignar contrata con «Costo del plan» (CR-07):** trajo S/ 15.00 y S/ 780.00 desde el plan.
- **Re-trabajo (CR-08):** entra con 0 a liquidar; el pago pide motivo y guarda quién lo decidió.
- **Deductivos al actualizar la valorización (CR-09).**
- **Rol de gastos generales, utilidad y descuento (CR-12):** quedan fuera de los niveles de la obra.
- **Importación de recetas (CR-04):** llena producto y actividad.
- **Costo de la receta (CR-03):** con 4 decimales.
- **Hoja de trabajo de presupuesto y plan (6.7):** se crea desde la cotización con sus 10 pestañas; «Enviar: presupuesto y plan» crea el plan en borrador con sus recetas. Lo que falla está en la corrección 8.
- **Portal de obra (4.11):**
  - ingreso con QR y PIN, y aviso y conteo del PIN errado;
  - avance con foto, que no se duplica al reintentar;
  - requerimiento de partida e interno con kits de EPP y útiles;
  - parte diario con firma;
  - valorizaciones de la contrata con las mismas cifras de Odoo.

---

## 10. Pendiente de otros (no es de Desarrollo)

| Tema | Responsable |
|---|---|
| Cuenta de caja chica, diario de rendiciones y diario de comprobantes de gastos (módulo de caja chica ya instalado, CR-14) | Ana |
| Vía de registro del adelanto (cuentas 4221010 y 1221010 ya cambiadas, CR-02) | Ana y localización |
| Numeración de racks y carga de los 1,293 productos del maestro v2.0 | Logística (Oscar) y ALTA |
| Personal de obra para probar cuadrilla y tareo | ALTA |
| Regla de aprobación de requerimientos de obra y usuarios del grupo Logística | CREVAL |
| Libro de carga 6.6: columna «Costo unitario sin APU» y «Costo unitario» con la regla de D1 (8.3) | ALTA |

---

## 11. Entrega y fechas

1. Completar la fecha comprometida de cada punto en la tabla 13.3 del requerimiento de la vertical.
2. **Orden sugerido:** 1 (devoluciones y analítica de la compra), 8 (sin ella la hoja no se puede usar y el envío puede borrar precios), luego 3 y 4, 2, 5 y 7, y por último 6.
3. Cuando esté instalado en creval-dev, ALTA repite la hoja E14 de la prueba integral con los criterios de aceptación de este documento.
