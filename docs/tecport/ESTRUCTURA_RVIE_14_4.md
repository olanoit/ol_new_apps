# Estructura oficial del formato RVIE 14.4

**Fuente:** Resolución de Superintendencia N.° 000112-2021/SUNAT, anexo publicado en
`https://www.sunat.gob.pe/legislacion/superin/2021/anexo-112-2021.pdf`, **Anexo N.º 2**
(«Información de la propuesta RVIE / estructura y reglas para elaborar el archivo plano»).
Extraído el 15/08/2026.

Trabajo en clean-room: esta es la fuente de verdad de la implementación.
Ver [FASE0_ACTA_LICENCIAS.md](FASE0_ACTA_LICENCIAS.md).

---

## Cuántos campos tiene el archivo: 33

El anexo describe 40 campos más un rango de campos libres, pero **el archivo no los lleva todos**.
La **nota 7** del anexo es explícita:

> «Cuando el generador complementa la Propuesta del RVIE deberá remitir información de los campos
> **del 1 al 33** y del 41 al 57. La estructura **no considerará los campos del 34 al 40**; es
> decir será una estructura de 51 campos.»

Y cada uno de los campos 34 a 40 repite en su regla:

> «Este campo no es considerado para la construcción del archivo de texto (txt).»

Los campos 41 a 57 son de libre utilización y, si no se usan, «no incluya ni la información ni los
palotes». **El archivo queda en 33 campos.**

Esto explica los dos desvíos encontrados:

| Implementación | Campos que emite | Desvío |
|---|---:|---|
| **Norma** | **33** | — |
| Odoo Enterprise 19 | 35 | **+2**: emite los campos 34 (`Tipo de Nota`) y 35 (`Est. Comp`), que la norma excluye |
| `tecport/l10n_pe` (v18) | 34 | **+1**: emite el campo 34 |
| `al_l10n_pe_ple` v4 | **33** | ✅ |

---

## Los 33 campos

| # | Nemotécnico | Long. | Formato | Descripción |
|---:|---|---|---|---|
| 1 | RUC | 11 | Numérico | RUC del generador |
| 2 | ID | Hasta 1500 | Alfanumérico | Razón social del generador |
| 3 | Periodo | 6 | Numérico | `AAAAMM` |
| 4 | CAR SUNAT | 29 | Alfanumérico | Código de Anotación de Registro; lo asigna SUNAT |
| 5 | Fecha de emisión | 10 | `DD/MM/AAAA` | |
| 6 | Fecha Vcto/Pago | 10 | `DD/MM/AAAA` | Obligatorio para el tipo de comprobante `14` |
| 7 | Tipo CP/Doc. | 2 | Alfanumérico | Tabla 3 del Anexo 1 |
| 8 | Serie del CDP | Hasta 20 | Alfanumérico | |
| 9 | Nro CP o Doc. (Nro Inicial Rango) | Hasta 20 | Alfanumérico | |
| 10 | Nro Final (Rango) | Hasta 20 | Alfanumérico | Anotación consolidada de operaciones diarias |
| 11 | Tipo Doc Identidad | 1 | Alfanumérico | Del cliente |
| 12 | Nro Doc Identidad | Hasta 15 | Alfanumérico | |
| 13 | Apellidos Nombres / Razón Social | Hasta 1500 | Alfanumérico | |
| 14 | Valor Facturado Exportación | 12,2 | Numérico | |
| 15 | BI Gravada | 12,2 | Numérico | Base imponible de la operación gravada |
| 16 | Dscto BI | 12,2 | Numérico | Descuento de la base imponible |
| 17 | IGV / IPM | 12,2 | Numérico | |
| 18 | Dscto IGV / IPM | 12,2 | Numérico | Descuento del IGV |
| 19 | Mto Exonerado | 12,2 | Numérico | |
| 20 | Mto Inafecto | 12,2 | Numérico | |
| 21 | ISC | 12,2 | Numérico | |
| 22 | BI Grav IVAP | 12,2 | Numérico | |
| 23 | IVAP | 12,2 | Numérico | |
| 24 | ICBPER | 12,2 | Numérico | |
| 25 | Otros Tributos | 12,2 | Numérico | |
| 26 | Total CP | 12,2 | Numérico | Importe total del comprobante |
| 27 | Moneda | 3 | Alfanumérico | Tabla 2 |
| 28 | Tipo Cambio | 1,3 | Numérico | |
| 29 | Fecha Emisión Doc Modificado | 10 | `DD/MM/AAAA` | |
| 30 | Tipo CP Modificado | 2 | Numérico | |
| 31 | Serie CP Modificado | Hasta 20 | Alfanumérico | |
| 32 | Nro CP Modificado | Hasta 20 | Alfanumérico | |
| 33 | ID Proyecto / Operadores / Atribución | Hasta 50 | Alfanumérico | Contratos de colaboración empresarial |

