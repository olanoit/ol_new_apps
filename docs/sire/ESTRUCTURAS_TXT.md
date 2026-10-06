# SIRE: estructuras de los archivos planos que el contribuyente sube

Este documento copia lo que dicen las normas en `docs/sire/oficial/`. Las fuentes son:

| Sigla | Norma | Archivo |
|---|---|---|
| **112** | R.S. 112-2021/SUNAT: anexo 1 (tablas 1 a 10) y anexos 2 a 7 del RVIE | `oficial/anexo-112-2021.*` |
| **040** | R.S. 040-2022/SUNAT: cuerpo, que crea el RCE (art. 8-A y 9-A) | `oficial/040-2022.*` |
| **040-An** | Anexos de la R.S. 040-2022, que contienen: A (tablas 4, 7 y 10 modificadas), B (tablas 11 a 23), C a H (anexos 8 a 13) | `oficial/anexo-040-2022.*` |
| **138** | R.S. 138-2023/SUNAT, que modifica las tablas 1, 3, 5, 7 y 8, los anexos 2 a 5 (RVIE) y los anexos 8, 12 y 13 (RCE) | `oficial/Resolucion-000138-2023-*` |

Cuando la 138 cambia una regla, se indica con **[138]**. La 138 solo publica las filas que modifica (el resto aparece como «(…)»). Por eso, en cada campo rige el texto de la 138 si lo hay y, si no, el de la norma original.

Convenciones del documento: «Oblig.» = obligatorio y «CP» = comprobante de pago. Los números de tabla se refieren siempre al **anexo N.° 1** de la R.S. 112-2021, con las tablas que le añadió la 040-2022.

---

## 0. Reglas comunes

### 0.1 Separador y formatos (tabla 5 RVIE / tabla 12 RCE)

> «Los campos deben estar separados por el carácter "|" (conocido como pipe o palote). Adicionalmente, dichos archivos deben ser generados con los nombres que se detallan en [la tabla 6 (RVIE) / la tabla 13 (RCE)].»

| N° | Aspecto | Regla RVIE (tabla 5) | Regla RCE (tabla 12) |
|---|---|---|---|
| 1 | Monto negativo | Consignar el formato `- #.##` | Consignar el formato `- #.##` |
| 2 | Texto | Texto libre entre palotes. No debe contener los caracteres `\|`, `/`, `\` | igual |
| 3 | Alfanumérico | Letras en mayúsculas y minúsculas (de la A a la Z) y los caracteres especiales `( ) , .` | Letras en mayúsculas y minúsculas (de la A a la Z), **números** y los caracteres especiales `( ) , . -` |
| 4 | Fecha | Igual al periodo informado | Igual o menor al periodo informado |

Los importes se expresan como «hasta 12 enteros y hasta 2 decimales». El RCE y los anexos 5 y 13 añaden «sin comas de miles». El tipo de cambio va con «1 entero y 3 decimales» (`#.###`).

Ninguna de las cuatro normas regula el pipe final de línea, la codificación de caracteres ni el salto de línea.

### 0.2 Tipo y número de documento de identidad (tabla 5 / tabla 12)

| Cód. | Descripción (RCE) | Long. | Tipo | Longitud | Módulo 11 |
|---|---|---|---|---|---|
| 0 | Doc. trib. no dom. sin RUC («OTROS» en el RVIE) | 15 | A | V | – |
| 1 | DNI | 08 | N | F | – |
| 4 | Carnet de extranjería | 12 | A | V | – |
| 6 | RUC | 11 | N | F | M |
| 7 | Pasaporte | 12 | A | V | – |
| A | Céd. diplomática de identidad | 15 | N | F | – |
| B | Doc. identidad país residencia - no dom. | 15 | A | V | – |
| C | TIN - Doc. trib. PP.NN | 15 | A | V | – |
| D | IN - Doc. trib. PP.JJ | 15 | A | V | – |
| E | TAM - Tarjeta Andina de Migración | 15 | A | V | – |
| F | PTP - Permiso temporal de permanencia | 15 | A | V | – |
| G | **[138]** Salvoconducto (en el RVIE, tablas 1 y 5) | 15 | A | V | – |

En la tabla, A = alfanumérico (solo letras y números), N = numérico, F = longitud fija y V = longitud variable.

**[138], nota de la tabla 5:** si la factura (tipo 01) lleva un guion (-) en el tipo de documento del adquiriente, en los supuestos del inc. a) del num. 17.2 del art. 17 de la R.S. 097-2012 o del inc. a) del párr. 19.2 del art. 19 de la R.S. 117-2017, el RVIE lleva un guion (-) en «Tipo de Documento de Identidad del cliente» y en «Número de RUC o Documento de Identidad del cliente».

### 0.3 CAR (tabla 7, texto de 040-An anexo A y [138])

El CAR tiene **27 posiciones (an27)**:

| Parte | Longitud | Formato |
|---|---|---|
| RUC o documento de identidad del emisor | 11 | Alfanumérico |
| Tipo de CP o documento | 2 | Numérico |
| Serie | 4 | Alfanumérico |
| Número | 10 | Alfanumérico |

Reglas de construcción:

- Si el documento tiene menos de 11 dígitos, se completa con ceros a la izquierda. Si tiene más, se toman los 11 dígitos de la derecha.
- La serie o el número más cortos se completan con ceros a la izquierda. Si son más largos, se toman los dígitos de la derecha.
- Una serie o un número vacíos se completan con ceros.
- RCE, tipos 46, 50, 51, 52, 53 y 54: se usa el RUC del importador, del usuario del servicio (no domiciliados) o del retenedor (liquidación de compra).
- RC no domiciliados, tipos 00, 91, 97 y 98: se usa el documento del proveedor no domiciliado.
- Anotación consolidada: se usan los datos del primer comprobante del rango.
- **[138]** Si un ajuste posterior genera un CAR nuevo, el CAR se crea automáticamente.

En todos los archivos que se suben, el campo «CAR SUNAT» se envía **vacío** y lo completa SUNAT. Hay dos excepciones: el anexo 8 en sus variantes «incluir información» y «excluir/incluir», donde el CAR es obligatorio, y el campo «CAR Orig» de los ajustes.

> Discrepancia de la norma: el anexo 2 original (112) indica una longitud de 29 para el CAR. La [138] la corrige a 27.

### 0.4 Envío por servicio web (anexo 6 de la 112)

El servicio recibe un ZIP con un único archivo, junto con el hash SHA-256 del archivo de texto. Usa el método POST, que devuelve un ticket, y el método GET para consultar ese ticket. El token es OAuth 2.0 (JWT) con la clave SOL.

---

## 1. Nombres de archivo

### 1.1 Libros electrónicos (tabla 6 RVIE / tabla 13.1 RCE)

Patrón: `LE RRRRRRRRRRR AAAA MM DD LLLLLL CC O I M G [NN] .TXT`

| Posición | Nemotécnico | Significado |
|---|---|---|
| 01-02 | `LE` | Identificador fijo |
| 03-13 | `RRRRRRRRRRR` | RUC del deudor tributario |
| 14-17 | `AAAA` | Año |
| 18-19 | `MM` | Mes |
| 20-21 | `DD` | `00` para el RVIE y el RCE |
| 22-27 | `LLLLLL` | Código de libro: `140400` (RVIE), `080400` (RCE), `080500` (RC no domiciliados) |
| 28-29 | `CC` | Oportunidad (ver la tabla siguiente) |
| 30 | `O` | Indicador de operaciones: `0` cierre de operaciones por baja de inscripción en el RUC; `1` empresa o entidad operativa; `2` cierre del libro por no estar obligado a llevarlo |
| 31 | `I` | Contenido: `1` con información; `0` sin información |
| 32 | `M` | Moneda: `1` soles; `2` US dólares |
| 33 | `G` | `2` fijo («Generado por el SIRE/MIGE IGV») |
| 34-35 | `NN` | Correlativo de los ajustes posteriores (solo en los ajustes) |

> La tabla 6 del RVIE (112) define el correlativo en la posición «34-34 N», pero los nombres de esa misma tabla terminan en `NN`. La tabla 13 del RCE lo define como «34-35 NN».

Valores de `CC`:

| CC | RVIE (tabla 6) | RCE (tabla 13) |
|---|---|---|
| 00 | – | RC no domiciliados informado |
| 01 | Acepta la propuesta | Acepta la propuesta |
| 02 | Reemplaza la propuesta | Reemplaza la propuesta |
| 03 | Ajustes posteriores | Ajustes posteriores |
| 04 | Ajustes de periodos anteriores al SIRE, formato general | igual |
| 05 | Ajustes de periodos anteriores al SIRE, formato simplificado | igual |
| 06 | – | Ajustes de periodos anteriores al SIRE, RC no domiciliados |

Nombres que fija la norma:

| Caso | Nombre | Estructura |
|---|---|---|
| RVIE cuando acepta la propuesta | `LERRRRRRRRRRRAAAAMM0014040001OIM2.TXT` | (la genera SUNAT) |
| RVIE cuando reemplaza la propuesta | `LERRRRRRRRRRRAAAAMM0014040002OIM2.TXT` | Anexo 3 |
| RVIE ajustes posteriores | `LERRRRRRRRRRRAAAAMM0014040003OIM2NN.TXT` | Anexo 4 |
| RVIE ajustes de periodos anteriores, general | `LERRRRRRRRRRRAAAAMM0014040004OIM2NN.TXT` | Anexo 5.1 |
| RVIE ajustes de periodos anteriores, simplificado | `LERRRRRRRRRRRAAAAMM0014040005OIM2NN.TXT` | Anexo 5.2 |
| RCE cuando acepta la propuesta | `LERRRRRRRRRRRAAAAMM0008040001OIM2.TXT` | (la genera SUNAT) |
| RCE cuando reemplaza la propuesta | `LERRRRRRRRRRRAAAAMM0008040002OIM2.TXT` | Anexo 11 |
| RCE ajustes posteriores | `LERRRRRRRRRRRAAAAMM0008040003OIM2NN.TXT` | Anexo 12 (8.4) |
| RCE ajustes de periodos anteriores, general | `LERRRRRRRRRRRAAAAMM0008040004OIM2NN.TXT` | Anexo 13 (5.1) |
| RCE ajustes de periodos anteriores, simplificado | `LERRRRRRRRRRRAAAAMM0008040005OIM2NN.TXT` | Anexo 13 (5.3) |
| RC no domiciliados | `LERRRRRRRRRRRAAAAMM0008050000OIM2.TXT` | Anexo 9 |
| RC no domiciliados, ajustes posteriores RCE | `LERRRRRRRRRRRAAAAMM0008050003OIM2NN.TXT` | Anexo 12 (8.5) |
| RC no domiciliados, ajustes de periodos anteriores al SIRE | `LERRRRRRRRRRRAAAAMM0008050004OIM2NN.TXT` | Anexo 13 (5.2) |

> Discrepancia de la norma: para el último caso, la tabla 13 da el nombre con `CC = 04`, pero su leyenda define `06` como «Reporte de Ajustes Posteriores de periodos anteriores al SIRE - Registro de Compras - Información de Operaciones con sujetos No Domiciliados». Ningún texto de la 040 ni de la 138 resuelve la contradicción.
>
> El archivo de **comparación** con la propuesta (anexo 3 RVIE / anexo 11 RCE) usa la misma estructura que el reemplazo. La norma no le asigna un nombre propio.

