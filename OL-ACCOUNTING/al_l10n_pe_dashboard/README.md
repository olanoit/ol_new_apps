# Tablero Perú (AL)

Documentación funcional: [Tablero de la app Perú](../../mkdocs/content/applications/finance/fiscal_localizations/peru/dashboard.md)

Tablero `spreadsheet.dashboard` «Perú» (grupo Finanzas) que abre la app Perú desde el menú
**Tablero** (`ir.actions.client` `action_spreadsheet_dashboard` con `params.dashboard_id`).

- `l10n_pe.dashboard.tax`: vista SQL de comprobantes publicados con base, IGV (apuntes con
  tributo 1000/1016) y total en soles, con signo de negocio (ventas y compras en positivo,
  notas de crédito en negativo).
- `l10n_pe.dashboard.builder`: arma el JSON de la hoja en Python. Cada bloque comprueba los
  modelos y campos que usa (`_has`) y que los lean los grupos del tablero (contable y
  auditor); si no, se omite. Se reescribe al instalar o actualizar el módulo
  (`<function>` en `data/dashboard_data.xml`) y en `_register_hook` cuando cambió el conjunto
  de módulos, salvo que el tablero tenga revisiones de la app Tableros (alguien lo editó).
- Las pruebas validan el JSON con `_check_spreadsheet_data` (modelos y campos) y que cada
  fuente responda con los permisos del contable y del auditor.
