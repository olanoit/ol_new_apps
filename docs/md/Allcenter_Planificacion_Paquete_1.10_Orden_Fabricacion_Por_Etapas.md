# Planificación de obra — fabricación por etapas (paquete 1.10)

19-oct-2026 · versión 2 · @Vicente · Para Cristóbal Och

## Cambios frente a la versión del 18-oct

- **Base del código:** se revisó contra el commit `38b5ada` del 19-oct de `olanoit/ol_new_apps`, rama 19.0. Entre `66355aa` y `38b5ada` el planificador cambió datos de demostración, pruebas y el aviso de accesorios faltantes (`al_construction_planner_production` 3.20261018). Las líneas citadas son las de `38b5ada`.
- **Revisión independiente:** un segundo revisor contrastó cada referencia de este documento con el código el 19-oct. Sus correcciones ya están incorporadas: la herencia del proyecto en Odoo 19, la unión de órdenes hijas, el saldo negativo con tolerancia, el despacho parcial, la receta real y los campos que vienen de otro módulo.
- **Listas de materiales (M110-02):** las listas de fabricación ahora son registros aparte de la lista de la tipología. Motivo: el generador del plan usa la lista de la tipología como fuente de materiales cuando los módulos no traen receta (`plan_generate_wizard.py`, líneas 280 a 305). Si esa lista se convirtiera en la de armado, el plan perdería producción, instalación y acabado.
- **Orden hija y exceso (M110-04):** ahora cubre:
  - la confirmación automática de la orden hija, que hace Odoo dentro del abastecimiento;
  - los accesorios de armado, que hoy están escritos para la etapa `assembly`;
  - el informe de presupuestado frente a real del puente de producción.
- **Despacho (M110-05):** se rehízo. El despacho nativo lleva la obra y el departamento, y al validarlo los módulos pasan a «En obra» (decisión del 19-oct, hallazgo HM-39).
- **Requerimientos nuevos:**
  - Cifras de la solicitud de aprobación y rechazo después de aprobar (M110-08): hallazgos HM-37 y HM-31.
  - Formato del lote configurable (M110-09): hallazgo HM-38.
- **Corrección:** la acción nativa «Force Approval» no es solo del administrador. La tiene el grupo «Aprobaciones / Oficial: aprobar todas las solicitudes» (verificado en dev1, acción 607, grupo 72).
- **Puesta en marcha:** ahora tiene orden de trabajo, dependencias, tamaño relativo y migración.

## Objetivo y alcance

La fabricación de mobiliario se hace con la fabricación nativa de Odoo:
- corte en Puente Piedra, que entrega un paquete de piezas;
- traslado del paquete a Breña;
- armado en Breña, que entrega los módulos con su lote;
- despacho de los módulos a la obra, por departamento.

Plantas, estaciones, operaciones y la cadena entre plantas son configuración nativa. Ya están hechas y probadas en `newallcenter_dev_1`.

Este paquete pide nueve ajustes al planificador (M110-01 a M110-09). Con ellos, el planificador alimenta a Odoo sin imponerle la planta, no aplana las listas y deja trazabilidad de cada módulo hasta la obra. Todo lo propio es configurable. Cada requerimiento termina con su línea «Efecto en Manufactura».

Sale de la prueba integral de Montecarmelo del 18 y 19-oct-2026: hallazgos HM-28 y HM-31 a HM-39 del caso de prueba.

Marcas de fuente:
- [V] leído o probado en `newallcenter_dev_1` el 18 o el 19-oct-2026;
- [C] código leído (Odoo 19 rama 19.0, o repositorio OL-PROJECTS en `38b5ada`);
- [D] decisión de Vicente, con fecha;
- [P] propuesta de la asesoría, por validar.

## Hallazgos y requerimientos

| Hallazgo | Qué pasó en la prueba | Lo resuelve |
| --- | --- | --- |
| HM-28 · lista de la tipología junta etapas | El mismo producto de armado y de instalación se suma en una línea con la primera etapa; la orden pide lo de instalación | M110-02 |
| HM-32 · orden sin etapas | Una orden por cocina con la lista plana: produce «la cocina» en Puente Piedra con las cuatro etapas | Configuración nativa más M110-01 y M110-02 |
| HM-33 · el paquete cuenta como cambio de material | Las 12 órdenes de armado quedaron «excede» con 0 % y «con cambio de material» | M110-04 |
| HM-34 · orden de corte sin plan | Las 12 órdenes de corte tienen el proyecto, pero no el plan ni los ambientes | M110-04 |
| HM-35 · una planta por corrida | El closet CL01B, que solo tiene corte, necesitó otra corrida del asistente | M110-03 |
| HM-36 · closet sin armado sin camino a Breña | El producto del CL01B queda en Puente Piedra y el despacho desde Breña no lo encuentra | Configuración: ruta de abastecimiento en la categoría, o despacho desde Puente Piedra |
| HM-37 · cifras de la solicitud | «Presupuestado −20», diferencia 40 y 1,000 % para un pedido de 20 | M110-08 |
| HM-31 · rechazo después de aprobar | Se rechazó en Aprobaciones una solicitud ya aprobada y el requerimiento siguió aprobado | M110-08 |
| HM-38 · lote repetido entre closets | CL01A, CL02 y CL03 del 301 con el mismo lote ZZMONTEC-0301-MCL01 | M110-09 |
| HM-39 · estado de los módulos | Después de producir y despachar, las 17 tareas de módulo del 302 siguen «Planificado» | M110-03 y M110-05 |
| Pedido del 19-oct | La lista de Aprobaciones no muestra los datos para decidir ni aprueba en bloque | M110-07 |

## Flujo

| Paso | Planta | Documento | Lo crea |
| --- | --- | --- | --- |
| 1. Orden de armado de la tipología y el piso | Breña, estación «Armado · Azcona» o «Armado · Castrovirreyna 2.º piso» | Orden de fabricación (BRE/MO) con su orden de trabajo | Asistente «Crear órdenes de fabricación» del plan |
| 2. Orden de corte del paquete de piezas | Puente Piedra, estación «Producción de piezas · Puente Piedra» | Orden de fabricación (PPD/MO), hija de la de armado, con su orden de trabajo | Odoo, al confirmar la de armado |
| 3. Entrega de planchas y tapacanto | Puente Piedra | PPD/PC | Odoo |
| 4. Traslado del paquete a Breña | Puente Piedra → Breña | PPD/OUT y BRE/IN, por tránsito | Odoo |
| 5. Entrega del paquete y los accesorios de armado | Breña | BRE/PC | Odoo |
| 6. Despacho de los módulos a la obra, por departamento | Breña → obra | Tipo «Despacho a obra» (BRE/DO), con obra y departamento (M110-05) | Logística |
| 7. Instalación y acabado | Obra | Requerimiento de obra (M19-03) | Jefe de producción o supervisores |
| Aparte: piezas de posventa, garantía y reposición urgente | Breña, estación «Producción de piezas · Castrovirreyna 1.er piso» | Tipo de operación «Producción de piezas · posventa» (BRE/PV), con motivo (M110-06) | Jefe de producción |

Odoo crea los pasos 2 a 5 de forma nativa. La orden de corte lleva el proyecto porque su lista de materiales lo tiene: `project_mrp` pone en la orden el proyecto de su lista (`project_mrp/models/mrp_production.py`, `_compute_project_id`, l. 11-15) [C, V].

## Configuración ya hecha en dev1 el 18-oct-2026 [V]

Hay que replicarla en dev2 y en producción. No requiere desarrollo.

| Qué | Dónde | Valor |
| --- | --- | --- |
| Categoría «02 MATERIA PRIMA PIEZAS / Paquetes de piezas» | Inventario › Configuración › Categorías de productos | Rutas «Replenish on Order (MTO)» y «ALMACEN BREÑA: suministrar producto de ALMACEN PUENTE PIEDRA»; costo promedio |
| Regla «PPD: Zona de carga → PPD/Tránsito» (id 37) | Inventario › Configuración › Reglas | Método de suministro «Activar otra regla». Sin esto, Odoo traslada pero no crea la orden de corte |
| Tipo de operación «Despacho a obra» | Inventario › Configuración › Tipos de operación | Almacén Breña, interno, de Azcona/Racks a Proyectos, prefijo DO |
| Producto «Paquete de piezas» por tipología | Inventario › Productos | Uno por cada una de las 14 tipologías de Montecarmelo, por ejemplo ZZMONTEC-40-26-C07-PAQ |
| Lista de corte por tipología | Fabricación › Listas de materiales | Operación «ALMACEN PUENTE PIEDRA: Manufactura», proyecto de la obra, materiales de producción de piezas (11 líneas en C07) |
| Lista de armado por tipología | Igual | Operación «ALMACEN BREÑA: Manufactura», proyecto de la obra. Componentes: 1 paquete y los materiales de armado (8 líneas en C07). Subproductos: los módulos de la tipología (13 en C07), con participación en el costo |
| Órdenes de trabajo activadas | Fabricación › Configuración › Ajustes | «Órdenes de trabajo» marcado |
| Estación «Producción de piezas · Puente Piedra» (PPD-PZ) | Fabricación › Configuración › Centros de trabajo | Costo por hora 0, porque las estaciones solo registran tiempos (decisión D26 del 22-set). Después se divide en seccionadora, canteadora, ranuradora y otras |
| Estación «Armado · Azcona» (BRE-AZ-AR) | Igual | Costo por hora 0. Alternativa: «Armado · Castrovirreyna 2.º piso» |
| Estación «Armado · Castrovirreyna 2.º piso» (BRE-CV-AR) | Igual | Costo por hora 0. Alternativa: «Armado · Azcona» |
| Estación «Producción de piezas · Castrovirreyna 1.er piso (posventa y urgencias)» (BRE-CV-PZ) | Igual | Costo por hora 0. Para garantías y reposiciones rápidas a obra |
| Operación en cada lista | Pestaña «Operaciones» de cada lista de materiales | Corte: «Producción de piezas» en PPD-PZ. Armado: «Armado» en BRE-AZ-AR, que tiene como alternativa la de Castrovirreyna. Tiempo de 60 min por unidad: valor provisional inventado hasta medirlo |
| Tipo de operación «Producción de piezas · posventa» | Inventario › Configuración › Tipos de operación | Fabricación en Breña, prefijo PV, de Castrovirreyna/Corte 1er piso a Azcona/Racks |

