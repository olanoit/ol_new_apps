Historial de cambios — PE - Libros Electrónicos PLE (AL)
========================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_ple.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 12.20261007 — 07/10/2026

- RVIE 14.4: un comprobante con CDR rechazado por SUNAT (códigos 2000-3999) se anota en cero, como los anulados (nota 4 del anexo 2 de la RS 112-2021). En Odoo 19 sigue publicado y «por enviar», así que antes iba con sus importes; las excepciones 0100-1999 (no recibido, se reenvía) no cuentan como rechazo.

## 11.20261007 — 07/10/2026

- Corregido: el registro de compras (8.4 y 8.5) y el de ventas (14.4) informaban los comprobantes en dólares con los importes en dólares. Ahora van en soles, con la moneda y el tipo de cambio aparte, como los declara la contabilidad real (13 223,10 USD se informan como 46 214,73 con T.C. 3,495).

## 10.20261007 — 07/10/2026

- Libros del asistente (retenciones, consignaciones, simplificados, activos, costos y libro 3): cada línea del TXT cierra con «|», como los archivos del PLE; antes el validador podía rechazarlos.
- Registro de compras 8.4: ya no incluye comprobantes anulados (la norma lo prohíbe); el ISC de un ítem gravado va en la base imponible; IVAP, exportación y líneas sin impuesto se informan, y los campos 15-24 suman el total. 8.5: valor de la adquisición completo y convenio con dos dígitos.
- Ventas 14.4: una línea gratuita ya no infla la base gravada y la retención del 3 % ya no reduce el total. Compras y ventas con el RUC de la compañía principal también desde una sucursal.
- Simplificados y consignaciones: sucursales incluidas; proveedor con tipo «VAT» genérico informado como RUC o DNI y con el nombre de la empresa; estado 0 sin crédito fiscal; vencimiento solo en recibos de servicios públicos; prefijo A/C en apertura y cierre; consignaciones con hora de Perú y saldos iniciales sin movimientos. Plan de cuentas 5.4 con la tabla 17 configurada.
- Activos y libro 3: los activos cerrados y archivados ya no desaparecen del 7.1 ni del 3.9; código de cuenta correcto aunque la compañía activa sea otra; depreciación importada y fecha de inicio de uso corregidas; porcentaje máximo 100; 7.3 y 7.4 validan catálogo, cuotas y monto; no se repiten filas del 10.3 ni del 3.19.
- Excel de revisión: importes como número, archivos de los libros nativos con extensión .xlsx y encabezados con el nombre real del campo.
- El TXT del 8.4 se bloquea si hay notas de crédito o débito sin enlazar al comprobante que modifican (SUNAT las rechazaría) y lista cuáles son; el Excel de revisión se sigue generando para encontrarlas.

## 9.20261007 — 07/10/2026

- Corregido: el TXT del RCE 8.4 salía con 41 campos y el anexo 8 pide 37 (los campos 38 a 41 no van en el archivo); el Excel de revisión los sigue mostrando.
- Tipo de cambio de compras y ventas desde la tasa de la factura y, en notas de crédito y débito, el del documento modificado (antes se calculaba dividiendo totales).
- Las sucursales se incluyen en los libros de la compañía y sus importes por grupo de impuestos ya no salen en cero.
- La base imponible ya no incluye el ISC; el 8.3 y el 14.2 separan gravado, exonerado e inafecto; el 14.2 informa los anulados (estado 2) y lleva T.C. 1.000 en soles; el 8.3 marca estado 6 o 7 para comprobantes de periodos anteriores.
- Las notas de débito informan el documento que modifican en el 8.3/14.2, el 5.4 ya no mezcla cuentas de otras compañías y el campo 31 del 8.4 lleva la aduana del documento modificado.

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
