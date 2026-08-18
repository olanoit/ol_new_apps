# Estructura oficial de los formatos RCE 8.4 y 8.5

**Fuente:** Resolución de Superintendencia N.° 040-2022/SUNAT, anexo publicado en
`https://www.sunat.gob.pe/legislacion/superin/2022/anexo-040-2022.pdf` (57 páginas), que modifica
la RS N.° 000112-2021/SUNAT. Extraído el 15/08/2026.

- **8.4** → Anexo C, «ANEXO 8. Información de la propuesta del RCE / estructura y reglas para
  elaborar el archivo plano que complementa la propuesta del RCE» → **41 campos**.
- **8.5** → Anexo D, «ANEXO 9. Información relativa a documentos de no domiciliados» → **35 campos**.

Este documento es la **fuente de verdad** de la implementación (trabajo en clean-room: no se
consulta el código del proyecto origen). Ver [FASE0_ACTA_LICENCIAS.md](FASE0_ACTA_LICENCIAS.md).

---

## Reglas generales

- Campos separados por `|` (pipe). Cada línea termina en `|` y el archivo usa CRLF.
- Importes: hasta 12 enteros y 2 decimales, sin separador de miles, punto decimal. Aceptan negativos.
- Fechas: `DD/MM/AAAA`.
- Periodo: `AAAAMM` en el 8.4 (campo 3) y en el 8.5 (campo 1).
- Nomenclatura del archivo (Tabla 13 del Anexo 1):
  `LE` + RUC(11) + `AAAAMM` + `00` + código de libro + correlativo(5) + indicadores + `.TXT`
  - 8.4 → código `080400`; 8.5 → código `080500`.
  - Ambos se entregan **dentro de un ZIP** con el mismo nombre base.
- Tablas de referencia del Anexo 1: **11** tipo de comprobante RCE, **12** reglas generales por tipo
  de comprobante, **7** estructura del CAR, **4** código de aduana, **2** moneda, **23**
  clasificación de bienes y servicios, **16** países, **17** vinculación económica,
  **18** convenios de doble imposición, **19** tipo de renta, **20** modalidad de servicio,
  **21** exoneraciones.

---

## Formato 8.4 — Registro de Compras (41 campos)