Notas:
- **Ruta de fabricación:** en Odoo 19 no se marca en el producto. Odoo la aplica sola cuando el producto tiene lista de materiales [C].
- **Instalación y acabado:** sus materiales quedaron fuera de las dos listas. Se piden con el requerimiento de obra.
- **Cantidades por etapa:** las listas se armaron con los materiales de cada módulo de la tipología, que traen su etapa separada. Así, el tornillo 4x30 de C07 queda con 4 en armado y 54 en instalación, en lugar de 58 en una sola línea (corrige HM-28 para la prueba).
- **Reparto del costo entre módulos:** según el costo de material del plan de cada módulo, producción de piezas más armado. Por ejemplo, en C07 MOD BAJO CAJONERA lleva 10.31 % y MOD BAJO 420 4.82 %. La «cocina armada» queda en cero y sirve de control.
- **Lista de la tipología en dev1:** para la prueba se convirtió a mano la lista de la tipología (por ejemplo, la lista 18 de C07) en la de armado. Con M110-02 esto cambia: la lista de la tipología vuelve a ser la receta completa y la de armado va aparte. Al volver a importar, el importador las deja así.
- **Verificación:** se creó una orden de armado de COCINA 08 sin indicar planta (BRE/MO/00005). Odoo la puso en Breña porque así lo dice su lista. Al confirmarla, creó la orden de corte PPD/MO/00007 en Puente Piedra con el proyecto de la obra, y cada orden sacó su orden de trabajo en su estación. Se cancelaron después de verificar.

## Lo que ya es configurable

**En Odoo, nativo [C, V]:**
- **Plantas:** cada almacén con fabricación es una planta, con su tipo de operación «Manufactura».
- **Planta de cada etapa:** el campo «Operación» de su lista de materiales.
- **Estaciones:** los centros de trabajo, con estaciones alternativas.
- **Operaciones:** cada lista lleva sus operaciones, cada una en una estación.
- **Cadena entre plantas:** las rutas de abastecimiento y de fabricación bajo pedido.
- **Proyecto:** la orden toma el proyecto de su lista de materiales (`project_mrp`). Por eso cada lista de fabricación lleva el proyecto de la obra.
- **Lista que se usa:** cuando un producto tiene varias listas, Odoo toma la de menor secuencia (`mrp/models/mrp_bom.py`, `_bom_find`, orden `sequence, product_id, id`).

**En el planificador, desde el paquete 1.7 (M17-02):**
- **Catálogo de etapas** (Planificación de obra › Configuración › Etapas): nombre, número, etapa padre, tipo («Fabricación», «Ejecución en campo» o «Control»), «Consume en la orden de fabricación», etapa anterior, duración y color.
- **Etapa en cada dato:** cada material de la tipología, cada línea del plan y cada actividad lleva su etapa.
- **Pedidos por etapa:** el requerimiento de obra trae del plan solo la sub etapa elegida, y «Pedir accesorios» propone los de armado.
- **Base del margen de exceso:** por material o por total de la orden, en Ajustes (`construction_production_margin_basis`).

**Etapas de dev1 [V]:**

| Número y nombre | Código | Tipo | Consume en la orden |
| --- | --- | --- | --- |
| 1 Producción (agrupa) | `furniture_production` | Fabricación | No |
| 1.1 Producción de piezas | `production` | Fabricación | Sí |
| 1.2 Armado | `assembly` | Ejecución en campo | Sí |
| 2 Instalación (agrupa) | `furniture_installation` | Ejecución en campo | No |
| 2.1 Instalación | `installation` | Ejecución en campo | No |
| 2.2 Acabado | `finishing` | Ejecución en campo | No |
| 2.3 Limpieza | `cleaning` | Ejecución en campo | No |

**Dato por revisar:** «1.2 Armado» está como «Ejecución en campo», aunque se hace en Breña y consume en la orden. No lo cambié, porque el tipo de etapa se usa en el código. `_field_codes()` (`construction_stage.py`, línea 249) solo devuelve las etapas de campo, que son las que se asignan a una contrata o a una cuadrilla. Si «1.2» pasa a «Fabricación», el armado ya no se podría asignar a una contrata de armado. Cristóbal debe confirmar si eso se quiere.

## Desarrollos

Criterio de Vicente del 18-oct-2026: el planificador se ofrecerá a otras empresas de manufactura, de muebles de madera, metal u otras. Por eso lo propio debe ser configurable y apoyarse en lo nativo de Odoo, sin soluciones a la medida de Allcenter [D]. Nada de lo que sigue nombra a Puente Piedra, a Breña, a la cocina ni un código de etapa: todo sale de datos de configuración.

### Guía para el desarrollo con Claude Code

**Repositorio y versiones**
- **Repositorio:** `olanoit/ol_new_apps`, carpeta `OL-PROJECTS`, rama 19.0, commit `38b5ada` del 19-oct-2026.
- **Versiones instaladas en dev1 [V]:**

| Módulo | Dev1 | Repositorio |
| --- | --- | --- |
| `al_construction_planner` | 19.0.42.20261016 | 42.20261016 |
| `al_construction_planner_mrp` | 19.0.3.20261016 | 3.20261016 |
| `al_construction_planner_furniture` | 19.0.6.20261017 | 6.20261017 |
| `al_construction_planner_purchase` | 19.0.5.20261016 | 5.20261016 |
| `al_construction_planner_approvals` | 19.0.2.20261017 | 2.20261017 |
| `al_construction_planner_approvals_mrp` | 19.0.1.20261017 | 1.20261017 |
| `al_construction_planner_production` | 19.0.2.20261017 | 3.20261018 (dev1 va atrasado) |
| `al_construction_planner_suite` | 19.0.8.20261018 | 8.20261018 |

**Módulos que se tocan**
- `al_construction_planner`: catálogo de etapas (M110-01) y saldo del plan (M110-08).
- `al_construction_planner_mrp`: asistente de órdenes, herencia del plan, etapas de la orden y motivo (M110-03, M110-04 y M110-06).
- `al_construction_planner_furniture`: importador, productos de módulo, lote y despacho (M110-02, M110-05 y M110-09).
- `al_construction_planner_purchase`: cifras de la solicitud del requerimiento (M110-08).
- `al_construction_planner_approvals`: lista de aprobaciones, aprobación en bloque y bloqueo del rechazo tardío (M110-07 y M110-08).
- `al_construction_planner_approvals_mrp`: comparación y exceso por etapa (M110-04) y cifras de la solicitud de la orden (M110-08).
- `al_construction_planner_production`: accesorios e informe por etapa (M110-04).

**Convenciones del repositorio [C]**
- Comentarios, docstrings y textos en español, con el código del requerimiento en el docstring, como «paquete 1.10, M110-04».
- Versión `N.AAAAMMDD` en `__manifest__.py`.
- El `CHANGELOG.md` de cada módulo no se edita a mano. Se genera desde `docs/fichas/<módulo>.yml`, sección `novedades`, con `python3 scripts/gen_changelog.py`. Las carpetas `docs/` y `scripts/` están en la raíz de `ol_new_apps`, no dentro de `OL-PROJECTS`.
- Las lecturas del plan desde planta van con `sudo()` y un comentario que diga por qué, como ya hace `_construction_versus_values`.
- La documentación técnica del planificador está en `docs/planificador/`, en la raíz del repositorio. Se propone agregar `DISENO_v1.10.md` con este paquete y actualizar `ACEPTACION.md` [P].

**Pruebas**
- Van en `al_construction_planner_suite/tests`, con `PlannerCommon` de `common.py` y `@tagged('post_install', '-at_install')`, como `test_production_order_v19.py`.
- Archivo nuevo propuesto: `test_stage_chain_v110.py`.
- Comando: `--test-tags /al_construction_planner_suite`.

**Reglas para todo el paquete**
- **Compatibilidad:** sin configuración nueva, todo funciona como hoy. Las pruebas actuales deben seguir pasando sin cambios.
- **Nada de códigos de etapa nuevos en el código.** En el flujo de la orden hay uno, `('stage', '=', 'assembly')` en `al_construction_planner_production/models/mrp_production.py`, línea 137, y M110-04 lo reemplaza. Hay otros fuera de este flujo, que no se tocan en este paquete: `STAGE_FIELDS` en `plan_generate_wizard.py` (l. 11-16) y el valor por defecto `'installation'` en `construction_dependency.py` (l. 55).
- **Multicompañía:** cada ajuste nuevo es por compañía. Los campos nuevos del catálogo de etapas usan `company_dependent=True`, porque el catálogo es común a todas las compañías. Es el primer uso de ese patrón en el planificador.
- **Sin Odoo Studio y sin vistas creadas en la base** (indicación de Cristóbal del 19-oct): todo va en el XML de los módulos.
- **Antes de escribir código:** comprobar que lo nativo no lo resuelve. Odoo 19 ya hace estas cuatro cosas, y el desarrollo no debe repetirlas:
  - toma la planta de la orden desde la lista de materiales (`stock_rule.py`, `_prepare_mo_vals`, línea 174: `picking_type = bom.picking_type_id or self.picking_type_id`);
  - aplica la ruta de fabricación si el producto tiene lista;
  - crea las órdenes hijas y los traslados por las rutas bajo pedido y de abastecimiento entre almacenes;
  - pone en la orden el proyecto de su lista (`project_mrp/models/mrp_production.py`, l. 11-15).

  Ojo: `project_mrp/models/stock.py` (l. 19-23) lee `group_id`, que en Odoo 19 ya no viene en los valores de abastecimiento (`stock/models/stock_move.py`, l. 1853-1869). Ese código no hace nada en 19 y no sirve de patrón.

