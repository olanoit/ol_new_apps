# PE - Retenciones de IGV (AL)

Régimen de Retenciones del IGV (R.S. 037-2002/SUNAT) sobre el marco
nativo de Odoo 19 (`l10n_account_withholding_tax`).
**Guía funcional:** [`docs/retenciones.md`](docs/retenciones.md) ·
**Plan:** [`docs/retencion/PLAN_MODULO_al_l10n_pe_retention.md`](../docs/retencion/PLAN_MODULO_al_l10n_pe_retention.md) ·
**Demo/validación:** [`tools/retention_demo_data.py`](tools/retention_demo_data.py).

## Qué hace

- **Agente de retención (compras)**: aplicabilidad automática en la
  factura (3 %, > S/ 700, excepciones SUNAT: agente-agente, buen
  contribuyente, boleta, detracción); el impuesto de retención se
  inyecta al publicar (sin alterar el total) y el wizard de pago propone
  el **3 % de cada pago** (parciales incluidos), asentando la retención
  en la cuenta 4011x. Numeración del comprobante (`R001-…`) al emitir el
  pago y **XML CRE** (UBL, borrador sin firma) desde el pago.
- **Proveedor retenido (ventas)**: registro de retenciones sufridas →
  asiento 40114 conciliado con la factura.
- **Reportes**: Resumen mensual TXT para el F.V. 626 y marca de
  retención en el PLE 8.3 (campo 26).
- Menú **Perú ▸ Retenciones IGV** (efectuadas / sufridas / resumen).

## Pruebas

```bash
./odoo-bin -c cfg/my/pe.cfg -d ol_pe_v19 -u al_l10n_pe_retention \
  --test-enable --test-tags /al_l10n_pe_retention --stop-after-init
```