| # | Nemotécnico | Long. | Formato | Descripción |
|---:|---|---|---|---|
| 1 | RUC | 11 | Numérico | RUC del generador u obligado a llevar el Registro de Compras |
| 2 | ID | Hasta 1500 | Alfanumérico | Razón social o apellidos y nombres del generador |
| 3 | Periodo | 6 | Numérico | `AAAAMM`; 01 ≤ MM ≤ 12 |
| 4 | CAR SUNAT | 27 | Alfanumérico | Código de Anotación de Registro (tabla 7). Se completa automáticamente |
| 5 | Fecha de emisión | 10 | `DD/MM/AAAA` | Fecha de emisión del comprobante |
| 6 | Fecha Vcto/Pago | 10 | `DD/MM/AAAA` | Obligatorio si campo 7 ∈ {14, 46, 50, 51, 52, 53, 54} |
| 7 | Tipo CP/Doc. | 2 | Alfanumérico | Tabla 11. **No permite 91, 97, 98** |
| 8 | Serie del CDP | Hasta 20 | Alfanumérico | Serie; para DAM/DSI se consigna el código de aduana |
| 9 | Año | 4 | Numérico | Año de emisión de la DAM o DSI; si campo 7 ∈ {50, 52, 54}, > 1981 |
| 10 | Nro CP o Doc. | Hasta 20 | Alfanumérico | Número del comprobante |
| 11 | Nro Final (Rango) | Hasta 20 | Alfanumérico | Número final en anotación consolidada de operaciones diarias |
| 12 | Tipo Doc Identidad | 1 | Alfanumérico | Tipo de documento de identidad del proveedor |
| 13 | Nro Doc Identidad | Hasta 15 | Alfanumérico | RUC o documento de identidad del proveedor |
| 14 | Apellidos Nombres / Razón Social | Hasta 1500 | Texto | Del proveedor |
| 15 | BI Gravado DG | 12,2 | Numérico | Base imponible, adquisiciones **destinadas a gravadas** |
| 16 | IGV / IPM DG | 12,2 | Numérico | IGV de la base del campo 15 |
| 17 | BI Gravado DGNG | 12,2 | Numérico | Base imponible, adquisiciones **destinadas a gravadas y no gravadas** |
| 18 | IGV / IPM DGNG | 12,2 | Numérico | IGV de la base del campo 17 |
| 19 | BI Gravado DNG | 12,2 | Numérico | Base imponible, adquisiciones **destinadas a no gravadas** |
| 20 | IGV / IPM DNG | 12,2 | Numérico | IGV de la base del campo 19 |
| 21 | Valor Adq. NG | 12,2 | Numérico | Valor de las adquisiciones no gravadas |
| 22 | ISC | 12,2 | Numérico | Impuesto Selectivo al Consumo |
| 23 | ICBPER | 12,2 | Numérico | Impuesto a las bolsas de plástico |
| 24 | Otros Trib/Cargos | 12,2 | Numérico | Otros conceptos y cargos fuera de la base imponible |
| 25 | Total CP | 12,2 | Numérico | Importe total del comprobante. **Obligatorio** |
| 26 | Moneda | 3 | Alfanumérico | Tabla 2 |
| 27 | Tipo de Cambio | 1,3 | Numérico | Formato `#.###`, positivo |
| 28 | Fecha Emisión Doc Modificado | 10 | `DD/MM/AAAA` | Del comprobante original que se modifica |
| 29 | Tipo CP Modificado | 2 | Alfanumérico | Obligatorio si campo 7 ∈ {07, 08, 87, 88, 97, 98} |
| 30 | Serie CP Modificado | Hasta 20 | Alfanumérico | Ídem |
| 31 | COD. DAM o DSI | 3 | Alfanumérico | Código de dependencia aduanera (tabla 4) |
| 32 | Nro CP Modificado | Hasta 20 | Alfanumérico | Ídem campo 29 |
| 33 | Clasif de Bss y Sss | 1 | Numérico | Tabla 23. Solo obligados por nivel de ingresos |
| 34 | Operadores/Partícipes | Hasta 50 | Alfanumérico | Contrato o proyecto; varios separados por guion (`1-Identificador`) |
| 35 | PorcPart | — | Numérico | Porcentaje de participación en contratos de colaboración |
| 36 | IMB | 1 | Numérico | Indicador de mes de baja / operación |
| 37 | CAR Orig / Ind E o I | 27 | Alfanumérico | CAR del comprobante en ajustes posteriores, o indicador de exclusión/inclusión |
| 38 | Detracción | 1 | Alfanumérico | `D` si la operación está sujeta a detracción |
| 39 | Tipo de Nota | 2 | Alfanumérico | Tipo de nota de crédito o débito |
| 40 | Est. Comp | 1 | Numérico | Estado del comprobante (tabla 14) |
| 41 | Inconsistencias | Hasta 20 | Alfanumérico | Marcas de inconsistencia detectadas (INCAL) |

### Estado del comprobante (campo 40, Tabla 14)

| Código | Significado |
|---|---|
| 1 | Anotación en el periodo |
| 2 | Anotación extemporánea (comprobante de periodos anteriores) |
| 3 | Anotación de comprobante en periodo distinto / ajuste |

---

## Formato 8.5 — Registro de Compras, operaciones con sujetos no domiciliados (35 campos)

