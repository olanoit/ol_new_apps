# Reporte de guía de remisión (SUNAT Perú)

## Origen

Migración y refactor de la parte de guía de remisión del módulo v18
`al_l10n_pe_edi` (`ce18/al/montegrande/alta/al_accounting/al_l10n_pe_edi`),
separada en su propio módulo para que sea instalable de forma
independiente del reporte de factura (`al_l10n_pe_invoice`) — ya
no comparten manifest, paperformat ni datos.

## Qué se descartó al migrar

- `_l10n_pe_edi_get_qr()` propio: el core v19 (`l10n_pe_edi_stock`) ya
  trae un método **idéntico** (misma búsqueda del adjunto CDR por nombre
  de archivo, mismo XPath sobre `DocumentDescription`). Reimplementarlo
  aquí sería código muerto — el reporte llama directamente
  `o._l10n_pe_edi_get_qr()`, que resuelve al del core.
- `btn_developer()`: método de debug sin valor productivo.

## Qué se mantiene y por qué

- **`_get_grouped_move_lines()`**: SUNAT exige una línea por bien
  transportado, no una por movimiento de stock — agrupa por
  producto/UdM y junta las series/lotes movidos.
- **Fallback de peso** (`_cal_weight`): el core (`stock_delivery`) calcula
  `weight` sumando el peso de cada movimiento
  (`move.product_id.weight × qty`); si los productos no tienen peso
  configurado, el resultado es 0 KGM, lo que la guía no debería declarar.
  Se extiende el compute para caer a `shipping_weight` en ese caso.
- **`_l10n_pe_edi_get_delivery_guide_values()`**: fuerza el recálculo del
  peso antes de armar el XML de la guía, para no depender del orden en
  que se escriben los movimientos relacionados.
