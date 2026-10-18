---
modulos: [al_construction_material_request]
---

# Requerimientos de materiales

El **requerimiento de obra** es el documento con el que la obra pide
materiales a la oficina. El residente lo crea para una obra, se aprueba por
niveles y Logística lo procesa con un botón: por cada material, lo que hay
libre en el almacén central sale a la obra por transferencia interna y lo que
falta pasa a compras como requerimiento de compra ya aprobado. Así el pedido no
viaja por correo ni Excel, todos ven si se aprobó, el almacén despacha
reservando y Compras no vuelve a comprar lo que ya había.

Lo usan residentes y personal de obra (piden), jefes de proyecto y gerencia de
operaciones (aprueban), Logística (procesa y despacha) y Compras (compra).

El consumo del material en la obra, el control de presupuesto por partida y la
aprobación de las órdenes de compra quedan fuera. El control del saldo contra
el plan de la obra lo agrega la [planificación de obra](planning.md).

![Requerimiento procesado con lo despachado y lo que pasa a compra](material_requests/request-processed.png)

## Configuración

1. Instale **Requerimientos de obra** (`al_construction_material_request`).
   Instala los módulos de la comunidad (OCA) **Requerimiento de compra**
   (`purchase_request`) y **Aprobación por niveles** (`base_tier_validation`).
2. Vaya a **Requerimientos de obra ‣ Configuración ‣ Ajustes** y complete el
   **Origen** (existencias del almacén central, incluidas sus sububicaciones),
   la ubicación padre **OBRAS**, el tipo de operación **Despacho a obra** y la
   recepción de compras. **Completar configuración** rellena lo que falte.
   Si los proyectos se llaman «código nombre» (`ROOFG-04-25 ROOF GARDEN`),
   active **El nombre del proyecto empieza con el código de obra**: el código
   se toma de la primera palabra, la ubicación se llama `ROOFG-04-25` y la
   cuenta analítica lleva ese código y el nombre `ROOF GARDEN`.
3. En cada obra, vaya a **Proyecto ‣ (proyecto) ‣ Ajustes**, active **Es obra**
   y asigne el **Jefe de proyecto**. Al marcarla se hace el **alta de obra**:
   la cuenta analítica de la obra (plan de proyectos) y su ubicación
   `OBRAS/<código>`, o `OBRAS/<obra>` si no tiene **Código de obra**. Si ya
   existe una ubicación con ese nombre bajo la ubicación padre, se reutiliza.
4. En **Requerimientos de obra ‣ Configuración ‣ Reglas de aprobación**, defina
   los niveles, los revisores, el dominio por monto y **Aprobar por
   secuencia**.
5. Asigne los grupos: **Solicitante** (obra), **Aprobador** (jefes),
   **Logística** (almacén), **Administrador** y **Gerencia de operaciones** para
   el nivel por monto.
6. Contabilidad configura la cuenta de compra en las categorías de producto.

![Ajustes del requerimiento de obra con el origen y los tipos de operación](material_requests/settings.png)

!!! warning "Importante"
    Si se instala `purchase_request_tier_validation`, los requerimientos de
    compra pedirían otra aprobación. Agregue el dominio
    `[('construction_request_id', '=', False)]` a sus reglas para excluir los
    que nacen de un requerimiento de obra.

## Conceptos

| Término | Significado |
|---|---|
| Obra | Proyecto marcado como obra, con su ubicación `OBRAS/<código>` y su cuenta analítica |
| Código de obra | Código corto de la obra (`ROOFG-04-25`): nombra su ubicación y es el código de su cuenta analítica |
| Origen o almacén central | Existencias desde las que se despacha, con sus sububicaciones |
| Disponible en central | Stock libre hoy (no reservado), en la unidad de la línea |
| Disponible al procesar | Foto del stock libre en el momento de procesar |
| Vía almacén central / Directo a obra | Cómo llega lo que se compra, por línea (**Si hay que comprar**) |
| Valor estimado | Cantidad × costo de cada material; lo usan las reglas de aprobación |

Todo traslado de bienes entre establecimientos de la misma empresa se sustenta
con guía de remisión remitente, motivo **04, Traslado entre establecimientos de
la misma empresa**. El despacho a obra lleva ese motivo para que la guía
electrónica salga correcta.

## Pedir materiales

1. Vaya a **Requerimientos de obra ‣ Requerimientos ‣ Requerimientos ‣ Nuevo**.
2. Elija la **Obra** y la **Fecha requerida**, y agregue los materiales con su
   cantidad. El requerimiento toma la ubicación de la obra y su analítica, y
   recibe el número `RQO/AAAA/#####`.
