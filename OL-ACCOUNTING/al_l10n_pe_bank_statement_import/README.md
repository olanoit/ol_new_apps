# PE - Extractos de bancos peruanos (AL)

Documentación funcional: [Extractos de bancos peruanos](../../mkdocs/content/applications/finance/accounting/bank_statements_pe.md)

Módulo técnico `al_l10n_pe_bank_statement_import` (Enterprise: depende de
`account_bank_statement_import_csv`):

- `models/statement_parser.py`: funciones puras. `read_rows` (XLSX con openpyxl, XLS con
  xlrd, HTML con lxml, texto con `csv.Sniffer`), `find_header` (sinónimos normalizados en
  las primeras 40 filas), `parse_amount` / `parse_date` y `parse_statement` (orden
  cronológico, saldos inicial y final, `unique_import_id` estable con desempate por orden).
- `account.journal._import_bank_statement`: si el archivo se reconoce, sigue el flujo base con
  el contexto `l10n_pe_bank_statement`, que hace que `_check_file_format` del módulo CSV lo
  deje pasar y que `_parse_bank_statement_file` lo lea; si no, el mapeo nativo.

Origen: proceso P11 de `docs/pagos/ANALISIS_PAGOS_INVERAGRO.md` (extractos; la recaudación
queda pendiente de la especificación de cada banco).