### 1.2 Archivos de complemento (tabla 6 RVIE / tablas 13.2 y 13.3 RCE)

| Caso | Nombre | Estructura |
|---|---|---|
| RVIE: complementar la propuesta con CP físicos | `RRRRRRRRRRR-CPF-AAAAMM-Correlativo.txt` | Anexo 2 |
| RCE: incluir CP no propuestos («Importación de comprobantes de pago», 13.2) | `RRRRRRRRRRR-CP-AAAAMM-Correlativo.txt` | Anexo 8, columna «Incluir CP» |
| RCE: información complementaria de CP de la propuesta (13.3) | `RRRRRRRRRRR-RCECOM-AAAAMM-Correlativo.tx` (sic) | Anexo 8, columna «Incluir/modificar/reubicar» |
| RCE: inclusión o exclusión de CP propuestos (13.3) | `RRRRRRRRRRR-RCEINEX-AAAAMM-Correlativo.tx` (sic) | Anexo 8, columna «Excluir/incluir excluidos» |
| RCE: tipo de cambio no publicado por la SBS (13.3) | `RRRRRRRRRRR-RCETCA-AAAAMM-Correlativo.txt` | Anexo 10 |

La extensión `.tx` de RCECOM y RCEINEX aparece así en la norma, sin la «t» final. Es casi seguro una errata, porque el anexo 10 usa `.txt` y su ejemplo es `20000000001-RCETCA-202201-01.txt`.

Posiciones de los nombres:

- CPF y CP: 01-11 RUC, 12 `-`, 13-15 `CPF`/`CP`, 16 `-`, 17-20 AAAA, 21-22 MM, 23 `-`, 24-25 correlativo, que empieza en 01 y llega hasta el último envío.
- 13.3: 01-11 RUC, 12 `-`, 13-18 identificador (`RCECOM` / `RCEINEX` / `RCETCA`), 19 `-`, 20-23 AAAA, 24-25 MM, 26 `-`, 27-28 correlativo.

> Las posiciones fijas no cuadran con todos los identificadores: `CP` tiene 2 caracteres y no 3, y `RCEINEX` tiene 7 y no 6. Conviene construir el nombre como `RUC-ID-AAAAMM-NN.txt` y no por posiciones.

La 040 permite usar un mismo archivo plano para incluir información, incluir CP y excluir. El tipo de cambio del anexo 10, en cambio, «debe enviarse en un archivo plano distinto» (art. 8-A.2.1 b).

---

## 2. RVIE: comparación o reemplazo de la propuesta (anexo 3)

`LE…0014040002OIM2.TXT`. Lleva los campos **1 a 33** y **41 a 57 (CLU)**. Los campos 34 a 40 no se informan: según la nota 4 del anexo, «son completados automáticamente a partir de la información que obra en los sistemas informáticos de la Administración» **[138]**.

La [138] amplió la nota 1: el anexo sirve para reemplazar la propuesta «o realizar la comparación entre la propuesta del RVIE y el archivo del generador».

| N° | Descripción / nemotécnico | Long. | Formato | Reglas |
|---|---|---|---|---|
| 1 | RUC del generador (RUC) | 11 | Numérico | Oblig. |
| 2 | Razón social del generador (ID) | Hasta 1500 | Alfanumérico | Oblig. Debe pertenecer al RUC del campo 1 **[138]** |
| 3 | Periodo | 6 | Numérico | Oblig. Formato `YYYYMM`, 01≤MM≤12. Periodo del RVIE a generar. **[138]** Si el campo 7 = 14, el periodo es el mes y año que señale la normativa del IGV |
| 4 | CAR SUNAT | (27) | Alfanumérico | Consignar vacío; se completa automáticamente |
| 5 | Fecha de emisión | 10 | Alfanumérico | Oblig. `DD/MM/AAAA`. YYYYMM ≤ periodo a informar y ≤ periodo del campo 3 |
| 6 | Fecha de vencimiento o de pago | 10 | Alfanumérico | `DD/MM/AAAA`. Oblig. si el campo 7 = 14: la fecha de vencimiento o la de pago, la que ocurra primero, y como máximo el mes siguiente al periodo del campo 3 |
| 7 | Tipo de CP/doc. | 2 | Alfanumérico | Oblig. Validar con la tabla 3 |
| 8 | Serie del CDP o de la máquina registradora | Hasta 20 | Alfanumérico | Tabla 3; regla general por tipo de documento (tabla 5) |
| 9 | Nro. CP o nro. inicial (rango) | Hasta 20 | Alfanumérico | Tabla 3; regla general (tabla 5). Para el IVAP, la constancia de depósito |
| 10 | Nro. final (rango) | Hasta 20 | Alfanumérico | Solo si el tipo es 00, 03, 12, 13, 18, 87 u 88; vacío en los demás. Desde el 01/07/2016, las boletas (03) de S/ 700 o más van en detalle. **[138]** Se permite la consolidación diaria de boletas y, desde el 01/10/2023, de los documentos tipo 18 que no dan derecho a crédito fiscal |
| 11 | Tipo de documento de identidad del cliente | 1 | Alfanumérico | Oblig. **(5)**, salvo: a) campo 7 ∈ {00, 05, 06, 07, 08, 11, 12, 13, 14, 15, 16, 18, 19, 23, 28, 30, 34, 35, 36, 37, 55, 56, 64, 87, 88}; b) campo 7 ∈ {07, 08, 87, 88} y campo 30 ∈ {03, 12, 13, 14, 36}; c) campo 14 > 0.00; d) campo 26 < 700.00 y campo 7 ∈ {03, 12} **[138]**: obligatorio si esos documentos tienen identificación; e) campo 10 no vacío. En esos casos es opcional y no acepta el valor 0. Validar con las tablas 1 y 5 **[138]** |
| 12 | Nro. RUC o doc. de identidad del cliente | Hasta 15 | Alfanumérico | Vacío si el CP no lo consigna. Mismas excepciones que el campo 11. Reglas de la tabla 5 |
| 13 | Razón social del cliente | Hasta 1500 | Alfanumérico | Mismas excepciones que el campo 11. Persona natural: apellido paterno, apellido materno y nombre completo. Vacío si el CP no lo consigna |
| 14 | Valor facturado de la exportación | 12,2 | Numérico | Positivo; negativo `- #.##` si el campo 7 ∈ {07, 87}; 0.00 si el CP está anulado |
| 15 | BI gravada | 12,2 | Numérico | Positivo; acepta negativo. Notas 07 y 87 con `- #.##` si el campo 29 cae en el periodo. No incluye el ISC. 0.00 si está anulado |
| 16 | Descuento de la BI | 12,2 | Numérico | Negativo; solo para los tipos 07 y 87 cuando el documento modificado es de periodos anteriores |
| 17 | IGV / IPM | 12,2 | Numérico | Igual que el campo 15 |
| 18 | Descuento del IGV / IPM | 12,2 | Numérico | Igual que el campo 16 |
| 19 | Monto exonerado | 12,2 | Numérico | Positivo; acepta negativo; `- #.##` para 07 y 87 |
| 20 | Monto inafecto | 12,2 | Numérico | Igual que el campo 19 |
| 21 | ISC | 12,2 | Numérico | Positivo o negativo; `- #.##` para 07 y 87 |
| 22 | BI gravada IVAP | 12,2 | Numérico | Oblig. si el campo 7 = 49; acepta negativos |
| 23 | IVAP | 12,2 | Numérico | Oblig. si el campo 7 = 49; acepta negativos |
| 24 | ICBPER | 12,2 | Numérico | Oblig. si el campo 7 ∈ {01, 03, 07, 08, 12}; 0.00 si no hay dato; `- #.##` para 07 |
| 25 | Otros tributos | 12,2 | Numérico | Suma de los conceptos que no forman parte de la BI; acepta negativos |
| 26 | Total CP | 12,2 | Numérico | Acepta negativos; `- #.##` para 07 y 87; 0.00 si está anulado |
| 27 | Moneda | 3 | Alfanumérico | ISO 4217; moneda de emisión; tabla 2 |
| 28 | Tipo de cambio | 1,3 | Numérico | Oblig. si el campo 27 ≠ PEN; positivo. Tipo de cambio de las normas de la materia |
| 29 | Fecha de emisión del documento modificado | 10 | Alfanumérico | Oblig. si el campo 7 ∈ {07, 08, 87, 88}. `DD/MM/AAAA`. ≤ periodo del campo 3. Si la nota modifica varios CP, se ponen todas las fechas separadas por coma (long. 1500) |
| 30 | Tipo del CP modificado | 2 | Alfanumérico **[138]** | Igual que el campo 29 (lista separada por coma); tabla 3 |
| 31 | Serie del CP modificado | Hasta 20 | Alfanumérico | Igual que el campo 29 |
| 32 | Nro. del CP modificado | Hasta 20 | Alfanumérico | Igual que el campo 29 |
| 33 | ID proyecto (operadores de la atribución) | Hasta 50 | Alfanumérico | Uso de los operadores y partícipes de contratos de colaboración sin contabilidad independiente |
| 41-57 | CLU (libre utilización) | hasta 200 | Texto | Si no se usan, no se incluye ni la información ni los palotes |

Notas del anexo 3:

- El tipo de cambio se aplica conforme a las normas de la materia.
- **[138]** Los CP electrónicos con baja comunicada y los CP o documentos físicos anulados se anotan en cero. Para los campos 22 y 23, solo si el campo 7 ≠ 49.
- **[138] (5)** Las excepciones de los campos 11 a 13 solo aplican cuando los CP y sus notas se emiten de manera física.

---

## 3. RVIE: complementar la propuesta (anexo 2), también con CP físicos

Archivo: `RRRRRRRRRRR-CPF-AAAAMM-Correlativo.txt`. El nombre viene de la tabla 6. El manual de servicios web, en `docs/sire/oficial/Manual_*Ventas*_Parte_I`, lo usa para «importar nuevos comprobantes propuesta» con `codLibro` 140000.

Según el art. 8.2.1 b) i) **[138]**, el archivo plano solo sirve para **incluir CP** que la tabla 3 permite complementar, «aun cuando hayan sido dados de baja o anulados». Para completar o modificar información de los CP ya propuestos se usa el formulario del módulo, no un archivo.

Estructura: campos **1 a 33** y **41 a 57**. La nota 7 de la [138] dice que «será una estructura de 50 campos»; la 112 decía 51. Los campos 34 a 40 (tipo de nota, estado, uso interno, valor de las operaciones gratuitas, tipo de operación, inconsistencias, uso interno) solo aparecen en la propuesta.

Los campos coinciden con los del anexo 3 (sección 2), con estas diferencias:

