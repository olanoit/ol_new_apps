Historial de cambios — PE - Cierre de tipo de cambio (AL)
=========================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_exchange_closure.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 4.20260828 — 27/09/2026

- Si se cambia el mes, la moneda, los tipos de cambio o la analítica de un cierre ya calculado, vuelve a borrador y hay que calcularlo de nuevo: ya no se puede contabilizar un cálculo desfasado.
- Un cierre solo se puede cancelar si no hay cierres posteriores contabilizados.
- Volver un cierre a borrador conserva su asiento cancelado en lugar de borrarlo, como exige la pista de auditoría.
- Cada compañía ve solo sus cierres, y el cierre incluye los apuntes de sus sucursales.
- El T.C. solo se descarga automáticamente para el dólar; para otras monedas se usa el registrado.

## 14/09/2026

- Menús de la app Perú reordenados.

## 2.20260828 — 28/08/2026

- El cierre pasa al grupo **Tipo de cambio** de la app Perú; menú **Cuentas del cierre de T.C.** en Configuración.

## 1.20260802 — 02/08/2026

- Primera versión en Odoo 19: saldos acumulados, detalle por socio, ganancia y pérdida separadas, analítica heredada y vista previa del asiento.
