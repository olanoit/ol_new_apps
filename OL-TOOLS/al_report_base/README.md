# Formato común de documentos impresos (AL)

Documentación: [Formato de los documentos impresos](../../mkdocs/content/developer/report_layout.md)

Módulo `al_report_base` para Odoo 19.

El formato del comprobante electrónico A4 para todos los documentos PDF de la
suite. Solo depende de `web`.

- `al_report_base.report_pe_page`: página completa (div `article`, encabezado,
  cuerpo del `t-call` y pie). Parámetros: `o`, `company`, `doc_title` y, opcionales,
  `doc_number`, `doc_extra`, `doc_address`, `page_class`.
- `report_pe_document_header` y `report_pe_document_footer`, para documentos que
  arman su propio `article`.
- `static/src/css/report_pe_document.css` (prefijo `pe-doc-`), en
  `web.report_assets_common` y `web.report_assets_pdf`.
- Papel `paperformat_pe_a4` y `paperformat_pe_a4_landscape`.

`al_account_base` conserva sus identificadores (`al_account_base.report_pe_document_header`
y `_footer`) como alias de estas plantillas.
