# Requerimiento de desarrollo · Correcciones de la vertical Planificación de obra

**Versión:** 1.0 · 25-oct-2026
**Para:** Cristóbal Olano (Desarrollo)
**De:** Vicente Catacora (ALTA Latam)
**Origen:** re-prueba del 25-oct-2026 en la base de pruebas creval-dev, con los módulos de construcción actualizados ese día a las 11:18 (hora de Lima)
**Documentos relacionados:**
- *Requerimiento de desarrollo · Vertical Planificación de obra v1.0*: capítulo 12 (correcciones), sección 4.11 (portal de obra) y tabla 13.3 (fechas).
- *Prueba integral v1.1*, hoja «E14 Re-prueba 25-oct»: el paso a paso de cada prueba.

---

## 0. Alcance y reglas generales

### 0.1 Qué cubre
Siete correcciones de la vertical que siguen abiertas después de la re-prueba:

| N° | Corrección | Módulo principal (indicativo) | Prioridad | Depende de |
|---|---|---|---|---|
| 1 | Validación de movimientos de almacén (CR-16) | `al_stock_base`, `al_construction_material_request`, `al_construction_planner_purchase` | Alta, bloqueante | — |
| 2 | Valorización al cliente por avance validado de la partida (CR-01) | `al_construction_planner_sale` | Alta | — |
| 3 | Decisiones del validador al actualizar la valorización de la contrata (CR-15) | `al_construction_planner_subcontract` | Alta | — |
| 4 | Redondeo único entre valorización y factura (CR-11) | `al_construction_planner_subcontract` | Media | 3 |
| 5 | Partida legible en el portal de obra (CR-17) | `al_construction_portal` | Media | — |
| 6 | Porcentaje del costo directo de un nivel elegido (CR-05) | `al_construction_planner` | Media | — |
| 7 | Ajustes menores del portal de obra | `al_construction_portal`, `al_construction_material_request` | Baja | 5 |

Los módulos de la columna «Módulo principal» se dedujeron de dónde aparecen los campos en la base; Desarrollo confirma cuál corresponde.

### 0.2 Reglas que aplican a todo
- **Funcionalidad genérica.** Nada del desarrollo debe depender de un cliente: no se usan nombres, formatos ni valores de CREVAL. Todo lo que es una regla de negocio queda como ajuste configurable.
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
| Almacén | Almacén CREVAL (WH): Almacén Central, Proyectos (una sububicación por obra) y Bajas |
| Portal | QR activo en la obra 096-26; usuarios de prueba «PRUEBA ALTA · Capataz de obra» y «PRUEBA ALTA · Supervisor MYFLA» |

---

## 1. Validación de movimientos de almacén (CR-16) · bloqueante

### 1.1 Situación
Validar cualquier movimiento de inventario falla con:

```
'stock.move' object has no attribute 'raw_material_production_id'
```

Evidencia en creval-dev:
- Recepción `WH/IN/00001` de la compra `P00030` (1 bls de cemento), botón **Validar** (`stock.picking.button_validate`).
- Ajuste de inventario del cemento (`stock.quant.action_apply_inventory`).
- Por eso el despacho `WH/OBRA/00001` quedó en espera y no se pudieron probar la recepción en obra ni la devolución, ni desde el escritorio ni desde el portal.

En creval-dev no hay ningún módulo de fabricación ni de mobiliario instalado. En newallcenter-dev2 el asistente **Devolver** falla en el mismo tipo de transferencias; puede tener el mismo origen.

### 1.2 Causa probable
Un módulo de la vertical lee o escribe `stock.move.raw_material_production_id` (campo de `mrp`) en un método heredado de `stock.move` o `stock.picking`, como `_action_done`, `_prepare_*` o un compute, sin comprobar que Fabricación esté instalada.

### 1.3 Diseño de la corrección
1. **Ubicar** cada referencia a campos de `mrp` (`raw_material_production_id`, `production_id`, `workorder_id`, `bom_line_id`, etc.) en los módulos que no dependen de `mrp`.
2. **Mover** esa lógica a un módulo puente que dependa de `mrp`: el existente de fabricación de la vertical o uno nuevo con `auto_install: True`.
3. **Si no se puede mover**, proteger el acceso: `if 'raw_material_production_id' in self._fields:` o `move._fields.get(...)`. Esta es la segunda opción, no la primera.
4. **Revisar también** el asistente de devolución (`stock.return.picking`, heredado por `al_stock_base` el 24-oct): debe proponer como destino la ubicación de origen del movimiento y no pisar `location_dest_id` con valores de mobiliario.
5. **Prueba automatizada mínima**, sin `mrp` instalado: recepción de compra, despacho a obra, recepción en obra y devolución, cada una validada sin error.

