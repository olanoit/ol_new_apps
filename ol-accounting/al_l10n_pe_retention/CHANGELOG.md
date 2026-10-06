Historial de cambios — PE - Retenciones de IGV (AL)
===================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_retention.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 8.20260828 — 27/09/2026

- La retención solo se aplica a compras gravadas con IGV: quedan fuera los recibos por honorarios y las compras exoneradas o inafectas.
- El XML del comprobante de retención reparte el pago y la retención entre cada factura pagada, y en facturas en dólares informa el importe en dólares, la retención en soles y el tipo de cambio.
- El resumen 626 lista una fila por factura, con importes en soles.
- Una factura ya publicada conserva su marca de retención aunque luego cambie el padrón del proveedor.
- Retenciones sufridas: cada compañía ve solo las suyas; no se puede registrar dos veces el mismo comprobante, ni registrarlo con monto cero, sobre una factura que no sea de venta o sin saldo por cobrar, ni borrarlo una vez registrado.
- La tasa de retención de Ajustes debe coincidir con la del impuesto de retención.

## 14/09/2026

- Resumen 626: periodo por defecto en el mes anterior, aviso cuando no hay retenciones y resumen con cantidad y total retenido.

## 5.20260828 — 27/08/2026

- Las excepciones del régimen se toman del padrón SUNAT, fuente única y editable.

## 2.20260719 — 19/07/2026

- Retención en el pago, retenciones sufridas, XML CRE y resumen 626.
- Etiquetas en español, cuenta transitoria y guía funcional con diagramas.