**Orden de trabajo y tamaño relativo [P]**

El tamaño es una estimación de la asesoría para ordenar el trabajo, no un plazo. El plazo lo da Cristóbal.

| Orden | Requerimiento | Depende de | Tamaño |
| --- | --- | --- | --- |
| 1 | Etapa con su planta (M110-01) | — | Pequeño |
| 2 | Saldo y cifras de la solicitud, rechazo tardío (M110-08) | — | Mediano |
| 3 | Listas de materiales por etapa (M110-02) | M110-01 | Grande |
| 4 | Orden hija con el plan y exceso por etapa (M110-04) | M110-01 y M110-02 | Grande |
| 5 | Asistente sin planta impuesta (M110-03) | M110-02 | Pequeño |
| 6 | Formato del lote (M110-09) | — | Pequeño |
| 7 | Despacho con departamento (M110-05) | M110-09 recomendable | Mediano |
| 8 | Motivo en la orden de posventa (M110-06) | — | Mediano |
| 9 | Lista de aprobaciones y aprobación en bloque (M110-07) | M110-08 | Mediano |

### Estado actual del código [C]

Hay dos caminos para fabricar, y los dos tienen la fabricación de mobiliario escrita en el código. Las líneas son las del commit `38b5ada`.

| Qué | Dónde | Qué hace hoy | Qué choca con lo nativo o con la prueba |
| --- | --- | --- | --- |
| Orden por ambiente o piso (W-04) | `al_construction_planner_mrp/wizards/plan_production_wizard.py`: campo `picking_type_id` (l. 24-28), `action_create` (l. 118-157) | Una orden por agrupador y producto de la tipología, con la lista de la tipología | El campo «Planta» es obligatorio y se impone a todas las órdenes (l. 133). No liga los módulos de la obra a la orden |
| Fuente de la orden en mobiliario | `al_construction_planner_furniture/wizards/plan_production_wizard.py`, `_production_source` (l. 8-15) | Producto y lista de la tipología (`typology.bom_id`) | Con M110-02 debe tomar la lista de fabricación |
| Generador del plan | `al_construction_planner_furniture/wizards/plan_generate_wizard.py`, l. 280-305 | Materiales de la receta del módulo; si no hay, de la lista del módulo; si no, de `typology.bom_id` | Por eso la lista de la tipología no puede convertirse en la de armado |
| Orden por módulo y departamento (M18-15) | `al_construction_planner_furniture/models/construction_module_product.py`, `action_create_module_productions` (l. 166-205) | Una orden por producto de módulo y departamento, con el lote del departamento | La lista del módulo (`_ensure_product`, l. 73-119) lleva las cuatro etapas y no tiene planta |
| Lote del departamento | Mismo archivo, `_department_lot` (l. 158-164) | Nombre «<nombre de la obra> <nombre del departamento>» | Formato fijo, sin tipología ni módulo (HM-38) |
| Envío de planta a obra (M18-16) | Mismo archivo, `action_ship_modules` (l. 227-275) | Traslado de los módulos de los departamentos con su lote | Toma el primer almacén de la compañía (`search(..., limit=1)`, l. 233) y su tipo interno: no sale de la planta que arma |
| Módulos «Producido» y «En obra» | Mismo archivo, `_post_inventory` (l. 283-290) y `stock.picking._action_done` (l. 299-307) | Solo actualiza los módulos ligados a la orden o al movimiento | La orden del asistente no liga módulos y el despacho nativo no tiene movimientos ligados (HM-39) |
| Lista de la tipología | `al_construction_planner_furniture/wizards/master_import_wizard.py`: `_analyze`, hoja BOM (l. 475-547), y `_sync_bom` (l. 983-1012) | Una lista con las cuatro etapas | Suma las filas por código: `lines[code]['stage'] = lines[code]['stage'] or stage` (l. 531) junta en la primera etapa un producto que está en dos (HM-28). `_sync_bom` busca las líneas actuales por código (l. 1000) |
| Control del plan en la orden | `al_construction_planner_mrp/models/mrp_production.py`: `_construction_plan_lines` (l. 42-51), `_construction_component_qty` (l. 53-65), `_construction_get_excess` (l. 87-101), `action_confirm` (l. 108-140) | Compara los componentes de las etapas de `_production_codes()` con el plan de los ambientes de la orden | Un componente sin etapa, como el paquete, cuenta como «componente que el plan no tiene» (l. 95-96). La orden hija no tiene plan |
| Comparación y exceso (M19-04/05) | `al_construction_planner_approvals_mrp/models/mrp_production.py`, `_construction_versus_values` (l. 89-132) | Presupuesto de todas las etapas de `_production_codes()` (l. 98) | No distingue la etapa de la orden: el corte compararía también lo de armado |
| Informe del planificador (M19-05) | `al_construction_planner_production/models/mrp_production.py`, `_construction_refresh_analysis` (l. 223-260) | Mismo filtro de etapas (l. 232) | Igual que la fila anterior |
| Accesorios de armado (M19-02) | Mismo archivo, `_construction_assembly_plan_lines` (l. 130-138) | Líneas del plan con `stage = 'assembly'` | Código de etapa escrito en el código. Con la orden hija con plan, la de corte también propondría accesorios y avisaría que faltan |
| Saldo del plan | `al_construction_planner/models/construction_plan_supply.py`, `_supply_check` (l. 57-62) | Exceso = pedido − saldo | Con saldo negativo, el exceso sale mayor que lo pedido: 20 − (−20) = 40 (HM-37) |
| Solicitud del requerimiento | `al_construction_planner_approvals/models/construction_material_request.py`, `_construction_approval_info` (l. 46-100) | La columna «Presupuestado» lleva el saldo (l. 74 y 89); el porcentaje es diferencia ÷ presupuestado de las líneas candidatas (l. 75) | Rótulo engañoso y diferencia inflada (HM-37). En la orden de fabricación la misma columna lleva el presupuesto, no el saldo (`approvals_mrp`, l. 273) |
| Rechazo de una solicitud ya aprobada | `al_construction_planner_approvals/models/construction_approval_mixin.py`, `_construction_approval_refused` (l. 201-212) | Si el documento ya no está «En aprobación», no hace nada | La solicitud queda rechazada y el documento sigue aprobado (HM-31) |

### Etapa con su planta (M110-01)

**Lugar:** `al_construction_planner/models/construction_stage.py` y `al_construction_planner/views/construction_stage_views.xml`.

**Campos nuevos en `construction.stage`:**

| Campo | Tipo | Etiqueta | Ayuda |
| --- | --- | --- | --- |
| `production_picking_type_id` | Many2one a `stock.picking.type`, `company_dependent=True`, dominio `[('code', '=', 'mrp_operation')]` | Planta (operación de fabricación) | Dónde se fabrica lo de esta etapa. Vacío: la etapa no tiene orden propia y sus materiales van en la orden de la etapa siguiente |
| `intermediate_categ_id` | Many2one a `product.category`, `company_dependent=True` | Categoría de lo que entrega | Categoría del producto intermedio que sale de esta etapa hacia la siguiente. Sus rutas llevan el material entre plantas |
| `accessory_request` | Boolean | Accesorios a pedido desde la orden | Los materiales de esta etapa se proponen con «Pedir accesorios» en la orden de fabricación (paquete 1.9, M19-02) |

**Método nuevo:** `_production_chain(company)` devuelve, en orden, las etapas con orden propia en la compañía:
- son las hojas de `_production_codes()` (l. 229-235) cuya `production_picking_type_id` en la compañía no está vacía;
- el orden es el de `_tree_sorted()` (l. 116-121).

```python
@api.model
def _production_chain(self, company):
    """Etapas con orden de fabricación propia en la compañía, en el orden del
    árbol (paquete 1.10, M110-01). Vacío: la fabricación de siempre."""
    stages = self.with_context(active_test=False).search([
        ('is_group', '=', False),
        '|', ('kind', '=', 'production'), ('production_consumption', '=', True)])
    stages = stages.with_company(company).filtered('production_picking_type_id')
    return self._tree_sorted(stages)
```

**Vista:** en el formulario de la etapa, un grupo «Fabricación» con los tres campos, visible si la etapa es de fabricación o consume en la orden.

**Migración:** un `post-migrate` de `al_construction_planner` marca `accessory_request = True` en la etapa de código `assembly`, si existe. Así, M19-02 sigue igual en las bases que ya lo usan.

**Configuración de Allcenter, solo datos:**
- «1.1 Producción de piezas»: planta «ALMACEN PUENTE PIEDRA: Manufactura», categoría «02 MATERIA PRIMA PIEZAS / Paquetes de piezas».
- «1.2 Armado»: planta «ALMACEN BREÑA: Manufactura», sin categoría porque es la última etapa, y «Accesorios a pedido desde la orden» marcado.

**Casos borde:**
- Una etapa con planta pero sin «Fabricación» ni «Consume en la orden» no entra en la cadena. La vista oculta el grupo.
- Dos compañías pueden tener cadenas distintas con el mismo catálogo.