3. Haga clic en **Solicitar aprobación**. El requerimiento pasa a **En
   aprobación** con una revisión por nivel; si ninguna regla aplica, pasa
   directo a **Aprobado**.

![Requerimiento en borrador con la obra y los materiales](material_requests/request-draft.png)

El formulario y las líneas se adaptan al celular: los materiales se muestran
como tarjetas.

Para material no previsto, marque **Material extra** y elija el **Motivo del
extra** (**Merma**, **Error de medida**, **Cambio del cliente** o
**Reposición**): sin motivo no se envía. El filtro **Material extra** los
separa en la lista. Con el planificador de obra, todo extra lo revisa la
Jefatura de Proyectos y se puede descontar a una contrata: vea
[Material extra y descuento a la contrata](planning/extra_material.md).

### Elegir niveles y etapas desde el plan

Con la [planificación de obra](planning.md) instalada, el borrador muestra el
recuadro **¿Para qué es el material?** debajo de la obra. Lo usan el
supervisor, el jefe de producción, el jefe de proyectos y el asistente de
proyectos, con el grupo **Solicitante**.

1. Elija los niveles en cascada. Hay un selector por cada nivel de la
   plantilla de la obra (Piso, Departamento, Ambiente, Mueble en mobiliario;
   Disciplina, Subpartida, Partida en una constructora) y cada lista muestra
   solo lo que cuelga de lo elegido arriba. Un nivel sin elegir significa
   «todos los de arriba»: si solo elige pisos, entra todo lo que cuelga de esos
   pisos. Un nivel que la obra no tiene no aparece.
2. Elija las **Etapas** (vacío: todas). La lista trae las etapas del perfil
   de vertical de la obra y las que usa su plan: una obra de mobiliario no
   ofrece las de construcción por partidas. Cada línea guarda su etapa en la
   columna **Etapa**.
3. Si el material es para una tarea del Gantt que no es nivel del plan
   (movilización, obras provisionales), elíjala en **Tareas del Gantt**. Esas
   tareas no tienen líneas en el plan: agregue el material a mano y cada línea
   queda con esa tarea.
4. Haga clic en **Traer materiales del plan**. Se crea una línea por material,
   nivel y etapa con lo que falta pedir del plan, agrupada en el nivel más bajo
   que eligió. La columna **Nivel** muestra la ruta corta («Dpto 102 /
   Cocina»).
5. Corrija cantidades o borre líneas antes de **Solicitar aprobación**. Una
   línea que agrega a mano toma el nivel y la etapa del recuadro cuando hay
   uno solo elegido; si eligió varios, indíquelos en la línea.

La **Fecha requerida** sale de la fecha de necesidad más temprana del plan. Si
esa fecha ya pasó, se propone la de hoy para que el requerimiento no nazca
vencido.

Cada línea traída queda enlazada a sus líneas del plan: **Saldo** y
**Control** muestran el saldo y marcan **Excede el plan** si pide más. Pulsar
otra vez el botón solo agrega lo que falta: una línea ya traída no se repite.
Una obra sin plan vigente funciona como siempre: se agrega el material a mano.

El asistente **Requerimiento de obra** del plan sigue siendo la vía completa
(agrupa por piso, departamento o ambiente y crea un requerimiento nuevo); este
botón llena el requerimiento abierto.

#### Material de producción

Mientras la orden de fabricación del planificador no esté en uso, el jefe de
producción también pide por aquí eligiendo la etapa **Producción**. Aparece el
campo **Planta**: elija la preproducción de la planta (por ejemplo,
`BRE/Preproducción` o `PPD/Preproducción`). El material de Producción se
despacha a esa ubicación y el de las demás etapas a la obra, en una
transferencia por destino; el costo sigue yendo a la obra por la analítica de
la línea.

Configuración:

- Marque **Preproducción de planta** en la ubicación (Inventario ‣
  Configuración ‣ Ubicaciones) para que se pueda elegir como planta.
- **Planificación de obra ‣ Configuración ‣ Ajustes ‣ Abastecimiento ‣
  Permitir la etapa Producción en el requerimiento de obra** (activo por
  defecto). Al desactivarlo, la etapa Producción deja de aparecer y un
  requerimiento con líneas de Producción no se envía.

## Aprobar

1. Los revisores filtran **Necesita mi revisión** y abren el requerimiento.
2. Haga clic en **Validar** o **Rechazar**. Con la última validación queda
   **Aprobado**; un rechazo deja **Rechazado**.
