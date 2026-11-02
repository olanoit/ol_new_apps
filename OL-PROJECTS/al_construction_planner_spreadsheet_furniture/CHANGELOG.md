Historial de cambios — Hoja de trabajo del planificador: mobiliario (AL)
========================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_planner_spreadsheet_furniture.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 9.20261102 — 02/11/2026

- Multicompañía: lo que se enlaza en sus registros y asistentes (obras, documentos, empleados, diarios…) se valida en el servidor contra la compañía del registro, el campo Compañía queda de solo lectura en sus vistas y sus ajustes por compañía llevan el ícono de Odoo «valores por compañía».

## 8.20261101 — 01/11/2026

- M113-01 a M113-03 y M116-09: «Validar» y «Enviar al planificador» en el menú «Planificación de obra»; con errores el envío lleva a ERRORES; se leen solo las pestañas del maestro; amarillo para el dato y gris para la fórmula.
- M113-04 y M113-05: «Importar Excel a la hoja» con revisión por pestaña, versión previa, productos nuevos y ampliación de la hoja; «Filas de la hoja de trabajo» en la ficha de la obra (0 = automático).
- M113-06: listas «Grupo de categoría», «Categoría» y «Producto», con los materiales de la obra primero; unidad y costo calculados, marcas rojo y ámbar y ajuste «Categoría raíz de materiales de la hoja».
- M113-07, M113-09 a M113-11: pestañas INICIO, FICHA, PROGRAMA y CONTROL; «Traer de Odoo» escribe en la hoja la obra del planificador.
- M113-08: panel «Planificación» y clic derecho para copiar un piso, asignar tipología, numerar ambientes, crear una variante, reemplazar un material y ver la ficha; ARBOL agrupado por piso. «Actualizar a la plantilla vigente…» lleva una hoja ya creada a la plantilla nueva.
- Rendimiento: TIPOLOGIAS lleva fórmulas en 500 filas y ACTIVIDADES en 2 000, así una hoja grande abre y se edita más rápido.

## 2.20261027 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 1.20261024 — 24/10/2026

- Primera versión: el maestro de mobiliario de la hoja de trabajo (v1.5, M15-15 y v1.8, M18-22), separado del módulo genérico (requerimiento CREVAL v1.0, 6.7).