**Criterio de aceptación:**
- Con esa configuración, `_production_chain(company)` devuelve [1.1, 1.2].
- Sin planta en 1.1, devuelve [1.2].
- Sin planta en ninguna, devuelve vacío y el importador se comporta como hoy.
- En otra compañía sin configuración, devuelve vacío.

Efecto en Manufactura: una empresa nueva define su cadena de plantas con datos, por ejemplo corte en una planta y pintura en otra.

### Listas de materiales por etapa (M110-02)

**Lugar:** `al_construction_planner_furniture/wizards/master_import_wizard.py`, `al_construction_planner_furniture/models/construction_typology.py` y `construction_module_product.py`.

**Decisión de diseño [P]:**
- La lista de la tipología (`typology.bom_id`) sigue siendo la receta completa, con todas las etapas. La usan el generador del plan (`plan_generate_wizard.py`, l. 304-305), el asistente de órdenes en mobiliario (`plan_production_wizard.py` de furniture, l. 13-14), `_sync_bom` (l. 986) y los datos de demostración (`tools/planner_demo_data.py`, l. 183).
- Las listas de fabricación son registros aparte.
- Para que Odoo use la de fabricación y no la receta, la de fabricación lleva secuencia 1 y la receta secuencia 1000. `_bom_find` elige por secuencia.
- Alternativa si la secuencia no basta: archivar la receta cuando hay cadena. El generador del plan la sigue leyendo por `typology.bom_id`, pero desaparece de la lista de Fabricación. Lo decide Cristóbal.

**Campo nuevo en `construction.typology`:** `production_bom_id`, Many2one a `mrp.bom`, «Lista de fabricación», de solo lectura. Es la lista de la última etapa de la cadena.

**Campo nuevo en `mrp.bom.line`:** `construction_intermediate`, Boolean, «Producto intermedio», de solo lectura. Lo marca el importador en la línea del intermedio.

**1. Corregir la suma de la hoja BOM.**
- En `_analyze` (l. 524-535), la clave de `result['bom'][typology]` pasa de `code` a `(code, stage)`. Un producto en dos etapas queda en dos líneas, como lo trae Oficina Técnica.
- `seen` (l. 526-527) y el aviso `bom_duplicate` (l. 536-540) pasan a contar por `(typology, code, stage)`. Así, el aviso solo sale cuando de verdad se repite una fila.
- Los consumidores de `data['bom']` se ajustan a la clave nueva:
  - el conjunto `codes` de `_apply` (l. 778);
  - el bucle de `unstaged_amount` (l. 541-546);
  - `_sync_bom` (l. 1000), que busca las líneas actuales por `(product_id.default_code, construction_consumption_stage)`.

**2. `_sync_bom` sigue armando la receta** de la tipología, con todas las etapas. Con cadena, le pone secuencia 1000 y el código «Receta (presupuesto)».

**3. Método nuevo `_sync_stage_boms(typology, company)`**, llamado después de `_sync_bom`:
- **Sin cadena** (`_production_chain(company)` vacío): no hace nada.
- **Fuente de cantidades:** los materiales de los módulos de la tipología (`construction.typology.module.material`: `product_id`, `qty`, `uom_id`, `stage`), sumados por producto, unidad y etapa. Cada línea de módulo es un módulo, sin cantidad propia. Si la tipología no tiene módulos con materiales, se usan las líneas de la receta.
- **Etapas sin materiales:** una etapa de la cadena sin materiales en la tipología se salta. Por ejemplo, un closet sin cajonera no tiene armado.
- **Etapas intermedias** (las de la cadena que no se saltaron, menos la última). Cada una lleva un producto intermedio:

  | Dato | Valor |
  | --- | --- |
  | Nombre | «<etapa> · <tipología> · <obra>» |
  | Código | `<prefijo de la obra>-<tipología>-<código de la etapa en mayúsculas>`, con el mismo prefijo que `_module_product_code` (`construction_module_product.py`, l. 50-54) |
  | Tipo | Almacenable, sin lote, sin compra ni venta |
  | Obra | `construction_project_id` = la obra, para que se archive al cerrarla |
  | Categoría | `intermediate_categ_id` de la etapa en la compañía |

  Su lista va en la planta de la etapa, con secuencia 1, los materiales de la etapa y el intermedio de la etapa previa, si existe (con `construction_intermediate = True`).
- **Última etapa no saltada:** una lista nueva del producto de la tipología, que se guarda en `typology.production_bom_id`, en la planta de la etapa, con secuencia 1. Lleva los materiales de la etapa y el intermedio previo.
- **Etapas que no están en `_production_codes()`**, como instalación y acabado: no entran en ninguna lista de fabricación.
- **Proyecto:** el de la obra en todas las listas (`project_id`, campo de `project_mrp`).
- **Al actualizar:** solo reescribe componentes y subproductos. Conserva `operation_ids` y lo demás puesto a mano, como las operaciones y estaciones de dev1. A cada componente le deja `construction_consumption_stage`; al intermedio lo deja sin etapa y con `construction_intermediate`.
- **Idempotente:** volver a importar no duplica productos ni listas. Busca los intermedios por código y la lista final por `typology.production_bom_id`.
- **Permisos:** con `sudo()` y comentario, como `_sync_bom` (l. 868-874).

**4. Subproductos de la lista de fabricación: los productos de módulo.**

Los productos de módulo nacen al aprobar el plan (`_create_module_products`, l. 136-146), después del importador. Por eso los subproductos se escriben en `_construction_on_approve` (l. 123-126), después de `_create_module_products()`, con un método de la tipología, por ejemplo `_sync_module_byproducts()`:
- un subproducto por línea de módulo, cantidad 1, en la lista `production_bom_id`;
- `cost_share` proporcional al costo de material del módulo en las etapas de la cadena: suma de `qty × price_unit_planned` de las líneas del plan del producto, o del `standard_price` si el plan no lo tiene;
- redondeado a dos decimales, con la diferencia a 100 % en el módulo mayor. El producto de la tipología queda con 0 % y sirve de control.
- Si no hay `production_bom_id` (tipología sin cadena), no hace nada.

**5. Lista del producto de módulo (M18-15).** `_ensure_product` (l. 73-119) deja de copiar las cuatro etapas: copia solo las etapas de `_production_codes()`. Con cadena, su lista va en la planta de la última etapa (`picking_type_id`). Así, la orden por módulo queda para reponer un módulo suelto sin pedir materiales de instalación.

La receta real reescribe esa misma lista al confirmarse (`construction_real_recipe.py`, `_update_module_bom`, l. 200-216), con todas sus etapas y sin planta. Debe aplicar el mismo filtro de etapas y conservar el `picking_type_id`.

**Casos borde:**
- Material sin etapa en el módulo: va a la receta, pero no a las listas de fabricación. El importador ya avisa con `bom_no_stage`.
- Tipología con cadena pero sin ningún material de las etapas de la cadena: no se crea lista de fabricación y el asistente usa la receta, como hoy, con un aviso.
- La categoría del intermedio está vacía: se usa la categoría por defecto y se avisa en el resultado del importador.

**Criterio de aceptación, con la configuración de M110-01 y la hoja de Montecarmelo:**
- **C07, lista de corte:** producto intermedio de «1.1» en Puente Piedra, con 11 componentes. El tornillo 4x30 no está.
- **C07, lista de fabricación:** en Breña, con el intermedio y 8 componentes de armado (el tornillo 4x30 con 4 unidades). Después de aprobar el plan, tiene 13 subproductos que suman 100 %.
- **C07, receta:** sigue con todas las etapas y secuencia 1000. El tornillo 4x30 aparece dos veces, con 4 en armado y 54 en instalación.
- **Closet sin materiales de armado:** su lista de fabricación es la de corte, en Puente Piedra, sin intermedio.
- **Volver a importar:** no duplica nada y conserva las operaciones de las listas.
- **Generar el plan otra vez:** da los mismos materiales que antes del cambio.
- **Sin planta en ninguna etapa:** la receta de hoy, sin listas nuevas, y las pruebas actuales siguen pasando.

Efecto en Manufactura: es la estructura que se probó a mano en dev1, generada por datos. Cuando esté la carga del despiece (M19-01), las piezas (`construction.typology.piece`) saldrán como subproductos de la lista de corte.

### Asistente de órdenes sin planta impuesta (M110-03)

**Lugar:** `al_construction_planner_mrp/wizards/plan_production_wizard.py`, su vista `plan_production_wizard_views.xml`, y `al_construction_planner_furniture/wizards/plan_production_wizard.py`.

- **Campo «Planta»** (`picking_type_id`, l. 24-28): deja de ser obligatorio y no tiene valor por defecto. La etiqueta pasa a «Forzar planta», con la ayuda «Vacío: cada orden se crea en la planta de su lista de materiales».
- **En `action_create` (l. 128-142):** si el campo está vacío, se usa `bom.picking_type_id`. Si la lista no tiene planta, se usa el tipo de fabricación por defecto de la compañía, como hoy.
- **Fuente en mobiliario:** `_production_source` (furniture, l. 8-15) devuelve `typology.production_bom_id or typology.bom_id`.
- **Módulos de la orden:** cada orden lleva `construction_module_task_ids`, que son las tareas de nivel módulo bajo los ambientes de la línea:

  ```python
  Task.search([('construction_space_task_id', 'in', line.space_task_ids.ids),
               ('construction_level', '=', 'module')])
  ```

  Así, `_post_inventory` (`construction_module_product.py`, l. 283-290) pasa esos módulos a «Producido» al cerrar la orden.
- **Vista previa:** una columna «Planta», con la planta de la lista de cada línea.

