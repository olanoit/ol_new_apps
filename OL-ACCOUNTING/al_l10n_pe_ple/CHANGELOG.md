Historial de cambios — PE - Libros Electrónicos PLE (AL)
========================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_ple.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 8.20260828 — 27/09/2026

- El RCE 8.4 ya no incluye los comprobantes del 8.5 (tipo 00) ni los recibos por honorarios (02).
- El RCE toma el periodo por la fecha contable: una factura recibida tarde va al mes en que se anota.
- Los borradores cancelados que nunca se emitieron no aparecen en el RCE ni en el RVIE; solo cuentan los diarios que usan documentos.
- La línea de título de los informes RCE 8.4, 8.5 y RVIE 14.4 ya no muestra los importes de una factura.
- Compras y ventas simplificados (8.3 y 14.2): los importes de facturas en moneda extranjera salen en soles, como el resto del libro.
- El Diario Simplificado (5.2) no genera filas por las subsecciones de la factura.
- La clasificación RCE solo se propone en facturas de proveedor en borrador: cambiar la del producto ya no reescribe lo publicado.
- Cada compañía ve únicamente sus registros de captura (4.1, 3.8, 3.19 y Libro 10).
- El Excel del RCE/RVIE se descarga con extensión .xlsx.
- Consignaciones (9.1/9.2) y Compras Simplificado (8.3): la serie y el número del comprobante salen del número de documento, no del nombre interno ni de la referencia libre.

## 17/09/2026

- Excel de revisión en todos los libros PLE: botones XLSX junto a los TXT de la localización oficial (1.1, 1.2, 5.1, 5.3, 6.1, Libro 3 y 12.1 / 13.1), con el formato del resto del módulo.
- Encabezados tomados del Anexo 2 oficial de SUNAT, que acompaña al módulo junto con la nomenclatura de los archivos.
- La fila de encabezados del Excel crece cuando el nombre del campo es largo.

## 6.20260828 — 14/09/2026

- Registro de Activos Fijos (PLE 7.1) en pantalla, con botones TXT 7.1, XLSX 7.1, TXT 7.3 y TXT 7.4.
- La depreciación del 7.1 ya no suma los asientos de baja o venta; los activos dados de baja salen del registro.

## 5.20260828 — 28/08/2026

- La ficha del producto vuelve a abrirse con el campo Clasificación RCE.

## 4.20260815 — 18/08/2026

- RCE 8.4 y 8.5 y RVIE 14.4 con la estructura oficial, extraídos sin el error de base de datos.
- Clasificación y estado RCE en productos y facturas de proveedor.
- Botón XLSX en los informes del RCE y del RVIE.

## 3.20260719 — 19/07/2026

- Excel de revisión por formato y sección propia en Ajustes ▸ Perú.

## 1.20260718 — 19/07/2026

- Libros 7, 4.1, 9, 3.8/3.9/3.19/3.23, 10 y simplificados en la app Perú, con guía funcional y datos de demostración.
