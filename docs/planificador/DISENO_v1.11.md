# Diseño del paquete 1.11 v3 · encargos de la verificación del 24 y 25-oct

Encargos que quedaron sin desarrollar tras la verificación de Vicente y su
asesoría: M111-21, M111-22 y M111-23 del paquete 1.11 (versión 1, actualizada
el 24-oct), los detalles menores del 24-oct, y M17-18 y M17-25 del paquete 1.7
parte 2 (vigentes según el 1.9). M19-01 queda fuera (ver al final).

Fuente: el resumen del encargo. La versión del proyecto «Allcenter» con
M111-21 a M111-23 y el paquete 1.7 parte 2 no estaban en el repositorio
cuando se desarrolló; lo que el resumen no precisa se marca en
«Diferencias».

## Módulos y versiones

| Módulo | Versión | Requerimientos |
| --- | --- | --- |
| `al_construction_material_request` | 27.20261024 | M111-22 (necesidad en el movimiento, hooks), detalles del 24-oct |
| `al_construction_planner_approvals` | 7.20261021 | M111-21 |
| `al_construction_planner_mrp` | 12.20261024 | M17-18, M17-25, M111-22 (aviso «Retazo disponible») |
| `al_construction_planner_furniture` | 12.20261021 | M17-25 |
| `al_construction_planner_mrp_request` (nuevo) | 2.20261025 | M111-22, M111-23 |
| `al_construction_planner` | 52.20261025 | Exceso del avance: actividad a cada aprobador (falla de la suite) |
| `al_construction_planner_suite` | 21.20261023 | Pruebas |

## Diferencias frente al requerimiento

| Punto del requerimiento | Implementado | Motivo |
| --- | --- | --- |
| M111-21: el interno «pasa por el jefe o el grupo» con Aprobaciones | Solicitud de Aprobaciones con un solo tramo «basta uno» (el jefe, o los usuarios del grupo sin quien pide); sin grupo, se aprueba al solicitarlo | Mismo resultado que la regla por niveles. El interno no tiene plan ni rutas: no se usa la tabla de rutas |
| M111-21: rechazo | Con Aprobaciones el rechazo devuelve el interno a **Borrador** con el motivo; por niveles queda **Rechazado** | Es como ya trata Aprobaciones al requerimiento de obra y al plan (M19-07); el aprobador y el aprobado son iguales con los dos motores |
| M111-21: jefe que pide su propio interno | Se excluye a quien pide; sin otro aprobador, se aprueba al solicitarlo | Odoo no deja a quien solicita aprobar su solicitud |
| M111-22: mover el modelo del retazo y el asistente a `al_stock_base` | Puente nuevo `al_construction_planner_mrp_request` (auto_install con `al_construction_planner_mrp` y `al_construction_planner_purchase`) | Patrón nativo de Odoo (`sale_mrp`, `purchase_mrp`). Mover el modelo exigiría migrar xmlids, campos y datos ya cargados en dev1 (lotes ZZ, productos retazo), y llevaría Fabricación a `al_stock_base`, que usan empresas sin ella. En `al_construction_material_request` solo hay hooks neutros |
| M111-22: necesidad del movimiento | El despacho guarda lo que cubre (mínimo entre la necesidad y lo despachado) y la entrega pendiente de compra, el resto | Así el redondeo cae en la entrega que lleva la última plancha (13.3 con 10.6 libres: 10 + 3.3, redondeo 0.7) |
| M111-22: la línea «cuenta la fracción cubierta» | El retazo entrega a la línea su % de plancha (R25 de 20.7 % = 0.207 plancha), no 1 unidad; con 7 + 0.21 la línea de 7.2 queda **Entregada** | Hook `_construction_request_line_qty` del movimiento |
| M111-22: sugerencia «Retazo disponible» | Columna informativa en el despacho (requerimiento y producción): el retazo más chico que alcanza y cuántos más hay | Es aviso, no asignación, como pide el requerimiento |
| M111-22: tipo del despacho a preproducción | `pbm_type_id` del almacén de la ubicación de preproducción, si está activo; si no, el de siempre. Se suma a los tipos que valida solo Logística | Con fabricación en un paso el tipo «Elegir componentes» está archivado |
| M111-23: dónde se pide | Menú **Requerimientos ‣ Reposiciones a planta** y botón **Pedir reposición a planta** en el requerimiento de obra | Sin el documento v3 no se conoce la pantalla pedida; el botón prellena obra, nivel y fecha |
| M111-23: responsable de la actividad | El **Jefe de producción** de Ajustes (el mismo de M17-18), que queda como responsable de la orden; vacío, los responsables de Fabricación de la compañía, nunca quien pide | Una sola opción por compañía para los dos encargos. En dev1 la actividad caía en quien pide porque la orden la crea el sistema con su usuario |
| M111-23: estados | Borrador, Pedida a planta, En fabricación, Fabricada por despachar, Recibida en obra, Cancelada; calculados con la orden y el despacho | «Despachada» y «recibida» coinciden: el despacho a obra deja la pieza en la ubicación de la obra |
| M111-23: despacho al terminar | Al terminar la orden (`button_mark_done`), transferencia de lo terminado de la orden a la ubicación de la obra con el «Despacho a obra» del almacén de la planta | Lo crea el sistema (`sudo`): quien termina la orden puede no tener Inventario |
| M17-18: «fecha confirmada» | Campo `construction_date_confirmed` en la orden; escribe la **Fecha límite** nativa (`date_deadline`) y mueve el fin de la etapa de producción de sus ambientes con `action_gantt_reschedule` (arrastre de las siguientes) | Odoo no tiene una fecha confirmada en la orden de fabricación; `date_deadline` es la nativa más cercana. Mover la etapa con el método del Gantt mantiene las fechas de necesidad y el aviso a Logística |
| M17-18: actividad | Tipo de actividad propio «Revisar y confirmar fecha» (`mail.activity.type`), hecha al confirmar la fecha | Opción en Ajustes, activa por defecto |
| M17-25: «departamento y ambiente» | «Dpto 501 / Cocina» en todos los avisos del asistente | Mismo formato que ya usaba «Sin marcar como medidos» |
| Detalle: «Pedir al almacén» de la línea | Campo nuevo `warehouse_src_id` (almacén) con inverso: elegir otro almacén pone su stock; la ubicación pasa a «Ubicación de origen», oculta por defecto | Logística sigue pudiendo elegir una sububicación |
| Detalle: «Salió de…» en inglés («Units») | Unidad y producto en el idioma de quien pide (o el de la compañía) | La nota la escribe quien valida, que puede tener otro idioma |

