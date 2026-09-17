[← Índice](README.md)

# Reportes PLE nativos (generados por la localización EE)

**Menú:** Perú ▸ Libros PLE ▸ **Reportes PLE nativos**. Son accesos
directos a los reportes de la localización oficial Enterprise: este módulo
**no los regenera**, solo los concentra en la app Perú y añade, junto a
cada botón TXT, uno **XLSX** con las mismas líneas para revisarlas.

El Excel se arma con el TXT oficial (no puede decir algo distinto del
archivo que se presenta), con el formato del resto del módulo y los
encabezados del Anexo 2 publicado por SUNAT
([`docs/ple/oficial`](../../docs/ple/oficial/README.md)).

## Diario y Mayor (5.1 / 5.3 / 6.1)

Abre el **Libro Mayor** (misma pantalla de aterrizaje de la app Perú).
En el botón de descarga del reporte están **PLE 5.1** (Diario), **PLE 5.3**
(plan contable utilizado) y **PLE 6.1** (Mayor), cada uno con su **XLSX
5.1 / 5.3 / 6.1**. **Inventory and Balance** descarga el Libro 3 en un ZIP
con un TXT por formato; **XLSX Inventario y Balance** lo entrega en un solo
Excel con una hoja por formato (3.1 a 3.25). Seleccionar antes el
**periodo mensual** en el filtro de fechas. El 5.3 se presenta obligatorio
en enero o en la primera generación del año.

## Caja y Bancos (1.1 / 1.2)

Abre el **Flujo de caja**; sus botones exportan PLE 1.1 (movimientos de
efectivo) y 1.2 (cuenta corriente), con sus botones **XLSX PLE 1.1
(Efectivo)** y **XLSX PLE 1.2 (Banco)**. Requiere diarios de banco/caja con
cuenta bancaria configurada (entidad financiera y nº de cuenta).

## Ventas (14.1) y Compras (8.1 / 8.2)

Reportes fiscales con una línea por comprobante. Configuración clave:

- Diarios de venta/compra con **documentos LATAM** habilitados (tipo de
  comprobante tabla 10 y serie correlativa).
- Clientes/proveedores con tipo y nº de documento (tabla 2).
- Facturas **publicadas** en el periodo; en compras, la fecha de la factura
  del proveedor y su número (`F001-…`).
- 8.2 solo aplica a compras a **no domiciliados** (documentos 91/97/98).

Nota: SUNAT migró los registros de ventas y compras al **SIRE**
(RVIE/RCE); los reportes EE ya apuntan a esa nomenclatura (RCE 8.4/8.5).

## Inventarios TXT (12.1 / 13.1)

Abre el wizard EE que genera el TXT del **inventario permanente** en
unidades físicas (12.1) y valorizado (13.1); **XLSX 12.1** y **XLSX 13.1**
dan el mismo contenido en Excel. Requiere: productos con tipo
de existencia (tabla 5), unidades con código SUNAT (tabla 6), almacenes con
código de establecimiento anexo y transferencias con tipo de operación
(tabla 12). La capa visual (kardex XLSX/PDF) está en
[Perú ▸ Kardex](kardex.md).
