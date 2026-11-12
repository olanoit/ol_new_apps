# Diseño del paquete 1.21 · Despacho y recepción en obra

Requerimiento: `ALTA_Planificacion_Paquete_1.21_Despacho_y_Recepcion_en_Obra.pdf`
(versión 2, 11-nov-2026), M121-01 a M121-03. Se entregan M121-01 y M121-02 juntos,
porque son la misma cadena. M121-03 («Dañado») no se hace: el requerimiento lo dejaba
opcional y el 12-nov-2026 se decidió mantener el texto libre.

El paquete se entrega solo. No se despliega el mismo día que el 1.20.

## 1. Lo que no se programa

La cadena es nativa de Odoo 19 y se configura en cada base (C1 a C10 del
requerimiento):

1. ubicación de tránsito;
2. tipo «Salida a obra» (tipo Salida, con la guía de remisión de `l10n_pe_edi_stock`);
3. tipo «Recepción en obra»;
4. ruta del almacén con una regla «Empujar a». La regla no marca «el destino lo da la
   regla» (`location_dest_from_rule`), así respeta la ubicación final de cada movimiento;
5. lista y recordatorios del tránsito.

Lo único que se programa es lo que la configuración no alcanza: «Procesar» fija el
destino de cada movimiento, y la recepción que crea la regla no trae el encabezado
de la salida.

## 2. M121-01 · «Procesar» despacha al tránsito

Módulo `al_construction_material_request` (núcleo del requerimiento, común a las
dos verticales).

| Qué | Dónde |
|---|---|
| Si el destino por defecto del tipo de despacho es un tránsito y la obra no está dentro de él, la salida va al tránsito. Lleva la dirección de entrega de la obra para la guía | `models/construction_material_request_process.py:126` (`_prepare_picking_vals`) y `:134` (`_construction_dispatch_transit`) |
| Cada movimiento lleva la obra como ubicación final (`location_final_id`, nativo). Vale también para lo que espera compra, que usa los mismos métodos | `models/construction_material_request_process.py:195` (`_prepare_move_vals`) |
| Dirección de entrega: la de la venta de la obra o, sin venta, el cliente del proyecto | `models/project_project.py:31` (`_construction_delivery_partner`) |
| Obra y departamento en el encabezado de la salida (campos de mobiliario) | `al_construction_planner_furniture/models/construction_site_dispatch.py:388` |

Sin tránsito en el tipo, «Procesar» no cambia: un paso, sin ubicación final ni
dirección. El motivo de traslado 04 ya lo ponía «Procesar» desde la v1.11. La
condición la decide la configuración del tipo; no hay condición por vertical.

## 3. M121-02 · Recepción encadenada

| Qué | Dónde |
|---|---|
| La transferencia que crea la regla de empuje copia de la salida el requerimiento, la obra (`project_id`) y el documento origen (el requerimiento, que es lo que muestra el portal). Se escribe después de asignar la transferencia: `sale_project_stock` fija el proyecto al crearla | `models/stock_move.py:46` (`_assign_picking`); `models/stock_picking.py:69` y `:74` |
| Mobiliario suma «Obra» y «Departamento» de su envío a obra | `al_construction_planner_furniture/models/construction_site_dispatch.py:379` |
| «Recibido en obra» cuenta lo que llega a la obra (un paso o recepción encadenada). La salida al tránsito cuenta como despachada, no como recibida. Devolver la salida antes de recibirla la descuenta | `models/construction_material_request_line.py:320` y `:324`; `models/stock_move.py:39` (`_construction_bound_for`) |
| «En tránsito: N materiales» en la ficha, con enlace a las recepciones pendientes | `models/construction_material_request.py:139` y `:289`; `views/construction_material_request_views.xml:45` |
| El aviso «Entrega en camino a la obra» sale al validar la salida: la acción programada del aviso corre al momento | `al_construction_portal/models/portal_notice.py:112` |

El requerimiento pasa a Hecho con la regla de siempre (`_check_done`). Se cumple
cuando todas las líneas tienen lo pedido en la obra o se cerraron con lo recibido.

El portal no cambia: lista lo que está «Listo» con destino en la obra. Con los dos
pasos, la recepción solo existe cuando la salida se validó, así que la salida en
«Listo» ya no aparece en el portal.

## 4. Integración

- **Inventario y kardex.** Un tránsito con compañía se valoriza como una ubicación
  interna (`stock_account`, `_should_be_valued`: `internal` o `transit`). El material
  sigue valorizado, y la salida y la recepción son dos traslados dentro de la
  compañía: no hay un segundo consumo. La comprobación en el kardex queda para la
  verificación en newallcenter-dev1.