**Casos borde:**
- **Autorización de la receta real.** Al ligar los módulos, la orden del asistente activa el bloqueo de la receta real (`construction_real_recipe.py`, `MrpProduction.action_confirm`, l. 313-325). Con el motor «Aplicación Aprobaciones» ese bloqueo se omite (`approvals_mrp`, l. 185-187). Con el motor de política, un solo módulo sobre el umbral bloquearía la orden de toda la tipología y el piso. Propuesta [P]: mantener el bloqueo y que el mensaje nombre el módulo y su departamento, para que la jefatura lo autorice sin rehacer la orden. Lo confirma Cristóbal.
- Orden con entrega parcial: Odoo hace una orden pendiente (backorder). Los módulos pasan a «Producido» con la primera orden cerrada. Se acepta por ahora [P]. El estado por lote queda para cuando el lote sea automático.

**Criterio de aceptación:**
- Una sola corrida del piso 3 sin forzar planta crea las órdenes de las cocinas en Breña. Al confirmarlas, Odoo crea sus órdenes de corte en Puente Piedra.
- El closet sin cajonera CL01B sale directo en Puente Piedra, en la misma corrida.
- Al cerrar el armado del 302, sus módulos quedan «Producido».
- Con «Forzar planta» lleno, todas las órdenes van a esa planta, como hoy.

Efecto en Manufactura: las órdenes nacen en la planta y la estación que dice la configuración, sin elegirlas.

### Orden hija con el plan y exceso por etapa (M110-04)

**1. Herencia del plan por el grupo de fabricación.** En Odoo 19 cada orden tiene su grupo de fabricación (`mrp.production.group`, creado en `mrp_production.py`, l. 1090-1091). El componente de la madre lleva ese grupo a los valores de abastecimiento (`mrp/models/stock_move.py`, `_prepare_procurement_values`, l. 656-660), y la regla lo pasa a los movimientos del traslado (`mrp/models/stock_rule.py`, `_get_stock_move_values`, l. 124-127). Así llega hasta la regla de fabricación de la planta de corte.

En `al_construction_planner_mrp`, `stock.rule._prepare_mo_vals`:
- lee `values.get('production_group_id')`;
- busca la madre con `self.env['mrp.production.group'].browse(id).production_ids`, filtrada a las que tienen plan;
- si hay una sola, pone en la hija `construction_plan_id` y `construction_space_task_ids` de la madre;
- no hereda `construction_module_task_ids`, porque los módulos se producen en la última etapa.

No usar el enlace madre-hija nativo (`parent_ids`, `_get_sources()`): Odoo lo escribe en `_post_run_manufacture`, después de confirmar la hija (`stock_rule.py`, l. 120-121).

**2. Confirmación automática de la hija.** Odoo crea la hija y la confirma en `stock.rule._run_manufacture` (`mrp/models/stock_rule.py`, l. 119-121). En ese momento no hay usuario frente a la pantalla.
- `_run_manufacture` se hereda para llamar a `super()` con el contexto `construction_from_procurement=True`.
- En `action_confirm` de `al_construction_planner_mrp` (l. 108-140), con ese contexto no se devuelve el asistente de la política de exceso:
  - si la política es «bloquear», la hija queda «excede» y se publica el aviso en la hija y en la madre, sin error, porque un error cancelaría la confirmación de la madre;
  - si la política es otra, la hija se confirma y queda «excede» con su aviso.
- Con el motor «Aplicación Aprobaciones», `al_construction_planner_approvals_mrp` ya confirma con `construction_exceed_checked=True` (l. 185-187). Solo hay que comprobar que la hija pase por ahí y quede con su comparación.

**3. Etapas de cada orden.** Método nuevo en `mrp.production`: `_construction_order_stages()`.
- Devuelve las etapas presentes en `bom_id.bom_line_ids.construction_consumption_stage` que están en `_production_codes()`.
- Si la lista no tiene ninguna línea con etapa, como las listas planas de hoy, devuelve `_production_codes()`: compatibilidad.

**4. Usar esas etapas en lugar de `_production_codes()` en los cinco lugares:**
- `al_construction_planner_mrp/models/mrp_production.py`, l. 49 y l. 59;
- `al_construction_planner_approvals_mrp/models/mrp_production.py`, l. 98;
- `al_construction_planner_production/models/mrp_production.py`, l. 232;
- `al_construction_planner_production/models/mrp_production.py`, l. 137. Aquí `('stage', '=', 'assembly')` pasa a ser las etapas de la orden con `accessory_request`, de M110-01. Si la orden no tiene ninguna, no se proponen accesorios y no se avisa que faltan (`_construction_notify_missing_accessories`).

**5. Excluir el intermedio.** Un componente es intermedio cuando:
- su línea de lista tiene `construction_intermediate = True`; o
- su línea no tiene etapa y su producto tiene lista de materiales en la compañía. Esto cubre las listas armadas a mano.

El intermedio no entra en `_construction_component_qty`, en la comparación, en el exceso ni en las asignaciones del plan.

**6. Asignaciones.** Las de la hija (`_construction_sync_allocations`, l. 67-85) se crean al confirmarla. Eso pasa dentro de la confirmación de la madre, así que no hace falta otro paso. Las líneas del plan de «1.1» quedan asignadas a la hija y las de «1.2» a la madre.

**Casos borde:**
- **Dos órdenes de armado de la misma tipología en pisos distintos, confirmadas juntas.** Odoo no junta sus hijas, porque `_make_mo_get_domain` (l. 148-169) también filtra por el grupo de la madre (l. 159-160) y cada orden tiene el suyo. Una prueba lo deja comprobado.
- Cancelar la madre cancela la hija si la regla tiene `propagate_cancel`. Si no, la hija queda con su plan y sus asignaciones: hay que revisarlo en la prueba.

**Criterio de aceptación, al confirmar el armado de C07 del piso 3:**
- La orden de corte que crea Odoo tiene el plan y los ambientes de la madre.
- Su «Presupuestado frente a real» muestra solo planchas y tapacanto, contra lo presupuestado de «1.1».
- El armado muestra solo lo de «1.2» y no marca el paquete como cambio de material.
- «Pedir accesorios» aparece en el armado y no en el corte.
- El exceso aprobado en una orden no afecta a la otra.
- Con la política «bloquear», la confirmación de la madre no falla por el exceso de la hija.

Efecto en Manufactura: el exceso queda en la etapa y la estación donde ocurre. El de tableros podrá separarse después en pieza, merma y retazo.

### Despacho a obra por departamento (M110-05)

Decisión de Vicente del 19-oct-2026: el despacho nativo lleva el departamento, y al validarlo los módulos de ese departamento pasan a «En obra» (HM-39).

**Lugar:** `al_construction_planner_furniture/models/construction_module_product.py`, clases `StockPicking` (l. 292-307) y `ConstructionResourcePlan`, más una vista heredada del formulario de transferencia.

**1. Tipo de operación.** Campo nuevo en `stock.picking.type`: `construction_site_dispatch`, Boolean, «Despacho a obra por unidad». Ayuda: «Las transferencias de este tipo llevan obra y departamento, y al validarlas los módulos del departamento pasan a "En obra"». Solo para tipos internos o de salida.

**2. Transferencia** (`stock.picking`):
- Ya existe `construction_project_id` (l. 295-297).
- Campo nuevo: `construction_apartment_task_id`, Many2one a `project.task`, «Departamento». Dominio: `[('project_id', '=', construction_project_id), ('construction_level', '=', 'apartment')]`.
- Los dos se ven y son obligatorios para validar si el tipo tiene `construction_site_dispatch`.
- La obra se propone sola desde la ubicación de destino. Es la obra cuya `construction_location_id` es la ubicación de destino o una ubicación madre de ella.
- `construction_location_id` y `construction_code` vienen de `al_construction_material_request`, que no es dependencia de `al_construction_planner_furniture` (su manifiesto solo depende de `al_construction_planner_mrp`). Antes de usarlos hay que comprobar que el campo existe, como ya hace el código en las l. 53 y 215. Sin el campo, la obra se elige a mano.

**3. Al confirmar o reservar:** reciben `construction_shipment_picking_id` = la transferencia los módulos del departamento cuyo producto está en ella, hasta la cantidad de cada producto. Quedan fuera los que ya tienen una transferencia hecha. Su «Estado del envío» pasa a «En tránsito», por el cálculo que ya existe (`_compute_construction_shipment_state`, l. 338-353).

**4. Al validar** (`_action_done`, l. 299-307, extendido):
- Para cada movimiento hecho de un producto de módulo de la obra (`product.construction_project_id` = la obra), los módulos son las tareas del departamento cuyo módulo de tipología tiene ese producto.
- Se toman tantas tareas como unidades hechas, de menor a mayor id, sin las que ya están «Instalado» o «Entregado».
- Esas tareas pasan a «En obra» y quedan con la transferencia.
- A los módulos ligados en el paso 3 que no salieron en lo hecho se les quita el enlace. Si no, el cálculo del estado los mostraría «En obra», porque mira el estado de la transferencia (l. 345).
- Si faltan módulos del departamento, un mensaje en la transferencia los nombra («No se despacharon: …»). No es error, porque el despacho puede ser parcial.

**5. Lote:** si está M110-09, la transferencia propone en cada línea el lote del departamento y avisa si el lote elegido no corresponde [P].

**6. Envío del planificador** (`action_ship_modules`, l. 227-275), que se mantiene para quien lo use:
- Usa el tipo de operación de un ajuste nuevo por compañía, «Tipo de operación del envío a obra», en lugar del primer almacén (l. 231-234). Su ubicación de origen es la del tipo.
- Si se envía un solo departamento, llena `construction_apartment_task_id`.
- Sin el ajuste, funciona como hoy.

