Historial de cambios — Costeo de piezas por medida (AL)
=======================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_mrp_piece_costing.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 2.20261023 — 23/10/2026

- Paquete 1.11, M111-12: los retazos declarados en el corte salen a su costo fijo, que se descuenta del valor de su tablero antes de repartir el resto entre las piezas.

## 1.20261017 — 17/10/2026

- Refactorización del costeador de piezas CNC de Allcenter (`allcenter_mrp_costeo_pieza` 0.4.1) con la misma lógica, en la suite y con pruebas.
