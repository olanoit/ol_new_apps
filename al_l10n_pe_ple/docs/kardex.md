[← Índice](README.md)

# Kardex (12.1 / 13.1) — capa visual del inventario permanente

**Menú:** Perú ▸ **Kardex (12.1/13.1)** (módulo `ol_stock_kardex_pe`).
Complementa el TXT PLE de Inventarios (que se genera desde
[Reportes PLE nativos](reportes_nativos.md)) con los formatos imprimibles
SUNAT 13.1 (valorizado) y 12.1 (unidades físicas).

## Menús

- **Generar Kardex**: wizard con periodo (mes o rango), filtros por
  producto/categoría/almacén y modo consolidado o por almacén. Exporta
  XLSX (réplica de la plantilla oficial `234_formato131.xls`), PDF o vista
  en pantalla con saldo corrido.
- **Kardex generados**: reportes producidos en segundo plano (volúmenes
  grandes) por el cron del módulo.

## Configuración previa

La misma del TXT 12.1/13.1: tipo de existencia en el producto (tabla 5),
código SUNAT de la unidad (tabla 6), código de establecimiento en el
almacén y tipo de operación (tabla 12) en las transferencias.

## Atajos

Botón **«Ver Kardex»** en la ficha del producto y de la categoría: abre el
wizard pre-filtrado.

Documentación completa del módulo: [`ol_stock_kardex_pe/README.md`](../../ol_stock_kardex_pe/README.md).
