# Hoja de trabajo del planificador de obra (AL)

Documentación funcional: [Pestaña Planificación y hoja de trabajo](../../mkdocs/content/applications/services/project/construction/planning/planning_worksheet.md)

Fase 21 del paquete de mejoras v1.5 del planificador de obra. Depende de
`documents_spreadsheet` (Odoo Enterprise) y se instala solo con el
planificador.

## Piezas

| Pieza | Qué hace |
|---|---|
| `project.project._construction_spreadsheet_data()` | Datos o-spreadsheet (versión 18.5): una pestaña por hoja de `master_import_layout.SHEETS` con sus encabezados y REFERENCIAS con dos listas de Odoo (`ODOO.LIST`) |
| `project.project.action_construction_open_spreadsheet()` | Crea o abre la hoja (`documents.document` con `construction_project_id`) |
| `documents.document.action_construction_send_to_planner(sheets)` | Arma un .xlsx con las pestañas del maestro y abre `construction.master.import.wizard` con su análisis |
| `static/src/send_to_planner.js` | Parche de `SpreadsheetAction` y menú Archivo ▸ Enviar al planificador (`topbarMenuRegistry`), visible solo en hojas de obra |
