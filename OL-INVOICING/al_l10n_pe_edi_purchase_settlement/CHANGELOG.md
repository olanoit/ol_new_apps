Historial de cambios — PE - Liquidación de compra electrónica (AL)
==================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`AAAAMMDD.N`).

Generado desde `docs/fichas/al_l10n_pe_edi_purchase_settlement.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 20261027.5 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 20261018.4 — 18/10/2026

- Los datos de demostración llevan nombres reales en lugar del prefijo DEMO; las bases que ya los tienen se renombran al actualizar.

## 20261012.3 — 12/10/2026

- Menú en Perú ▸ Proveedores ▸ Comprobantes.

## 20261012.2 — 12/10/2026

- Datos de demostración en «PE Company» (solo en bases con datos de demostración): productora de café sin RUC y dos liquidaciones de compra (una confirmada por enviar y otra en borrador), sin enviar nada a SUNAT.

## 20261011.1 — 11/10/2026

- Liquidación de compra electrónica (tipo 04): diario con serie L###, retención del IGV y de la renta (1,5 %, 4 % en el oro, nada hasta S/ 700) e importe total neto.
- XML SelfBilledInvoice firmado y enviado con el operador de la compañía y resumen diario de reversiones.
- Representación impresa, aviso de 75 UIT y total íntegro en los registros de compras (PLE y SIRE).