### 1.4 Flujo de construcción que debe funcionar

| Paso | Operación | Origen → destino | Referencias que conserva |
|---|---|---|---|
| Compra | Recepción | Proveedores → Almacén Central | Requerimiento, partida y analítica de la obra en la línea de compra |
| Despacho | Despacho a obra | Almacén Central → Proyectos/‹obra› | Requerimiento y partida |
| Recepción en obra | Validación del despacho por el capataz (portal) o el residente | — | Lo recibido; el faltante queda como pendiente |
| Devolución | Devolución al almacén | Proyectos/‹obra› → Almacén Central, o → Bajas si está dañado | Partida y requerimiento; baja el costo de la partida |

Relacionado: en la compra `P00030`, generada desde el requerimiento de obra `RQO/2026/00001`, la línea salió **sin analítica**. La línea de compra que nace de un requerimiento de obra debe llevar la analítica de la obra, o la de gastos generales si el requerimiento es interno, y la partida.

### 1.5 Datos existentes
No requiere migración.

### 1.6 Criterios de aceptación
1. Sin Fabricación instalada, la recepción de una compra se valida sin error.
2. El ajuste de inventario se aplica sin error.
3. Un requerimiento de obra aprobado y procesado genera el despacho. Al haber stock, el despacho queda listo y el capataz lo ve en **Recepción** del portal.
4. Al recibir en el portal menos de lo enviado, se valida lo recibido y el resto queda pendiente.
5. Una devolución desde el portal crea la transferencia de la obra al Almacén Central, o a Bajas si se marcó «Dañado», y baja el costo de la partida.
6. La línea de compra generada desde un requerimiento lleva la analítica y la partida.
7. En newallcenter-dev2, el asistente **Devolver** funciona en Despacho a obra y en Recepciones.

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

## 8. Lo que ya funciona (no requiere cambios)

- **Asignar contrata con «Costo del plan» (CR-07):** trajo S/ 15.00 y S/ 780.00 desde el plan.
- **Re-trabajo (CR-08):** entra con 0 a liquidar; el pago pide motivo y guarda quién lo decidió.
- **Deductivos al actualizar la valorización (CR-09).**
- **Rol de gastos generales, utilidad y descuento (CR-12):** quedan fuera de los niveles de la obra.
- **Importación de recetas (CR-04):** llena producto y actividad.
- **Costo de la receta (CR-03):** con 4 decimales.
- **Hoja de trabajo de presupuesto y plan (6.7):** se crea desde la cotización con sus 10 pestañas. Faltan probar «Validar plantilla» y «Enviar al planificador».
- **Portal de obra (4.11):**
  - ingreso con QR y PIN, y aviso y conteo del PIN errado;
  - avance con foto, que no se duplica al reintentar;
  - requerimiento de partida e interno con kits de EPP y útiles;
  - parte diario con firma;
  - valorizaciones de la contrata con las mismas cifras de Odoo.

---

## 9. Pendiente de otros (no es de Desarrollo)

| Tema | Responsable |
|---|---|
| Cuenta de caja chica, diario de rendiciones y diario de comprobantes de gastos (módulo de caja chica ya instalado, CR-14) | Ana |
| Vía de registro del adelanto (cuentas 4221010 y 1221010 ya cambiadas, CR-02) | Ana y localización |
| Numeración de racks y carga de los 1,293 productos del maestro v2.0 | Logística (Oscar) y ALTA |
| Personal de obra para probar cuadrilla y tareo | ALTA |
| Regla de aprobación de requerimientos de obra y usuarios del grupo Logística | CREVAL |

---

## 10. Entrega y fechas

1. Completar la fecha comprometida de cada punto en la tabla 13.3 del requerimiento de la vertical.
2. **Orden sugerido:** 1 (bloquea la prueba integral), luego 3 y 4, 2, 5 y 7, y por último 6.
3. Cuando esté instalado en creval-dev, ALTA repite la hoja E14 de la prueba integral con los criterios de aceptación de este documento.
