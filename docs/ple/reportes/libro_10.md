[← Mapa de cobertura](README.md)

# Libro 10 — Registro de Costos (PLE 10.1 / 10.2 / 10.3 / 10.4)

Generado por `al_l10n_pe_ple` desde **Perú ▸ Libros PLE ▸ Exportar PLE**.
Libro **anual** (el nombre de archivo consigna `MM=00`); obligatorio para
contribuyentes de régimen general con actividad de transformación.

## Fuente de datos

`mrp` no está instalado en la BD de referencia, por lo que los cuatro
formatos se **capturan** en **Perú ▸ Libros PLE ▸ Costos (Libro 10)**
(listas editables e importables). Los montos de inventario final (10.1
campo 4 y 10.3 campo 11) se capturan en positivo y el TXT los emite en
negativo. Un futuro submódulo `al_l10n_pe_ple_mrp` podría calcularlos desde
órdenes de producción.

## 10.1 — Estado de costo de ventas anual (6 campos)

Una fila por ejercicio (restricción de unicidad): inventario inicial de
productos terminados, costo de producción, inventario final (−), ajustes
diversos, estado `1`.

## 10.2 — Elementos del costo mensual (8 campos)

Una fila por mes (restricción de unicidad año+mes) dentro del **archivo
anual**; el campo 1 de cada fila lleva el periodo mensual `AAAAMM00` y el
archivo se ordena por mes. Columnas: materiales y suministros directos,
mano de obra directa, otros costos directos, GIF materiales, GIF mano de
obra indirecta, otros GIF.

## 10.3 — Costo de producción valorizado anual (13 campos)

Una fila por **proceso productivo**: código (10 car.) y descripción del
proceso, las seis columnas de elementos del costo (como 10.2), inventario
inicial de productos en proceso, inventario final en proceso (−), código
de **agrupamiento** (tabla 21 del Anexo 3, capturado) y estado.

## 10.4 — Centros de costos (7 campos)

Una fila por centro: correlativo (id del registro), código y descripción de
la unidad de operación (opcionales), código y descripción del centro de
costos (opcionales). El centro puede **precargarse desde una cuenta
analítica** (m2o que propone código y nombre, editables).

## Limitaciones

- Captura manual: los importes deben cuadrar con la contabilidad del
  ejercicio (cuentas 20/21/23 y elemento 9 del PCGE).
- El código de agrupamiento (tabla 21) y la definición de procesos son
  responsabilidad del contador de costos.
- Estados `8`/`9` no se generan automáticamente.
