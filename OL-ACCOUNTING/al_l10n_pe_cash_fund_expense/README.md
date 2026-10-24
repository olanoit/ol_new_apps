# PE - Gastos de empleados con caja chica (AL)

Documentación funcional: [Entregas a rendir y caja chica](../../mkdocs/content/applications/finance/accounting/cash_fund.md#gastos-de-la-app-gastos-pagados-con-un-fondo)

Módulo `al_l10n_pe_cash_fund_expense`, puente automático entre la app Gastos
(`hr_expense`) y `al_l10n_pe_cash_fund`. Un gasto pagado por el empleado con una
caja chica o una entrega a rendir se registra como la factura de su proveedor,
con su tipo y número de comprobante, y una rendición del fondo la paga
(requerimiento CREVAL v1.0, corrección CR-14).

## Campos

| Modelo | Campo | Uso |
|---|---|---|
| `hr.expense` | `l10n_pe_cash_fund_id` | Fondo abierto con el que se pagó |
| `hr.expense` | `l10n_latam_document_type_id`, `l10n_pe_document_number` | Comprobante del proveedor |
| `res.company` | `l10n_pe_expense_journal_id` | Diario de compras con documentos de esas facturas |