| N° | Diferencia respecto del anexo 3 |
|---|---|
| 3 | **[138]** Corresponde al periodo de la propuesta que se complementa. Si el campo 7 = 14, la propuesta consigna como periodo el mes y año de vencimiento. Desde el 01/10/2023, para las empresas de telecomunicaciones (MTC/OSIPTEL), el de la fecha de emisión |
| 4 | CAR vacío. Longitud 27 **[138]**; la 112 decía 29 |
| 6 | «En el archivo plano que complementa la propuesta del RVIE se debe indicar fecha de pago» |
| 7 | **[138]** Solo se permiten los tipos de la tabla 3 marcados «Si» en la columna «Información que complementa el archivo plano del RVIE» |
| 8 | Se permite consignar la serie de la máquina registradora |
| 11-13 | La lista de excepciones del literal a) **no** incluye los tipos 19, 23 ni 64 (anexo 2: 00, 05, 06, 07, 08, 11, 12, 13, 14, 15, 16, 18, 28, 30, 34, 35, 36, 37, 55, 56, 87, 88). **[138] (8)** Estas excepciones solo aplican a los CP físicos |
| 29 | La 112 decía `YYYY-MM-DD`. La **[138]** lo cambia a `DD/MM/AAAA` |
| 30 | Formato Numérico (en el anexo 3 es Alfanumérico) |

Notas **[138]**:

- **Nota 3, tipo de cambio de la propuesta:** es el tipo venta de la fecha de emisión. Para el tipo 14 de empresas que no son de telecomunicaciones se usa la fecha de vencimiento. Para las notas se usa la fecha de emisión del documento que modifican. El generador que complementa usa el tipo de cambio de las normas.
- **Nota 5:** los campos 28 y 33 pueden complementarse en la propuesta: se puede incluir información en ambos y, desde el 01/10/2023, modificar el campo 28.

---

## 4. RVIE: ajustes posteriores

### 4.1 Del periodo generado en el SIRE (anexo 4 y tabla 8)

`LE…0014040003OIM2NN.TXT`. **[138]** Se usa «un archivo plano por cada periodo generado respecto del cual se realice ajustes posteriores».

Estructura **[138]**: campos 1 a 33 iguales al anexo 3, más **41 = CAR Orig** y **42 a 57 = CLU**. Los campos 34 a 40 los completa SUNAT. En el campo 3, el periodo es el «periodo del RVIE a modificar».

| N° | Descripción | Long. | Formato | Reglas |
|---|---|---|---|---|
| 41 | CAR del CP a modificar (CAR Orig) | 27 | Alfanumérico | **[138]** Obligatorio siempre que se ajuste un CP o documento ya anotado: el CAR del CP anotado objeto del ajuste |
| 42-57 | CLU | hasta 200 | Texto | Si no se usan, no se incluyen |

> Antes de la 138, el anexo 4 tenía CLU 41-57 y no tenía CAR Orig. El campo 29 decía `YYYY-MM-DD`; la [138] lo cambia a `DD/MM/AAAA`.

**Tabla 8, procedimiento para ajustes posteriores [138]:**

1. Para modificar un CP anotado con error en un RVIE generado en el SIRE se envía un txt (anexo 4) con la información completa y correcta del CP y el CAR del CP anotado en el **campo 41**.
2. Si el CP está anotado en un Registro de Ventas generado en el PLE o en el portal, se envía un txt (anexo 5) con la información correcta.
3. Un CP nuevo, no anotado antes, se envía con todos los campos para que se genere un CAR nuevo.

> El texto original de la 112 (que ponía los campos 14 a 26 en «0.00» y volvía a anotar el CP) quedó sustituido por la [138].

### 4.2 De periodos anteriores al SIRE, registros distintos al RVIE (anexo 5)

Llevan llave única (CUO). **[138] (1)** «Se puede utilizar un archivo plano por cada periodo generado… Adicionalmente, a partir del 01 de octubre de 2023, en un mismo archivo plano podrán realizarse ajustes posteriores a varios periodos».

#### 5.1 Registro de Ventas e Ingresos: `LE…0014040004OIM2NN.TXT` (35 campos + CLU 36-70)

| N° | Long. | Oblig. | Llave | Descripción | Formato | Reglas |
|---|---|---|---|---|---|---|
| 1 | 8 | Sí | Sí | Periodo de ajuste | Numérico | `AAAAMM00`. **[138]** Menor al último periodo generado y anterior a la obligación de llevar el RVIE en el módulo RVIE. Si es menor al último periodo generado, el campo 35 debe ser 8 o 9 |
| 2 | Hasta 40 | Sí | Sí | CUO o número correlativo del mes (RER: correlativo del mes) | Texto | Si el campo 35 = 8, el CUO del periodo en que se omitió; si = 9, el CUO de la operación original. No acepta `&`. Si es un asiento consolidado, se añade un secuencial separado por `-` |
| 3 | De 2 hasta 10 | Sí | Sí | Correlativo del asiento | Alfanumérico | El primer carácter es A (apertura), M (movimiento) o C (cierre). Contribuyente del RER: `M-RER`. No acepta `&` |
| 4 | 10 | No | No | Fecha de emisión | DD/MM/AAAA | Oblig. Dentro del periodo del campo 1 |
| 5 | 10 | No | No | Fecha de vencimiento o de pago | DD/MM/AAAA | Oblig. solo si el campo 6 = 14 y el campo 35 = 8 o 9 |
| 6 | 2 | Sí | No | Tipo de CP | Numérico | Tabla 3 |
| 7 | Hasta 20 | Sí | No | Serie o serie de la máquina registradora | Alfanumérico | Tablas 3 y 6 (sic) |
| 8 | Hasta 20 | Sí | No | Número o número inicial | Alfanumérico | Tabla 5 |
| 9 | Hasta 20 | No | No | Número final | Numérico | Solo para los tipos 00, 03, 12, 13, 18, 87 y 88. Boletas de S/ 700 o más en detalle. **[138]** Consolidación de boletas y de documentos tipo 18 desde el 01/10/2023 |
| 10 | 1 | No | No | Tipo de documento del cliente | Alfanumérico | Oblig., salvo: campo 6 ∈ {00, 05, 06, 07, 08, 11, 12, 13, 14, 15, 16, 18, 19, 23, 26, 28, 30, 34, 35, 36, 37, 55, 56, 87, 88}; o tipos 07, 08, 87 y 88 con campo 29 ∈ {03, 12, 13, 14, 36}; o campo 13 > 0; o campo 25 < 700 con tipo 03 o 12; o campo 9 no vacío. No acepta 0. Tabla 2 (sic) |
| 11 | Hasta 15 | No | No | Nro. de documento del cliente | Alfanumérico | Igual que el campo 10; tabla 5 |
| 12 | Hasta 100 | No | No | Razón social del cliente | Texto | Igual que el campo 10 |
| 13 | 12,2 | No | No | Valor de la exportación | Numérico | Sin comas de miles |
| 14 | 12,2 | No | No | BI gravada | Numérico | Sin el ISC |
| 15 | 12,2 | No | No | Descuento de la BI | Numérico | Acepta negativos |
| 16 | 12,2 | No | No | IGV / IPM | Numérico | Acepta negativos |
| 17 | 12,2 | No | No | Descuento del IGV / IPM | Numérico | Acepta negativos |
| 18 | 12,2 | No | No | Exonerado | Numérico | Acepta negativos |
| 19 | 12,2 | No | No | Inafecto | Numérico | Acepta negativos |
| 20 | 12,2 | No | No | ISC | Numérico | Acepta negativos |
| 21 | 12,2 | No | No | BI IVAP | Numérico | Oblig. si el campo 6 = 49 y el campo 35 = 8 o 9 |
| 22 | 12,2 | No | No | IVAP | Numérico | Igual que el campo 21 |
| 23 | 12,2 | No | No | ICBPER | Numérico | Oblig. para los tipos 01, 03, 07, 08 y 12 (por defecto 0.00) |
| 24 | 12,2 | No | No | Otros tributos y cargos | Numérico | |
| 25 | 12,2 | No | No | Total CP | Numérico | Acepta negativos |
| 26 | 3 | No | No | Moneda | Alfanumérico | Tabla 3 (sic) |
| 27 | 1,3 | No | No | Tipo de cambio | Numérico | Oblig. si el campo 26 tiene dato; `#.###`; positivo |
| 28 | 10 | No | No | Fecha de emisión del documento modificado | DD/MM/AAAA | Oblig. si el tipo es 07, 08, 87 u 88 y el campo 35 = 8 o 9 |
| 29 | 2 | No | No | Tipo del CP modificado | Numérico | Igual que el campo 28; tabla 3 |
| 30 | Hasta 20 | No | No | Serie del CP modificado o código de la dependencia aduanera | Alfanumérico | Igual que el campo 28 |
| 31 | Hasta 20 | No | No | Nro. del CP modificado o DAM | Alfanumérico | Igual que el campo 28 |
| 32 | 12 | No | No | ID del contrato o proyecto | Texto | Operadores de contratos de colaboración |
| 33 | 1 | No | No | Error tipo 1: inconsistencia en el tipo de cambio | Numérico | «1» si no coincide con la estructura 1 de tipo de cambio |
| 34 | 1 | No | No | Indicador de pago con medios de pago | Numérico | «1» si se pagó con un medio de la tabla 10; si no, vacío |
| 35 | 1 | Sí | No | Estado (oportunidad de la anotación) | Numérico | `8` = periodo anterior **no** anotado; `9` = periodo anterior **sí** anotado |
| 36-70 | Hasta 200 | No | No | CLU | Texto | |

#### 5.2 Registro de Ventas e Ingresos simplificado: `LE…0014040005OIM2NN.TXT` (26 campos + CLU 27-52)

| N° | Long. | Oblig. | Descripción | Formato | Reglas |
|---|---|---|---|---|---|
| 1-3 | 8 / hasta 40 / 2-10 | Sí (llave) | Periodo `AAAAMM00`, CUO y correlativo del asiento | | Como en 5.1, con el estado en el campo 26 |
| 4 | 10 | No | Fecha de emisión | DD/MM/AAAA | Oblig. |
| 5 | 10 | No | Fecha de vencimiento o de pago | DD/MM/AAAA | Oblig. si el campo 6 = 14 y el campo 26 = 8 o 9 |
| 6 | 2 | Sí | Tipo de CP | Numérico | Tablas 3 y 5 |
| 7 | Hasta 20 | Sí | Serie | Alfanumérico | Tabla 5 |
| 8 | Hasta 20 | Sí | Número o número inicial | Alfanumérico | Tabla 5 |
| 9 | Hasta 20 | No | Número final | Numérico | Solo para los tipos 00, 03, 12, 13 y 87 |
| 10 | 1 | No | Tipo de documento del cliente | Alfanumérico | Oblig., salvo: campo 6 = 00; o campo 17 < 700 con tipo 03 o 12; o campo 9 no vacío. No acepta 0 |
| 11 | Hasta 15 | No | Nro. de documento del cliente | Alfanumérico | Igual que el campo 10 |
| 12 | Hasta 100 | No | Razón social del cliente | Texto | Igual que el campo 10 |
| 13 | 12,2 | No | BI gravada | Numérico | |
| 14 | 12,2 | No | IGV / IPM | Numérico | Acepta negativos |
| 15 | 12,2 | No | ICBPER | Numérico | Oblig. para los tipos 01, 03, 07, 08 y 12 |
| 16 | 12,2 | No | Otros conceptos, tributos y cargos | Numérico | |
| 17 | 12,2 | No | Total CP | Numérico | Acepta negativos |
| 18 | 3 | No | Moneda | Alfanumérico | Tabla 3 (sic) |
| 19 | 1,3 | No | Tipo de cambio | Numérico | Oblig. si el campo 18 tiene dato |
| 20 | 10 | No | Fecha del documento modificado | DD/MM/AAAA | Oblig. si el tipo es 07 u 08 y el campo 26 = 8 o 9 |
| 21 | 2 | No | Tipo del documento modificado | Numérico | Igual que el campo 20 |
| 22 | Hasta 20 | No | Serie del documento modificado | Alfanumérico | Igual que el campo 20 **[138]** (se quita «Código de la Dependencia Aduanera») |
| 23 | Hasta 20 | No | Nro. del documento modificado | Alfanumérico | Igual que el campo 20 **[138]** (se quita «o DUA») |
| 24 | 1 | No | Error tipo 1 (tipo de cambio) | Numérico | |
| 25 | 1 | No | Indicador de medios de pago | Numérico | Tabla 10 |
| 26 | 1 | Sí | Estado 8 / 9 | Numérico | Como el campo 35 de 5.1 |
| 27-52 | Hasta 200 | No | CLU | Texto | |

