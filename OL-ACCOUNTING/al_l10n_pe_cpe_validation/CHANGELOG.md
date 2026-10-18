Historial de cambios — PE - Consulta de validez de comprobantes en SUNAT (AL)
=============================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_cpe_validation.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 3.20261018 — 18/10/2026

- Los datos de demostración llevan nombres reales en lugar del prefijo DEMO; las bases que ya los tienen se renombran al actualizar.

## 2.20261012 — 12/10/2026

- Datos de demostración en «PE Company» (solo en bases con datos de demostración): tres facturas de proveedor con el resultado de la consulta ya registrado (válido, observado y no informado), sin llamar a SUNAT.

## 1.20261012 — 12/10/2026

- Consulta integrada de comprobantes de pago de SUNAT para facturas, boletas, liquidaciones de compra, notas y recibos por honorarios de proveedores: botón, acción en lote, aviso o bloqueo al publicar y acción programada.
- Credenciales de API SUNAT del RUC con el token renovado solo; si no se configuran, se usan las del SIRE.
