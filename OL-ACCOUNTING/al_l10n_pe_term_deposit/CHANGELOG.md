Historial de cambios — PE - Depósitos a plazo y garantías (AL)
==============================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_term_deposit.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 2.20261010 — 10/10/2026

- ITF (Ley 28194) opcional por depósito sobre el capital en la apertura, la cancelación y la liberación, con tasa y cuenta (6412) en Ajustes; los intereses y la renovación sin dinero nuevo están exonerados (Informe SUNAT 025-2004-SUNAT/2B0000).
- Penalidad por cancelación anticipada en el asistente: va a su cuenta o rebaja el ingreso por intereses.
- Garantías con finalidad (carta fianza, alquiler, contrato o licitación), beneficiario, documento garantizado y vigencia; el aviso usa la vigencia cuando no hay vencimiento.
- Depósitos en moneda extranjera: aviso si sus cuentas no están marcadas para el cierre de tipo de cambio de la suite.
- Reportes Perú ▸ Tesorería ▸ Cartera vigente (entidad, moneda y mes de vencimiento) e Intereses devengados (por depósito y mes); cada asiento queda enlazado a su depósito.

## 1.20261010 — 10/10/2026

- Primera versión: depósitos a plazo, fondos en garantía y depósitos en garantía entregados con apertura, devengo mensual de intereses (TEA, base 360/365), vencimiento con aviso, cancelación (también anticipada), renovación manual o automática con o sin capitalización y liberación parcial de garantías; menú Perú ▸ Tesorería.
