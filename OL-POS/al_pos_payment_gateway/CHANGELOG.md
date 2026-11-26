Historial de cambios — Cobro con pasarelas en el TPV: un método por pasarela y devoluciones (AL)
================================================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`AAAAMMDD.N`).

Generado desde `docs/fichas/al_pos_payment_gateway.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 20261027.7 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 20261018.6 — 18/10/2026

- Antes de mostrar el QR de la pasarela se revisa que el comprobante de la venta se pueda emitir: si no (por ejemplo, una línea sin impuesto en la boleta), el cajero ve el motivo y no se cobra.

## 20261018.5 — 18/10/2026

- El logo de la pasarela ocupa el mismo cuadro de 30 px que los demás íconos de la pantalla de pago.

## 20261018.4 — 18/10/2026

- El método de pago del TPV usa la tarjeta de 240 × 160 de la pasarela (como las imágenes de los métodos de pago de Odoo) cuando su módulo la trae.

## 20261018.3 — 18/10/2026

- El logo de la pasarela se ve más ancho, sobre fondo blanco y sin invertir en modo oscuro, para que la marca se lea en la pantalla de pago.

## 20261018.2 — 18/10/2026

- Cada método de pago en línea lleva el logo de su pasarela en la pantalla de pago del TPV (también los ya creados).

## 20261018.1 — 18/10/2026

- Primera versión: un método de pago del TPV por pasarela y devoluciones a la tarjeta.
