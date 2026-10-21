# PE - Impresión de cheques (AL)

Documentación funcional: [Cheques recibidos y girados ▸ Imprimir cheques propios](../../mkdocs/content/applications/finance/accounting/checks.md)

Módulo técnico `al_l10n_pe_check_printing`:

- `l10n_pe.check.layout`: tamaño de la hoja y posiciones en mm; crea y mantiene su
  `report.paperformat` (custom, sin márgenes, 96 dpi, sin smart shrinking).
- `account.journal.l10n_pe_check_layout_id`.
- Reporte sobre `l10n_latam.check` (solo `own_checks`): `ir.actions.report._render_qweb_pdf`
  pone en el contexto el formato de papel del formato del diario y `get_paperformat` lo usa.
  Prueba de impresión con `data={'l10n_pe_test_layout_id': …}`.
- Plantilla: un `div.article` por cheque con posiciones absolutas en mm; el `<style>` que
  quita el relleno del contenedor va **dentro** del article (Odoo arma el PDF solo con esos
  nodos). Verificado con `pdftotext -bbox`: cada dato a ≤ 0,3 mm de su posición.
- `report_action(..., config=False)`: el cheque no usa el diseño de documentos.

Origen: proceso P10 de `docs/pagos/ANALISIS_PAGOS_INVERAGRO.md`.
