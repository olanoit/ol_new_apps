Historial de cambios — Farmacia: convenios con EPS y empresas (AL)
==================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_pharmacy_insurance.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 3.20261027 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 2.20261019 — 19/10/2026

- Devoluciones en la caja: el paciente recupera solo lo que pagó y la parte cubierta vuelve a la aseguradora con el método del convenio.
- La liquidación resta las devoluciones de su periodo y emite una nota de crédito a la aseguradora si la venta ya se le facturó.
- Con redondeo de efectivo, se redondea solo el comprobante del paciente.
- Probado el XML de la boleta del paciente en una compañía peruana contra las reglas de cuadre de SUNAT.

## 1.20261019 — 19/10/2026

- Primera versión (mejora E10): convenios con EPS y empresas, cobertura en la caja, comprobante del paciente por su parte y liquidación con factura a la aseguradora.
