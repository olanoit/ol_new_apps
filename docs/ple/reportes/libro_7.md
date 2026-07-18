[← Mapa de cobertura](README.md)

# Libro 7 — Registro de Activos Fijos (PLE)

Generado por `al_l10n_pe_ple` desde **Perú ▸ Libros PLE**. Libro **anual**
(el nombre de archivo consigna `MM=00`); fuente de datos: `account.asset`
(módulo EE `account_asset`) más los campos SUNAT de la pestaña **PLE SUNAT**
de la ficha del activo.

## Formatos y nombres de archivo

| Formato | Código | Archivo (ej. RUC 20512528458, ejercicio 2025) |
|---|---|---|
| 7.1 Activos revaluados y no revaluados | `070100` | `LE20512528458202500000701000011 11.txt` (sin espacios) |
| 7.3 Diferencia de cambio | `070300` | ídem con `070300` |
| 7.4 Arrendamiento financiero | `070400` | ídem con `070400` |

Patrón: `LE + RUC + AAAA + 00 + 00 + código + 00 + O + I + M + 1`
(`O`=indicador de operaciones del wizard, `I`=1 con datos / 0 vacío,
`M`=1 soles).

## Configuración previa

En cada activo (pestaña **PLE SUNAT**):

- **Código del activo (PLE)** — campo 5 del 7.1; si se omite se genera
  `AF<id>` automáticamente.
- **Tipo de activo (T18)** — obligatorio (el wizard rechaza la exportación
  si falta). Código de 1 dígito de la tabla 18 del Anexo 3 de SUNAT.
- **Estado del activo (T19)** — por defecto `1`.
- **Catálogo (T13)** — por defecto `9` (catálogo propio); 7.3/7.4 solo
  admiten `3` o `9`.
- Marca / modelo / serie-placa — se emiten `-` si están vacíos.
- **Método (T20)** y **% depreciación** se proponen desde el método de Odoo
  (lineal → `1`, % = 100/años) y son editables.
- Para 7.3: moneda de adquisición, valor en ME y TC de adquisición.
- Para 7.4: marcar «Arrendamiento financiero» + nº y fecha de contrato
  (obligatorios), inicio, cuotas y monto total.

## Mapeo campo a campo (7.1 — 37 campos)

| # | Campo SUNAT | Fuente Odoo |
|---|---|---|
| 1 | Periodo `AAAA0000` | ejercicio del wizard |
| 2 | CUO | `account.asset.id` |
| 3 | Correlativo | `M<id>` |
| 4 | Cód. catálogo (T13) | `l10n_pe_ple_catalog` (def. `9`) |
| 5 | Código del activo | `l10n_pe_ple_code` (def. `AF<id>`) |
| 6–7 | Catálogo/código UNSPSC | vacíos (opcionales) |
| 8 | Tipo de activo (T18) | `l10n_pe_asset_type` |
| 9 | Cuenta contable | `account_asset_id.code` |
| 10 | Estado del activo (T19) | `l10n_pe_asset_status` |
| 11 | Descripción | `name` (40 car.) |
| 12–14 | Marca / modelo / serie-placa | campos PLE (def. `-`) |
| 15 | Saldo inicial | `original_value` (+ mejoras previas) si adquirido antes del ejercicio |
| 16 | Adquisiciones | `original_value` si adquirido en el ejercicio |
| 17 | Mejoras | activos hijos (aumentos de valor) del ejercicio |
| 18 | Retiros/bajas | `original_value` si `disposal_date` cae en el ejercicio |
| 19–23 | Ajustes / revaluaciones | `0.00` (no gestionado en Odoo) |
| 24 | Fecha de adquisición | `acquisition_date` |
| 25 | Fecha inicio de uso | `prorata_date` (o adquisición) |
| 26 | Método depreciación (T20) | `l10n_pe_depre_method` |
| 27 | Doc. autorización cambio método | `l10n_pe_depre_auth_doc` (def. `-`) |
| 28 | % depreciación | `l10n_pe_depre_rate` |
| 29 | Deprec. acumulada ejercicio anterior | asientos de depreciación publicados con fecha < 01/01 + `already_depreciated_amount_import` |
| 30 | Deprec. del ejercicio | asientos de depreciación publicados del ejercicio |
| 31–36 | Deprec. de retiros/ajustes/revaluaciones | `0.00` (ver limitaciones) |
| 37 | Estado de operación | `1` |

## Mapeo 7.3 (15 campos)

Activos con **moneda de adquisición** configurada. Campos: periodo, CUO,
correlativo, catálogo (3/9), código, fecha de adquisición, valor ME
(`l10n_pe_fx_amount`), TC adquisición (`l10n_pe_fx_rate`, 3 dec.), valor MN
(`original_value`), TC al 31/12 (tasa de `res.currency.rate` a fin de
ejercicio — la alimenta `al_l10n_pe_currency`), ajuste por diferencia de
cambio (`ME × TC cierre − MN`), depreciación del ejercicio, dep. de retiros
(`0.00`), dep. otros ajustes (`0.00`), estado.

## Mapeo 7.4 (11 campos)

Activos con «Arrendamiento financiero» marcado: periodo, CUO, correlativo,
catálogo, nº contrato, fecha contrato, código del activo, inicio del
arrendamiento, nº cuotas, monto total del contrato, estado.

## Reglas de estado

Libro contable → estado `1` (operación del ejercicio). Los estados `8`/`9`
(regularizaciones de ejercicios anteriores) no se generan automáticamente;
de necesitarse, corregir el TXT manualmente antes de validar en el PLE.

## Limitaciones conocidas

- Revaluaciones, ajustes por inflación y sus depreciaciones (campos 19–23 y
  31–36) se emiten `0.00`: Odoo no modela revaluación de activos.
- La depreciación asociada a retiros/bajas (campo 31) se emite `0.00`; el
  asiento de baja de Odoo ajusta el gasto pero no se desglosa aquí.
- Activos totalmente depreciados y no dados de baja siguen apareciendo
  (correcto según SUNAT).
- Verificación final: cargar el TXT en el validador del PLE de SUNAT.
