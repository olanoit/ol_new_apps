# Diseño del paquete 4 de CREVAL · correcciones de la rutina integral

Fuente: «Requerimiento de desarrollo · Paquete 4» v1.1 (10-nov-2026),
CR-27 a CR-37. CR-28 y CR-32 pasan al paquete 5 (CR-45 y CR-44). Los
nombres de obra, montos y usuarios de la prueba no se copian: el repositorio
es público. Manda `ARQUITECTURA_COMUN.md` en lo común.

## 1. Revisión de configuración

Se comprobó la tabla de alternativas de cada requerimiento. Ninguna ruta
configurable (Odoo nativo, `OL-THIRD-PARTY`, módulos AL) cumple: son errores
de código o reglas que la hoja no puede expresar.

## 2. Qué se hizo

| CR | Módulo | Cambio |
|---|---|---|
| CR-34 | `al_construction_planner_subcontract` | `action_confirm` recalcula cada partida marcada desde la línea de la orden (`_fresh_rows`); no usa las columnas de solo lectura que el navegador no manda. La cantidad nueva no baja de lo valorizado |
| CR-33 | `al_construction_planner_subcontract` | `button_cancel` quita la contrata de las líneas del plan sin otra orden vigente (o deja la de esa orden). «Asignar contrata» cuenta como tomada solo una línea con orden vigente |
| CR-27 | `al_construction_planner_spreadsheet`, `al_construction_planner_sale` | «Costo real» = `ROUND(metrado × ROUND(costo; «Product Price»); moneda)` en la plantilla y en «Traer de Odoo»; el envío suma por partida con el mismo redondeo y, si hay diferencia, nombra las partidas |
| CR-29 | `al_construction_planner_sale` | «Validar» (mismo `_parse` que el envío): APU de partida en contrata sin actividad de contrata; nivel en modo Catálogo sin cuenta (escrita o por el nombre del título); celdas con `#REF!` en cualquier columna; una columna obligatoria que falta da un solo error y no encadena los de las pestañas que la usan |
| CR-30 | `al_construction_planner_sale` | El nombre de cada nivel sale de la fila que lo da (título o columnas Especialidad y Sub-especialidad de cualquier partida); el nodo se ubica por código; «Validar» avisa si dos filas dan nombres distintos |
| CR-31 | hoja, venta y núcleo | Columna «Suministro del cliente» en APU_DETALLE (lista Sí/No) que el envío pasa a la línea de la receta; «Reemplazar lo generado» conserva la marca |
| CR-35 | `al_construction_planner` | La lista de la etapa actual lee las etapas hoja de todo el catálogo, también las archivadas |
| CR-36 | `al_construction_planner_subcontract` | Avance del mismo día de la intervención: se rechaza si se registró después de confirmarla, con el nombre y la hora |
| CR-37 | núcleo, mobiliario, contratas, requerimiento | Cronograma y Árbol con el término de la plantilla (sin nivel de módulo cuentan partidas; totales por tipo de recurso); agrupadores sin duplicados; «(Nn)» oculto; avance «Partida» y línea del plan por su nombre; «Tipologías» solo con mobiliario o si la obra las tiene; aprobación por «Eje › Grupo»; «(1 línea)» |

## 3. Pendiente de datos en creval-dev

Las correcciones de datos que pide el documento (P00039 y su intervención,
líneas del plan 19 sin contrata) se hacen en la base después de desplegar, con
permiso.

Hecho el 10-nov, con permiso y respaldo previo de la base, por script con el
ORM (`construction_plan_force` para el plan aprobado):

- P00039: la línea de 4.0306 vuelve a 80 und (80 recibidas).
- P00039-INT01: 176 contratadas, 80 ejecutadas, 80 valorizadas, saldo 96,
  S/ 1,120.00 valorizado y S/ 1,344.00 liberado. Lo ejecutado es lo validado
  hasta la confirmación: AVN/2026/00187 (10 und, reportado después) no cuenta,
  como manda CR-36; el avance sigue validado en la base.
- Plan 19: las líneas 1417, 1418, 1424, 1464 y 1467 quedan sin contrata (solo
  tenían asignaciones de P00038, anulada).
