Historial de cambios — Hoja de trabajo del planificador de obra (AL)
====================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_planner_spreadsheet.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 6.20261027 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 5.20261016 — 27/10/2026

- CR-18, a: todas las celdas se guardan como texto (la hoja con números no abría: «content.startsWith is not a function»); migración que convierte las hojas de trabajo existentes sin perder sus revisiones.
- CR-18, c y d: PRESUPUESTO con las columnas A a W del libro 6.6 y sus fórmulas (metrado y costo ofertado, precio unitario, costo real, parcial de venta y reserva); «Traer de Odoo» reescribe esa pestaña completa, llena «Costo unitario sin APU» de las partidas sin receta con su costo o su precio (D1) y los % de gastos generales, imprevistos, utilidad y descuento de OBRA desde la cotización, con 6 decimales.
- CR-18, D3 y D4: «Enviar al planificador: presupuesto» queda deshabilitado con la cotización confirmada; la hoja de una cotización sin obra trae la biblioteca de recetas y sus insumos.

## 4.20261016 — 24/10/2026

- Requerimiento CREVAL v1.0, 6.7: la hoja de trabajo es genérica, sin dependencia de mobiliario: presupuesto, APU y plan con las hojas del libro de carga (6.6), menú Planificación de obra (validar, enviar con destino presupuesto o plan, actualizar insumos, traer de Odoo, nueva versión) y copias numeradas. El maestro de mobiliario pasa al puente al_construction_planner_spreadsheet_furniture.

## 3.20261016 — 23/10/2026

- Requerimiento CREVAL v1.0, capítulo 5: accesos, menús y botones con los grupos en dos ejes (Plan: consulta, planificador, aprueba; Ejecución: reporta avance, ejecuta, valida, aprueba).

## 2.20261016 — 16/10/2026

- Hoja de trabajo de la oficina técnica (v1.8, M18-22): resúmenes con tablas dinámicas, listas dependientes, referencias de productos y categorías; el envío al planificador crea los productos nuevos.

## 1.20261013 — 13/10/2026

- Hoja de trabajo de la obra en Documentos con una pestaña por hoja del maestro y la pestaña REFERENCIAS con listas de Odoo de actividades y tipologías.
- Menú Archivo ▸ Enviar al planificador: abre «Importar maestro y ETO» con la vista previa, las advertencias y los errores por fila.
