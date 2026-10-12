# PE - Retención de renta de 4.ª categoría (AL)

Documentación funcional: [Retención de renta de 4.ª categoría](../../mkdocs/content/applications/finance/fiscal_localizations/peru/fourth_category.md)

Módulo `al_l10n_pe_fourth_category` para Odoo 19.

- `account.move`: recibo por honorarios (`l10n_pe_fourth_category_receipt`,
  documento 02 de proveedor), evaluación (`_l10n_pe_fourth_category_evaluate`:
  agente → constancia vigente → tope en soles) y sincronización del impuesto
  de 4.ª en las líneas en borrador (formulario, `create`, `write` y `_post`).
  El estado guardado solo depende del propio recibo.
- `res.company`: agente, tasa, tope, cuenta (40172 por identificador del plan)
  e impuesto de retención creado bajo demanda (`_l10n_pe_fourth_category_tax`).
- `l10n_pe.fourth.category.suspension`: constancia del Formulario 1609 por
  prestador y compañía, vigente del día siguiente a su emisión al 31/12.
- `l10n_pe.fourth.category.report`: recibos pagados en el mes (fecha de la
  última conciliación) y archivo `.4ta` (estructura 20 del anexo 3 de la
  planilla electrónica).
- `l10n_pe.fourth.category.certificate` y reporte QWeb con
  `al_report_base.report_pe_page`: certificado anual de rentas y retenciones.
- Datos de demostración: `tools/fourth_category_demo_data.py`.

Pendiente: el archivo `.ps4` de prestadores (estructura no confirmada en
fuente oficial) y las notas de crédito sobre recibos por honorarios.