## Notas técnicas

- Regla 8.9 (M111-12): en `al_construction_material_request` la necesidad
  solo se escribe en productos indivisibles con la casilla de la compañía
  (`_construction_is_whole(company, 'request')`); los dos hooks nuevos
  (`_get_dispatch_picking_type_for`, `_construction_request_line_qty`)
  devuelven lo de siempre sin el puente.
- `construction.replacement.request`: ACL para Solicitante, Logística y
  Fabricación: usuario; reglas de multicompañía, «propias y de mis obras»
  para el solicitante (como el requerimiento) y todas para Logística y
  Fabricación. La orden, el BoM y la actividad los crea el sistema con
  `sudo()` justificado; los datos de la orden se muestran con
  `compute_sudo`.
- El aviso «Retazo disponible» reutiliza la búsqueda del asistente
  (`_remnant_lines`), no almacenado.

## Pruebas

| Archivo | Cubre |
| --- | --- |
| `test_package_111_internal_approvals.py` | M111-21: jefe del departamento, grupo sin jefe, sin grupo, mismo resultado con los dos motores (Solicitante interno) |
| `test_package_111_v3_request.py` | M111-22 (necesidad en despacho y pendiente, sin cambios en otros productos, cubrir y quitar retazo con Almacenero, tipo a preproducción), M111-23 (reposición completa con Solicitante y Fabricación: usuario), detalles del 24-oct |
| `test_package_111_v3_production.py` | M17-18 (actividad, fecha confirmada en la orden y la etapa, opción apagada; jefe con Fabricación: usuario) y M17-25 |

## M19-01 · carga del despiece y la optimización

No se implementó, como se pidió. Sigue postergada desde el 1.10: los
documentos ya cuentan con su ausencia (la orden de corte toma la necesidad de
su lista de materiales y «Piezas (m²)» se corrige al declarar,
`construction_cut_closing_edit_pieces`). Para estimarla hace falta:

1. El archivo real que entrega el optimizador (PDF de la OP o Excel) de una
   orden de corte de dev1, con sus piezas y sus planchas.
2. La decisión D-M1 del 23-set: cómo se identifica cada pieza dentro del
   paquete (código, módulo y posición).
3. Si la carga reemplaza la necesidad de una orden ya confirmada (el 1.11 v2
   dice que sí y vuelve a redondear) y quién la hace.
