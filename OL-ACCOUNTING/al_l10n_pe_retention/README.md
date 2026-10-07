# PE - Retenciones de IGV (AL)

Régimen de Retenciones del IGV (R.S. 037-2002/SUNAT) sobre el marco
nativo de Odoo 19 (`l10n_account_withholding_tax`).
**Guía funcional:** [`docs/retenciones.md`](docs/retenciones.md) ·
**Plan:** [`docs/retencion/PLAN_MODULO_al_l10n_pe_retention.md`](../../docs/retencion/PLAN_MODULO_al_l10n_pe_retention.md) ·
**Demo/validación:** [`tools/retention_demo_data.py`](tools/retention_demo_data.py).

## Qué hace

- **Agente de retención (compras)**: la factura queda «comprendida en el
  régimen» salvo las excepciones SUNAT (agente de retención o de
  percepción, buen contribuyente, comprobante distinto de 01/08/12,
  operación sin IGV, detracción). El impuesto de retención se inyecta al
  publicar (sin alterar el total) y el asistente de pago propone el **3 % de
  cada pago** (parciales incluidos). **Monto mínimo** (art. 12): no se
  retiene si los comprobantes pagados juntos suman S/ 700 o menos; si
  superan el mínimo se retiene aunque cada factura sea menor. En moneda
  extranjera, al T.C. venta oficial de la fecha del pago.
- **Comprobante de Retención Electrónico (tipo 20)**: numeración `R001-…` al
  emitir el pago, XML UBL 2.0, **firma y envío** con el proveedor de
  `l10n_pe_edi` (IAP, SUNAT directo —servicio de retenciones— o
  Estela/Digiflow), ZIP con el CDR y **representación impresa** (PDF).
- **Compatibilidad con Odoo 20**: misma interfaz que el módulo oficial
  `l10n_pe_edi_withholding` (Enterprise 19.4/20): campos
  `l10n_pe_edi_status`, `l10n_pe_edi_warnings`,
  `l10n_pe_edi_attachment_file`, `l10n_pe_edi_retention_number`,
  `l10n_pe_edi_is_required`; métodos `_l10n_pe_edi_get_retention_breakdown`,
  `_l10n_pe_edi_generate_retention_bstr`, `action_l10n_pe_edi_send_retention`…;
  modelo `account.edi.xml.ubl_pe_withholding`; impuesto
  `purchase_tax_withholding_3` y secuencia
  `l10n_pe_edi_withholding_sunat_sequence` con los xmlids oficiales (un
  impuesto ya configurado recibe el xmlid en vez de duplicarse). Diferencia
  deliberada: retenemos el 3 % del importe **con IGV**, como manda la norma
  (los XML de prueba oficiales retienen sobre la base sin IGV).
- **Proveedor retenido (ventas)**: registro de retenciones sufridas →
  asiento 40114 conciliado con la factura.
- **Reportes**: Resumen mensual TXT para el F.V. 626 y marca de
  retención en el PLE 8.3 (campo 26).
- Menú **Perú ▸ Retenciones IGV** (efectuadas / sufridas / resumen).

## Pendiente

Reversión del CRE (resumen diario de reversiones), letras y compensaciones
como momento del pago, descuento de una nota de crédito posterior en la
siguiente retención. El módulo oficial de Odoo 20 tampoco implementa la
reversión (solo reserva el estado «cancelled»). Ver
`docs/retencion/INVESTIGACION_APPS_Y_NORMA.md`.

## Pruebas

```bash
./odoo-bin -c cfg/my/pe.cfg -d ol_pe_v19 -u al_l10n_pe_retention \
  --test-enable --test-tags /al_l10n_pe_retention --stop-after-init
```