### Campos 34-40, que NO se emiten

`Tipo de Nota` (34), `Est. Comp` (35), uso interno de SUNAT (36 y 40),
`Valor OP Gratuitas` (37), `Tipo Operación` (38) e `Incal`/inconsistencias (39).
Aparecen en la propuesta que muestra SUNAT, a título referencial.

---

## Reglas de negocio recogidas

**Nota 3 — tipo de cambio.** Se usa el tipo de cambio **venta** de la fecha de emisión del
comprobante; para el tipo `14`, el de la fecha de vencimiento. En notas de crédito y débito se
utiliza el de la fecha de emisión **del documento que modifican**.

**Nota 4 — comprobantes anulados.** Los comprobantes electrónicos con CDR distinto de aceptado,
los que tienen baja comunicada y los físicos anulados **se anotan con importe cero (0.00)**: no se
excluyen del registro. Implementado.

**Notas de crédito de periodos anteriores.** Cuando una nota de crédito (tipo `07` u `87`)
rectifica un comprobante de un periodo **anterior**, su base e IGV se informan en los campos de
descuento **16 y 18** en vez de en el 15 y el 17. Implementado.

---

## Nomenclatura del archivo

Igual que el RCE (Tabla 6 del Anexo 1):

```
LE + RUC(11) + AAAA + MM + 00 + 140400 + CC + O + I + M + 2
```

Con el código de oportunidad `CC`:

| Código | Significado |
|---|---|
| 01 | Registro de ventas cuando **acepta** la propuesta |
| 02 | Registro de ventas cuando **reemplaza** la propuesta |
| 03 | Reporte de ajustes posteriores |
| 04, 05 | Ajustes de periodos anteriores al SIRE |

La implementación usa `02`, igual que Enterprise.

---

## Estado de la implementación

`al_l10n_pe_ple` v4.20260815, `models/rvie_report.py`. Extracción por ORM
(`l10n_pe.rce.extractor._rvie_moves`), porque el motor de Enterprise sufre el
[mismo fallo SQL](BUG_EE_RCE_SQL.md) que en el RCE.

Ejemplo real generado (factura de 1000 + IGV):

```
20512528458|Servicios Andinos Demo S.A.C.|202603||15/03/2026||01|FFI|1||6|20601034809|
CLIENTE DEMO S.A.C.|0.00|1000.00|0.00|180.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|
1180.00|PEN|||||||
```

**Signo de los importes:** en una venta el ingreso se anota al haber, así que el extractor invierte
el signo contable para que el registro informe positivos en facturas y negativos en abonos.

### Cobertura de tests

11 tests: número de campos y rechazo de estructuras inválidas, nomenclatura, importes positivos,
cabecera, anulado a cero, nota de crédito del mismo periodo (negativo), nota de crédito de periodo
anterior (a los campos de descuento), referencia al documento modificado, filtro de periodo y
archivo vacío.