**Trazabilidad que queda en el planificador:**
- **En cada módulo:** «Envío a obra» con el enlace a la transferencia, «Estado del envío» y «Recibido en obra» con la fecha.
- **En cada transferencia:** la obra y el departamento.
- **En el árbol del plan:** el avance de despacho por departamento y por piso, con los estados de sus módulos.
- **En el lote:** la orden que lo produjo y la transferencia que lo llevó (trazabilidad nativa).

**Configuración de Allcenter:** marcar «Despacho a obra por unidad» en «Despacho a obra» de Breña (BRE/DO) y en el tipo que se use desde Puente Piedra para los closets sin armado (HM-36).

**Criterio de aceptación:**
- El despacho del Dpto 302 con el tipo BRE/DO no se valida sin obra y departamento.
- Al reservarlo, los módulos del 302 que van en él quedan «En tránsito».
- Al validarlo, quedan «En obra», con la transferencia y la fecha.
- Si falta un módulo, la transferencia lo nombra y ese módulo sigue «Producido».
- Una transferencia interna sin la marca no cambia nada.

Efecto en Manufactura: el despacho sale de la planta que arma, con el lote del departamento y su guía, y deja el avance por departamento en el planificador.

### Motivo obligatorio en la orden de posventa (M110-06)

Decisión de Vicente del 18-oct-2026: las órdenes de posventa, garantía y reposición urgente llevan motivo obligatorio, elegido de una lista configurable. Lo pedía también la propuesta de almacenes del 20-set (decisión 12).

Lo nativo no lo cubre: la orden de fabricación de Odoo 19 no tiene motivo, solo el texto libre «Origen» [C]. El modelo analítico del proyecto separa dos casos que hoy son órdenes idénticas:
- **Reproceso:** falla, deterioro o pérdida. Etapa analítica «Reproceso».
- **Reemplazo pedido por el cliente:** con adicional facturable. Etapa analítica «Armado».

**Lugar:** `al_construction_planner_mrp`.

**Modelo nuevo `construction.production.reason`** («Motivo de fabricación»):

| Campo | Tipo | Nota |
| --- | --- | --- |
| `name` | Char, obligatorio, traducible | |
| `code` | Char | |
| `active` | Boolean | |
| `company_id` | Many2one a `res.company` | Vacío: todas |
| `analytic_account_id` | Many2one a `account.analytic.account` | «Etapa analítica». Dominio: el plan analítico de etapa de la compañía, si el puente analítico lo tiene configurado [P] |
| `generates_additional` | Boolean | «Genera adicional al cliente» |

- **Seguridad** (`security/ir.model.access.csv`): lectura para `mrp.group_mrp_user`; creación, edición y borrado para `mrp.group_mrp_manager`.
- **Menú:** Fabricación › Configuración › Motivos de fabricación.
- **Datos:** el módulo no trae motivos de Allcenter. La lista de abajo se carga como configuración.

**En el tipo de operación** (`stock.picking.type`, solo los de fabricación): casilla `construction_reason_required`, «Pide motivo».

**En la orden de fabricación:**
- `construction_reason_id`: Many2one al modelo nuevo. Visible si el tipo pide motivo y obligatorio al confirmar.
- `construction_reason_note`: Text, «Detalle del motivo».
- Obra opcional, con el `project_id` nativo, para cargar el costo a la obra que se repone.
- **Al confirmar sin motivo:** error «Esta operación pide motivo».
- **Búsqueda:** filtro y agrupación por motivo.

**Datos iniciales propuestos [P], para revisar con Producción:**
- Falla de fabricación (Reproceso);
- Daño en el transporte (Reproceso);
- Daño en obra por terceros (Reproceso);
- Pérdida (Reproceso);
- Cambio pedido por el cliente (Armado, genera adicional);
- Garantía de posventa (Reproceso).

**Configuración de Allcenter:** marcar «Pide motivo» en «Producción de piezas · posventa» (BRE/PV).

**Criterio de aceptación:**
- Una orden BRE/PV no se confirma sin motivo.
- Con «Cambio pedido por el cliente», el filtro por motivo la separa de las de reproceso.
- Las órdenes de «ALMACEN BREÑA: Manufactura» no piden motivo.
- Un usuario de Fabricación sin ser responsable no puede crear motivos.

Efecto en Manufactura: el costo de no calidad sale por obra y por motivo, como pide el modelo analítico. La estación de Castrovirreyna registra sus tiempos por orden.

### Lista de aprobaciones con los datos para decidir y aprobación en bloque (M110-07)

Pedido de Vicente del 19-oct-2026, al ver las 12 solicitudes de armado de la prueba. La lista nativa «Solicitud de aprobación» (`approvals.approval_request_view_tree`, vista 1660 en dev1) solo muestra asunto, propietario, categoría, fechas y estado. Para decidir hay que abrir cada solicitud, y no se puede aprobar en bloque.

**Restricción:** no usar Odoo Studio ni vistas creadas en la base. Por indicación de Cristóbal, todo va en el código del módulo, para no chocar con los desarrollos ni con las localizaciones.

**Lugar:** `al_construction_planner_approvals`, en `models/approval_request.py`, `views/approval_request_views.xml` y `wizards/approval_refuse_wizard.py`.

**Lo que ya existe [C]:**
- **En la solicitud:** `construction_origin_name`, `construction_project_id`, `construction_amount` (exceso en soles) y `construction_todo` (tramo y aprobadores, sin guardar).
- **En las líneas** (`approval.product.line`): `construction_change_type`, `construction_qty_budget`, `construction_qty_diff`, `construction_diff_pct` y `construction_amount_diff`.
- **Aprobar varias:** `action_approve` (l. 227-242) ya acepta varias solicitudes. Para cada una toma los aprobadores del tramo activo que son el usuario actual (`_construction_active_approvers`, l. 109-117), y solo da error si no le toca en ninguna.
- **Estados de los tramos:** `_construction_sync_steps` deja «Por aprobar» solo a quien tiene el tramo activo y «En espera» a los demás. Con eso basta para el filtro «Me toca aprobar».

**1. Campos nuevos en `approval.request`.** Son calculados, se guardan, y dependen de `product_line_ids.construction_change_type`, `product_line_ids.construction_diff_pct` y `product_line_ids.construction_qty_diff`.
- `construction_excess_pct` («Exceso %»): el mayor `construction_diff_pct` de las líneas.
- `construction_change_summary` («En el plan»), de tipo selección:
  - «Cantidad» si todas las líneas son cambio de cantidad;
  - «Fuera del plan» si todas son de material;
  - «Ambos» si hay de los dos.
- `construction_excess_lines` («Materiales con exceso»): número de líneas.
- `construction_excess_qty_label` («Exceso (cantidad)»):
  - con una sola línea, la cantidad con su unidad, por ejemplo «20 Unidades»;
  - con varias, «N materiales», porque no se suman unidades distintas.

**2. Vista de lista** que hereda `approvals.approval_request_view_tree`. Columnas después de `name`, en este orden:
1. documento de origen;
2. obra;
3. «En el plan»;
4. exceso %;
5. exceso en cantidad;
6. exceso en soles, con el grupo «Planificación de obra: ve montos» (`al_construction_planner.group_planner_amounts`). Quien no lo tiene, como el jefe de producción, no ve el monto (decisión del 18-oct);
7. por aprobar (`construction_todo`, solo para mostrar).

Además:
- **Decoración:** en rojo las filas «Fuera del plan» o «Ambos».
- **Búsqueda** (hereda la vista de búsqueda del módulo):
  - filtro «Me toca aprobar»: `[('approver_ids.user_id', '=', uid), ('approver_ids.status', '=', 'pending')]`;
  - filtros «Fuera del plan» y «Exceso mayor a 10 %» (el 10 % es un valor de ejemplo);
  - agrupar por obra y por documento de origen.

**3. Aprobar y rechazar en bloque.**
- **Aprobar:** una acción de servidor en el XML del módulo, «Aprobar», con `binding_model_id` = `approval.request`, `binding_view_types` = `list` y el grupo de usuario de Aprobaciones. Llama a un método nuevo, `action_construction_bulk_approve()`:
  - separa las solicitudes en las que el usuario no tiene el tramo activo; esas no se tocan;
  - aprueba las demás con `action_approve()`;
  - devuelve una notificación con las aprobadas y las que no le tocaban («No le toca aprobar: …»).
- **Rechazar:** el asistente `construction.approval.refuse.wizard` pasa de `approval_id` (Many2one) a `approval_ids` (Many2many). Pide un solo motivo para todas, y se ofrece también como acción de la lista. Las solicitudes en las que el usuario no tiene el tramo activo se omiten con el mismo aviso.
- **Force Approval:** la acción nativa (607) sigue igual, para el grupo «Aprobaciones / Oficial: aprobar todas las solicitudes».

**Criterio de aceptación, con las 12 solicitudes de armado del piso 3:**
- **Lo que ve Annabelees:** cada fila con su orden de fabricación, la obra, «Fuera del plan» (por el paquete, mientras no esté M110-04), el exceso % y «N materiales».
- **Aprobar en bloque:** selecciona las 12 y pulsa Acciones › «Aprobar». Las 12 quedan aprobadas y las órdenes liberadas.
- **Usuario sin tramo:** si hace lo mismo, el aviso lista las 12 y no aprueba ninguna.
- **Rechazar en bloque:** con un motivo, las 12 quedan rechazadas y cada orden recibe el motivo en su historial.
- **Jefe de producción:** no ve la columna de soles.

Efecto en Manufactura: el jefe de producción y la jefatura liberan en un paso las órdenes de un piso, sin perder el control por tramos.

### Cifras de la solicitud y rechazo después de aprobar (M110-08)

Decisión de Vicente del 19-oct-2026: entra en este paquete (HM-37 y HM-31).