---

## 5. RCE: anexo 8, complementar la propuesta

El anexo tiene tres variantes: **(A)** incluir información o modificar o reubicar la que SUNAT pone por defecto; **(B)** incluir CP, notas u otros documentos no propuestos; **(C)** excluir CP de la propuesta o volver a incluir los excluidos.

Nombres de archivo: **A** = `RUC-RCECOM-AAAAMM-NN`, **B** = `RUC-CP-AAAAMM-NN` y **C** = `RUC-RCEINEX-AAAAMM-NN` (ver la sección 1.2).

Según la nota 8, se envían los campos **1 a 37** y **42 a 80**, es decir, 76 campos. Los campos 38 a 41 (detracción, tipo de nota, estado e inconsistencias) solo aparecen en la propuesta.

| N° | Descripción / nemotécnico | Long. | Formato | (A) Incluir/modificar/reubicar | (B) Incluir CP no propuestos | (C) Excluir/incluir excluidos |
|---|---|---|---|---|---|---|
| 1 | RUC del generador | 11 | Numérico | vacío | Oblig. | vacío |
| 2 | Razón social del generador (ID) | Hasta 1500 | Alfanumérico | vacío | Oblig.; debe pertenecer al RUC | vacío |
| 3 | Periodo | 6 | Numérico | vacío | Oblig. `AAAAMM`; el periodo de la propuesta que se complementa | vacío |
| 4 | CAR SUNAT | 27 | Alfanumérico | **Oblig.**: CAR del CP propuesto que se complementa | vacío (automático) | **Oblig.**: CAR del CP propuesto que se excluye o incluye |
| 5 | Fecha de emisión | 10 | Alfanumérico | vacío | Oblig. `DD/MM/AAAA`; ≤ periodo (campo 3), salvo los tipos propuestos 01, 08, 23, 30, 34, 42, 50, 52, 53 y 54 (**[138]** se quita el 46) según la columna «Serie/Número de la máquina registradora» de la tabla 11; tabla 12 | vacío |
| 6 | Fecha de vencimiento o de pago | 10 | Alfanumérico | vacío | `DD/MM/AAAA`. Oblig. si el campo 7 ∈ {14, 46, 50, 51, 52, 53, 54}. ≤ periodo, salvo el tipo 14 (≤ mes siguiente). Se pone la fecha de pago, salvo en el tipo 14 (vencimiento o pago, la primera) | vacío |
| 7 | Tipo de CP/doc. | 2 | Alfanumérico | vacío | Oblig.; tabla 11; no admite 91, 97 ni 98; solo los tipos que la tabla 11 permite complementar | vacío |
| 8 | Serie del CDP o código de la aduana | Hasta 20 | Alfanumérico | vacío | Obligatorio u opcional según la tabla 11; si el campo 7 ∈ {50, 51, 52, 53, 54}, se valida con la tabla 4 (aduanas); tabla 12 | vacío |
| 9 | Año de la DAM o DSI | 4 | Numérico | vacío | Oblig. si el campo 7 ∈ {50, 51, 52, 53, 54}: mayor a 1981 y ≤ año del periodo | vacío |
| 10 | Nro. CP o nro. inicial (rango) | Hasta 20 | Alfanumérico | vacío | Oblig., salvo si el campo 7 = 00; tablas 11 y 12. Consolidación diaria de los tipos que no dan crédito fiscal (00, 03, 05, 06, 07, 08, 11, 12, 13, 14, 15, 16, 18, 19, 23, 28, 30, 34, 35, 36, 37, 44, 45, 55, 56, 87, 88): número inicial | vacío |
| 11 | Nro. final (rango) | Hasta 20 | Alfanumérico | vacío | Solo para la lista anterior con el campo 10 lleno y los campos 15 a 20 = 0.00 | vacío |
| 12 | Tipo de documento del proveedor | 1 | Alfanumérico | vacío | Oblig., salvo si el campo 7 = 00 o el campo 7 ∈ {03, 05, 06, 07, 08, 11, 12, 13, 14, 15, 16, 18, 19, 23, 28, 30, 34, 35, 36, 37, 55, 56, 87, 88} con el campo 11 lleno; tablas 1 y 12 | vacío |
| 13 | Nro. de documento del proveedor | Hasta 15 | Alfanumérico | vacío | Igual que el campo 12; tabla 12 | vacío |
| 14 | Razón social del proveedor | Hasta 1500 | Alfanumérico | vacío | Igual que el campo 12; persona natural: apellido paterno, apellido materno y nombres | vacío |
| 15 | BI gravada DG | 12,2 | Numérico | Si el campo 15 de la propuesta > 0; positivo; negativo si el tipo es 07, 87 o 25 (en este caso, si el campo 34 empieza con «1»). Los campos 15 + 17 + 19 deben sumar el campo 15 propuesto (tolerancia ±1) | Positivo; acepta negativo con `- #.##`. Tipo 46: BI = campo 16 / tasa del IGV. Si el campo 11 está lleno, 0.00. El ISC forma parte de la BI. Oblig. | vacío |
| 16 | IGV / IPM DG | 12,2 | Numérico | Si el campo 16 propuesto > 0; mismo signo que el campo 15; igual a campo 15 × tasa (±1). Los campos 16 + 18 + 20 deben sumar el campo 16 propuesto (±1) | Mismo signo que el campo 15; impuesto de la adquisición del campo 15. Oblig. | vacío |
| 17 | BI gravada DGNG | 12,2 | Numérico | Igual que el campo 15 | Igual que el campo 15 (para el tipo 46, en función del campo 18). Además: si el campo 7 ∈ {50, 52, 53, 54} y el AAAAMM del campo 6 = campo 3, 0.00 | vacío |
| 18 | IGV / IPM DGNG | 12,2 | Numérico | Igual que el campo 16 (sobre el campo 17) | Igual que el campo 16 (sobre el campo 17) | vacío |
| 19 | BI gravada DNG | 12,2 | Numérico | Igual que el campo 15 | Igual que el campo 15 (para el tipo 46, en función del campo 20) | vacío |
| 20 | IGV / IPM DNG | 12,2 | Numérico | Igual que el campo 16 (sobre el campo 19) | Igual que el campo 16 (sobre el campo 19) | vacío |
| 21 | Valor de las adquisiciones no gravadas | 12,2 | Numérico | vacío | Positivo; acepta negativo (07, 87 y 25). Exoneradas más inafectas; incluye el ISC de los ítems no gravados | vacío |
| 22 | ISC | 12,2 | Numérico | Positivo; negativo `- #.##` para 07, 87 y 25. Solo el ISC deducible; no afecta la BI ni el total | igual | vacío |
| 23 | ICBPER | 12,2 | Numérico | vacío | Acepta negativo; oblig. si el campo 7 ∈ {01, 03, 07, 08, 12, 87, 88}; 0.00 si no hay dato | vacío |
| 24 | Otros tributos y cargos | 12,2 | Numérico | vacío | Suma de los conceptos que no forman parte de la BI; acepta negativo | vacío |
| 25 | Total CP | 12,2 | Numérico | vacío | Acepta negativos (07, 87 y 25) | vacío |
| 26 | Moneda | 3 | Alfanumérico | vacío | Oblig.; moneda de emisión; tabla 2 | vacío |
| 27 | Tipo de cambio | 1,3 | Numérico | Positivo, `#.###`, según las normas. Solo para quien lleva contabilidad en moneda nacional; quien la lleva en moneda extranjera lo cambia en el módulo (Propuesta ▸ Tipo de Cambio) | Oblig. si el campo 26 ≠ PEN (contabilidad en soles) o ≠ USD (contabilidad en USD); positivo; `#.###` | vacío |
| 28 | Fecha de emisión del documento modificado | 10 | Alfanumérico | Aplicable a los CP **físicos** modificados con una nota de crédito o débito electrónica; `DD/MM/AAAA`; ≤ periodo | Oblig. si el campo 7 ∈ {07, 08, 87, 88}; `DD/MM/AAAA`; ≤ campo 3 | vacío |
| 29 | Tipo del CP modificado | 2 | Alfanumérico | vacío | Oblig. si el campo 7 ∈ {07, 08, 87, 88}; tabla 11 | vacío |
| 30 | Serie del CP modificado | Hasta 20 | Alfanumérico | vacío | Igual que el campo 29 | vacío |
| 31 | Código de la aduana (DAM/DSI) | 3 | Alfanumérico | vacío | Oblig. si el campo 29 ∈ {50, 52}; tabla 4 | vacío |
| 32 | Nro. del CP modificado | Hasta 20 | Alfanumérico | vacío | Igual que el campo 29 | vacío |
| 33 | Clasificación de bienes y servicios | 1 | Numérico | (A y B) Indicador 1 a 5 de la tabla 23. Solo para quien superó 1500 UIT de ingresos en el ejercicio anterior | (igual que A) | vacío |
| 34 | ID proyecto de operadores o partícipes | Hasta 50 | Alfanumérico | (A y B) Oblig. si el campo 7 = 25. Operador: `1-Identificador del Contrato`; partícipe (tipo 25): `2-Identificador de Contrato`. Formato `#-Identificador de Contrato`; tabla 12 | (igual que A) | vacío |
| 35 | Porcentaje de participación | 2,2 | Numérico | Opcional; operadores; si el campo 34 empieza con 1 y las posiciones 12 y 13 del CAR ≠ 25 | Opcional; si el campo 34 empieza con 1 y el campo 7 ≠ 25 | vacío |
| 36 | IMB (impuesto materia del beneficio, Ley 31053) | 12,2 | Numérico | (A y B) Positivo; acepta negativo (07 y 87) | (igual que A) | vacío |
| 37 | CAR Orig / indicador E o I | 27 | Alfanumérico | vacío | vacío | Solo para los CP cargados automáticamente en la propuesta: `1` = excluir un CP de la «Propuesta del RCE» (no aplica a los tipos 07 y 87); `2` = incluir un CP de «Excluidos». Tabla 22 |
| 42-80 | CLU | Hasta 200 | Texto | Si no se usan, no se incluyen | Si no se usan, no se incluyen | «No enviar estos campos» |

Notas relevantes del anexo 8 (040-An, págs. 28):

