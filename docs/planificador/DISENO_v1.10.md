# Diseño del paquete 1.10 · fabricación por etapas

Requerimiento: `docs/md/Allcenter_Planificacion_Paquete_1.10_Orden_Fabricacion_Por_Etapas.md`
(versión 2 del 19-oct-2026). Implementado el 19-oct-2026 sobre `12a3b97` (sin cambios en
`OL-PROJECTS` desde `38b5ada`, así que las líneas que cita el requerimiento siguen valiendo).

## Módulos y versiones

| Módulo | Versión | Requerimientos |
| --- | --- | --- |
| `al_construction_planner_mrp` | 4.20261019 | M110-01, M110-03, M110-04, M110-06 |
| `al_construction_planner_furniture` | 7.20261019 | M110-02, M110-03, M110-05, M110-09 |
| `al_construction_planner_approvals` | 3.20261019 | M110-07, M110-08 |
| `al_construction_planner_approvals_mrp` | 2.20261019 | M110-04, M110-08 |
| `al_construction_planner_production` | 4.20261019 | M110-04, M110-08 |
| `al_construction_planner_suite` | 9.20261019 | Pruebas |

El núcleo (`al_construction_planner`) y el puente de compras no cambian.

## Diferencias frente al requerimiento

| Punto del requerimiento | Implementado | Motivo |
| --- | --- | --- |
| M110-01: campos de planta y categoría en `al_construction_planner` | En `al_construction_planner_mrp` (`models/construction_stage.py`) | El núcleo no depende de Inventario: un Many2one a `stock.picking.type` lo obligaría a instalar Inventario en las empresas sin fabricación |
| M110-01: «un grupo Fabricación en el formulario de la etapa» | Tres columnas en la lista editable de etapas, visibles en las filas de fabricación o que consumen en la orden | El catálogo de etapas no tiene formulario: se edita en la lista |
| M110-01: `accessory_request` por compañía | Casilla común a todas las compañías | La regla de compañía se aplica a la planta y la categoría; que el armado proponga accesorios es propio de la etapa. La marca se pone en `assembly` con una migración (bases existentes) y con el `post_init_hook` (instalaciones nuevas) |
| M110-02: la lista del producto de módulo «copia solo las etapas de `_production_codes()`» | Se quitan las etapas que no consumen en la orden; los materiales sin etapa se conservan | Las recetas reales de hoy pueden traer líneas sin etapa (prueba `test_real_recipe_versus_and_threshold`) y quitarlas cambiaría la lista sin aviso |
| M110-02: receta frente a lista de fabricación | Por secuencia (1 frente a 1000) | Decisión abierta para Cristóbal; archivar la receta queda como alternativa |
| M110-03: autorización de la receta real | Se mantiene el bloqueo; el mensaje nombra el módulo y su departamento | Propuesta [P] del requerimiento |
| M110-04: madre de la hija | Campo nuevo `construction_parent_id` («Orden de la etapa siguiente») en la orden | Lo escribe `_prepare_mo_vals`; sirve para avisar a la madre y como trazabilidad, sin usar el enlace nativo que Odoo escribe después de confirmar |
| M110-04: «Pedir accesorios» solo en el armado | Además del filtro de líneas, el botón se oculta si la orden no tiene etapas con accesorios | Criterio «aparece en el armado y no en el corte» |
| M110-05: lote que no corresponde | Mensaje en la transferencia al validarla | El requerimiento lo marca [P]; un error impediría despachar un módulo prestado de otra unidad |
| M110-07: acción «Aprobar» con «el grupo de usuario de Aprobaciones» | Visible para usuarios internos (`base.group_user`) | En Odoo 19 Aprobaciones no tiene un grupo de usuario: `group_approval_user` es «Oficial: aprobar todas» (el de Force Approval). El método solo aprueba donde el usuario tiene el tramo activo |
| M110-08: «Ya pedido» y «Saldo» en la orden de fabricación | Vacíos; «Presupuestado» lleva lo presupuestado de los ambientes | Como dice el requerimiento: la orden se compara con lo presupuestado, no con un saldo |
| M110-09: departamento sin número | El lote queda sin `{unidad_num}` y se avisa en el historial del plan | Un error impediría crear la orden por módulo |

## Notas técnicas

- `_construction_order_stages()` lee la lista de la orden con `sudo()`: quien confirma en
  planta no administra listas.
- El intermedio se reconoce por `construction_intermediate` o, en listas hechas a mano, por no
  tener etapa y tener lista propia (`_bom_find`).
- La hija se confirma dentro de `stock.rule._run_manufacture` con el contexto
  `construction_from_procurement`: no hay asistente de exceso ni error; queda «excede» con el
  aviso en ella y en la madre.
- `action_approve` de Aprobaciones (y de `approvals_purchase`) espera una sola solicitud: la
  aprobación en bloque las recorre una por una.
- El formato del lote no usa `str.format`: Odoo 19 lo parchea y devuelve la plantilla sin
  formatear si una clave se parece a un atributo prohibido.
- Los cambios de estado que hace el propio sistema al mover los tramos llevan el contexto
  `construction_sync_steps`, que el bloqueo del rechazo tardío respeta.

## Pruebas

- `al_construction_planner_suite/tests/test_stage_chain_v110.py`: cadena, importador, listas,
  subproductos, asistente, orden hija, exceso, lote, despacho y motivo.
- `al_construction_planner_suite/tests/test_approvals_v110.py`: resumen de la lista,
  aprobación y rechazo en bloque, saldo negativo y rechazo tardío.
- Criterios y resultados: `ACEPTACION.md`, sección «Paquete 1.10».
