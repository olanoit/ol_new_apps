# Diseño del paquete 1.12 · costo por etapa, reposición a planta y modalidad de ejecución

Fuente: «Requerimiento · paquete 1.12» (27-oct-2026), que reemplaza a
M111-24, M111-25, M111-26 y HM-20. Sale de la prueba integral v2 de
mobiliario; los nombres de obra, montos y usuarios de esa prueba no se copian
aquí.

## Módulos

| Módulo | Requerimientos |
| --- | --- |
| `al_construction_planner` | M112-04: «Modalidad por defecto» en la etapa, «Modalidad» en la actividad, regla de cambio por `space_task_id` |
| `al_construction_planner_furniture` | M112-04: «Generar plan» produce personal propio o contrata |
| `al_construction_planner_mrp` | M112-01 y M112-02 (`stock.move`), ajuste por compañía; ahora depende de `project_mrp_account` |
| `al_construction_planner_budget` | M112-02: el hook de apuntes no completa el consumo de una orden de obra que ya trae su etapa |
| `al_construction_planner_mrp_request` | M112-03 |
| `al_construction_planner_suite` | Pruebas `test_package_112_*` |

## Decisiones

| Punto | Decisión | Motivo |
| --- | --- | --- |
| M112-01/02: dónde | En `al_construction_planner_mrp`, sumando `project_mrp_account` a sus dependencias (opción que el requerimiento deja a desarrollo) | Ahí están `construction_intermediate`, `_construction_is_intermediate` y el motivo. `project_mrp_account` es auto-instalable y ya está en las bases con Fabricación y Contabilidad: no hace falta otro puente |
| M112-02: cómo | La etapa y la partida se ponen en `stock.move._get_analytic_distribution` (clave `obra,etapa,partida`), no en `_prepare_analytic_line_values` | Al recalcular los apuntes, `_perform_analytic_distribution` compara las cuentas del apunte con las claves de la distribución: con las columnas solo en el apunte, Odoo lo borraría y crearía otra vez en cada recálculo |
| M112-02: el hook | `_create_analytic_move` corre con el contexto `construction_analytic_by_move`; el hook de `al_construction_planner_budget` salta los apuntes de categoría «Orden de fabricación» con ese contexto | Si ninguna regla da la etapa de la línea, el hook ponía la primera etapa de fabricación: el armado volvería a caer en el corte |
| M112-02: motivo | La cuenta del motivo reemplaza la de su plan analítico; la partida sigue saliendo de las reglas; lo que el proyecto ya trae en otras columnas se respeta | Lo pedido |
| M112-01: ajuste | `res.company.construction_intermediate_no_analytic`, activo por defecto (excepción a P4 aprobada el 27-oct) | Anotar en la sección 8 de `ARQUITECTURA_COMUN.md` cuando ese documento esté en el repositorio |
| M112-03 | La lista del tipo configurado (o sin tipo), como antes; si no hay, la del producto en cualquier planta (`bom_type='normal'`) con el primer tipo de fabricación de su almacén que pide motivo (`sequence, id`). Sin lista o sin tipo: `UserError` y ninguna orden | Lo pedido. La lista y los tipos los lee el sistema (`sudo`) porque quien pide no tiene Fabricación |
| M112-04: orden de búsqueda | Ambiente (`construction_execution_mode` de la tarea `space`) › actividad › etapa › personal propio | Lo pedido. El campo del ambiente ya existía (CREVAL); se muestra en la tarea de nivel ambiente |
| M112-04: personal propio | `resource_type='labor'` con la misma actividad, cantidad, unidad y precio (`activity._get_rate`) | Lo pedido |
| M112-04: contrata a todo costo | Sale como contrata y se avisa en el asistente | No aplica al mobiliario |
| M112-04: pruebas anteriores | `PlannerCommon` pone las etapas en «Contrata solo de mano de obra» | Esas pruebas validan contratas; el personal propio por defecto se prueba en `test_package_112_mode` |

## Fuera de alcance

- Los apuntes duplicados que ya existen en las bases: la corrección vale para
  los consumos nuevos (o recalculados).
- El consumo en obra del hook (`stock_move_id` del asiento), señalado en el
  requerimiento como nota para el diseño del asiento de costo.
- El conflicto C-01 (catálogo de etapas de toda la base): la modalidad de una
  etapa vale para todas las compañías.

## Pruebas

`al_construction_planner_suite/tests`: `test_package_112_analytic` (M112-01 y
M112-02, con «Fabricación: usuario»), `test_package_112_request` (M112-03,
«Solicitante» y «Fabricación: usuario») y `test_package_112_mode` (M112-04).