- (1) Por defecto, el valor y el IGV propuestos van en los campos 15 y 16, el tipo de cambio en el 27 (el último publicado por la SBS) y la clasificación en el 33 («1 Mercadería…»).
- (5) Los campos 15, 16, 17, 18, 19, 20, 22, 27, 33, 34, 35 y 36 pueden complementarse. Se puede reubicar lo de los campos 15 y 16 en los campos 17 a 20, incluir información en los campos 22, 34, 35 y 36, y modificar los campos 27 y 33.
- (3) Los CP afectos al IVAP van en los campos 21 y 24, según la nota. La suma de los campos 15, 17 y 19 es la BI total y la de los campos 16, 18 y 20 es el IGV total. Si no hay dato, se pone 0.00.
- (2) No se anotan los CP dados de baja, revertidos ni anulados con una nota de crédito tipo 02 (error en el RUC).
- (9) La consolidación diaria de los CP sin derecho a crédito fiscal requiere un sistema de control computarizado. Sus importes van en los CLU.
- (13) No se pueden incluir CP que SUNAT no tenga, según la tabla 11.
- (14) Se puede volver a incluir un excluido hasta antes de generar el RCE.
- (15) **El CAR debe ser único en cada archivo plano que se importe.**

> Discrepancia de la norma: la nota 1 dice que la inclusión de excluidos se marca «consignando en el campo 36 el indicador», pero la fila de la tabla y la tabla 22 lo ubican en el **campo 37**.

**Tabla 22, inclusiones y exclusiones:**

- `1` Exclusión: un CP propuesto pasa a «Excluidos». No aplica a los tipos 07 y 87. Al generar el RCE, pasa a la propuesta del mes siguiente.
- `2` Inclusión: un CP previamente excluido vuelve a la «Propuesta del RCE».

---

## 6. RCE: anexo 9, no domiciliados (registro 8.5)

`LE…0008050000OIM2.TXT`. El nombre debe cumplir la tabla 13. Lleva los campos **1 a 35** y **36 a 45 (CLU)**. El archivo **no** lleva el RUC ni la razón social del generador.

| N° | Long. | Descripción / nemotécnico | Formato | Regla global | Tabla del anexo 1 |
|---|---|---|---|---|---|
| 1 | 8 | Periodo | Numérico | Oblig. «Validar formato AAAAMM3.» (sic; ver la nota) 01≤MM≤12. ≤ periodo a generar | – |
| 2 | 27 | CAR SUNAT | Alfanumérico | Vacío; automático | 7 |
| 3 | 10 | Fecha de emisión | DD/MM/AAAA | Oblig. ≤ periodo del RC no domiciliados a generar | – |
| 4 | 2 | Tipo de CP del no domiciliado | Alfanumérico | Oblig. Solo 00, 91, 97 y 98. Tabla 11; regla general de la tabla 12 | 11, 12 |
| 5 | Hasta 20 | Serie | Alfanumérico | Opcional. Tablas 11 y 12 | 11, 12 |
| 6 | Hasta 20 | Número | Alfanumérico | Oblig. Tablas 11 y 12 | 11, 12 |
| 7 | 12,2 | Valor de las adquisiciones | Numérico | Opcional; positivo; acepta negativo | – |
| 8 | 12,2 | Otros conceptos adicionales | Numérico | Opcional; positivo; acepta negativo | – |
| 9 | 12,2 | Total CP | Numérico | Oblig. | – |
| 10 | 2 | Tipo de CP que sustenta el crédito fiscal | Numérico | Opcional. Solo 00, 46, 50, 51, 52 y 53 | 11 |
| 11 | Hasta 20 | Serie del CP que sustenta el crédito fiscal (o aduana, si es DAM o DSI) | Alfanumérico | Opcional; regla general | 12 |
| 12 | 4 | Año de la DAM o DSI | Numérico | Opcional. Si el campo 11 (sic) ∈ {50, 52}: mayor a 1981 y ≤ año del periodo | – |
| 13 | Hasta 20 | Nro. del CP que sustenta el crédito fiscal | Alfanumérico | Opcional; regla general | 12 |
| 14 | 12,2 | Monto de retención del IGV | Numérico | Opcional; positivo | – |
| 15 | 3 | Moneda | Alfanumérico | Oblig. | **2** |
| 16 | 1,3 | Tipo de cambio | Numérico | Oblig. si el campo 15 ≠ PEN (contabilidad en soles) o ≠ USD (contabilidad en USD); `#.###`; positivo | – |
| 17 | 4 | País de residencia del no domiciliado | Numérico | Oblig. | **16** (países) |
| 18 | Hasta 100 | Razón social del no domiciliado | Texto | Oblig. Persona natural: apellido paterno, apellido materno y nombre completo | – |
| 19 | Hasta 100 | Domicilio en el extranjero | Texto | Opcional | – |
| 20 | Hasta 15 | Nro. de identificación del no domiciliado | Texto | Oblig. | – |
| 21 | Hasta 15 | Nro. de identificación fiscal del beneficiario efectivo | Texto | Opcional | – |
| 22 | Hasta 100 | Razón social del beneficiario efectivo | Texto | Opcional | – |
| 23 | 4 | País de residencia del beneficiario efectivo | Numérico | Opcional | **16** |
| 24 | 2 | Vínculo entre el contribuyente y el residente en el extranjero | Numérico | Opcional | **17** |
| 25 | 12,2 | Renta bruta | Numérico | Opcional | – |
| 26 | 12,2 | Deducción / costo de enajenación de bienes de capital | Numérico | Opcional; acepta negativos | – |
| 27 | 12,2 | Renta neta | Numérico | Opcional | – |
| 28 | 3,2 | Tasa de retención | Numérico | Opcional | – |
| 29 | 12,2 | Impuesto retenido | Numérico | Opcional | – |
| 30 | 2 | Convenio para evitar la doble imposición | Numérico | **Oblig.** | **18** |
| 31 | 1 | Exoneración aplicada | Numérico | Opcional | **21** |
| 32 | 2 | Tipo de renta | Numérico | **Oblig.** | **19** |
| 33 | 1 | Modalidad del servicio prestado | Numérico | Opcional | **20** |
| 34 | 1 | Aplicación del penúltimo párrafo del art. 76 de la LIR | Numérico | Opcional; consignar `1` si aplica (no hay tabla) | – |
| 35 | 27 | CAR del CP a modificar en ajustes posteriores | Alfanumérico | Vacío | – |
| 36-45 | Hasta 200 | CLU | Texto | Si no se usan, no se incluyen | – |

Notas del anexo 9:

- (2) «Los campos serán opcionales solo en el caso que el generador no cuente con esa información».
- (3) Tipo de cambio: numeral 17 del art. 5 del Reglamento del IGV.

> Para el campo 1, la longitud 8 sugiere `AAAAMM00`, como en el anexo 13, pero el texto oficial dice «AAAAMM3.». Es probable que sea «AAAAMM» seguido del número de la siguiente regla. El anexo 12 (8.5) repite la errata.

> Numeración de tablas: las tablas que mencionaste (35 países, 27 vínculo, 25 convenios, 31 renta, 33 exoneración) siguen la numeración del PLE. En el SIRE son las **tablas 16 a 21 del anexo 1**, que añadió la 040-2022 en su anexo B.

### 6.1 Tablas que usa el anexo 9

**Tabla 16, países:** 040-An, anexo B, págs. 13-15 (`anexo-040-2022.txt` líneas 1410-1688). Tiene **273 filas**, con códigos de 4 dígitos entre 9001 y 9897. Perú = `9589`.

**Tabla 17, tipo de vinculación económica** (art. 24 del Reglamento de la LIR, D.S. 122-94-EF):

| N° | Descripción (resumen fiel) | Base |
|---|---|---|
| 00 | Sin vinculación | – |
| 01 | Una persona natural o jurídica posee más del 30 % del capital de otra persona jurídica, directamente o por intermedio de un tercero | Art. 24 num. 1 |
| 02 | Más del 30 % del capital de dos o más personas jurídicas pertenece a una misma persona natural o jurídica, directamente o por intermedio de un tercero | num. 2 |
| 03 | En los casos anteriores, cuando la proporción del capital pertenece a cónyuges entre sí o a personas naturales vinculadas hasta el 2.º grado de consanguinidad o afinidad | num. 3 |
| 04 | El capital de dos o más personas jurídicas pertenece en más del 30 % a socios comunes | num. 4 |
| 05 | Las personas jurídicas o entidades cuentan con uno o más directores, gerentes, administradores u otros directivos comunes con poder de decisión en los acuerdos financieros, operativos y/o comerciales | num. 5 |
| 06 | Dos o más personas naturales o jurídicas consolidan estados financieros | num. 6 |
| 07 | Contrato de colaboración empresarial con contabilidad independiente: vinculado con las partes que participan en más del 30 % del patrimonio del contrato o que tienen poder de decisión | num. 7 |
| 08 | Contrato de colaboración empresarial sin contabilidad independiente: la vinculación entre cada parte y la contraparte se verifica individualmente | num. 8 |
| 09 | Contrato de asociación en participación en que un asociado participa en más del 30 % de los resultados o utilidades, o tiene poder de decisión | num. 9 |
| 10 | Una empresa no domiciliada con uno o más establecimientos permanentes en el país: hay vinculación entre la empresa y cada establecimiento, y entre los establecimientos | num. 10 |
| 11 | Una empresa domiciliada con uno o más establecimientos permanentes en el extranjero | num. 11 |
| 12 | Influencia dominante en los órganos de administración (mayoría absoluta de votos o, en las decisiones del art. 126 de la LGS, el mayor número de acciones con voto y al menos el 10 %), o el 80 % o más de las ventas a una persona que represente al menos el 30 % de sus compras. Aplica también con personas interpuestas | num. 12 |

**Tabla 18, convenios para evitar la doble tributación:** 00 Ninguno · 01 Canadá · 02 Chile · 03 Comunidad Andina de Naciones (CAN) · 04 Brasil · 05 Estados Unidos Mexicanos · 06 República de Corea · 07 Confederación Suiza · 08 Portugal · 09 Otros.

**Tabla 19, tipo de renta** (código · descripción · artículo de la LIR · código OCDE):

