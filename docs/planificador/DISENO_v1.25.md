# Diseño del paquete 1.25 · Requerimiento de fabricación como documento, y la obra en el nombre del plan de recursos

Requerimiento: `docs/md/ALTA_Planificacion_Paquete_1.25_Requerimiento_de_Fabricacion.pdf`
(versión 2, borrador, 27-nov-2026), M125-01 a M125-05.

Se programó en el orden propuesto: M125-05 primero, M125-01 y M125-02 juntos,
y M125-03 y M125-04 al final. Todo va en un solo cambio, sin otro paquete.

## 1. Ubicación (ARQUITECTURA_COMUN, sección 4)

| Qué | Capa | Módulo |
|---|---|---|
| Requerimiento de fabricación, su secuencia, sus vistas y menús, la cancelación y la actividad | Puente de Fabricación | `al_construction_planner_mrp` |
| El requerimiento en la orden, en la orden de corte hija y en la transferencia | Puente de Fabricación | `al_construction_planner_mrp` |
| La obra en el nombre del plan; nombre corto por contexto | Núcleo | `al_construction_planner` |
| Nombre corto donde la pantalla ya muestra la obra | Núcleo y puentes de ventas, compras, hoja de cálculo y contratas | ver M125-05 |

No hay condiciones por vertical. El asistente es el mismo para mobiliario
(tipologías) y para construcción por partidas (líneas de producción del plan).
La tipología de la orden la entrega la vertical por `_production_source`, como
antes.

## 2. M125-05 · La obra en el nombre del plan de recursos

| Qué | Dónde |
|---|---|
| «número · vN · obra»; con el contexto `construction_plan_short_name`, «número · vN» | `al_construction_planner/models/construction_resource_plan.py` (`_compute_display_name`, `_construction_short_name`) |
| Buscar un plan por el nombre de su obra | mismo modelo, `_rec_names_search = ['name', 'project_id.name']` |

El nombre de la obra se lee con `sudo`: quien ve el plan (planta, almacén)
puede no leer la ficha de la obra. Solo se toma su nombre.

**Dónde se usa el nombre corto** (punto 3 del pedido):

| Pantalla | Archivo |
|---|---|
| Selector de plan del árbol de recursos (suma la obra a mano) | `al_construction_planner/static/src/plan_tree/plan_tree.js` (contexto en `searchRead`) |
| Selector de plan de la matriz insumo-producto (ídem) | `al_construction_planner/static/src/io_matrix/io_matrix.js` |
| Selector del Cronograma (agrupa por obra) | `al_construction_planner/models/construction_plan_tree.py` (`get_schedule_plans`) |
| Cartera del Inicio (fila de la obra) | `al_construction_planner/models/construction_planner_home.py` (ya era «número · vN» escrito a mano) |
| Tablero de abastecimiento (selector de obra) | `al_construction_planner_purchase/models/construction_supply_board.py` |
| Flujo de caja de la obra (selector de obra) | `al_construction_planner_sale/models/construction_schedule_report.py` |
| Hoja de trabajo de la obra («Plan de Odoo: …») | `al_construction_planner_spreadsheet/models/documents_document.py` |
| «Documento origen» de la orden de contrata («obra · plan») | `al_construction_planner_subcontract/wizards/plan_contract_wizard.py` |
| Campo «Plan de recursos» del requerimiento de fabricación (la obra está al lado) | `al_construction_planner_mrp/views/manufacturing_request_views.xml` |

El Gantt manda `plan_name` en su carga, pero ninguna pantalla lo muestra: no se
tocó.

**Punto 4 del pedido.** El mensaje «La obra %s ya tiene un plan %s.»
(`construction_resource_plan.py`, `_check_single_version`) no nombra el plan:
su segundo valor es «vigente» o «en preparación». No hubo que cambiarlo.

## 3. M125-01 · Requerimiento de fabricación como documento

| Qué | Dónde |
|---|---|
| Modelo `construction.manufacturing.request` (cabecera, ambientes, notas, estado calculado, referencia nativa) | `al_construction_planner_mrp/models/manufacturing_request.py` |
| Secuencia RQF por compañía | mismo archivo (`_construction_next_number`); plantilla en `data/manufacturing_request_data.xml` |
| El asistente crea el requerimiento antes que las órdenes, les pone su número y abre el requerimiento | `wizards/plan_production_wizard.py` (`_prepare_request_values`, `action_create`) |
| Formulario, lista, búsqueda, acción; botón de la obra | `views/manufacturing_request_views.xml` |
| Menús «Requerimientos de fabricación» en el planificador (Abastecimiento) y en Manufactura › Operaciones | `views/menus.xml` |
| Permisos y regla multicompañía | `security/ir.model.access.csv`, `security/ir_rule.xml` |

**Estado.** Se calcula de las órdenes del requerimiento sin contar las
canceladas, con la tabla del pedido. Las órdenes de corte hijas no cuentan.