**Qué pasó [V]:**
- RQO/2026/00007 pidió 20 tornillos 5x60.
- La solicitud mostró «Presupuestado −20», diferencia 40 y 1,000 %.
- El −20 es el saldo de las líneas del plan del nivel: lo presupuestado menos lo ya pedido por RQO/2026/00004 y RQO/2026/00005.
- RQO/2026/00005 se aprobó y después se rechazó su solicitud, pero siguió aprobado (HM-31). Por eso sigue restando.
- La diferencia de 40 sale de `_supply_check`: pedido menos saldo, 20 − (−20).
- El 1,000 % es 40 ÷ 4: las líneas candidatas del nivel suman 4 presupuestados (deducido de la fórmula de la l. 75, no leído en la base).

**1. Exceso que se muestra.** El control no cambia: `_supply_check` (`al_construction_planner/models/construction_plan_supply.py`, l. 57-62) sigue devolviendo pedido menos saldo, y sus llamadas lo siguen comparando con la tolerancia. Las llamadas son `al_construction_planner_mrp/models/mrp_production.py` (l. 98) y `al_construction_planner_purchase/models/construction_material_request.py` (l. 258 y l. 323). Así, un plan ya pasado sigue marcando cualquier pedido nuevo.

Lo que cambia es la cifra que va a la solicitud: el exceso que se muestra es `min(pedido, pedido − saldo)`. Con saldo negativo, todo lo pedido es exceso, pero nunca más que lo pedido.

Ejemplo: saldo −20, tolerancia 5 y pedido de 3. Hoy el control da 23, que supera 5, y lo marca. Con este cambio lo sigue marcando, y la solicitud muestra exceso 3.

El pedido de accesorios no usa `_supply_check`: calcula su saldo en `al_construction_planner_production/models/mrp_production.py` (l. 98-107) y la diferencia en `construction_accessory_request.py` (l. 149). Se le aplica la misma regla de cifra.

**2. Columnas de la línea de la solicitud** (`approval.product.line`):

| Campo | Etiqueta | Qué lleva |
| --- | --- | --- |
| `construction_qty_planned` (nuevo) | Presupuestado | Lo presupuestado de las líneas del plan que cubre la línea |
| `construction_qty_requested_before` (nuevo) | Ya pedido | Lo pedido por otros documentos sobre esas líneas |
| `construction_qty_budget` (se cambia la etiqueta) | Saldo | Presupuestado menos ya pedido; puede ser negativo |
| `quantity` (nativo) | Pedido | Lo que pide este documento |
| `construction_qty_diff` (se cambia la etiqueta) | Exceso | Pedido menos el saldo positivo |
| `construction_diff_pct` | Exceso % | Exceso ÷ presupuestado × 100; 100 % si está fuera del plan |

**3. Quién llena las columnas:**
- **Requerimiento:** `_construction_approval_info` de `construction_material_request.py` (l. 46-100) las llena todas.
- **Orden de fabricación:** `approvals_mrp`, l. 252-279. Llena «Presupuestado» con `qty_budget` de la comparación, «Pedido» con lo requerido y el exceso. «Ya pedido» y «Saldo» quedan vacíos, porque la orden se compara con lo presupuestado de sus ambientes y no con un saldo.
- **Pedido de accesorios:** `al_construction_planner_production/models/construction_accessory_request.py`, `_construction_approval_info` (l. 128) las llena como el requerimiento.

**4. Rechazo después de aprobar:**
- **En `approval.request`:** `action_refuse`, `action_withdraw` y `action_cancel` (l. 244-257) dan error si la solicitud es de obra, su `construction_notified_status` es «approved» y el documento de origen ya no está esperando la aprobación. Por ejemplo, un requerimiento que ya no está «En aprobación», o una orden con el exceso aprobado.
- **El mismo control en `approval.approver.write`**, cuando el estado pasa a rechazado. Así se cubre el cambio desde la lista de aprobadores del formulario. El control no aplica a lo que escribe el propio sistema: `_construction_sync_steps` cancela los aprobadores que quedan (`approval_request.py`, l. 149). Esa llamada debe pasar un contexto, por ejemplo `construction_sync_steps=True`, que el control respete.
- **Mensaje:** «El documento %s ya siguió con la aprobación. Para revertirla, devuélvalo a borrador o anúlelo desde el documento.»

**Criterio de aceptación:**
- Con 4 presupuestados y 24 ya pedidos, un pedido de 20 muestra: presupuestado 4, ya pedido 24, saldo −20, pedido 20, exceso 20 y exceso % 500.
- Con saldo 10, un pedido de 15 muestra exceso 5, como hoy.
- Con saldo −20 y tolerancia 5, un pedido de 3 se sigue marcando y la solicitud muestra exceso 3.
- Una solicitud aprobada cuyo requerimiento ya está aprobado no se puede rechazar desde Aprobaciones. El mensaje lleva al documento.
- Una solicitud pendiente se sigue rechazando como hoy.

Efecto en Manufactura: el jefe de producción y Oficina Técnica ven el exceso real de cada orden y pedido. Una decisión revertida en Aprobaciones no deja documentos aprobados que siguen consumiendo saldo.

### Formato del lote del módulo (M110-09)

Decisión de Vicente del 19-oct-2026: el formato del lote se configura (HM-38). El 18-oct quedó que el lote del armado se escribe al producir. Este ajuste no cambia eso: lo usan la orden por módulo (reposición), el envío del planificador y la propuesta de lote del despacho (M110-05).

**Lugar:** `al_construction_planner_furniture`: `res.company`, `res.config.settings` y `_department_lot` (`construction_module_product.py`, l. 158-164).

**Ajuste por compañía:** `construction_module_lot_pattern`, Char, «Formato del lote del módulo». Por defecto `{obra_nombre} {unidad}`, que es el formato de hoy.

**Claves del formato:**

| Clave | Valor | Ejemplo en dev1 |
| --- | --- | --- |
| `{obra}` | `project.construction_code` o, si no existe el campo o está vacío, el nombre | ZZMONTEC-40-26 |
| `{obra_prefijo}` | El código de la obra hasta el primer guion | ZZMONTEC |
| `{obra_nombre}` | El nombre del proyecto | ZZMONTEC-40-26 MONTECARMELO PRUEBA |
| `{unidad}` | El nombre del departamento | Dpto 301 |
| `{unidad_num}` | Los dígitos del nombre del departamento, con ceros a la izquierda hasta 4 | 0301 |
| `{tipologia}` | El código de la tipología | CL02 |
| `{modulo}` | El código del módulo | MCL01 |

**Método:** `_department_lot(product, apartment)` pasa a `_module_lot(product, apartment)`. Se deja un alias para no romper llamadas. La tipología y el módulo salen del módulo de tipología cuyo `product_id` es el producto.

**Validación:** al guardar el ajuste, una clave desconocida da error y nombra las claves válidas.

**Configuración de Allcenter:** `{obra_prefijo}-{unidad_num}-{tipologia}-{modulo}`, que da MONTEC-0301-CL02-MCL01 en la obra real y ZZMONTEC-0301-CL02-MCL01 en la de prueba.

**Casos borde:**
- Dos closets iguales en el mismo departamento (la misma tipología dos veces) comparten lote. Es correcto: es el mismo producto en la misma unidad.
- Departamento sin dígitos en el nombre: `{unidad_num}` queda vacío y se avisa.

**Criterio de aceptación:**
- Con el formato de Allcenter, la orden por módulo del CL02 del 301 lleva el lote MONTEC-0301-CL02-MCL01.
- CL01A y CL03 del mismo departamento llevan lotes distintos.
- Sin ajuste, el lote es el de hoy.

Efecto en Manufactura: la etiqueta del módulo dice obra, departamento, tipología y posición, y el despacho puede comprobar que cada lote va a su departamento.

### Pruebas automatizadas

**Archivo propuesto:** `al_construction_planner_suite/tests/test_stage_chain_v110.py`.

**Escenario:** la obra de `PlannerCommon` con dos almacenes de prueba, cada uno con su tipo «Manufactura», y dos etapas de fabricación configuradas.

**Casos:**
1. `_production_chain()` sin plantas, con una, con dos y en una segunda compañía sin configuración.
2. **Importador con cadena:**
   - receta completa con secuencia 1000;
   - dos listas encadenadas con secuencia 1;
   - un producto en dos etapas queda en dos líneas;
   - la etapa de campo queda fuera de las listas de fabricación;
   - al reimportar no se duplica nada y se conservan las operaciones.
3. **Importador sin cadena:** la receta de hoy, sin listas nuevas.
4. **Generar el plan** con y sin cadena: los mismos materiales.
5. **Aprobar el plan:** subproductos de módulo con participación que suma 100 %.
6. **Asistente sin forzar planta:**
   - cada orden en la planta de su lista;
   - las tareas de módulo quedan ligadas;
   - al confirmar, la hija hereda el plan, los ambientes y el proyecto.
7. **Confirmación de la hija con la política «bloquear»:** la madre se confirma y la hija queda «excede».
8. **Dos madres de la misma tipología confirmadas juntas:** las hijas no se juntan, y cada una lleva el plan y los ambientes de su madre.
9. **Comparación por etapa:**
   - el intermedio no es cambio de material;
   - el exceso queda en su orden;
   - los accesorios solo en la orden de la etapa con `accessory_request`.
10. **Despacho con departamento:**
    - no se valida sin departamento;
    - «En tránsito» al reservar;
    - «En obra» al validar;
    - en un despacho parcial, el módulo que no salió sigue «Producido» y sin enlace;
    - aviso de módulos faltantes.
