Historial de cambios — Pagos con Niubiz (AL)
============================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_payment_niubiz.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 5.20261027 — 27/10/2026

- Recupera su ícono original; el isotipo de ALTA queda solo para los módulos que no tenían ícono.

## 4.20261027 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.
- La imagen del proveedor de pago no cambia: pasa a static/img/niubiz_icon.png.

## 3.20261018 — 18/10/2026

- Ícono al estilo de Odoo (marca centrada sobre fondo transparente) y tarjeta de 240 × 160 para el método de pago del TPV.

## 2.20261009 — 09/10/2026

- Etiquetas más cortas en la transacción: «Fecha Niubiz» y «Constancia PagoEfectivo».

## 1.20261006 — 06/10/2026

- Primera versión en la suite (adaptación de payment_niubiz): el modal ya se abre, la anulación cancela la transacción y el pago, rutas firmadas, contraseña solo para administradores, reintentos de conexión y pruebas; validado con pagos reales en el sandbox.
