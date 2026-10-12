# PE - Pagos masivos a proveedores (AL)

Documentación funcional: [Pagos masivos a proveedores](../../mkdocs/content/applications/finance/accounting/batch_payments.md)

Módulo `al_l10n_pe_batch_payment` para Odoo 19 (Enterprise: `account_batch_payment`).

- Método de pago `pe_bank_txt` en los lotes de pago salientes; el formato sale de
  `res.bank.l10n_pe_batch_format` del banco del diario.
- `models/bank_formats.py`: funciones puras por banco (BCP, BBVA, Interbank,
  Scotiabank, Banco de la Nación), sin `env`, probadas sin base de datos.
- `res.partner.bank.l10n_pe_cci` (20 dígitos) y `l10n_pe_account_kind`.
- Controles en `check_payments_for_errors` y archivo en `_generate_export_file`
  (patrón de NACHA de Odoo).
- BCP: archivo de proveedores de Telecrédito (cabecera con marca del ITF, abono
  con modalidad y registro 3 por comprobante); `group_by_beneficiary` junta los
  pagos al mismo proveedor y cuenta. Opciones `l10n_pe_batch_itf_exempt`,
  `l10n_pe_batch_validate_idc` y `l10n_pe_batch_documents` en el diario.
- Cuenta preferida: `res.partner.bank._l10n_pe_preferred` elige la del proveedor
  en el banco del diario (pago y asistente de registro de pagos).

Los bancos no publican sus especificaciones: valide el primer archivo con el banco.
Datos de demostración: `tools/batch_payment_demo_data.py`.