| N° | Descripción | Art. LIR | OCDE |
|---|---|---|---|
| 00 | Bienes | | |
| 01 | Arrendamiento de predios | 9 a) | 06 |
| 02 | Enajenación de inmuebles y derechos sobre inmuebles | 9 a) | 06 |
| 03 | Rentas de bienes situados en el país o derechos utilizados en el país, incluida la enajenación | 9 b) | 12 |
| 04 | Regalías: los bienes o derechos por los que se pagan se utilizan en el país | 9 b) | 12 |
| 05 | Regalías: el pagador es domiciliado | 9 b) | 12 |
| 06 | Capitales, intereses, comisiones, primas y operaciones financieras: el capital se utiliza en el país o el pagador es domiciliado (incluidos los seguros de vida o invalidez que no tienen origen en el trabajo personal) | 9 c) | 11 |
| 07 | Dividendos y otras distribuciones de utilidades de una empresa, fondo o patrimonio domiciliado o constituido en el país | 9 d) | 10 |
| 08 | Rendimientos de ADR y GDR con subyacente de acciones emitidas por empresas no domiciliadas | 9 d) | 10 |
| 09 | Actividades civiles, comerciales, empresariales o de cualquier índole llevadas a cabo en el territorio nacional | 9 e) | 21 |
| 10 | Trabajo personal realizado en el territorio nacional (con las excepciones de ingreso temporal) | 9 f) | 15 |
| 11 | Rentas vitalicias y pensiones originadas en el trabajo personal, pagadas por un domiciliado | 9 g) | 18 |
| 12 | Enajenación de acciones y participaciones de empresas constituidas en el Perú, fuera de bolsa | 9 h) | 13 |
| 13 | Enajenación de certificados, títulos, bonos, papeles comerciales y otros valores de fondos o patrimonios constituidos en el Perú, fuera de bolsa | 9 h) | 13 |
| 14 | Redención o rescate de esos valores, fuera de bolsa | 9 h) | 13 |
| 15 | Enajenación de acciones, participaciones y valores mobiliarios emitidos en el Perú, dentro de bolsa | 9 h) | 13 |
| 16 | Redención o rescate de esos valores, dentro de bolsa | 9 h) | 13 |
| 17 | Enajenación de ADR y GDR con subyacente de acciones de empresas domiciliadas | 9 h) | 13 |
| 18 | Servicios digitales prestados por Internet que se utilizan económicamente en el país | 9 i) | 21 |
| 19 | Asistencia técnica que se utiliza económicamente en el país | 9 j) | 7 |
| 20 | Intereses de obligaciones de una entidad emisora constituida en el país | 10 a) | 11 |
| 21 | Remuneración pagada por domiciliados a un miembro de un consejo directivo o de administración que actúa en el extranjero | 10 b) | 16 |
| 22 | Honorarios o remuneraciones del sector público nacional por trabajos en el exterior | 10 c) | 19 |
| 23 | Resultados provenientes de la contratación de IFD | 10 d) | 7 |
| 24 | Resultados de IFD con cobertura destinados a la generación de RFP | 10 d) | 7 |
| 25 | IFD sin cobertura destinados a la generación de RFP | 10 d) | 7 |
| 26 | IFD con activo subyacente referido al tipo de cambio, 180 días (el domiciliado presta el IFD y el no domiciliado obtiene el resultado) | 10 d) | 7 |
| 27 | Enajenación indirecta de acciones de personas jurídicas domiciliadas | 10 e) | 13 |
| 28 | Enajenación de ADR con subyacente de esas acciones | 10 e) | 13 |
| 29 | Distribución por reducción de capital dentro de los 12 meses siguientes a un aumento (nuevos aportes, capitalización o reorganización) | 10 f) | 10 |
| 30 | Seguros: 7 % sobre las primas; comisiones por reaseguros | 12 y 48 a) | 07-21 |
| 31 | Alquiler de naves: 8 % de los ingresos brutos | 12 y 48 b) | 8 |
| 32 | Alquiler de aeronaves: 60 % de los ingresos brutos | 12 y 48 c) | 8 |
| 33 | 1 % de los ingresos brutos por transporte aéreo | 12 y 48 d) | 8 |
| 34 | Otros transportes no aéreos ni marítimos (por la parte prestada en el país) | 12 y 48 d) | 8 |
| 35 | 2 % de los ingresos brutos por fletamento o transporte marítimo | 12 y 48 d) | 8 |
| 36 | Empresas por reciprocidad en líneas extranjeras con sede en esos países | 12 y 48 d) | 24 |
| 37 | Servicios portadores, teleservicios o finales, difusión y valor añadido (salvo los servicios digitales del 4-A) | 12 y 48 e) | 07-21 |
| 38 | 10 % de las remuneraciones brutas por suministro de noticias y material informativo o gráfico | 12 y 48 f) | 07-21 |
| 39 | 20 % de los ingresos brutos por el uso de películas, video tape, radionovelas, discos y medios similares | 12 y 48 g) | 07-21 |
| 40 | 15 % de los ingresos brutos por suministro de contenedores sin prestar el servicio de transporte (texto truncado en la fuente) | 12 y 48 h) | 8 |
| 41 | 80 % de los ingresos brutos por exceso de estadía de contenedores | 12 y 48 i) | 07-21 |
| 42 | 20 % de los ingresos brutos por la cesión de derechos de retransmisión por TV de eventos en vivo del extranjero | 12 y 48 j) | 07-21 |
| 43 | Extranjeros que ingresan al país con calidades específicas para prestar servicios | 13 | 15 |

**Tabla 20, modalidad del servicio prestado por el no domiciliado:**

1. Servicio prestado íntegramente en el Perú.
2. Servicio prestado parte en el Perú y parte en el extranjero.
3. Servicio prestado exclusivamente en el extranjero.

**Tabla 21, exoneraciones de operaciones de no domiciliados (art. 19 de la LIR):**

1. Intereses de créditos de fomento otorgados, directamente o mediante intermediarios, por organismos internacionales o instituciones gubernamentales extranjeras.
2. Rentas de los inmuebles de propiedad de organismos internacionales que les sirven de sede.
3. Remuneraciones de los funcionarios y empleados de gobiernos extranjeros, instituciones oficiales extranjeras y organismos internacionales por el ejercicio de su cargo en el país, si los convenios constitutivos lo establecen.
4. Ingresos brutos de las representaciones deportivas nacionales de países extranjeros por sus actuaciones en el país.
5. Regalías por asesoramiento técnico, económico, financiero u otro prestado desde el exterior por entidades estatales u organismos internacionales.
6. Ingresos de los espectáculos en vivo de teatro, zarzuela, música clásica, ópera, opereta, ballet y folclor calificados como culturales por el INC.

**Aplicación del art. 76 (campo 34):** no hay tabla. Se consigna `1` si aplica el penúltimo párrafo del art. 76 de la LIR y, si no, se deja vacío.

---

## 7. RCE: anexo 10, complemento del tipo de cambio

Archivo: `RRRRRRRRRRR-RCETCA-AAAAMM-Correlativo.txt`, con separador `-` (ejemplo: `20000000001-RCETCA-202201-01.txt`). Se usa cuando la SBS no publica el tipo de cambio de una moneda. El archivo va separado de los demás complementos.

| N° | Descripción | Nemotécnico | Regla global | Long. | Formato |
|---|---|---|---|---|---|
| 1 | Periodo | Periodo | Oblig.; `AAAAMM`; 01≤MM≤12; igual al periodo del RCE a generar | 6 | Numérico |
| 2 | Fecha de emisión del CP (3) | Fecha de emisión | Oblig.; `DD/MM/AAAA`; AAAAMM ≤ campo 1. Debe ser una fecha que figura en la subopción «Tipo de Cambio» de la propuesta | 10 | Alfanumérico |
| 3 | Moneda | Moneda | Oblig.; la moneda informada en la propuesta (subopción «Tipo de Cambio») | 3 | Alfanumérico |
| 4 | Tipo de cambio de la moneda extranjera a soles | Tipo de Cambio a Soles | Oblig.; positivo; `#.###` | 1,3 | Numérico |
| 5 | Tipo de cambio de soles a USD | Tipo de Cambio a Dólar | Solo si se lleva la contabilidad en moneda extranjera; positivo; `#.###` | 1,3 | Numérico |

Nota (3): se pone la fecha de emisión del CP anotado o, si es una nota de crédito o débito, la del CP modificado, tal como aparece en la subopción «Tipo de Cambio».

---

## 8. RCE: anexo 11, comparación o reemplazo de la propuesta

`LE…0008040002OIM2.TXT`. Lleva los campos **1 a 37** y **42 a 80 (CLU)**. Según la nota 6, los campos 38 a 41 «son completados automáticamente».

| N° | Descripción / nemotécnico | Long. | Formato | Reglas clave |
|---|---|---|---|---|
| 1 | RUC del generador | 11 | Numérico | Oblig. |
| 2 | Razón social del generador (ID) | Hasta 1500 | Alfanumérico | Oblig.; debe pertenecer al RUC |
| 3 | Periodo | 6 | Numérico | Oblig. `AAAAMM`; el periodo de la propuesta que se reemplaza |
| 4 | CAR SUNAT | 27 | Alfanumérico | **Vacío**; automático |
| 5 | Fecha de emisión | 10 | Alfanumérico | Oblig. `DD/MM/AAAA`; ≤ periodo; tabla 12 |
| 6 | Fecha de vencimiento o de pago | 10 | Alfanumérico | Oblig. si el campo 7 ∈ {14, 46, 50, 51, 52, 53, 54} (mismas reglas que el anexo 8) |
| 7 | Tipo de CP | 2 | Alfanumérico | Oblig.; tabla 11; no admite 91, 97 ni 98 |
| 8 | Serie (o código de la aduana) | Hasta 20 | Alfanumérico | Según la tabla 11; tabla 4 si el campo 7 ∈ {50, 51, 52, 53, 54} |
| 9 | Año de la DAM o DSI | 4 | Numérico | Oblig. si el campo 7 ∈ {50, 51, 52, 53, 54}; > 1981 y ≤ año del periodo |
| 10 | Nro. CP o inicial | Hasta 20 | Alfanumérico | Oblig., salvo el tipo 00; consolidación de los CP sin crédito fiscal |
| 11 | Nro. final | Hasta 20 | Alfanumérico | Solo en la consolidación, con los campos 15 a 20 = 0.00 |
| 12 | Tipo de documento del proveedor | 1 | Alfanumérico | Oblig., salvo el tipo 00 o la lista de tipos con el campo 11 lleno; tablas 1 y 12 |
| 13 | Nro. de documento del proveedor | Hasta 15 | Alfanumérico | Igual que el campo 12 |
| 14 | Razón social del proveedor | Hasta 1500 | Alfanumérico | Igual que el campo 12 |
| 15 | BI DG | 12,2 | Numérico | Oblig.; negativo para 07, 87 y 25 (con el campo 34 empezando por «1»); tipo 46 = campo 16 / tasa; 0.00 si el campo 11 está lleno; incluye el ISC si el ítem está gravado |
| 16 | IGV DG | 12,2 | Numérico | Oblig.; mismo signo que el campo 15 |
| 17 | BI DGNG | 12,2 | Numérico | Igual que el campo 15 |
| 18 | IGV DGNG | 12,2 | Numérico | Igual que el campo 16 |
| 19 | BI DNG | 12,2 | Numérico | Igual que el campo 15 |
| 20 | IGV DNG | 12,2 | Numérico | Igual que el campo 16 |
| 21 | Valor de las adquisiciones no gravadas | 12,2 | Numérico | Exoneradas más inafectas; acepta negativo |
| 22 | ISC | 12,2 | Numérico | Solo el ISC deducible |
| 23 | ICBPER | 12,2 | Numérico | Oblig. si el campo 7 ∈ {01, 03, 07, 08, 12}; 0.00 si no hay dato |
| 24 | Otros tributos y cargos | 12,2 | Numérico | |
| 25 | Total CP | 12,2 | Numérico | Acepta negativos |
| 26 | Moneda | 3 | Alfanumérico | Oblig.; tabla 2 |
| 27 | Tipo de cambio | 1,3 | Numérico | Oblig. si el campo 26 ≠ PEN (contabilidad en soles) o ≠ USD (contabilidad en USD); `#.###` |
| 28 | Fecha de emisión del documento modificado | 10 | Alfanumérico | Oblig. si el campo 7 ∈ {07, 08, 87, 88}; `DD/MM/AAAA` |
| 29 | Tipo del CP modificado | 2 | Alfanumérico | Igual que el campo 28; tabla 11 |
| 30 | Serie del CP modificado | Hasta 20 | Alfanumérico | Igual que el campo 28 |
| 31 | Código de la aduana (DAM/DSI) | 3 | Alfanumérico | Oblig. si el campo 29 ∈ {50, 52}; tabla 4 |
| 32 | Nro. del CP modificado | Hasta 20 | Alfanumérico | Igual que el campo 28 |
| 33 | Clasificación de bienes y servicios | 1 | Numérico | Tabla 23; solo para quien superó 1500 UIT en el ejercicio anterior |
| 34 | ID proyecto de operadores o partícipes | Hasta 50 | Alfanumérico | Oblig. si el campo 7 = 25; `1-…` (operador) o `2-…` (partícipe) |
| 35 | Porcentaje de participación | 2,2 | Numérico | Opcional; si el campo 34 empieza con 1 y el campo 7 ≠ 25 |
| 36 | IMB (Ley 31053) | 12,2 | Numérico | Acepta negativo para 07 y 87 |
| 37 | CAR Orig | 27 | Alfanumérico | «1. Vacío. 2. Campo aplicable para Ajustes Posteriores» |
| 42-80 | CLU | Hasta 200 | Texto | Si no se usan, no se incluyen |

