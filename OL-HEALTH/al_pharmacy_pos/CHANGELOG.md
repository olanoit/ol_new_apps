Historial de cambios — Farmacia: punto de venta (AL)
====================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_pharmacy_pos.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 7.20261019 — 19/10/2026

- Precio por vencer: al vender un lote dentro de una escala, la línea recibe el descuento y la nota «Por vencer: vence dd/mm/aaaa»; los lotes vencidos no se ofrecen.

## 6.20261019 — 19/10/2026

- Empresa vinculada (DS 020-2024-SA, art. 32-B): aviso al agregar el producto y leyenda «Empresa vinculada» en la línea y en el ticket.
- Rótulo de venta fraccionada (art. 48) desde el recibo del TPV o la orden: establecimiento, producto, laboratorio, concentración, vía, lote y vencimiento.

## 5.20261018 — 18/10/2026

- El precio por presentación de la línea sale del total: el blíster de S/ 1,50 + IGV muestra S/ 1,77 y no S/ 1,80 (precio por tableta redondeado multiplicado por 10).

## 4.20261018 — 18/10/2026

- Datos de demostración: los medicamentos de la botica se venden en la caja.

## 3.20261018 — 18/10/2026

- Listas de precios en las presentaciones: el porcentaje o la fórmula se aplica al precio de la caja o el blíster, y se recalcula al cambiar la lista o la cantidad.

## 2.20261018 — 18/10/2026

- Entrega 2: alternativas genéricas, receta en la caja, control del Q.F., lotes FEFO y registro de la dispensación.

## 1.20261018 — 18/10/2026

- Primera versión (prototipo E0): venta por presentación con precio propio en el TPV.
