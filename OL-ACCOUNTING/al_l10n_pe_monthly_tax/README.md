# PE - Declaración mensual IGV y renta (621) (AL)

Documentación funcional: [Declaración mensual (621)](../../mkdocs/content/applications/finance/fiscal_localizations/peru/monthly_tax.md)

Módulo `al_l10n_pe_monthly_tax` para Odoo 19.

- `l10n_pe.tax.regime`: régimen tributario del RUC (General, MYPE Tributario,
  Especial) desde una fecha.
- `l10n_pe.monthly.tax`: un documento por compañía y periodo (borrador,
  calculado, declarado) con IGV, saldo a favor, percepciones y retenciones con
  arrastre y pago a cuenta del impuesto a la renta; asiento opcional del pago
  a cuenta.
- Lee las percepciones (`l10n_pe.perception.received`) y retenciones
  (`l10n_pe.retention.received`) sufridas si esos módulos están instalados;
  no depende de ellos.

Normas: art. 85 y 120 de la Ley del Impuesto a la Renta; art. 6 del
D. Leg. 1269 (MYPE Tributario).
