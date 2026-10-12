Historial de cambios — PE - Base Contabilidad (AL)
==================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_account_base.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 15.20261012 — 12/10/2026

- Modelo `al.pe.demo` con las ayudas comunes de los datos de demostración de la suite (compañía «PE Company» de l10n_pe, xmlids sin actualizar, diarios sin documentos electrónicos, RUC con dígito verificador).

## 14.20261012 — 12/10/2026

- Notas de crédito y débito cuyo comprobante original no está en Odoo: pestaña «Comprobante modificado» con tipo, serie, número y fecha, que usan el PLE y el SIRE (_l10n_pe_modified_document).
- Total de la DAM o DSI (_l10n_pe_customs_total): base + IGV + otros derechos, común al PLE y al SIRE.

## 13.20261011 — 11/10/2026

- Retención del IGV del cliente agente (_l10n_pe_customer_retention): 3 % del comprobante de más de S/ 700, sin detracción, con IGV y si la compañía no es agente ni buen contribuyente; la usan el comprobante impreso, el XML y el factoring.
- Reparto de esa retención entre las cuotas (_l10n_pe_retention_split), el mismo en el PDF y en el XML.

## 12.20261011 — 11/10/2026

- El encabezado, el pie y la hoja de estilos de los comprobantes impresos pasan a al_report_base, común a todos los documentos de la suite; las plantillas de este módulo quedan como alias.

## 11.20261011 — 11/10/2026

- Los accesos de Ajustes ▸ Perú ▸ Documentación llevan a la nueva organización del sitio: documentación para usuarios, novedades, localización y nómina peruanas y sección del desarrollador.

## 10.20261011 — 11/10/2026

- Sección «Documentación» al final de Ajustes ▸ Perú: URL del sitio de documentación de la suite (MkDocs) y accesos a guías funcionales, novedades, contabilidad, planillas y documentación técnica.

## 9.20261009 — 09/10/2026

- Etiqueta más corta en el diario: «Excluir del PLE» (el detalle pasa a la ayuda).

## 8.20261008 — 08/10/2026

- Encabezado común (plantilla al_account_base.report_pe_document_header): nombre de la compañía, domicilio fiscal, teléfono y correo con etiqueta y recuadro R.U.C./tipo/número; más espacio entre el encabezado y la primera sección.
- Tablas de datos solo con el borde exterior (sin líneas entre filas); las líneas quedan solo en las tablas de detalle.
- Pie de página común en cada página: compañía, R.U.C., domicilio, contacto, fecha de impresión y «Página X de Y».
- Hoja de estilos común de los comprobantes impresos PE (report_pe_document.css, prefijo pe-doc-): blanco y negro, encabezado con logo y recuadro R.U.C./tipo/número, tablas con borde redondeado y cabecera gris oscuro; la usan la factura A4, la guía de remisión y el comprobante de retención.

## 7.20261008 — 08/10/2026

- Ícono propio de la app Perú en el menú principal (logo de la Marca Perú).

## 6.20261008 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).

## 5.20261007 — 07/10/2026

- Factura: nuevas páginas «Facturación PE» y «Contabilidad PE», cada una con pestañas internas donde los módulos de la localización ponen sus datos (anclas l10n_pe_invoicing_notebook, l10n_pe_accounting_notebook y «Registros electrónicos»). «Contabilidad PE» no se muestra en ventas.

## 4.20260815 — 27/09/2026

- El botón **Restablecer a borrador** ya no aparece en los asientos bloqueados con hash ni en los comprobantes que exigen solicitar la anulación a SUNAT: allí el sistema lo rechazaba igualmente con un error.

## 3.20260815 — 14/09/2026

- Configuración de la app Perú en cinco secciones, con la nueva sección **Contabilidad** de atajos a la configuración nativa.
- Orden del primer nivel de la app: Tipo de cambio, Letras de cambio, Detracciones, Retenciones IGV, SIRE, Libros PLE, Kardex y Configuración.

## 2.20260815 — 18/08/2026

- Naturaleza del diario y exclusión de los libros electrónicos.
- Código SUNAT del banco y establecimiento anexo, con validación de formato.

## 1.20260717 — 19/07/2026

- Glosa en asientos y apuntes, menú raíz Perú y aplicación Perú en Ajustes.