**Tabla 23, clasificación de bienes y servicios:**

1. Mercadería, materia prima, suministro, envases y embalajes.
2. Adquisiciones de activo fijo.
3. Otros activos no considerados en el numeral 2.
4. Gastos de educación, recreación, salud, culturales, representación, capacitación, de viaje, mantenimiento de vehículo y premios.
5. Otros gastos no incluidos en el numeral 4.

### 8.1 Comparación con las 37 columnas que emite `al_l10n_pe_sire`

La lista que nos pasaste coincide **campo a campo y en el mismo orden** con los campos 1 a 37 del anexo 11:

```
1 RUC | 2 razón social | 3 periodo | 4 CAR (vacío) | 5 F. emisión | 6 F. vcto/pago | 7 tipo CP | 8 serie |
9 año DAM | 10 nro CP | 11 nro final | 12 tipo doc | 13 nro doc | 14 razón social prov. | 15 BI DG | 16 IGV DG |
17 BI DGNG | 18 IGV DGNG | 19 BI DNG | 20 IGV DNG | 21 valor NG | 22 ISC | 23 ICBPER | 24 otros | 25 total |
26 moneda | 27 TC | 28 F. emisión mod | 29 tipo CP mod | 30 serie mod | 31 cod DAM | 32 nro CP mod |
33 clasif. bienes | 34 id proyecto | 35 % participación | 36 IMB | 37 CAR orig
```

- **No sobra nada.** El anexo 11 no admite los campos 38 a 41 (detracción, tipo de nota, estado, inconsistencias): los completa SUNAT y no deben enviarse.
- **No falta nada obligatorio.** Los campos 42 a 80 (CLU) son opcionales y, si no se usan, no deben ir ni siquiera los palotes vacíos.

Puntos a verificar en el generador (son reglas de la norma, no diferencias de columnas):

- El campo 4 (CAR) va vacío. El campo 37 (CAR orig) va **vacío en el reemplazo** y solo se llena en el anexo 12.
- Fechas en `DD/MM/AAAA`. Importes sin comas de miles y con negativos en formato `- #.##`. Tipo de cambio con 3 decimales (`#.###`).
- El campo 9 (año DAM) y el campo 31 (código de la aduana) solo para DAM y DSI. El campo 31 depende del campo **29** ∈ {50, 52}, no del campo 7.
- El campo 15 debe ser 0.00 cuando el campo 11 (nro. final) está lleno. En la consolidación, los campos 15 a 20 deben valer 0.00.
- El campo 33 solo es exigible a quien superó 1500 UIT de ingresos.
- Tipos 91, 97 y 98 prohibidos en el 8.4: van al anexo 9 (8.5).

---

## 9. RCE: anexo 12, ajustes posteriores del RCE generado en el SIRE

**Tabla 15, procedimiento:**

1. Para modificar un CP anotado con error en un RCE generado en el SIRE se envía un txt (anexo 12) con la información completa y correcta y el CAR del CP anotado. El CAR va en el **campo 37** si el CP está en el Registro de Compras o en el **campo 35** si está en el RC de no domiciliados.
2. Si el CP está anotado en un Registro de Compras del PLE o del portal, se usa el anexo 13.

**[138]** Se usa «un archivo plano por cada periodo generado respecto del cual se realice ajustes posteriores» (en el 8.4 y en el 8.5).

### 9.1 Registro 8.4: `LE…0008040003OIM2NN.TXT`

Tiene la misma estructura que el anexo 11 (campos 1 a 37 y CLU 42 a 80), con estas diferencias:

| N° | Diferencia |
|---|---|
| 3 | Periodo: «Corresponde al periodo objeto de ajuste» |
| 5, 6, 9 | Las fechas y el año se validan contra «el periodo del RCE a ajustar» |
| 37 | **CAR Orig, 27, Alfanumérico**: «Obligatorio, siempre y cuando se esté efectuando un ajuste respecto de un comprobante de pago o documento previamente anotado. CAR corresponde a comprobante de pago o documento anotado objeto de ajuste» |

Nota 7 del anexo 12: los campos 38 a 41 los completa SUNAT.

### 9.2 Registro 8.5 no domiciliados: `LE…0008050003OIM2NN.TXT`

Tiene la misma estructura que el anexo 9 (35 campos y CLU 36 a 45), con estas diferencias:

| N° | Diferencia |
|---|---|
| 1 | Periodo: «Corresponde al periodo objeto de ajuste» (repite «AAAAMM3.») |
| 3 | Fecha de emisión ≤ periodo del RC no domiciliados «a ajustar» |
| 35 | **CAR Orig, 27**: «1. Obligatorio. CAR corresponde a comprobante de pago o documento anotado objeto de ajuste» |

---

## 10. RCE: anexo 13, ajustes de registros de compras distintos al RCE (PLE o portal)

**[138] (1)** «Se puede utilizar un archivo plano por cada periodo generado… e inclusive en un mismo archivo plano podrán realizarse ajustes posteriores a varios periodos».

### 10.1 Registro de compras 5.1: `LE…0008040004OIM2NN.TXT` (42 campos + CLU 43-84)

| N° | Long. | Oblig. | Llave | Descripción | Formato | Observaciones |
|---|---|---|---|---|---|---|
| 1 | 8 | Sí | Sí | Periodo | Numérico | «Validar formato AAAAMM003.» (sic, por `AAAAMM00`); menor al último periodo generado y anterior a la obligación de llevar el RCE en el SIRE |
| 2 | Hasta 40 | Sí | Sí | CUO o correlativo del mes (RER: correlativo del mes) | Texto | Si el campo 42 = 9, el CUO de la operación original. No acepta `&`. Consolidado: secuencial con `-` |
| 3 | De 2 hasta 10 | Sí | Sí | Correlativo del asiento (A, M o C) | Alfanumérico | RER: `M-RER`. No acepta `&` |
| 4 | 10 | Sí | No | Fecha de emisión | DD/MM/AAAA | Menor al último periodo generado y anterior a la obligación del SIRE |
| 5 | 10 | No | No | Fecha de vencimiento o de pago (2) | DD/MM/AAAA | Oblig. si el campo 6 = 14 y el campo 42 = 9 |
| 6 | 2 | Sí | No | Tipo de CP | Numérico | Tabla 11; no admite 91, 97 ni 98 |
| 7 | Hasta 20 | No | No | Serie (código de la aduana para DAM o DSI) | Alfanumérico | Optativo; tablas 4, 11 y 12 |
| 8 | 4 | No | No | Año de la DAM o DSI | Numérico | Si el campo 6 ∈ {50, 52}: > 1981 y ≤ año |
| 9 | Hasta 20 | Sí | No | Número o número inicial (3) | Alfanumérico | Tablas 11 y 12 |
| 10 | Hasta 20 | No | No | Número final (3) | Numérico | Para la lista de tipos sin crédito fiscal (00, 03, 05, 06, 07, 08, 11, 12, 13, 14, 15, 16, 18, 19, 23, 26, 28, 30, 34, 35, 36, 37, 55, 56, 87, 88), el campo 9 debe ser ≥ 0 |
| 11 | 1 | No | No | Tipo de documento del proveedor | Alfanumérico | Oblig., salvo los tipos de la lista (incluidos 91, 97 y 98) o las notas 07, 08, 87, 88, 97 y 98 con el campo 28 ∈ {03, 12, 13, 14, 36}; tabla 1 |
| 12 | Hasta 15 | No | No | Nro. de documento del proveedor | Alfanumérico | Igual que el campo 11; tabla 12 |
| 13 | Hasta 100 | No | No | Razón social del proveedor | Texto | Igual que el campo 11 |
| 14 | 12,2 | No | No | BI DG | Numérico | Acepta negativos |
| 15 | 12,2 | No | No | IGV DG | Numérico | Mismo signo que el campo 14 |
| 16 | 12,2 | No | No | BI DGNG | Numérico | Acepta negativos |
| 17 | 12,2 | No | No | IGV DGNG | Numérico | Mismo signo que el campo 16 |
| 18 | 12,2 | No | No | BI DNG | Numérico | Acepta negativos |
| 19 | 12,2 | No | No | IGV DNG | Numérico | Mismo signo que el campo 18 |
| 20 | 12,2 | No | No | Valor de las adquisiciones no gravadas | Numérico | Acepta negativos |
| 21 | 12,2 | No | No | ISC deducible | Numérico | Acepta negativos |
| 22 | 12,2 | No | No | ICBPER | Numérico | Oblig. para los tipos 01, 03, 07, 08 y 12 (por defecto 0.00) |
| 23 | 12,2 | No | No | Otros tributos y cargos | Numérico | Acepta negativos |
| 24 | 12,2 | Sí | No | Total CP | Numérico | Acepta negativos; **suma de los campos 14 a 23** |
| 25 | 3 | No | No | Moneda | Alfanumérico | Tabla 2 |
| 26 | 1,3 | No | No | Tipo de cambio (4) | Numérico | `#.###`; positivo |
| 27 | 10 | No | No | Fecha del CP modificado (5) | DD/MM/AAAA | Oblig. si el campo 6 ∈ {07, 08, 87, 88, 97, 98} |
| 28 | 2 | No | No | Tipo del CP modificado | Numérico | Igual que el campo 27; tabla 11 |
| 29 | Hasta 20 | No | No | Serie del CP modificado | Alfanumérico | Igual que el campo 27 |
| 30 | 3 | No | No | Código de la aduana (DAM/DSI) | Alfanumérico | Oblig. si el campo 28 ∈ {50, 52}; tabla 4 |
| 31 | Hasta 20 | No | No | Nro. del CP modificado | Alfanumérico | Igual que el campo 27 |
| 32 | 10 | No | No | Fecha de la constancia de depósito de detracción (6) | DD/MM/AAAA | ≤ mes siguiente al periodo del campo 1 |
| 33 | Hasta 24 | No | No | Nro. de la constancia de detracción (6) | Alfanumérico | Positivo, si es numérico |
| 34 | 1 | No | No | Marca de CP sujeto a retención | Numérico | `1` si está sujeto a retención; si no, vacío |
| 35 | 1 | No | No | Clasificación de bienes y servicios | Numérico | Tabla 23 (1500 UIT) |
| 36 | 12 | No | No | ID del contrato o proyecto | Texto | Operadores |
| 37 | 1 | No | No | Error tipo 1: tipo de cambio | Numérico | «1» si no coincide con la estructura 1 |
| 38 | 1 | No | No | Error tipo 2: proveedores no habidos | Numérico | «1» si corresponde (estructura 2) |
| 39 | 1 | No | No | Error tipo 3: proveedores que renunciaron a la exoneración del Apéndice I | Numérico | «1» si corresponde (estructura 3) |
| 40 | 1 | No | No | Error tipo 4: DNI usado en liquidaciones de compra cuyo titular ya tiene RUC | Numérico | Solo para el tipo 04 |
| 41 | 1 | No | No | Indicador de medios de pago | Numérico | «1» si se usó un medio de la tabla 10 |
| 42 | 1 | Sí | No | Estado de ajuste | Numérico | Oblig.; `9` = ajuste o rectificación de una operación registrada en un periodo anterior a la vigencia del registro de compras del SIRE |
| 43-84 | Hasta 200 | No | No | CLU | Texto | |