3. Para corregir un rechazado, haga clic en **Volver a borrador**: se borran las
   revisiones y se puede pedir aprobación de nuevo.

Con la regla de demostración, el jefe de proyecto revisa todos los pedidos y
la gerencia de operaciones además los que superan S/ 10 000.

!!! tip "Consejo"
    Con el planificador y el motor **Aplicación Aprobaciones**, el requerimiento
    sin cambios frente al plan va directo al almacén y los cambios de material o
    de cantidad se aprueban en **Aprobaciones**, según la tabla de rutas (ver
    [Aprobaciones del plan y del requerimiento](planning/approvals.md)).

![Regla de aprobación por niveles con el umbral por monto](material_requests/approval-rule.png)

## Procesar el pedido

Logística abre el requerimiento aprobado y hace clic en **Procesar**. Por cada
línea:

- lo que hay libre en el central entra en una transferencia **Despacho a obra**
  reservada;
- lo que falta pasa a un requerimiento de compra ya aprobado, porque el de obra
  ya pasó su aprobación;
- si la compra llega **Vía almacén central**, se crea además la transferencia
  central → obra en espera de la compra.

Si las líneas tienen destinos distintos (material de producción a la planta y
el resto a la obra), sale una transferencia por destino.

El requerimiento pasa a **En proceso** y el chatter anota la división de cada
material. Si al reservar se obtiene menos de lo calculado (otro pedido se llevó
el stock), la diferencia pasa a compra y el chatter lo anota. Un pedido en una
unidad distinta (por ejemplo, docenas) se divide en la unidad de la línea.

### Despachar

En **Transferencias** del requerimiento, el almacén valida el despacho. El
material queda en `OBRAS/<obra>` y la guía de remisión sale con el motivo 04.
Cada línea del requerimiento tiene su propio movimiento, aunque el mismo
producto se pida para dos niveles: lo validado llega a cada línea. Hasta que
el almacén valida, la línea dice **Por despachar**.
Un traslado interno entre el central y la obra no genera asiento contable: la
analítica viaja en el movimiento solo como trazabilidad.

### Comprar y recibir

1. Desde **Req. de compra**, Compras crea la orden de compra. Toma la fecha
   requerida y la analítica de cada línea; lo que va al central y lo que va
   directo a obra no se mezclan en una misma línea.
2. Al recibir:
    - **Vía almacén central**: entra al central y la salida a la obra queda
      reservada con exactamente lo recibido;
    - **Directo a obra**: entra a la ubicación de la obra.
3. Cuando todo lo pedido está en la ubicación de la obra, el requerimiento pasa
   solo a **Hecho**. Una devolución de la obra al almacén resta de **Recibido en
   obra**.

### Compra masiva consolidada

Compras junta en una sola orden lo que piden varias obras:

1. Vaya a **Compras ‣ Pedidos ‣ Compra masiva**. Aparecen las líneas de las
   solicitudes de compra aprobadas de todas las obras que todavía no están en
   una orden, agrupadas por producto, con su total **Por ordenar**.
2. Marque las líneas que va a comprar y use **Acción ‣ Crear petición de
   oferta**. Elija el proveedor y, si quiere sumarlas a una orden en borrador,
   la **Orden de compra**.
3. Se crea una sola línea por producto con la suma exacta, a stock general, sin
   analítica de las obras.

| Solicitud | Obra | Pedido | Comprado |
|---|---|---:|---:|
| PR00005 | ACACIAS 353 | 100 | 100 |
| PR00006 | TORRE A | 40 | 40 |
| PR00007 | ACACIAS 353 | 25 | 25 |
| **Orden** | | | **165** |

- Cada solicitud, y el requerimiento de obra que la originó, muestra como
  comprado solo su parte, aunque la orden tenga una sola línea.
- El origen de la orden nombra todas las solicitudes con su obra: «PR00005
  (ACACIAS 353), PR00006 (TORRE A), PR00007 (ACACIAS 353)».
- Si la orden compra más que lo pedido (mínimo del proveedor, redondeo), el
  exceso se reparte en proporción a lo que pidió cada solicitud.
- Lo que va directo a una obra conserva su destino y no se mezcla con el stock
  general.
- Una línea ya puesta en una orden sale de la lista; si la orden se cancela,
  vuelve.

### Cancelar

Solo Logística cancela un requerimiento en proceso: se anulan las
transferencias pendientes y las líneas de compra que aún no están en una orden.
Lo despachado se queda en la obra y lo ya pedido al proveedor no se toca; el
chatter lo avisa.