**Secuencia por compañía.** El módulo trae una plantilla (`RQF/%(year)s/`,
relleno 5) con otro código. La primera vez que una compañía crea un
requerimiento, se le crea su secuencia `construction.manufacturing.request` con
ese prefijo; así cada compañía numera desde 00001. El prefijo se cambia en
Ajustes › Técnico › Secuencias, en la secuencia de la compañía.

**«Ambientes».** Son los de las órdenes creadas (las líneas de la vista previa
con niveles), no lo marcado en el árbol: un ambiente que el aviso excluye no
entra. Se muestran como «Piso / Departamento / Ambiente · Tipología» (la
etiqueta de `_space_label` ampliada). En construcción por partidas el nivel con
etapas no tiene piso, departamento ni tipología y queda solo su nombre.

**Cabecera protegida.** La escribe el asistente al crear el requerimiento. Un
`write` de esos campos que no viene del sistema se rechaza (sección 8 de la
arquitectura, 16-nov-2026); las personas solo escriben «Notas». No se duplica;
no se elimina si tiene órdenes.

**Permisos.**

| Grupo | Lee | Escribe (notas) | Crea | Cancela |
|---|---|---|---|---|
| Planificación de obra: ejecuta (`group_planner_user`, quien usa el asistente) | Sí | Sí | Sí | Sí |
| Planificación de obra: consulta (`group_planner_plan_viewer`) | Sí | No | No | No |
| Inventario: usuario (`stock.group_stock_user`, incluye Fabricación) | Sí | No | No | Sí, si es de Fabricación |

El jefe de producción (Fabricación: usuario) lee, recibe la actividad y
cancela. El historial y la actividad se escriben con lectura
(`_mail_post_access = 'read'`). Cancelar usa la cancelación nativa de la orden,
que exige los permisos de Fabricación de quien cancela.

**Lo que no cambió.** La vista previa del asistente (`_prepare_lines`) y lo que
lleva cada orden: producto, lista, cantidad, planta, `construction_plan_id`,
`construction_space_task_ids`, `project_id`, la sincronización de asignaciones y
el paso del plan a «En curso».

## 4. M125-02 · Requerimiento a la vista en la orden, en la lista y en sus documentos

| Qué | Dónde |
|---|---|
| `mrp.production.construction_mrp_request_id` (solo lectura, sin copiarse), `construction_group_task_id` (Agrupador) y `construction_typology_id` (Tipología) | `models/mrp_production_request.py` |
| La orden de corte hija hereda el requerimiento de la madre | `models/stock_rule.py` (`_prepare_mo_vals`, donde ya heredaba plan y ambientes) |
| Etiqueta junto al número y botón inteligente «Requerimiento», primero de la fila; columna «Requerimiento» opcional y visible; campo y agrupador en la búsqueda | `views/mrp_production_views.xml` |
| El menú «Órdenes de fabricación» del planificador abre en «Borrador» y agrupado por requerimiento, con el grupo «RQF · obra · agrupador» | acción nueva `action_planner_productions`; el menú conserva su xmlid; el de Manufactura no cambia |
| `stock.picking.construction_mrp_request_id` (calculado, con búsqueda en las referencias) en el formulario, junto a «Documento origen», y en la búsqueda | `models/mrp_production_request.py`, `views/mrp_production_views.xml` |

**Referencia nativa.** El asistente crea una `stock.reference` con el número
del requerimiento y la agrega a las órdenes (`reference_ids`) y a sus
movimientos. No se pasa al crear la orden: si la orden nace con referencias,
Odoo no crea la suya propia (`mrp.production.create`), y el pedido exige
conservarla. Con la referencia en los movimientos, Odoo la pasa sola al
abastecimiento: a la orden de corte hija (`stock.rule._prepare_mo_vals`) y a las
transferencias (`stock.move._prepare_procurement_values`). No hizo falta
propagarla a mano. Lo comprueba la prueba de la cadena de dos plantas con
entrega a producción (`TestPackage125Chain`).

**Nombre largo.** El requerimiento se muestra con su número. Con el contexto
`construction_request_long_name` (la acción del planificador) se muestra
«número · obra · pisos», que es lo que se lee en la fila de grupo.

## 5. M125-03 · Una actividad por requerimiento

| Qué | Dónde |
|---|---|
| Tipo de actividad «Revisar y confirmar las órdenes del requerimiento», del requerimiento | `data/manufacturing_request_data.xml` |
| La actividad va al requerimiento; las órdenes sin requerimiento siguen con la suya | `models/production_date_review.py` (`_construction_schedule_date_review`, `_construction_date_review_note`) y `models/manufacturing_request.py` (`_construction_schedule_review`) |
| Se cierra sola cuando ninguna orden queda en «Borrador», con la fecha confirmada (o el estado) de cada orden | `_construction_close_review`, llamado tras `action_confirm` y `action_cancel` de la orden y tras cancelar el requerimiento |

El destinatario es el mismo: «Jefe de producción» de la compañía o, sin él, los
responsables de Fabricación (`_construction_production_heads`); se guarda en el
requerimiento. «Fecha confirmada» sigue en cada orden con su efecto. El
interruptor de Ajustes no cambió de texto: apagado, no hay actividad.

## 6. M125-04 · Cancelar el requerimiento

