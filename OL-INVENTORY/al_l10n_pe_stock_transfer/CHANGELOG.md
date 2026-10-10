Historial de cambios — PE - Traslados internos y bienes de terceros (AL)
========================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_stock_transfer.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 2.20261010 — 10/10/2026

- Catálogo 20 completo para la empresa: se añaden 02 Compra, 06 Devolución, 07 Recojo de bienes transformados, 08 Importación y 09 Exportación (anexo de la R.S. 240-2024/SUNAT); 13 «Otros» con descripción obligatoria que va en la guía; 08 y 09 exigen la DAM o DS.
- Guía en recepciones que traslada la empresa (02, 07, 08): parte del proveedor, llega al almacén y la empresa es destinataria.
- Motivo propuesto según la operación (04 entre establecimientos, 06 en devoluciones y al dueño de bienes de terceros, 02 en recepciones) o el que fije el tipo de operación.
- Partida y llegada propias con el RUC de la empresa y el código de establecimiento anexo en todas las guías; la guía impresa usa el mismo destinatario, punto de llegada y motivo que el XML.
- Datos de demostración «DEMO TRAS» (tools/stock_transfer_demo_data.py), capturas y guía funcional.

## 1.20261010 — 10/10/2026

- Primera versión: guía de remisión en transferencias internas entre establecimientos (motivo 04, destinatario = remitente, código de establecimiento anexo en partida y llegada) y bienes de terceros visibles en la transferencia, con filtros en existencias, movimientos y transferencias, y el propietario en las observaciones de la guía y en la guía impresa.