11. **Orden de posventa:** sin motivo da error; con motivo se confirma.
12. **Lista de aprobaciones:**
    - campos de resumen con una línea de cantidad, una de material y las dos;
    - aprobar y rechazar en bloque, con y sin tramo;
    - columna de soles oculta sin «ve montos».
13. **Saldo negativo:** el pedido se sigue marcando y la solicitud muestra como exceso lo pedido. Rechazo de una solicitud aprobada con el documento ya aprobado: error. Los aprobadores cancelados por el sistema no disparan el error.
14. **Formato del lote:** con y sin ajuste; clave desconocida da error.
15. **Las pruebas actuales siguen pasando**, en especial:
    - `test_production_order_v19.py`;
    - `test_production_excess_v19.py`;
    - `test_approvals_v19.py`;
    - `test_module_product_v18.py`;
    - `test_import.py`;
    - `test_generate.py`;
    - `test_supply.py`;
    - `test_furniture_v18.py`, por la receta real.

### Puesta en marcha

1. Publicar en dev1 y correr la suite. Antes, poner al día `al_construction_planner_production` en dev1 (2.20261017 → 3.20261018).
2. **Configurar:**
   - planta y categoría de «1.1» y «1.2», y «Accesorios a pedido desde la orden» en «1.2» (M110-01);
   - «Despacho a obra por unidad» en BRE/DO (M110-05);
   - «Pide motivo» en BRE/PV y la lista de motivos (M110-06);
   - el formato del lote (M110-09).
3. **Volver a enviar la hoja de Montecarmelo al planificador:**
   - la lista de la tipología vuelve a ser la receta completa;
   - las listas de fabricación salen del importador;
   - los paquetes hechos a mano (ZZMONTEC-40-26-<tipología>-PAQ) y sus listas se archivan;
   - antes, revisar que no queden órdenes abiertas con esas listas.
4. **Ordenar la prueba:** cancelar o cerrar las órdenes de prueba que siguen abiertas, como PPD/MO/00002. No se canceló porque tiene abierto el pedido de accesorios ACC/2026/00001.
5. **Repetir la prueba E-03 del caso de Montecarmelo:** crear las órdenes del piso 3 en una corrida, confirmar, producir, trasladar, despachar por departamento y aprobar en bloque.

## Lo que no se desarrolla

- **Etapa de cada material:** ya existe. La pone Oficina Técnica en la columna «Etapa de consumo» de la hoja de trabajo, y el importador avisa si falta.
- **Pedido por etapa:** el requerimiento de obra por sub etapa y «Pedir accesorios» ya funcionan.
- **Closets:** la cajonera y el cuerpo son dos módulos de la tipología, con su etapa en cada material. Es dato de Oficina Técnica.
- **Agrupación de órdenes:** el asistente del plan ya agrupa por piso. Sale una orden por tipología y piso.
- **Plantas, estaciones y operaciones:** son nativas de Odoo y ya están configuradas.
- **Posventa y urgencias en Breña:** orden de fabricación nativa con el tipo «Producción de piezas · posventa» y la estación de Breña. Solo se agrega el motivo (M110-06).
- **Lote del armado:** por ahora se escribe al producir (decisión del 18-oct). La propuesta automática de lote en la orden de armado queda como mejora posterior y puede usar el formato de M110-09.
- **Closet sin armado (HM-36):** es configuración. Hay dos caminos: la ruta de abastecimiento a Breña en la categoría de los productos de tipología, o el despacho desde Puente Piedra con un tipo marcado «Despacho a obra por unidad».

**Fuera de este paquete, hallazgos de la misma prueba que van por otro lado:**
- «Asignar contrata» sin etapa toma todas las etapas, y cancelar la orden de compra no libera la contrata (HM-29).
- Validar avances pide permisos de Nómina (HM-30).
- La semana de la cuadrilla corre el turno al inicio de la semana de la obra (HM-26).
- **Liquidación de contrata:** la cuenta de retención y el aprobador (Harry Alvarado, gerente de Administración y Finanzas) son configuración, no desarrollo.

## Decisiones tomadas

Por Vicente el 18-oct-2026:

- **Plantas:** las piezas se producen en Puente Piedra y se envían a Breña. El armado se hace en Breña y sus módulos se despachan a la obra.
- **Odoo nativo primero:** usar la fabricación nativa y desarrollar lo mínimo.
- **Órdenes:** una orden de corte y una de armado por tipología y piso.
- **Costo del armado:** se reparte entre los módulos según su costo de material del plan. La «cocina armada» queda en cero.
- **Despacho:** por departamento.
- **Cajoneras de closet:** se arman en Breña, como regla general. El cuerpo, las puertas y los forros se arman en obra.
- **Desarrollos configurables:** los desarrollos propios deben ser configuración genérica para cualquier empresa de manufactura.
- **Montos:** el jefe de producción ve el exceso en porcentaje y no en monto. Ya funciona así.
- **Plantas y estaciones:**
  - Puente Piedra tiene la estación «Producción de piezas».
  - Breña tiene dos sedes de armado: Azcona y el 2.º piso de Castrovirreyna.
  - La «Producción de piezas» de Breña, para posventa, garantías y reposiciones urgentes, está en el 1.er piso de Castrovirreyna.
- **Orden por módulo y departamento (M18-15):** queda solo para reponer un módulo suelto.
- **Posventa y urgencias:** llevan motivo obligatorio, elegido de una lista configurable (M110-06).
- **Listas por obra:** las arma el importador, por etapa.

Por Vicente el 19-oct-2026:

- **Lote:** obra-departamento-tipología-módulo, por ejemplo MONTEC-0301-CL02-MCL01. Con obra-departamento-módulo, los closets de un mismo departamento repetían el lote (HM-38). El armado lo escribe al producir. El formato se configura (M110-09).
- **Sin Odoo Studio:** no se usa Studio ni vistas creadas en la base, por indicación de Cristóbal.
- **Despacho con departamento:** el despacho nativo lleva obra y departamento, y actualiza los módulos (M110-05).
- **Cifras y rechazo tardío:** HM-37 y HM-31 entran en este paquete (M110-08).

## Decisiones abiertas

- [ ] **Identidad de la pieza dentro del paquete** (decisión D-M1 del flujo de manufactura del 23-set), para cuando esté la carga del despiece (M19-01).
- [ ] **Guía de remisión** del traslado y del despacho (H-32): con Ximena.
- [ ] **Estaciones por máquina:** seccionadora, canteadora, ranuradora y perforadora. Vicente entrega la lista.
- [ ] **Base del exceso:** por material o por total de la orden. El ajuste ya existe; Vicente lo verá después.
- [ ] **Cajoneras de closet:** en el seguimiento de Montecarmelo las arma la contrata en obra («ARMADO CAJONERA CON CAJONES», S/ 15). Vicente decidió el 18-oct que la regla es armarlas en Breña. Oficina Técnica debe poner sus correderas y tornillos en «1.2 Armado» en la proyección.
- [ ] **Lista de motivos de posventa:** la define Producción con Proyectos. Propuesta inicial en M110-06.
- [ ] **Tipo de «1.2 Armado»:** si pasa a «Fabricación», deja de poder asignarse a una contrata de armado. Lo confirma Cristóbal.
- [ ] **Receta frente a lista de fabricación:** separarlas por secuencia o archivar la receta (M110-02). Lo decide Cristóbal.
- [ ] **«En obra» al validar el despacho:** hoy la llegada a obra no se registra aparte. Si se quiere una recepción en obra, el despacho iría en dos pasos [P].
- [ ] **Plazo y estimación** de M110-01 a M110-09: Cristóbal.

## Fuentes

- **Base `newallcenter_dev_1`** ([newallcenter-dev1.altalatam.com](https://newallcenter-dev1.altalatam.com)), 18 y 19-oct-2026:
  - prueba BRE/MO/00003 y PPD/MO/00005, con sus traslados, y despacho BRE/ZZDO/00001;
  - verificaciones BRE/MO/00004 y PPD/MO/00006, y BRE/MO/00005 y PPD/MO/00007, canceladas;
  - prueba E-03 del piso 3: BRE/MO/00006 a 00017, PPD/MO/00008 a 00020, BRE/DO/00001 a 00003;
  - RQO/2026/00004, 00005 y 00007 con sus solicitudes;
  - catálogo de etapas, versiones de los módulos, vista 1660 y acción 607 de Aprobaciones;
  - configuración descrita arriba.
- **Odoo 19, rama 19.0** (github.com/odoo/odoo):
  - `mrp/models/stock_rule.py` (`_run_manufacture`, `_make_mo_get_domain`, `_prepare_mo_vals`, `_get_stock_move_values`);
  - `mrp/models/stock_move.py` y `mrp/models/mrp_production.py` (grupo de fabricación);
  - `stock/models/stock_move.py` (`_prepare_procurement_values`);
  - `mrp/models/mrp_bom.py` (`_bom_find`);
  - `mrp/models/product.py`;
  - `stock/models/stock_warehouse.py`;
  - `project_mrp/models/stock.py` y `project_mrp/models/mrp_production.py`;
  - `mrp/models/mrp_workcenter.py`.
- **Repositorio OL-PROJECTS, commit `38b5ada`:**
  - catálogo de etapas;
  - importador de tipologías y generador del plan;
  - productos de módulo, lote y envío;
  - asistente de órdenes del plan;
  - control de exceso y comparación;
  - accesorios e informe;
  - saldo del plan;
  - aprobaciones;
  - convenciones de `README.md`, `docs/fichas` y `docs/planificador`.
- **Caso de prueba integral Montecarmelo:** hallazgos HM-26 y HM-28 a HM-39.
- **Documentos de Planificación de obra:** paquetes 1.7 parte 2, 1.8 y 1.9; flujo de manufactura del 23-set-2026.