| # | Nemotécnico | Long. | Formato | Descripción |
|---:|---|---|---|---|
| 1 | Periodo | 6 | Numérico | `AAAAMM`, menor o igual al periodo a generar |
| 2 | CAR SUNAT | 27 | Alfanumérico | Se completa automáticamente |
| 3 | Fecha de emisión | 10 | `DD/MM/AAAA` | **Obligatorio** |
| 4 | Tipo CP/Doc. | 2 | Alfanumérico | **Solo 00, 91, 97, 98** (tabla 11) |
| 5 | Serie del CDP | Hasta 20 | Alfanumérico | Opcional |
| 6 | Nro CP o Doc. | Hasta 20 | Alfanumérico | **Obligatorio** |
| 7 | Val Adquisiciones | 12,2 | Numérico | Valor de las adquisiciones |
| 8 | Otros | 12,2 | Numérico | Otros conceptos adicionales |
| 9 | Total CP | 12,2 | Numérico | **Obligatorio** |
| 10 | Tipo CP CF | 2 | Numérico | Comprobante que sustenta el crédito fiscal; solo 00, 46, 50, 51, 52, 53 |
| 11 | Serie CP CF | Hasta 20 | Alfanumérico | Para DAM/DSI, código de aduana |
| 12 | Año | 4 | Numérico | Año de emisión de la DAM o DSI que sustenta el crédito fiscal |
| 13 | Nro CP CF | Hasta 20 | Alfanumérico | Número del comprobante que sustenta el crédito fiscal |
| 14 | Monto Ret | 12,2 | Numérico | Monto de retención del IGV |
| 15 | Moneda | 3 | Alfanumérico | Tabla 2 |
| 16 | Tipo de Cambio | 1,3 | Numérico | Si la moneda ≠ USD se consigna el tipo de cambio utilizado |
| 17 | País | 4 | Numérico | País de residencia del sujeto no domiciliado (tabla 16) |
| 18 | Razón social del sujeto | Hasta 100 | Texto | **Obligatorio** |
| 19 | Domicilio | Hasta 100 | Texto | Domicilio en el extranjero |
| 20 | ID sujeto | Hasta 15 | Texto | Identificación del no domiciliado. **Obligatorio** |
| 21 | ID beneficiario | Hasta 15 | Texto | Opcional |
| 22 | Razón Social del beneficiario | Hasta 100 | Texto | Opcional |
| 23 | País beneficiario | 4 | Numérico | Tabla 16 |
| 24 | Vínculo | 2 | Numérico | Tipo de vinculación económica (tabla 17) |
| 25 | Rta Bta | 12,2 | Numérico | Renta bruta |
| 26 | Deduc/Costo | 12,2 | Numérico | Deducción o costo de enajenación de bienes de capital |
| 27 | Rta Neta | 12,2 | Numérico | Renta neta |
| 28 | Tasa | 2 dec. | Numérico | Tasa de retención |
| 29 | Impto | 12,2 | Numérico | Impuesto retenido |
| 30 | Convenio | 2 | Numérico | Convenio para evitar la doble imposición (tabla 18) |
| 31 | Exon. | 1 | Numérico | Exoneración aplicada (tabla 21) |
| 32 | Tipo Rta | 2 | Numérico | Tipo de renta (tabla 19) |
| 33 | Mod Serv | 1 | Numérico | Modalidad del servicio prestado (tabla 20) |
| 34 | Art. 76 | 1 | Numérico | Aplicación del artículo 76 de la Ley del Impuesto a la Renta |
| 35 | CAR Orig | 27 | Alfanumérico | CAR del comprobante a modificar en ajustes posteriores |

---

## Contraste con la salida del proyecto origen

Los archivos de referencia exportados en la Fase 0 (ver [REFERENCIA_ESTRUCTURA.md](REFERENCIA_ESTRUCTURA.md))
**no cumplen el número de campos de la norma vigente**:

| Formato | Norma RS 040-2022 | Origen (v18) | Diferencia |
|---|---:|---:|---:|
| 8.4 | 41 campos | 38 | **−3** |
| 8.5 | 35 campos | 36 | **+1** |

Además, en la muestra del 8.5 del origen:

- El **campo 4 (Tipo CP/Doc.)** trae `01` (factura), cuando la norma solo admite `00`, `91`, `97` y `98`
  para operaciones con no domiciliados.
