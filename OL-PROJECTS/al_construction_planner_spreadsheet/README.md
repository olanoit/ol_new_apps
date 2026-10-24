# Hoja de trabajo del planificador de obra (AL)

Documentación funcional: [Pestaña Planificación y hoja de trabajo](../../mkdocs/content/applications/services/project/construction/planning/planning_worksheet.md)

Requerimiento CREVAL v1.0, 6.7: presupuesto, APU y plan de la obra en una hoja de
cálculo de Documentos (Odoo Enterprise) con las hojas del libro de carga (6.6,
asistente `construction.budget.book.wizard` de `al_construction_planner_sale`).
Se instala solo con el puente de ventas del planificador y `documents_spreadsheet`.
El maestro de mobiliario vive en `al_construction_planner_spreadsheet_furniture`.

## Piezas

| Pieza | Qué hace |
|---|---|
| `documents.document` | Vínculo con la obra y la cotización, tipo de hoja, versión; servicios de la hoja: enviar, validar, costos vigentes, traer de Odoo, nueva versión |
| `project.project`, `sale.order` | Plantilla de presupuesto y plan, botón «Hoja de trabajo» y carpeta Presupuestos › cotización |
| `static/src/send_to_planner.js` | Menú «Planificación de obra» de la hoja (y «Archivo › Enviar al planificador» del maestro de mobiliario) |
| `migrations/4.20261016` | Las hojas existentes pasan a ser maestros de mobiliario |