| Qué | Dónde |
|---|---|
| Botón «Cancelar», visible salvo «Cancelado» y «Producido» | formulario del requerimiento |
| Diálogo «Cancelar RQF/…»: órdenes que ya pasaron a producción (orden, tipología, estado) y, debajo, las que siguen en borrador; «Cancelar las órdenes en borrador» y «Volver» | `wizards/manufacturing_request_cancel_wizard.py`, vista en `views/manufacturing_request_views.xml` |
| Cancelación nativa de cada orden y mensaje en el historial con quién y qué órdenes | `_construction_cancel_drafts` |

**Diferencia.** El pedido dice «pide confirmación» cuando todo está en borrador.
Se usa el mismo diálogo en los dos casos: con todo en borrador muestra solo la
tabla de borradores con «Se cancelan todas las órdenes del requerimiento». Sin
órdenes en borrador, el diálogo solo informa y no ofrece cancelar.

## 7. Integración con la suite

- **Movimientos de stock.** No se agregó código que corra en cada movimiento:
  la referencia se pone una vez, en el asistente, y la propaga Odoo.
- **Bases compartidas.** El requerimiento y la referencia solo se ponen en
  órdenes del asistente. Ventas y reposición no cambian.
- **Aprobaciones.** El control de exceso sigue por orden; el estado del
  requerimiento no depende de la aprobación. La suite del puente de
  aprobaciones de fabricación corre con los dos motores.
- **Nombre del plan.** Cambia el texto en Compras, Fabricación, la hoja en
  Documentos y los mensajes; ningún dato guardado.

## 8. Diferencias frente al requerimiento

| Punto | Diferencia | Motivo |
|---|---|---|
| M125-01, 12 | «Leen» también los usuarios de Inventario | El almacenero ve el número en la entrega y lo abre (M125-02, punto 7) |
| M125-01, punto 9 | «Órdenes de corte» y «Entregas a producción» se ocultan cuando no hay | Evita botones en cero en un requerimiento en borrador |
| M125-02, punto 7 | El número del requerimiento en la entrega va como campo bajo «Documento origen» | El encabezado de la transferencia es un grupo de campos |
| M125-04, punto 2 | Confirmación con el mismo diálogo (ver sección 6) | Una sola pantalla para los dos casos |
| M125-04 | Los usuarios de Fabricación leen las tipologías de la obra (`construction.typology`, solo lectura) | El jefe de producción, sin grupos del planificador, abre el requerimiento y su diálogo de cancelación, que muestran la tipología de cada orden; sin ese permiso daba error de acceso (lo detectó `TestScreens125`) |
| M125-05, punto 4 | Sin cambio en «La obra %s ya tiene un plan %s.» | El mensaje no nombra el plan (ver sección 2) |
| Verificación en las bases de desarrollo de mobiliario y de construcción por partidas, con capturas | No hecha en este cambio | Se hace al desplegar; desde aquí no se entra a esas bases |

## 9. Pruebas

`al_construction_planner_suite/tests/test_package_125.py`:

| Clase | Qué prueba |
|---|---|
| `TestPackage125` | Con la jefatura de proyectos y el jefe de producción, sin administrador: creación, ambientes, origen, mensaje del plan, secuencia por compañía, estados, cabecera protegida, botones, menús, marca de la orden, duplicado, agrupación, actividad (encendida, apagada, sin jefe), cancelación (todo en borrador y con una orden confirmada), ambientes libres de nuevo, nombre del plan y búsqueda por obra |
| `TestPackage125Chain` | Dos plantas con entrega a producción: la orden de corte hija y las transferencias llevan la referencia; búsqueda por requerimiento en transferencias |
| `TestScreens125` | Prueba de pantalla, entrando por el árbol de recursos (así comprueba que el diálogo del asistente se cierra): asistente, formulario, botones inteligentes, marca en la orden, lista agrupada y diálogo de cancelación (`static/tests/tours/package125_request_tour.js`) |

Se ajustaron las pruebas que leían la orden en la acción del asistente
(`test_supply.py`, `test_native_v17.py`): la acción abre ahora el requerimiento.

## 10. Tabla final por código

| Código | Commit | Versión del módulo | Pruebas | Diferencias |
|---|---|---|---|---|
| M125-01 | (este cambio) | `al_construction_planner_mrp` 20261127.21 | `TestPackage125`, `TestScreens125` | Lectura para Inventario; botones ocultos en cero |
| M125-02 | (este cambio) | `al_construction_planner_mrp` 20261127.21 | `TestPackage125`, `TestPackage125Chain`, `TestScreens125` | Número en la entrega como campo |
| M125-03 | (este cambio) | `al_construction_planner_mrp` 20261127.21 | `TestPackage125` | — |
| M125-04 | (este cambio) | `al_construction_planner_mrp` 20261127.21 | `TestPackage125`, `TestScreens125` | Un solo diálogo |
| M125-05 | (este cambio) | `al_construction_planner` 20261127.90 y puentes de ventas, compras, hoja y contratas | `TestPackage125` | Punto 4 sin cambio |
