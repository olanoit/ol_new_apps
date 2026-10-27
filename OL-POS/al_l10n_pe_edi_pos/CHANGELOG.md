Historial de cambios — PE - Comprobantes Electrónicos en el TPV (AL)
====================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_edi_pos.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 17.20261027 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 16.20261019 — 19/10/2026

- Las tarjetas de regalo y las recargas del monedero ya no llevan el impuesto inafecto: no entran en el comprobante (Informe SUNAT 097-2010). Lo hace el nuevo módulo al_l10n_pe_pos_loyalty, que se instala solo.
- El ticket con formato de comprobante admite líneas, pagos y notas que otros módulos ajustan para que diga lo mismo que el comprobante.

## 15.20261018 — 18/10/2026

- También la recarga del monedero electrónico de Odoo lleva el impuesto inafecto, aunque no haya un programa de monedero.

## 14.20261018 — 18/10/2026

- Las tarjetas de regalo y las recargas del monedero llevan el impuesto inafecto: sin impuesto la boleta no se emitía y una venta cobrada con Niubiz o Culqi quedaba pagada pero sin cerrar en la caja.

## 13.20261008 — 14/10/2026

- Con el pago en línea del TPV (QR que el cliente paga en su teléfono), el ticket ya no deja el TPV en blanco: el encabezado de l10n_pe_edi_pos leía la factura antes de que llegara.

## 12.20261008 — 08/10/2026

- Etiquetas en español: los campos sin etiqueta propia (Activo, Nombre, Compañía, contadores…) y los heredados de Odoo (Creado por, Mensajes, Actividades…) ya no se muestran en inglés.

## 11.20261008 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).

## 10.20261007 — 07/10/2026

- «Emisión SUNAT retenida» pasa a «Facturación PE ▸ Comprobante electrónico».

## 9.20261007 — 07/10/2026

- Corregido: se podía emitir factura a un cliente con 11 dígitos cuyo tipo de documento no es RUC (SUNAT la rechaza); ahora se exige el tipo RUC en caja y en el servidor.
- Una boleta sin cliente va al Consumidor Final anónimo (antes la venta no se sincronizaba).
- El ticket muestra todos los totales del XML (ISC, IVAP, gratuitas, exportación, otros tributos) y la tasa real del IGV.
- Si el comprobante electrónico no llegó a emitirse, el ticket lo indica y no muestra un número inventado.
- El QR del ticket usa el documento de la empresa cliente, como el XML.

## 8.20261006 — 06/10/2026

- Corregido: una boleta elegida en caja para un cliente con RUC salía como factura (tipo 01) numerada en la serie de boletas, y SUNAT la rechazaba (error 1001). Ahora el tipo de comprobante es siempre el elegido en caja.

## 7.20260721 — 27/09/2026

- Devoluciones: la nota de crédito de una factura se emite en el diario de facturas (antes caía en el de boletas); devolver un «Recibo» sin comprobante ya no genera un comprobante electrónico.
- El ticket CPE convive con el ticket estándar en vez de reemplazarlo: el ticket normal vuelve a mostrar redondeo, descuentos, dirección de la compañía y lo que añaden otros módulos (fidelización, restaurante, importe en letras de Odoo).
- El ticket CPE muestra el redondeo de efectivo y el vendedor de la venta.
- El QR del ticket se genera en la propia caja: sale también sin conexión y siempre a tiempo para la impresión.
- Una serie de boletas ya no puede numerar una factura (ni al revés), y solo se usan series publicadas.
- Textos del diálogo de comprobante preparados para traducción.

## 25/07/2026

- Versión para Odoo 19: diálogo de comprobante con serie fija por caja, diario por tipo, validación de RUC, emisión retenida y ticket con formato CPE.
