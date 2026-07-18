[← Mapa de cobertura](README.md)

# Libro 4 — Retenciones incisos e) y f) Art. 34 LIR (PLE 4.1)

Generado por `al_l10n_pe_ple` desde **Perú ▸ Libros PLE ▸ Exportar PLE**.
Libro **mensual** (código `040100`, nombre de archivo con `MM` del periodo).

## Fuente de datos

Odoo no tiene nómina peruana, por lo que las retenciones se **capturan** en
**Perú ▸ Libros PLE ▸ Retenciones 4.1** (lista editable, importable con el
importador estándar de Odoo). Cada registro: fecha de pago/retención,
prestador (contacto con tipo y nº de documento), monto bruto y retención
efectuada — ambos **en positivo**; el exportador aplica el signo.

## Estructura (10 campos)

| # | Campo SUNAT | Fuente Odoo |
|---|---|---|
| 1 | Periodo `AAAAMM00` | wizard (ejercicio + mes) |
| 2 | CUO | id del registro de captura |
| 3 | Correlativo | `M<id>` |
| 4 | Fecha de pago/retención | `date` |
| 5 | Tipo doc. identidad (T2) | `l10n_latam_identification_type_id.l10n_pe_vat_code` (fallback: 6 si RUC de 11 dígitos, 0 en otro caso) |
| 6 | Nº documento | `partner_id.vat` |
| 7 | Apellidos y nombres | `partner_id.name` (100 car.) |
| 8 | Monto bruto | `gross_amount` |
| 9 | Retención efectuada | `-withheld_amount` (**negativa o 0.00**) |
| 10 | Estado de operación | `1` |

## Limitaciones

- Estados `8`/`9` (regularizaciones) no se generan automáticamente.
- Si en el futuro se instala una nómina peruana, este modelo puede poblarse
  desde recibos por honorarios/planilla en lugar de captura manual.
