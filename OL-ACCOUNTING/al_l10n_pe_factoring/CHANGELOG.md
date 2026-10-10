Historial de cambios — PE - Factoring de facturas (AL)
======================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_factoring.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 4.20261010 — 10/10/2026

- Factura negociable (DU 013-2020): conformidad expresa o presunta (8 días calendario) o disconformidad, que impide ceder; fecha de anotación en CAVALI; aviso si la factura es al contado.
- El valor nominal propuesto es el monto neto pendiente de pago: sin la detracción ni la retención del IGV del cliente agente.
- Cobro parcial por factura: lo cobrado cubre primero el adelanto y luego libera el retenido.
- Comisión facturada por el factor: se elige su factura de proveedor y el descuento la paga (el IGV queda como crédito fiscal en ella).
- Sin recurso: pérdida del retenido no liberado (6741). Con recurso en moneda extranjera: la obligación se cancela al cambio histórico y la diferencia va a diferencia de cambio.
- Costo financiero por operación y menú Perú ▸ Factoring ▸ Costo financiero.

## 3.20261010 — 10/10/2026

- Una factura cedida que sigue pendiente no se puede pagar con «Pagar» (la cobra el factor): aviso en la factura y el cobro se registra desde la operación.

## 2.20261010 — 10/10/2026

- Con recurso la factura ya no se da por pagada al cederla: sigue pendiente en la cuenta del cliente (NIIF 9), en su saldo, vencimientos y recordatorios, y queda pagada con el cobro del factor; la recompra solo devuelve el adelanto.
- Datos de demostración «DEMO FAC» (tools/factoring_demo_data.py) y capturas de la ficha.

## 1.20261010 — 10/10/2026

- Primera versión: operaciones de factoring con y sin recurso sobre las facturas de cliente (cesión, desembolso, devengo de intereses, cobro del factor y recompra), cuentas del PCGE por modalidad y moneda, «Ceder a factoring» desde la lista de facturas, pestaña Factoring en la factura y menú Perú ▸ Factoring con análisis.
