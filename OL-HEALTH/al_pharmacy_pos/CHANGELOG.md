Historial de cambios — Farmacia: punto de venta (AL)
====================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`AAAAMMDD.N`).

Generado desde `docs/fichas/al_pharmacy_pos.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 20261027.10 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 20261022.9 — 22/10/2026

- Bioequivalentes en la caja: entre las alternativas y en la ficha del producto, con la etiqueta «Bioequivalente»; se cargan aunque no entren en el límite de productos.
- Al tocar un equivalente en la ficha, la caja lo cambia en el pedido con la misma cantidad (antes solo lo buscaba).

## 20261022.8 — 22/10/2026

- Ficha del producto en la caja con la información farmacéutica: condición de venta, composición, forma, vía, laboratorio, registro sanitario, DIGEMID, IGV, almacenamiento, presentaciones, lotes por vencimiento y equivalentes con precio y stock.
- Filtro por principio activo en lugar del de etiquetas (ajuste por caja, activo por defecto).
- Búsqueda de productos también por principio activo y sus sinónimos, en lo cargado y en el servidor.

## 20261019.7 — 19/10/2026

- Precio por vencer: al vender un lote dentro de una escala, la línea recibe el descuento y la nota «Por vencer: vence dd/mm/aaaa»; los lotes vencidos no se ofrecen.

## 20261019.6 — 19/10/2026

- Empresa vinculada (DS 020-2024-SA, art. 32-B): aviso al agregar el producto y leyenda «Empresa vinculada» en la línea y en el ticket.
- Rótulo de venta fraccionada (art. 48) desde el recibo del TPV o la orden: establecimiento, producto, laboratorio, concentración, vía, lote y vencimiento.

## 20261018.5 — 18/10/2026

- El precio por presentación de la línea sale del total: el blíster de S/ 1,50 + IGV muestra S/ 1,77 y no S/ 1,80 (precio por tableta redondeado multiplicado por 10).

## 20261018.4 — 18/10/2026

- Datos de demostración: los medicamentos de la botica se venden en la caja.

## 20261018.3 — 18/10/2026

- Listas de precios en las presentaciones: el porcentaje o la fórmula se aplica al precio de la caja o el blíster, y se recalcula al cambiar la lista o la cantidad.

## 20261018.2 — 18/10/2026

- Entrega 2: alternativas genéricas, receta en la caja, control del Q.F., lotes FEFO y registro de la dispensación.

## 20261018.1 — 18/10/2026

- Primera versión (prototipo E0): venta por presentación con precio propio en el TPV.
