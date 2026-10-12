# PE - Cheques recibidos y girados (AL)

Documentación funcional: [Cheques recibidos y girados](../../mkdocs/content/applications/finance/accounting/checks.md)

Módulo `al_l10n_pe_check` para Odoo 19, sobre `l10n_latam_check` (nativo, LGPL).

- `models/account_chart_template.py`: cuentas 1033001, 1689001 y 1049001 y los
  diarios CHQT y CHQR en la plantilla `pe`; `_post_load_data` completa el
  método «Cheques propios» de los bancos.
- `res.company._l10n_pe_check_setup()`: lo mismo en compañías existentes
  (`post_init_hook`), idempotente.
- `l10n_latam.check`: `_check_issuer_vat` acepta RUC, DNI o carné de extranjería
  en Perú; `l10n_pe_presentation_deadline` (Ley 27287, arts. 199 y 207) y
  `_l10n_pe_presentation_warnings`, usados por el asistente de transferencia.
- Datos de demostración en `models/al_pe_demo.py` (`_load_demo_check`).
