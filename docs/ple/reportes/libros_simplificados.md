[← Mapa de cobertura](README.md)

# Formatos simplificados — PLE 5.2 / 5.4 / 8.3 / 14.2

Generados por `al_l10n_pe_ple` desde **Perú ▸ Libros PLE ▸ Exportar PLE**.
Libros **mensuales**, **excluyentes** con los formatos completos (5.1/5.3,
8.1, 14.1 de `l10n_pe_reports` EE): solo aplican a contribuyentes
autorizados a llevar contabilidad simplificada.

## Habilitación

**Ajustes ▸ Perú ▸ «Libros PLE simplificados»** (campo
`l10n_pe_ple_simplified` en la compañía). Sin la bandera, el wizard rechaza
estos formatos y su grupo permanece oculto.

## 5.2 — Libro Diario de Formato Simplificado (21 campos, como el 5.1)

Una línea por **apunte contable** de los asientos publicados del mes (todos
los diarios): cuenta, moneda (tabla 4, código ISO), tipo de comprobante
(`l10n_latam_document_type_id` o `00`), serie/folio (último grupo de
dígitos del número del documento, igual criterio que EE), fechas contable /
vencimiento / operación, **glosa** (glosa de línea o del asiento —
`l10n_pe_gloss` de `al_account_base` — o referencia), debe/haber y estado
`1`. CUO = id del asiento; correlativo = `M<id de línea>`.

## 5.4 — Detalle del Plan Contable (8 campos, como el 5.3)

Todas las cuentas activas de la compañía: código, descripción, código de
plan `01` (PCGE, tabla 17) y estado `1`. Periodo `AAAAMM01`.

## 8.3 — Registro de Compras Simplificado (32 campos)

Facturas y notas de crédito de proveedor publicadas del mes. El número del
CdP se toma de la **referencia del proveedor** (`ref`). Montos: BI gravada
(base con IGV), IGV/IPM, ICBPER (impuestos cuyo nombre contiene «ICBPER»),
otros conceptos (base sin IGV); total = suma de los cuatro. Notas de
crédito en **negativo**. TC a 3 decimales solo si el documento no está en
soles. Campos opcionales de detracción/retención/errores se emiten vacíos.

## 14.2 — Registro de Ventas Simplificado (26 campos)

Facturas y notas de crédito de cliente publicadas del mes; mismos criterios
de montos/signos/TC que el 8.3, con los datos del comprobante modificado
(campos 20–23) resueltos desde `reversed_entry_id` para las NC.

## Limitaciones

- El desglose de impuestos usa una heurística (base con/sin IGV + nombre
  «ICBPER»): operaciones mixtas gravadas/exoneradas en un mismo documento
  se agrupan según si el documento lleva IGV. Para casuística tributaria
  compleja usar los formatos completos de EE.
- Estados distintos de `1` (0/2/6/7/8/9) no se generan automáticamente.
- Documentos anulados no se incluyen (solo asientos publicados).
