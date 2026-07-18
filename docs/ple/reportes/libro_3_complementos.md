[← Mapa de cobertura](README.md)

# Libro 3 — Formatos complementarios (PLE 3.8 / 3.9 / 3.19 / 3.23)

`l10n_pe_reports_lib` (EE) genera la mayor parte del Libro 3; estos cuatro
formatos faltantes los aporta `al_l10n_pe_ple` desde **Perú ▸ Libros PLE ▸
Exportar PLE**. El Libro 3 usa nombre de archivo con **día** (`AAAAMMDD` de
la fecha de los EEFF) y **oportunidad de presentación** (`CC`, 01–07),
ambos configurables en el wizard.

## 3.8 — Detalle de la cuenta 30 Inversiones mobiliarias (12 campos)

Captura en **Perú ▸ Libros PLE ▸ Inversiones 3.8** (Odoo no modela
títulos/valores): fecha del saldo, emisor (contacto, o solo nombre si es
extranjero sin documento → tipo doc `0`), código del título (tabla 15),
valor nominal unitario, cantidad, costo total en libros y provisión (en
positivo; el TXT la emite **negativa**). El wizard exporta los registros
cuya fecha coincide con la **fecha de los EEFF**.

| # | Campo | Fuente |
|---|---|---|
| 1 | Periodo `AAAAMMDD` | fecha EEFF del wizard |
| 2–3 | CUO / correlativo | id del registro / `M<id>` |
| 4–6 | Tipo doc, nº doc, nombre del emisor | contacto o `0`/`-`/nombre |
| 7 | Código del título (T15) | captura (2 díg.) |
| 8–10 | Valor nominal / cantidad / costo en libros | captura |
| 11 | Provisión (−) | captura, signo aplicado al exportar |
| 12 | Estado | `1` |

## 3.9 — Detalle de la cuenta 34 Intangibles (9 campos)

**Automático** desde `account.asset`: se incluyen los activos cuya cuenta
de activo empieza por **`34`** (PCGE), vigentes a la fecha de los EEFF.
Amortización acumulada = asientos de depreciación publicados hasta esa
fecha + importe importado (`already_depreciated_amount_import`), emitida en
negativo.

| # | Campo | Fuente |
|---|---|---|
| 1 | Periodo `AAAAMMDD` | fecha EEFF |
| 2–3 | CUO / correlativo | id del activo / `M<id>` |
| 4 | Fecha de inicio de la operación | `acquisition_date` |
| 5 | Cuenta contable | `account_asset_id.code` |
| 6 | Descripción | nombre del activo (40 car.) |
| 7 | Valor contable | `original_value` |
| 8 | Amortización acumulada (−) | depreciación publicada hasta la fecha EEFF |
| 9 | Estado | `1` |

## 3.19 — Estado de cambios en el patrimonio neto (16 campos)

Captura en **Perú ▸ Libros PLE ▸ Patrimonio 3.19**: una fila por **rubro**
(m2o al catálogo de rubros de `l10n_pe_reports_lib`, tabla 34; el catálogo
T22 se propone desde el sector del rubro) con las 12 columnas monetarias
del Anexo 2 (capital, acciones de inversión, capital adicional, resultados
no realizados, reservas legales, otras reservas, resultados acumulados,
diferencia de conversión, ajustes al patrimonio, resultado neto, excedente
de revaluación, resultado del ejercicio).

## 3.23 — Notas a los estados financieros (PDF)

Sin estructura TXT: la norma exige un **PDF**. El wizard permite adjuntarlo
y lo incluye en el ZIP con el nombre oficial
(`LE…032300CC<O><I><M>1.pdf`).

## Limitaciones

- 3.8 y 3.19 son de captura manual (importables con el importador
  estándar); deben cuadrar con el balance del ejercicio.
- 3.9 asume el prefijo de cuenta `34` del PCGE para identificar
  intangibles.
- Estados `8`/`9` no se generan automáticamente.