## Ejemplo

Datos de demostración «DEMO RQO»: obra **Colegio A**, almacén central con 60
bolsas de cemento libres. Requerimiento `RQO/2026/00245`:

| Material | Pedido | Costo | Libre al procesar | Transferencia | Compra | Llega |
|---|---|---|---|---|---|---|
| Cemento bolsa 42.5 kg | 100 | 29,50 | 60 | 60 | 40 | Vía almacén central |
| Fierro 1/2" | 50 | 46,00 | 200 | 50 | 0 | — |
| Arena gruesa | 8 m³ | 65,00 | 5 m³ | 5 m³ | 3 m³ | Directo a obra |

**Valor estimado**: 100 × 29,50 + 50 × 46,00 + 8 × 65,00 = 2 950,00 + 2 300,00
+ 520,00 = **S/ 5 770,00**. Solo revisa el jefe de proyecto; un pedido de 400
bolsas (S/ 11 800,00) pasaría además por gerencia.

1. **Procesar** crea el despacho a obra con 60 bolsas, 50 fierros y 5 m³ de
   arena, reservado; un requerimiento de compra con 40 bolsas (vía central) y
   3 m³ (directo a obra); y la transferencia central → obra de 40 bolsas en
   espera de la compra.
2. El almacén valida el despacho, sin asiento contable y con guía motivo 04.
3. La orden de compra pide 40 bolsas con destino el central y 3 m³ con destino
   final la obra.
4. La factura del proveedor la registra Contabilidad como cualquier compra; la
   cuenta sale de la categoría del producto. Por ejemplo:

    | Cuenta | Descripción | Debe | Haber |
    |---|---|---|---|
    | 6031 | Compras: 40 × 29,50 + 3 × 65,00 | 1 375,00 | |
    | 40111 | IGV 18 % sobre 1 375,00 | 247,50 | |
    | 4212 | Facturas por pagar al proveedor | | 1 622,50 |
    | | **Totales** | **1 622,50** | **1 622,50** |

5. Las 40 bolsas entran al central y su salida a la obra queda reservada; los
   3 m³ entran directo a la obra.
6. Con las 100 bolsas, los 50 fierros y los 8 m³ en `OBRAS/Colegio A`, el
   requerimiento pasa a **Hecho**.

## Reportes

- **Vale de requerimiento** (PDF A4): materiales, división, aprobaciones,
  documentos relacionados y firmas.
- **Materiales pedidos** (Logística): todas las líneas con su situación.
- Lista, tablero, calendario por fecha requerida y actividades.
- Stock por obra: **Inventario ‣ Informes ‣ Existencias**, filtrando la
  ubicación de la obra. El [kárdex valorizado](../../../inventory_and_mrp/inventory/kardex.md)
  registra los traslados.

![Vale del requerimiento con materiales, aprobaciones y firmas](material_requests/request-voucher.png)

## Casos especiales

| Situación | Qué pasa | Qué hacer |
|---|---|---|
| No se pidió aprobación | Ninguna regla aplicó (sin jefe de proyecto o bajo el umbral) | Revisar las reglas y el jefe de proyecto de la obra |
| **Disponible en central** en 0 aunque hay stock | El stock está reservado por otro documento o fuera del origen | Revisar reservas y sububicaciones del origen |
| El residente no ve el requerimiento | Solo ve los suyos y los de obras que sigue o dirige | Hacerlo seguidor de la obra o asignarlo |
| «Indique el motivo del material extra» | Es un extra sin motivo | Elegir el **Motivo del extra** |

Cada compañía tiene su configuración y sus reglas.

!!! info "Ver también"
    - [Planificación de obra](planning.md)
    - [SUNAT: guía de remisión remitente](https://orientacion.sunat.gob.pe/02-guia-de-remision-remitente)
    - [MEF: Plan Contable General Empresarial](https://www.mef.gob.pe/es/consejo-normativo-de-contabilidad/plan-contable)
    - [Ubicaciones en Odoo 19](https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/inventory/warehouses_storage/inventory_management/use_locations.html) y [Compras](https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/purchase.html)
    - OCA: [purchase_request](https://github.com/OCA/purchase-workflow/tree/19.0/purchase_request) y [base_tier_validation](https://github.com/OCA/tier-validation/tree/19.0/base_tier_validation)
    - Referencia técnica: [al_construction_material_request](../../../../developer/reference/modules/al_construction_material_request/index.md)