- **Analítica.** La salida al tránsito no lleva analítica de obra
  (`_get_analytic_distribution` exige destino en la obra). La recepción copia la
  analítica de la línea y la aplica al entrar a la obra.
- **Compras.** La espera de compra (`make_to_order`) va al tránsito con la obra como
  ubicación final, y sale cuando llega la compra.
- **Sobrescrituras.** `_assign_picking` y `_action_done` llaman a `super()` y
  salen enseguida si la transferencia no es de un requerimiento de obra.

## 5. Pruebas

- `al_construction_material_request/tests/test_package_121_dispatch.py`
  (`TestDispatchTransit121`):
  - salida al tránsito con ubicación final, encabezado y dirección;
  - cadena completa validada por el almacenero (Inventario + Logística, sin
    «Administrador»): recepción en «Listo» con el requerimiento, en tránsito no
    cuenta como recibido, al recibir pasa a Hecho;
  - devolver la salida antes de recibirla;
  - un paso con el tipo de hoy.
- `al_construction_portal/tests/test_package_121_reception.py`
  (`TestPortalReception121`), con el residente como usuario portal:
  - el portal no muestra la salida sin validar y sí la recepción, con el
    requerimiento como origen;
  - recepción con faltante (entrega parcial con el requerimiento) y luego el resto
    (requerimiento Hecho).
- La configuración C1 a C5 de las pruebas está en
  `al_construction_material_request/tests/common.py` (`setup_dispatch_transit`).

## Diferencias frente al requerimiento

- M121-03 («Dañado») no se hace (decisión del 12-nov-2026): sigue el texto libre
  «Faltantes o daños» y el retorno manual.
- La obra no tiene un campo de dirección. La dirección de entrega de la guía sale de la
  venta de la obra (dirección de entrega) o del cliente del proyecto. Si la guía
  necesita otra, se cambia en la salida antes de generarla.
- En el núcleo, la «Obra» del encabezado es el proyecto nativo (`project_id`, de
  `project_stock`). Los campos «Obra» (`construction_project_id`) y «Departamento»
  (`construction_apartment_task_id`) son del puente de mobiliario, que los llena en la
  salida al tránsito y los copia a la recepción.
- El aviso «Entrega en camino» lo sigue enviando la acción programada. Al validar la
  salida, la acción corre al momento en lugar de esperar su próxima vuelta.

## Verificación en las instancias (12-nov-2026)

Desplegado en creval_dev_1, newallcenter_dev_1 y newallcenter_dev_2 (vmic_dev_1 no
tiene estos módulos). En newallcenter-dev1, con el tipo de despacho del almacén
principal apuntando a «Salida a obra (prueba 1.21)», que queda así:

| Criterio | Resultado |
|---|---|
| «Procesar» crea la salida al tránsito, ubicación final la obra | OK: un movimiento, final = ubicación de la obra |
| Encabezado de la salida: obra, requerimiento, dirección de entrega | OK. «Departamento» vacío: el requerimiento de prueba no tiene departamento |
| Validar la salida crea la recepción en «Listo» | OK (regla de empuje nativa) |
| Recepción con obra, requerimiento y origen | OK |
| Aviso «Entrega en camino» al validar la salida | OK, en el chatter de la recepción |
| Portal: «Requerimiento de obra · RQO/… · …» | OK, con un residente de prueba (usuario portal) |
| «Recibido en obra» no cambia con la recepción pendiente | OK: despachado 20, recibido 0, «En tránsito» 1 |
| Al confirmar en el portal sube lo recibido y el requerimiento pasa a Hecho | OK: recibido 20, Hecho |
| Sin tránsito, un paso | OK: el otro almacén conserva «Despacho a obra» (destino Proyectos) |
| Kardex | Las dos transferencias van entre ubicaciones valoradas de la misma compañía: sin valor, como el despacho de un paso |

## Resultado por código

| Código | Commit | Versión | Pruebas | Diferencias |
|---|---|---|---|---|
| M121-01 | 23be35d5 | material_request 37, furniture 31 | `TestDispatchTransit121` | Dirección de entrega desde la venta o el cliente |
| M121-02 | 23be35d5 | material_request 37, portal 16, furniture 31 | `TestDispatchTransit121`, `TestPortalReception121` | Aviso por la acción programada al momento |
| M121-03 | — | — | — | No se hace (decisión del 12-nov-2026) |