- El **número del comprobante** aparece en el campo 5 (Serie, opcional) y el campo 6
  (Nro CP, **obligatorio**) queda vacío — parecen invertidos.

No se ha verificado si el origen sigue una versión anterior del anexo. En cualquier caso, **la
implementación se ciñe a la norma vigente**, no a la salida del origen. Esto obliga a matizar de
nuevo el criterio de aceptación nº 1: para 8.4 y 8.5 la referencia estructural es **este documento**,
y los archivos del origen solo sirven para contrastar la *selección de comprobantes* y los
*importes*, no el número ni el orden de los campos.

---

## ⚠ Enterprise 19 ya genera 8.4 y 8.5 — corrección al análisis

Verificado en código el 15/08/2026. Los handlers de `l10n_pe_reports` **no** emiten los formatos
PLE clásicos que sus nombres de archivo sugieren, sino los del RCE:

| Archivo en EE | `_description` | `_get_report_number()` | Formato real |
|---|---|---|---|
| `account_ple_purchase_8_1.py` | «PLE Purchase Report 8.1 (Now RCE 8.4)» | `08040002` | **RCE 8.4**, oportunidad 02 (reemplaza la propuesta) |
| `account_ple_purchase_8_2.py` | «PLE Purchase Report 8.2 (Now RCE 8.5)» | `08050000` | **RCE 8.5**, no domiciliados |
| `account_ple_sales_14_1.py` | «PLE Sales Report 14.1 (Now RVIE 14.2)» | — | RVIE |

Esto corrige la premisa del [análisis inicial](ANALISIS_Y_PLAN_TECPORT_L10N_PE.md), que daba por
hecho que EE solo cubría los PLE 8.1/8.2/14.1 clásicos. El error vino de mirar los nombres de
archivo y el directorio `data/` en lugar de los números de reporte.

### Estado real del 8.4 en Enterprise

El handler emite **44 claves**: los **41 campos oficiales en el orden correcto**, más dos
heredados del 8.1 clásico y un campo técnico de cierre.

| Situación | Campos |
|---|---|
| ✅ Correctos y poblados | 1-10, 12-32 |
| ⚠ Presentes pero **siempre vacíos** | 11 (`last_payment_number`, «Related payment not implemented yet»), 33 `services`, 34 `contract_identification_OSIC`, 35 `percentage`, 36 `tax_mbl`, 37 `car_cp`, **38 `deduction` (detracción)**, 39 `refund_type`, **40 `payment_state` (estado del comprobante)**, 41 `inconsistencies` |
| ❌ **Sobran** (no existen en la norma) | 42 `date_cdd`, 43 `name_cdd` — fecha y número de la constancia de detracción, que eran los campos 32-33 del PLE 8.1 clásico |
| — | 44 `final_pipe`, campo técnico para el pipe de cierre |

Otros defectos verificados en `_get_file_txt()`:

- El **indicador de moneda** del nombre de archivo está **fijo a `1` (soles)**:
  `"LE%s%s%02d00%s1%s12"` — una compañía con contabilidad en dólares generaría un nombre incorrecto.
- El resto de la nomenclatura sí es correcta: `LE` + RUC + `AAAA` + `MM` + `00` + `080400` + `02`
  + `O` + `I` + `1` + `2`, que coincide con la Tabla 13.

### Consecuencia para la Fase 3

**No hay que reimplementar el 8.4 ni el 8.5**, sino **completar el handler de Enterprise**:
quitar los 2 campos sobrantes, poblar los 9 vacíos y corregir el indicador de moneda.

Al implementarlo apareció un obstáculo mayor: el motor de consulta de Enterprise
(`_get_ple_report_data`) **está roto** y hace fallar los tres reportes con un error SQL. Ver
[BUG_EE_RCE_SQL.md](BUG_EE_RCE_SQL.md). La extracción se reescribió con el ORM
(`al_l10n_pe_ple/models/rce_extractor.py`), manteniendo la ficha de `account.report` de
Enterprise para la interfaz.

---

