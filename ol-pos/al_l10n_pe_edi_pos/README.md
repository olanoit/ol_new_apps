# PE - Comprobantes Electrónicos en el TPV (AL)

Facturación electrónica peruana desde el punto de venta de Odoo 19.

## Funcionalidad

- **Selector Boleta/Factura** en la pantalla de pago (junto al botón de
  cliente): diálogo de selección con **boleta por defecto**. La factura
  exige un cliente con RUC (11 dígitos); si no hay cliente, abre la
  selección al elegir factura y bloquea el cobro con aviso si falta.
- **Diario por tipo de documento**: en Ajustes → Punto de venta →
  Contabilidad, sección *Comprobantes electrónicos (Perú)*, se configura
  el **diario de boletas** (serie B###) y el **diario de facturas**
  (serie F###). La factura contable de la orden se crea en el diario del
  tipo elegido (`_prepare_invoice_vals`).
- **Toda venta emite CPE**: con ambos diarios configurados, al cobrar la
  orden se marca "a facturar" automáticamente.
- **Ticket con formato CPE**: el recibo del TPV replica el diseño del
  ticket 80mm de `al_l10n_pe_invoice` — encabezado con RUC, tipo y
  número de documento entre reglas, datos del cliente, detalle sin
  bordes verticales, desglose SUNAT (Op. gravadas/exoneradas/inafectas,
  ICBPER, IGV), importe en letras (SON:), pagos/vuelto y **QR de
  representación impresa** (R.S. 018-2005/SUNAT:
  `RUC|tipo|serie|folio|IGV|total|fecha|tipoDoc|nroDoc`), disponible en
  cuanto la factura se publica, sin esperar el CDR de SUNAT.

## Arquitectura

- `pos.order.l10n_pe_doc_type` viaja del frontend al backend con la
  sincronización estándar (pos.order carga todos sus campos).
- El recibo lee los datos fiscales del `account.move` que `read_pos_data`
  devuelve tras facturar (número, desglose `l10n_pe_edi_amount_*` de
  `al_l10n_pe_invoice`, importe en letras y QR); si imprime antes de la
  sincronización, cae a los totales del POS.
- El diálogo selector (`DocTypePopup`) sigue el mismo contrato awaitable
  (`makeAwaitable` + lista `{id, label, isSelected, item}`) que el
  selector de vendedor de referencia.
- Para compañías no peruanas (o TPV sin diarios configurados) el recibo
  reproduce el diseño estándar del core.

## Origen

Port a Odoo 19 del módulo v18 `al_l10n_pe_edi_pos` (farmaniacos),
combinado con los patrones de `extendrix_ticket_pos` (recibo OWL v19),
`extendrix_vendedor_pos` (selector) y `pos_journal_multi_choice`
(diario por tipo).
