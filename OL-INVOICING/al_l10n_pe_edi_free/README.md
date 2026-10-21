# PE - Operaciones gratuitas en el CPE (AL)

Documentación funcional: [Operaciones gratuitas](../../mkdocs/content/applications/finance/fiscal_localizations/peru/electronic_invoicing/free_transfers.md)

Módulo técnico `al_l10n_pe_edi_free`. Completa lo que `l10n_pe_edi` (Odoo 19
Enterprise) trae para las transferencias gratuitas, contrastado con las reglas
de validación de SUNAT del 26.08.2026 (`docs/anticipos/oficial/`).

| # | Caso | Odoo 19 | Con el módulo |
|---|---|---|---|
| G1 | Gratuita exonerada o inafecta (21, 31-37) | Solo «0% Gra»: el ítem se cobra y la afectación por defecto es 11 (3111) | Grupo `sale_tax_free_exempt_group` (9996 0 % + «-Base»), afectación 37 |
| G2 | Afectación 37 | Fuera de `FREE_AFFECTATION_REASONS`: precio y código 01 (3234) | Gratuita |
| G3 | Leyenda 1002 | A mano; sin ella el «-Base» sale como tributo vacío | Se pone y se quita al publicar (2416) |
| G4 | Factura de total 0 con plazo | «Credito» con importe 0 | Contado, sin plazo |
| G5 | Valor referencial 0, IGV incoherente con la afectación, ítem gratuito cobrado | Rechazo en SUNAT | `UserError` al publicar (2641, 3110, 3111) |

El botón **Transferencia gratuita** (`action_l10n_pe_free_transfer`) convierte
la factura en borrador. Referencia de uso: `inveragro_factura` (v16), que lo
resolvía reescribiendo los totales de las líneas; aquí se usa el mecanismo
nativo de v19 (grupos de impuestos con «-Base» y la leyenda 1002).

Pruebas: `tests/test_free_transfer.py` con el validador de
`al_l10n_pe_edi_downpayment_discount/tests/sunat_rules.py` más las reglas de
gratuitas (2640, 3234, 3110, 3111, 3276, 3302, 2416).
