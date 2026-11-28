Historial de cambios — PE - Comprobantes Electrónicos (AL)
==========================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`AAAAMMDD.N`).

Generado desde `docs/fichas/al_l10n_pe_invoice.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 20261128.30 — 28/11/2026

- En un Comprobante electrónico (A4) de varias páginas, los totales salen una sola vez, al final del detalle; antes se repetían al pie de cada página. Lo mismo en un ticket largo.

## 20261126.29 — 26/11/2026

- El recuadro gris del A4 admite avisos de una sola fila (leyenda de percepción).

## 20261126.28 — 26/11/2026

- Comprobante electrónico (A4) con diseño nuevo: importe total destacado en un bloque de totales a la derecha, con el importe en letras a su izquierda; columnas del detalle marcadas con líneas verticales y sin rayas entre filas; datos del cliente más juntos y con el nombre en negrita.
- En el A4, Condición, Tipo de cambio, Vendedor y pedido solo aparecen cuando tienen valor; la detracción va en un recuadro gris propio con sus datos en columnas, y el QR lleva su leyenda y el resumen de la firma.
- Ticket de 80 mm con diseño nuevo: importe total grande entre dos reglas, cada línea con la descripción a todo el ancho y debajo «cantidad × precio», cabecera del detalle sin fondo gris, datos del cliente en dos columnas y QR más grande.

## 20261126.26 — 26/11/2026

- El detalle del Comprobante electrónico (A4) se completa con filas en blanco cuando tiene pocas líneas, para que no se vea compacto. El mínimo (10 por defecto) se cambia en Ajustes ▸ Perú ▸ Comprobantes electrónicos ▸ Filas mínimas del detalle; con 0 no se agregan.

## 20261126.25 — 26/11/2026

- El botón Vista previa de la factura y el portal del cliente muestran el formato Comprobante electrónico (A4), igual que Imprimir y el envío por correo; la descarga desde el portal sin PDF generado también. Si el cliente o el diario tienen otro formato elegido, manda ese.

## 20261126.24 — 26/11/2026

- Los formatos se llaman «Comprobante electrónico (A4)» (antes CPE A4) y «Comprobante electrónico (ticket)» (antes CPE Ticket) en el menú Imprimir y en el envío por correo.

## 20261126.23 — 26/11/2026

- Facturas de compañías peruanas: el botón Imprimir y el envío por correo usan por defecto el formato CPE A4. Si el cliente o el diario tienen otro formato elegido, manda ese. CPE A4 y CPE Ticket se pueden elegir como formato de factura en el cliente y en el diario.

## 20261027.22 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 20261018.21 — 18/10/2026

- Las líneas sin producto (descuento de una NC, intereses de una ND) imprimen «Servicio» en la columna Unidad, como la unidad ZZ del XML.

## 20261011.20 — 11/10/2026

- El XML de la factura informa la retención del IGV del cliente agente como cargo/descuento global con el código 62 del catálogo 53 (MultiplierFactorNumeric, importe y base), el mismo importe que rebaja el neto pendiente.

## 20261011.19 — 11/10/2026

- El «Monto neto pendiente de pago» y las cuotas (XML y PDF A4 y ticket) ya no incluyen la retención del IGV cuando el cliente es agente de retención (R.S. 193-2020/SUNAT, numeral 2.1).

## 20261008.18 — 08/10/2026

- Ticket: datos de la compañía al final (nombre, R.U.C., domicilio fiscal, teléfono, correo y web).

## 20261008.17 — 08/10/2026

- Encabezado común (plantilla al_account_base.report_pe_document_header): nombre de la compañía, domicilio fiscal, teléfono y correo con etiqueta y recuadro R.U.C./tipo/número; más espacio entre el encabezado y la primera sección.
- Tablas de datos solo con el borde exterior (sin líneas entre filas); las líneas quedan solo en las tablas de detalle.
- Pie de página común en cada página: compañía, R.U.C., domicilio, contacto, fecha de impresión y «Página X de Y».
- Comprobante A4 con el estilo común de los comprobantes PE en blanco y negro: encabezado con recuadro R.U.C./tipo/número, datos del adquirente en tabla, y líneas, totales, importe en letras, detracción e información adicional con QR en una sola tabla; cuotas y cuentas bancarias con la misma cabecera gris.
- Ticket 80 mm: recuadro del documento con R.U.C., cabecera gris oscuro del detalle y totales e importe en letras en la misma tabla.

## 20261008.16 — 08/10/2026

- La pestaña «Documentos EDI» (estado del envío al OSE, errores y descarga del XML) pasa a «Facturación PE ▸ Envío electrónico» y la ve el equipo de facturación, no solo el modo desarrollador.

## 20261008.15 — 08/10/2026

- Ajustes por compañía con el ícono de Odoo «valores por compañía» (company_dependent).

## 20261008.14 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).

## 20261007.13 — 07/10/2026

- La página «Peruvian EDI» de l10n_pe_edi se reemplaza por «Facturación PE ▸ Comprobante electrónico» (motivos y leyendas), con la OC externa; la detracción va detrás. Test de estructura del formulario.

## 20261007.12 — 07/10/2026

- Corregido: al facturar a un contacto de una empresa, el A4 imprimía el nombre del contacto y su documento (vacío); ahora muestra la empresa y su RUC, como el XML y el QR.
- Corregido: las notas de crédito y débito ya no imprimen forma de pago ni cuadro de cuotas, que el XML no lleva.
- A crédito, el A4 y el ticket muestran el monto neto pendiente de pago (total menos detracción) y las cuotas, como exige la R.S. 193-2020/SUNAT; el ticket no mostraba ninguno de los dos.

## 20260828.11 — 27/09/2026

- Las exportaciones y las operaciones gratuitas tienen su propia fila en el pie (**Op. exportación**, **Op. gratuitas**): antes la exportación no se sumaba y lo gratuito salía como «otros tributos», y el PDF no cuadraba con el XML.
- La fila **Descuento** muestra el descuento real sin IGV, tanto el porcentaje por línea como el descuento global; antes salía 0.00 o no salía.
- Las notas de crédito y de débito imprimen el **documento que modifican** y el **motivo**, también en A4 (la nota de débito antes no lo mostraba en ningún formato).
- Las cuotas de crédito se siguen viendo al reimprimir una factura ya pagada (antes salía una sola cuota de 0.00).
- La moneda se imprime según el documento (una factura en euros ya no dice «SOLES») y el IGV muestra la tasa aplicada, por ejemplo **IGV (10%)**.

## 14/09/2026

- Certificados digitales dentro de la sección **Comprobantes electrónicos** de la configuración de la app Perú.

## 20260828.8 — 28/08/2026

- Los certificados digitales, antes solo en Contabilidad, también desde la app Perú.

## 20260827.7 — 27/08/2026

- El descuento global vuelve a imprimirse; en Odoo 19 salía siempre en cero.
- Pruebas del desglose de IGV, exonerado, inafecto e ICBPER, moneda extranjera, notas de crédito, cuotas y descuento.

## 20260719.6 — 25/07/2026

- Versión para Odoo 19: formatos A4 y ticket, QR del XML firmado, monto en letras nativo y desglose tributario almacenado.