### 10.2 Registro de compras de no domiciliados 5.2: `LE…0008050004OIM2NN.TXT` (36 campos + CLU 37-72)

Ver en la sección 1.1 la contradicción entre `04` y `06` en este nombre.

| N° | Long. | Oblig. | Llave | Descripción | Formato | Observaciones |
|---|---|---|---|---|---|---|
| 1 | 8 | Sí | Sí | Periodo | Numérico | `AAAAMM00`; menor al último periodo generado y anterior a la obligación del SIRE |
| 2 | Hasta 40 | Sí | Sí | CUO o correlativo | Texto | Si el campo 36 = 9, el CUO original. No acepta `&` |
| 3 | De 2 hasta 10 | Sí | Sí | Correlativo del asiento (A, M o C) | Alfanumérico | RER: `M-RER` |
| 4 | 10 | Sí | No | Fecha de emisión | DD/MM/AAAA | |
| 5 | 2 | Sí | **Sí** | Tipo de CP | Alfanumérico | Solo 00, 91, 97 y 98; tabla 12 |
| 6 | Hasta 20 | No | No | Serie | Alfanumérico | Opcional |
| 7 | Hasta 20 | Sí | **Sí** | Número | Alfanumérico | Tablas 11 y 12 |
| 8 | 12,2 | No | No | Valor de las adquisiciones | Numérico | |
| 9 | 12,2 | No | No | Otros conceptos adicionales | Numérico | |
| 10 | 12,2 | Sí | No | Total | Numérico | Oblig. |
| 11 | 2 | No | No | Tipo de CP que sustenta el crédito fiscal | Numérico | Solo 00, 46, 50, 51, 52 y 53 |
| 12 | Hasta 20 | No | No | Serie del CP que sustenta el crédito fiscal o aduana | Alfanumérico | |
| 13 | 4 | No | No | Año de la DAM o DSI | Numérico | Si el campo 11 ∈ {50, 52} |
| 14 | Hasta 20 | No | No | Nro. del CP que sustenta el crédito fiscal | Alfanumérico | |
| 15 | 12,2 | No | No | Monto de retención del IGV | Numérico | |
| 16 | 3 | Sí | No | Moneda | Alfanumérico | Tabla 2 |
| 17 | 1,3 | No | No | Tipo de cambio | Numérico | Oblig. si el campo 16 ≠ PEN; `#.###` |
| 18 | 4 | Sí | No | País del no domiciliado | Alfanumérico | Tabla 16 |
| 19 | Hasta 100 | Sí | No | Razón social del no domiciliado | Texto | |
| 20 | Hasta 100 | No | No | Domicilio en el extranjero | Texto | |
| 21 | Hasta 15 | Sí | No | Nro. de identificación del no domiciliado | Texto | |
| 22 | Hasta 15 | No | No | Identificación fiscal del beneficiario | Texto | |
| 23 | Hasta 100 | No | No | Razón social del beneficiario | Texto | |
| 24 | 4 | No | No | País del beneficiario | Alfanumérico | Tabla 16 |
| 25 | 2 | No | No | Vínculo | Alfanumérico | Tabla 17 |
| 26 | 12,2 | No | No | Renta bruta | Numérico | |
| 27 | 12,2 | No | No | Deducción / costo | Numérico | Acepta negativos |
| 28 | 12,2 | No | No | Renta neta | Numérico | |
| 29 | 3,2 | No | No | Tasa de retención | Numérico | |
| 30 | 12,2 | No | No | Impuesto retenido | Numérico | |
| 31 | 2 | Sí | No | Convenio | Numérico | Tabla 18 |
| 32 | 1 | No | No | Exoneración | Numérico | Tabla 21 |
| 33 | 2 | Sí | No | Tipo de renta | Numérico | Tabla 19 |
| 34 | 1 | No | No | Modalidad del servicio | Numérico | Tabla 20 |
| 35 | 1 | No | No | Aplicación del art. 76 | Numérico | `1` si aplica |
| 36 | 1 | Sí | No | Estado | Numérico | `9` = ajuste o rectificación de un periodo anterior |
| 37-72 | Hasta 200 | No | No | CLU | Texto | |

Los campos del país (18 y 24) y del vínculo (25) figuran como Alfanumérico en el anexo 13. En el anexo 9 son Numérico.

### 10.3 Registro de compras simplificado 5.3: `LE…0008040005OIM2NN.TXT` (32 campos + CLU 33-64)

| N° | Long. | Oblig. | Llave | Descripción | Formato | Observaciones |
|---|---|---|---|---|---|---|
| 1-3 | 8 / hasta 40 / 2-10 | Sí | Sí | Periodo `AAAAMM00`, CUO y correlativo | | Si el campo 32 = 9, el CUO original |
| 4 | 10 | Sí | No | Fecha de emisión | DD/MM/AAAA | |
| 5 | 10 | No | No | Fecha de vencimiento o de pago | DD/MM/AAAA | Oblig. si el campo 6 = 14 y el campo 42 (sic) = 9 |
| 6 | 2 | Sí | No | Tipo de CP | Numérico | Tabla 11; no admite 91, 97 ni 98 |
| 7 | Hasta 20 | Sí | No | Serie o aduana | Alfanumérico | «Optativo»; tablas 4, 11 y 12 |
| 8 | Hasta 20 | Sí | No | Número o número inicial | Alfanumérico | Tablas 11 y 12 |
| 9 | Hasta 20 | No | No | Número final | Numérico | Para la lista de tipos sin crédito fiscal, el campo 8 debe ser ≥ 0 |
| 10 | 1 | No | No | Tipo de documento del proveedor | Alfanumérico | Oblig., salvo la lista de tipos (incluido el 91); no acepta 0 |
| 11 | Hasta 15 | No | No | Nro. de documento del proveedor | Alfanumérico | Igual que el campo 10 |
| 12 | Hasta 100 | No | No | Razón social del proveedor | Texto | Igual que el campo 10 |
| 13 | 12,2 | No | No | BI DG | Numérico | Acepta negativos |
| 14 | 12,2 | No | No | IGV / IPM | Numérico | Mismo signo que el campo 13 |
| 15 | 12,2 | No | No | ICBPER | Numérico | Oblig. para los tipos 01, 03, 07, 08 y 12 |
| 16 | 12,2 | No | No | Otros tributos y cargos | Numérico | |
| 17 | 12,2 | Sí | No | Total | Numérico | Suma de los campos 13, 14, 15 y 16 |
| 18 | 3 | No | No | Moneda | Alfanumérico | Tabla 2 |
| 19 | 1,3 | No | No | Tipo de cambio | Numérico | `#.###` |
| 20 | 10 | No | No | Fecha del CP modificado | DD/MM/AAAA | Oblig. si el tipo es 07, 08, 87 u 88 |
| 21 | 2 | No | No | Tipo del CP modificado | Numérico | Igual que el campo 20 («tabla 4», sic) |
| 22 | Hasta 20 | No | No | Serie del CP modificado | Alfanumérico | Si el tipo es 07, 08, 87, 88, 97 o 98 |
| 23 | Hasta 20 | No | No | Nro. del CP modificado | Alfanumérico | Si el tipo es 07, 08, 87 u 88 |
| 24 | 10 | No | No | Fecha de la constancia de detracción | DD/MM/AAAA | |
| 25 | Hasta 24 | No | No | Nro. de la constancia de detracción | Alfanumérico | |
| 26 | 1 | No | No | Marca de retención | Numérico | |
| 27 | 1 | No | No | Clasificación de bienes y servicios | Numérico | Tabla 23 |
| 28 | 1 | No | No | Error tipo 1: tipo de cambio | Numérico | |
| 29 | 1 | No | No | Error tipo 2: no habidos | Numérico | |
| 30 | 1 | No | No | Error tipo 3: renuncia a la exoneración | Numérico | |
| 31 | 1 | No | No | Indicador de medios de pago | Numérico | Tabla 10 |
| 32 | 1 | Sí | No | Estado | Numérico | `9` = ajuste de un periodo anterior |
| 33-64 | Hasta 200 | No | No | CLU | Texto | |

Notas del anexo 13:

- (2) Fecha según el lit. b) del inc. II del num. 1 del art. 10 del Reglamento del IGV.
- (3) Consolidación con un sistema computarizado.
- (4) Tipo de cambio: num. 17 del art. 5 del Reglamento del IGV.
- (5) Los ajustes de las notas de crédito y débito van en las columnas de base e impuesto.
- (6) Los campos de detracción solo se usan en los casos de detracciones y son optativos si hay un sistema de enlace.

---

## 11. Lo que no se pudo extraer o queda ambiguo

- **Tabla 3 (RVIE) y tabla 11 (RCE), tipos de CP y la columna que indica si cada tipo puede complementarse:** no se copian aquí. Están en `anexo-112-2021.txt` (líneas 361-1006), modificada por la [138] (líneas 252-686), y en `anexo-040-2022.txt` (líneas 153-1015).
- La **138 publica solo filas sueltas** («(…)»). Donde no reproduce una fila, rige la anterior. No hay texto consolidado oficial en `oficial/`.
- **Erratas de la norma**, que se copian tal cual:
  - «AAAAMM3.» en el periodo de los anexos 9 y 12 (8.5).
  - «AAAAMM003.» en el anexo 13 (5.1).
  - Extensión `.tx` en RCECOM y RCEINEX.
  - `CC 04` frente a `06` para los ajustes de no domiciliados.
  - Campo 36 frente a campo 37 como indicador E/I en el anexo 8.
  - «campo 42» en el anexo 13 (5.3).
  - Posición «34-34 N» frente a `NN` en el nombre del RVIE.
- Las normas **no** definen la codificación de caracteres, el fin de línea ni el pipe final. Esos detalles están en los manuales del servicio web (`Manual_*`), que no forman parte de este documento.