## Estado de la implementación

`al_l10n_pe_ple` v4.20260815. Ambos formatos generados y verificados sobre la base `ol_pe_v19`.

| Aspecto | 8.4 | 8.5 |
|---|---|---|
| Campos emitidos | **41** ✅ | **35** ✅ |
| Nombre de archivo | `LE…080400 02 1 1 1 2` ✅ | `LE…080500 00 1 1 1 2` ✅ |
| Indicador de moneda | correcto (soles/dólares) ✅ | ✅ |
| Extracción | ORM, sin SQL crudo ✅ | ✅ |

Ejemplo real generado (8.4, factura de 1000 + IGV):

```
20512528458|Servicios Andinos Demo S.A.C.|202603||09/03/2026||01|F001||2644||6|20601034809|
EUROCAPITAL SERVICIOS FINANCIEROS S.A.C.|1000.00|180.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|
0.00|1180.00|PEN|||||||5|||||||1||
```

### Campos poblados que Enterprise dejaba vacíos

| # | Campo | Origen del dato |
|---|---|---|
| 33 | Clasificación de bienes y servicios | `product.template.l10n_pe_rce_classification` (tabla 23), propagada a la factura por el importe de mayor peso |
| 38 | Detracción | `al_l10n_pe_detraction` si está instalado; se emite `D` |
| 39 | Tipo de nota | `l10n_pe_edi_refund_reason`, solo en comprobantes que modifican otro |
| 40 | Estado del comprobante | derivado del estado del asiento y del tipo de documento (tabla 14) |

### Campos que siguen vacíos, y por qué

- **4 y 37 (CAR)**: los asigna SUNAT, no el contribuyente.
- **11 (nº final del rango)**: solo aplica a la anotación consolidada de operaciones diarias.
- **34, 35 (operadores y % de participación)**: contratos de colaboración empresarial, no modelados.
- **36 (IMB)**, **41 (inconsistencias)**: los determina SUNAT.
- **8.5, campos 21-29 y 31**: beneficiario efectivo y liquidación de la renta de no domiciliados;
  son opcionales en la norma y dependen de un cálculo de retención de renta que Odoo no modela.

### Defectos del proyecto origen que no se heredan

| Defecto en tecport | Aquí |
|---|---|
| 8.4 con 38 campos | 41 ✅ |
| 8.5 con 36 campos | 35 ✅ |
| 8.5 con tipo de comprobante `01` (no admitido) | solo 00/91/97/98 ✅ |
| 8.5 con el número en el campo 5 y el 6 (obligatorio) vacío | número en el campo 6 ✅ |

### Cobertura de tests

59 tests en `al_l10n_pe_ple`, todos en verde. Los del RCE cubren: número de campos y rechazo de
estructuras inválidas, nomenclatura del archivo en sus cinco indicadores, formato de importes /
tipos de cambio / fechas / texto saneado, separación 8.4 ↔ 8.5 por tipo de comprobante, filtro de
periodo, y los campos 33 y 40.

---

## Cobertura ya existente en la suite `al_*`

`al_l10n_pe_sire` (módulo propio) ya implementa el mapeo de los 41 campos del 8.4 en
`_sire_parse_row()` de `models/sire_rce.py`, construido en su día desde el manual oficial de
servicios web del SIRE. Coincide campo a campo con la tabla de arriba (sus `cols[0..40]` son los
campos 1 a 41). Es código propio y reutilizable sin restricción, y es el punto de partida natural
para el generador del 8.4.

También aporta las constantes de negocio ya validadas:

- `RCE_EXCLUDED_DOC_TYPES = ('02', '91', '97', '98')` — los recibos por honorarios van al RHE.
- `RCE_SELF_ISSUED_DOC_TYPES = ('46', '50', '51', '52', '53', '54')` — el CAR usa el RUC del adquiriente.
- `RCE_DUE_DATE_DOC_TYPES = ('14', '46', '50', '51', '52', '53', '54')` — fecha de vencimiento obligatoria (campo 6).
