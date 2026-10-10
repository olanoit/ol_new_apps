Historial de cambios — PE - Factoring de facturas (AL)
======================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_factoring.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 3.20261010 — 10/10/2026

- Una factura cedida que sigue pendiente no se puede pagar con «Pagar» (la cobra el factor): aviso en la factura y el cobro se registra desde la operación.

## 2.20261010 — 10/10/2026

- Con recurso la factura ya no se da por pagada al cederla: sigue pendiente en la cuenta del cliente (NIIF 9), en su saldo, vencimientos y recordatorios, y queda pagada con el cobro del factor; la recompra solo devuelve el adelanto.
- Datos de demostración «DEMO FAC» (tools/factoring_demo_data.py) y capturas de la ficha.

## 1.20261010 — 10/10/2026

- Primera versión: operaciones de factoring con y sin recurso sobre las facturas de cliente (cesión, desembolso, devengo de intereses, cobro del factor y recompra), cuentas del PCGE por modalidad y moneda, «Ceder a factoring» desde la lista de facturas, pestaña Factoring en la factura y menú Perú ▸ Factoring con análisis.
