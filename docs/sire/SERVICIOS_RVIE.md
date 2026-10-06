# Servicios API SIRE Ventas (RVIE): especificación según el manual oficial

**Fuente única:** *Manual de servicios Web API SIRE Ventas*, versión 22 (08/03/2024), en
`docs/sire/oficial/Manual_de_servicios_Web_Api_Ventas_v22_Parte_I.{pdf,txt}` (págs. 1-35) y
`..._Parte_II.{pdf,txt}` (págs. 36-102 de la numeración impresa; la página N de la Parte II es la impresa N+35).

Este documento solo copia el manual. Las capturas «Result OK» del PDF son imágenes y no aparecen en el `.txt`;
aquí se transcriben a mano (se avisa cuando una parte es ilegible). Cuando el manual no dice algo, se indica
**«el manual no lo indica»**. Las notas **⚠ Inconsistencia** señalan contradicciones internas del propio manual.

---

## 0. Convenciones comunes (todas copiadas del manual)

### 0.1 Host y prefijo

- Host: `https://api-sire.sunat.gob.pe`
- Prefijo de todos los servicios: `/v1/contribuyente/migeigv/libros/...`
- «Los servicios del API SIRE no deben ser consumidos desde un cliente Web, en caso de utilizar un cliente Web se
  producirá error de CORS» (sección 5, pág. 21).
- «Los servicios API REST que impliquen el desarrollo de un cliente TUS […] deben ser desarrollados en el lenguaje
  JAVA (Ver Anexo 7.5)» (sección 5, pág. 21). Ver §0.5.

### 0.2 Token (5.1 Servicio Api Seguridad, pág. 21)

- `POST https://api-seguridad.sunat.gob.pe/v1/clientessol/{client_id}/oauth2/token/`
- Cabecera: `Content-type: application/x-www-form-urlencoded` (marcada «opcional»).
- Cuerpo (form-urlencoded): `grant_type=password`, `scope=https://api-sire.sunat.gob.pe`, `client_id`,
  `client_secret`, `username={RUC}{USUARIO}`, `password={CLAVESOL}`.
- Respuesta OK (captura): `{"access_token": "eyJ…", …}` (el resto del JSON no se ve en la captura).
- Respuesta de error (captura, HTTP 400): `{"error_description": "Error en la autenticacion del usuario.", "error": "access_denied"}`.
- La validez del token: **el manual no lo indica**.

### 0.3 Cabeceras de los servicios REST

Todas las tablas de los servicios REST indican:

| Cabecera | Valor |
|---|---|
| `Content-Type` | `application/json` |
| `Accept` | `application/json` |
| `Authorization` | `Bearer <token obtenido de la autenticación>` |

En muchos servicios la tabla añade antes la línea `Content-type: application/x-www-form-urlencoded` y, a
continuación, la tabla con `application/json`. Se reproduce tal cual en cada servicio.

### 0.4 `numRuc`

El control de cambios de la v22 (pág. 6) dice: «Se retira el parámetro numRuc (obligatorio) de todos los servicios
dado que ese dato se encuentra en el token del contribuyente». Aun así, los ejemplos de metadatos TUS y el ejemplo
Java del Anexo V siguen enviando `numRuc`.

### 0.5 Protocolo TUS (sección 6 y Anexo V)

- Sección 6: tus.io es «un protocolo abierto para carga reanudable basado en HTTP»; el manual solo proporciona el
  endpoint servidor y remite a <https://tus.io/implementations> para el cliente.
- Servicios que funcionan como servidor TUS: 5.3, 5.4, 5.5, 5.6 y 5.7.
- Anexo V (págs. 73-102): cliente Java con `tus-java-client` **0.5.0**
  (`https://repo1.maven.org/maven2/io/tus/java/client/tus-java-client/0.5.0/tus-java-client-0.5.0.jar`), más clases
  propias (`TusResponseBody`, `Http401And403CodeException`, `Http422CodeException`, `HttpErrorCodeException`,
  `TusClientCustom`, `TusUploaderCustom`) para leer los errores 401/403/422.
- Lo que se deduce **del código Java del Anexo V** (no hay otra descripción del protocolo en el manual):
  - Creación: `POST <url de upload>` con cabeceras `Tus-Resumable: 1.0.0` (`TUS_VERSION = "1.0.0"`),
    `Upload-Length: <bytes>`, `Upload-Metadata: <metadatos codificados>` y las cabeceras configuradas en el cliente
    (`authorization: Bearer <TOKEN>`). La respuesta debe ser 2xx y traer `Location` (URL del upload).
    401/403 → `Http401And403CodeException`; 422 → `Http422CodeException`.
  - Envío: `PATCH <Location>` (o `POST` con `X-HTTP-Method-Override: PATCH`) con
    `Content-Type: application/offset+octet-stream`. El cliente por defecto usa trozos de 2 MiB
    (`setChunkSize(2 * 1024 * 1024)`); el `Demo.java` usa `uploader.setChunkSize(1024)`.
  - Al terminar, `uploader.finish()` lee el cuerpo de la última respuesta (`TusResponseBody`): ahí viene el ticket.
  - `Upload-Metadata`: formato estándar TUS `clave base64(valor)` separados por comas. Los ejemplos del manual
    muestran exactamente ese formato (p. ej. `filename TEUy…,filetype YXBwbGljYXRpb24vemlw,numRuc MjAx…`).
- `Demo.java` (págs. 100-102), copiado literalmente en lo esencial:

  ```java
  HOST_PUBLICA = "https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/";
  END_POINT_PROPUESTA = "libros/rvierce/receptorpropuesta/web/propuesta/upload";
  headers.put("authorization", "Bearer " + TOKEN);
  metaData.put("filename", archivo.getName());
  metaData.put("filetype", extension[1]);          // extensión del archivo, p. ej. "zip"
  metaData.put("numRuc", "20108745216");
  metaData.put("perTributario", "202304");
  metaData.put("codOrigenEnvio", "3");
  metaData.put("codLibro", "140000");
  metaData.put("codProceso", "1");
  metaData.put("codTipoCorrelativo", "1");
  metaData.put("nomArchivoImportacion", archivo.getName());
  // archivo de ejemplo: LE201000174912023110014040003111201.zip (ruta …\ajuste_posterior\)
  ```

### 0.6 Respuestas de error genéricas (idénticas en todos los servicios)

```json
{ "cod":"500", "msg":"Internal Server Error - Se presento una condicion inesperada que impidio completar el Request", "exc":"java.lang.NullPointerException at ..." }
```

```json
{ "cod":"422", "msg":"Unprocessable Entity - Se presentaron errores de validacion que impidieron completar el Request", "errors":[ { "cod":"1001", "msg":"El campo “numRuc” no enviado o es vacío" }] }
```

### 0.7 Ticket

Formato `numTicket` (alfanumérico, String): `[AAAA99999999]` → `AAAA` año, `99` tipo de correlativo (Anexo II),
`99999999` número correlativo de envío. En las capturas el ticket tiene 14 caracteres (p. ej. `20230100000119`).

---

## 5.2 Consultar año y mes

| Campo | Valor (manual pág. 22-23) |
|---|---|
| Descripción | Permite consultar los periodos (años y meses) habilitados para el contribuyente. |
| Método | `GET` |
| URL | `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/padron/web/omisos/{codLibro}/periodos` |
| Cabeceras | §0.3 (`Content-Type`, `Accept`, `Authorization`) |
| Cuerpo | No aplica |

**Parámetros de URL**

| Parámetro | Formato-tipo | Obligatorio | Valores |
|---|---|---|---|
| `codLibro` | alfanumérico-String | Sí | `140000` RVIE |

**Salida** (tabla): `numEjercicio` (String, año o ejercicio), `desEstado` (String, descripción del ejercicio),
`lisPeriodos` (array) con `perTributario`, `codEstado` (código del estado del periodo) y `desEstado`.
Los valores de `codEstado` posibles: **el manual no lo indica** (en la captura solo aparece `"01"` = `"Presentado"`).

**Ejemplo** — URL `…/padron/web/omisos/140000/periodos`. Respuesta OK (captura, HTTP 200): la raíz es un **array**:

```json
[
  {
    "numEjercicio": "2023",
    "desEstado": "Presentado",
    "lisPeriodos": [
      { "perTributario": "202305", "codEstado": "01", "desEstado": "Presentado" },
      { "perTributario": "202304", "codEstado": "01", "desEstado": "Presentado" },
      { "perTributario": "202303", "codEstado": "01", "desEstado": "Presentado" },
      { "perTributario": "202302", "codEstado": "01", "desEstado": "Presentado" }
    ]
  }
]
```

**Errores 422:** `1140` El campo “codLibro” no enviado o es vacío.

---

## 5.4 Importar nuevos comprobantes propuesta (TUS)

| Campo | Valor (manual págs. 25-26) |
|---|---|
| Descripción | Permite al generador agregar nuevos comprobantes que no han sido propuestos por la administración. |
| Método | TUS (§0.5): `POST` de creación + `PATCH` de envío |
| URL | `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/receptorpropuesta/web/propuesta/upload` |
| Cabeceras | `Content-type: application/x-www-form-urlencoded` + «Metadata Cliente TUS» |
| Cuerpo | No aplica (el archivo va por TUS) |
| Tecnología | «Uso del protocolo TUS.IO (Ver ítem 6. Documentación TUS.IO)» |

> Es **la misma URL** que 5.3 (reemplazo de la propuesta); lo que distingue el proceso es `codProceso`.

**Metadatos TUS**

| Metadato | Formato-tipo | Obligatorio | Descripción / valor |
|---|---|---|---|
| `filename` | alfanumérico-String | Sí | Nombre de archivo |
| `filetype` | alfanumérico-String | Sí | Tipo de archivo |
| `perTributario` | alfanumérico-String | Sí | Periodo tributario |
| `codOrigenEnvio` | alfanumérico-String | Sí | `2` Servicio web |
| `codProceso` | alfanumérico-String | Sí | `1` «Importar CP» (Anexo I) |
| `codTipoCorrelativo` | alfanumérico-String | Sí | `01` Tipo envíos masivos (Anexo II) |
| `nomArchivoImportacion` | alfanumérico-String | Sí | Nombre definido en la tabla 6 del Anexo N° 1 de la R.S. 112-2021/SUNAT, «estructura e información del archivo texto para complementar la propuesta del RVIE con comprobantes de pago físicos»: `RRRRRRRRRRR-CPF-AAAAMM-Correlativo.txt` |
| `codLibro` | alfanumérico-String | Sí | `140000` RVIE |

**Ejemplo de metadatos** (manual, base64 decodificado entre corchetes):
`filename MjAxMDAxNzY0NTAtQ1BGLTIwMjMwMi0wMS56aXA=` [`20100176450-CPF-202302-01.zip`],
`filetype YXBwbGljYXRpb24vemlw` [`application/zip`], `numRuc MjAxMDAxNzY0NTA=` [`20100176450`],
`perTributario MjAyMzAy` [`202302`], `codOrigenEnvio MQ==` [`1`], `codProceso MQ==` [`1`],
`codTipoCorrelativo MQ==` [`1`], `nomArchivoImportacion` = mismo valor que `filename`, `codLibro MTQwMDAw` [`140000`].

**Salida:** `numTicket` (§0.7). Captura «Result OK» (pestaña Respuesta del navegador): cuerpo en **texto plano**
`20230100000124` (sin JSON).

**Errores 422** (lista común a 5.3, 5.4, 5.5, 5.6 y 5.7):

- 1001 El campo “numRuc” no enviado o es vacío
- 1002 Solo se permite dato numérico de 11 dígitos para el número de RUC.
- 1003 El RUC ingresado no existe o no es válido
- 1005 El campo ‘perTributario’ no enviado o es vacio
- 1006 Formato de perTributario no cumple con el formato ‘yyyymm’
- 1007 El perTributario de búsqueda no debe ser mayor a la fecha actual
- 1028 El campo “codOrigenEnvio” no enviado o es vacío
- 1029 Código tipo de Origen de Envio no permitido o no valido
- 1030 Solo se permite dato numérico de 1 dígito para el codOrigenEnvio
- 1025 El campo “codProceso” no enviado o es vacío
- 1026 Código Proceso no permitido o no valido
- 1027 Solo se permite dato numérico para el codProceso
- 1138 El campo "codProceso" es nulo o vacío
- 1139 Código de Proceso no permitido o no valido
- 1048 Solo se permite dato numérico de 1 dígito para el codTipoOrigen
- 1022 nombre del archivo no enviado o es vacio.
- 1024 El archivo <nombre del archivo txt> fue previamente enviado.
- 1044 Error en la <<Posición - Descripción>> del nombre del archivo plano, favor de corregir
- 1348 La extensión del archivo es diferente a “.zip”, por favor corregir
- 1346 El tamaño del archivo comprimido en formato “.zip” debe ser menor o igual a 6GB.
- 1350 El tamaño del archivo mayor a 0 Kb.
- 1351 Se ha producido un error al realizar el envío del archivo, por favor volver a intentar el envío
- 1048 Solo se permite dato numérico de 2 dígitos para el codTipoCorrelativo *(el código 1048 aparece dos veces con textos distintos)*
- 1049 El campo “codTipoCorrelativo” no enviado o es vacio
- 1050 Código tipo de Correlativo no permitido o no valido
- 1140 El campo “codLibro” no enviado o es vacío

> ⚠ Inconsistencias: (a) la tabla dice `nomArchivoImportacion` = `….txt`, pero el ejemplo y el error 1348 exigen
> `.zip` (las Funcionalidades de la Guía de Uso hablan de «archivo de formato .txt zipeado»); (b) la tabla dice
> `codOrigenEnvio = 2`, el ejemplo base64 envía `1` y el `Demo.java` envía `3`; (c) la tabla dice
> `codTipoCorrelativo = 01`, el ejemplo envía `1`.

---

## 5.5 Importar nuevos comprobantes preliminar (TUS)

| Campo | Valor (manual págs. 27-28) |
|---|---|
| Descripción | Permite importar nuevos comprobantes en el preliminar de RVIE. |
| Método | TUS (§0.5) |
| URL | `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/receptorpreliminar/web/preliminar/upload` |
| Cabeceras | `Content-type: application/x-www-form-urlencoded` + metadatos TUS |
| Cuerpo | El manual no incluye fila «Parámetros[body]» en este servicio |
| Requisito (Guía de Uso, Funcionalidad 3, pág. 16) | «previamente debe haber reemplazado la propuesta» (5.3) |

**Metadatos TUS:** mismos campos y obligatoriedad que 5.4, con:

| Metadato | Valor |
|---|---|
| `codProceso` | `4` «Importa CP - Preliminar» |
| `codOrigenEnvio` | `2` Servicio web |
| `codTipoCorrelativo` | `01` |
| `nomArchivoImportacion` | tabla 6 del Anexo N° 1 de la R.S. 112-2021/SUNAT, «estructuras e información del registro electrónico - RVIE»: `LERRRRRRRRRRRAAAAMM0014040002OIM2.txt` |
| `codLibro` | `140000` |

**Ejemplo de metadatos:** `filename`/`nomArchivoImportacion` = `LE2010017645020230200140400020112.zip`,
`filetype` = `application/zip`, `numRuc` = `20100176450`, `perTributario` = `202302`, `codOrigenEnvio` = `1`,
`codProceso` = `4` (`NA==`), `codTipoCorrelativo` = `1`, `codLibro` = `140000`.

**Salida:** `numTicket`. Captura: texto plano `20230100000123`.

**Errores:** lista común de 5.4 (aquí el manual la titula «Lista de errores» sin «422»).

---

## 5.6 Importar ajustes posteriores (TUS)

| Campo | Valor (manual págs. 28-30) |
|---|---|
| Descripción | Cargar ajustes posteriores SIRE |
| Método | TUS (§0.5) |
| URL | `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/receptorajustesposteriores/web/ajustesposteriores/upload` |
| Cabeceras | `Content-type: application/x-www-form-urlencoded` + metadatos TUS |
| Cuerpo | No Aplica |
| Requisito (Funcionalidad 4, pág. 16) | «debe primero haber generado el periodo que desea ajustar» |

**Metadatos TUS:** mismos campos que 5.4, con:

| Metadato | Valor según la tabla | Valor en el ejemplo |
|---|---|---|
| `codProceso` | `6` «Cargar Ajuste posteriores del SIRE» | `87` (`ODc=`) |
| `codOrigenEnvio` | `2` | `1` |
| `codTipoCorrelativo` | `01` | `1` |
| `nomArchivoImportacion` | tabla 6 del Anexo N° 1 R.S. 112-2021/SUNAT; «la estructura dependerá de la descripción consignada» | `LE20100176450202302001404000311102.zip` |
| `perTributario` | Periodo tributario | `202302` |
| `codLibro` | `140000` | `140000` |

> ⚠ Inconsistencia: la tabla pide `codProceso = 6` (Anexo I: «Cargar Ajuste posteriores al periodo actual»), pero
> el ejemplo envía `87` (Anexo I: «Importar CP en Ajustes Posteriores RVIE.»). El manual no aclara cuál acepta el
> servidor. Qué periodo va en `perTributario` (el ajustado o el actual): **el manual no lo indica**.

**Salida:** `numTicket`. Captura: texto plano `20230100000124`.
**Errores 422:** lista común de 5.4.

---

## 5.7 Importar ajustes posteriores de periodos anteriores (TUS)

| Campo | Valor (manual págs. 30-31) |
|---|---|
| Descripción | Cargar Ajustes posteriores anteriores de periodos anteriores al SIRE |
| Método | TUS (§0.5) |
| URL | `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/receptorajustesposteriores/web/ajustesposteriores/upload` (**misma URL que 5.6**) |
| Cabeceras | `Content-type: application/x-www-form-urlencoded` + metadatos TUS |
| Cuerpo | No Aplica |
| Requisito (Funcionalidad 5, pág. 17) | «debe hacerlo referenciando al último periodo generado en el SIRE» |

**Metadatos TUS:** mismos campos que 5.4, con:

| Metadato | Valor según la tabla | Valor en el ejemplo |
|---|---|---|
| `codProceso` | `7` «Cargar Ajuste posteriores anteriores a la vigencia» | `88` (`ODg=`) |
| `codOrigenEnvio` | `2` | `1` |
| `codTipoCorrelativo` | `01` | `1` |
| `nomArchivoImportacion` | tabla 6 del Anexo N° 1 R.S. 112-2021/SUNAT; «la estructura dependerá de la descripción consignada» | `LE201001764502023030014040004111202.zip` |
| `perTributario` | Periodo tributario | `202303` |
| `codLibro` | `140000` | `140000` |

> ⚠ Igual que 5.6: tabla `7` frente a ejemplo `88` (Anexo I 88: «Importar CP en Ajustes Posteriores de periodos
> anteriores RVIE general.»; 89 es la variante «simplificado»). Cuándo usar 88 o 89: **el manual no lo indica**.

**Salida:** `numTicket`. Captura: texto plano `20230100000124`.
**Errores 422:** lista común de 5.4.

---

## 5.10 Exclusión definitiva de notas de crédito y facturas

| Campo | Valor (manual págs. 33-34) |
|---|---|
| Descripción | Permite la exclusión de las notas de crédito y facturas de manera definitiva e irreversible |
| Método | `POST` |
| URL | `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvie/propuesta/web/propuesta/{perTributario}/retiracomprobante?codCar={codCar}&codSituacion={codSituacion}` |
| Cabeceras | `Content-type: application/x-www-form-urlencoded`; tabla: `Content-Type: application/json`, `Accept: application/json`, `Authorization: Bearer …` |
| Cuerpo | No aplica |

**Parámetros (URL)**

| Parámetro | Formato-tipo | Obligatorio | Valores |
|---|---|---|---|
| `perTributario` (path) | alfanumérico-String | Sí | Periodo tributario |
| `codCar` (query) | alfanumérico-String | Sí | Código de Anotación de Registro (CAR SUNAT); error 1136: numérico de 27 dígitos |
| `codSituacion` (query) | alfanumérico-String | Sí | `0` inactivo |

**Ejemplo:** `…/propuesta/202302/retiracomprobante?codCar=2013729131301FD880000001007&codSituacion=0`
(el CAR del ejemplo tiene letras pese al error 1136).
**Salida:** HTTP 200, `Content-Type: application/json`. Captura: cuerpo `"OK"`.

**Errores:** 1005 perTributario no enviado o vacío · 1006 formato ‘yyyymm’ · 1135 El campo “codCar” no enviado o es
vacío · 1136 Solo se permite dato numérico de 27 dígitos para el Codigo CAR. · 1120 Solo se permite dato numérico de 1
dígito para el codSituacion.

---

## 5.11 Agregar tipo de cambio masivo

| Campo | Valor (manual págs. 34-35) |
|---|---|
| Descripción | Permite actualizar masivamente todos los tipos de cambio de comprobantes que la administración no encontró tipo de cambio propuesto; los montos propuestos se actualizan con el o los tipos de cambio ingresados. |
| Método | `POST` |
| URL | `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvie/propuesta/web/masivo/{perTributario}/guardacomplementomasivo` |
| Cabeceras | §0.3 |
| Cuerpo | JSON (array) |

> No es una carga TUS ni un archivo TXT: es un cuerpo JSON.

**Parámetro de URL:** `perTributario` (alfanumérico-String, obligatorio).

**Cuerpo (array de objetos)**

| Campo | Formato-tipo | Obligatorio | Descripción |
|---|---|---|---|
| `fecEmision` | dd/mm/yyyy-String | Sí | Fecha de emisión del documento |
| `codMoneda` | numérico-String | Sí | Códigos de moneda |
| `mtoTipoCambio` | decimal-String | Sí | Tipo de cambio de PEN (Soles) a USD (Dólares) |
| `mtoCambioMonedaExt` | decimal-String | No | Tipo de cambio de moneda extranjera a PEN (Soles) |

**Ejemplo de cuerpo** (captura):

```json
[
  { "fecEmision": "2023-01-01", "codMoneda": "USD", "mtoTipoCambio": "3.45" },
  { "fecEmision": "2023-01-03", "codMoneda": "EUR", "mtoTipoCambio": "4.75" },
  { "fecEmision": "2023-01-05", "codMoneda": "USD", "mtoTipoCambio": "3.46" }
]
```

> ⚠ Inconsistencia: la tabla dice `dd/mm/yyyy` y `codMoneda` «numérico», pero el ejemplo usa `yyyy-mm-dd` y códigos
> ISO alfabéticos (`USD`, `EUR`). La tabla de monedas válidas: **el manual no la indica**.

**Salida:** HTTP 200, `Content-Type: application/json`. Captura: cuerpo vacío (vista «Text»).

**Errores 422:** 1005, 1006, 1007 (perTributario) · 1141 Código tipo de moneda no permitido o no valido · 1142 No se
permite el tipo de dato para codMoneda · 1143 El campo "codMoneda" es nulo o vacío · 1144 El campo "mtoTipoCambio" es
nulo o vacío · 1145 Solo se permite dato numérico y decimal para el mtoTipoCambio.

---

## 5.12 Editar tipo de cambio individual

| Campo | Valor (manual págs. 36-37) |
|---|---|
| Descripción | Edita el tipo de cambio individual en propuesta de ventas |
| Método | `PUT` |
| URL | `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvie/propuesta/web/propuesta/{perTributario}/complementoindividual` |
| Cabeceras | `Content-type: application/x-www-form-urlencoded`; tabla §0.3 |
| Cuerpo | JSON (objeto) |

**Parámetro de URL:** `perTributario` (alfanumérico-String, obligatorio).

| Campo del cuerpo | Formato-tipo | Obligatorio | Descripción |
|---|---|---|---|
| `codCar` | alfanumérico-String | Sí | CAR SUNAT |
| `codMoneda` | numérico-String | Sí | Códigos de moneda |
| `mtoTipoCambio` | decimal-String | Sí | Tipo de cambio de PEN a USD |
| `mtoCambioMonedaExt` | decimal-String | No | Tipo de cambio de moneda extranjera a PEN |

**Ejemplos de cuerpo** (capturas; CAR transcritos de imagen de baja resolución):

```json
{ "codCar": "<CAR ilegible>", "codMoneda": "EUR", "mtoTipoCambio": "4.760" }
{ "codCar": "<CAR ilegible>", "codMoneda": "EUR", "mtoTipoCambio": "3.71", "mtoCambioMonedaExt": "4.11" }
```

(Los dígitos exactos de los CAR no son legibles con seguridad; se ve que `codMoneda` va como `"EUR"`.)

**Salida:** HTTP 200, `application/json`. Captura: `"OK"`.

**Errores 422:** 1005, 1006, 1007 · 1135, 1136 (codCar) · 1141, 1142, 1143 (codMoneda) · 1144, 1145 (mtoTipoCambio).

---

## 5.13 Eliminar comprobante propuesta

| Campo | Valor (manual págs. 37-38) |
|---|---|
| Descripción | Permite eliminar un comprobante de la propuesta que ha sido agregado por el contribuyente |
| Método | `POST` |
| URL | `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvie/propuesta/web/propuesta/{perTributario}/eliminacomprobante` |
| Cabeceras | §0.3 |
| Cuerpo | JSON (array) |

**Parámetro de URL:** `perTributario` (obligatorio).

| Campo (cada elemento) | Formato-tipo | Obligatorio | Descripción |
|---|---|---|---|
| `numSerieCDP` | alfanumérico-String | Sí | Número de serie del comprobante de pago o documento |
| `numCDP` | alfanumérico-String | Sí | Número del comprobante |
| `codCar` | alfanumérico-String | Sí | CAR SUNAT |
| `codTipoCDP` | alfanumérico-String | Sí | Solo permite 00, 01, 03, 05, 06, 07, 08, 11, 12, 13, 14, 15, 16, 18, 21, 24, 25, 27, 28, 30, 32, 34, 35, 36, 37, 42, 43, 44, 45, 48, 49, 55 y 56 «(en tanto haya sido incorporado por importación o agregar en ningún caso se debe eliminar el CP propuesto)» |

**Ejemplo de cuerpo** (captura):

```json
[ { "codTipoCDP": "01", "codCar": "<CAR de 27 posiciones>", "numCDP": "1", "numSerieCDP": "0001" } ]
```

(Captura de baja resolución: la serie se lee como `0001`/`B001`; el CAR no es legible con exactitud.)

**Salida:** HTTP 200, `application/json`. Captura: `"OK"`.

**Errores 422:** 1005, 1006, 1007 · 1070 No se ha encontrado información de comprobantes de pago en Periodo
Seleccionado · 1135, 1136 · 1323 El campo "numSerieCDP" es nulo o vacío · 1011 El campo “codTipoCDP” no enviado o es
vacío · 1012 El codTipoCDP ingresado no existe o no es válido.

---

## 5.14 Eliminar comprobante preliminar

| Campo | Valor (manual págs. 38-39) |
|---|---|
| Descripción | Permite eliminar un comprobante del preliminar RVIE |
| Método | `PUT` |
| URL | `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/gestionlibro/web/registroslibros/{perTributario}/comprobantepreliminar` |
| Cabeceras | §0.3 |
| Cuerpo | JSON (array) |
| Requisito (Funcionalidad 6, pág. 17) | «previamente debe haber reemplazado la propuesta» |

| Campo (cada elemento) | Formato-tipo | Obligatorio | Descripción |
|---|---|---|---|
| `codCar` | alfanumérico-String | Sí | CAR SUNAT |
| `codTipoCDP` | alfanumérico-String | Sí | Todos los códigos de la tabla 03 del anexo 01 de la R.S. 112-2021/SUNAT |
| `numSerieCDP` | alfanumérico-String | Sí | Serie |
| `numCDP` | alfanumérico-String | Sí | Número |

**Ejemplo de cuerpo** (captura): `[ { "codTipoCDP": "01", "codCar": "<CAR>", "numCDP": "0009", "numSerieCDP": "0123" } ]`
(valores de baja resolución).

**Salida:** HTTP 200, `application/json`. Captura: `"OK"`.

**Errores 422:** 1005, 1006, 1007 · 1135, 1136 · 1323 · 1011 · 1012.

---

## 5.15 Eliminar reemplazo propuesta

| Campo | Valor (manual pág. 40) |
|---|---|
| Descripción | Permite eliminar el reemplazo de la propuesta. |
| Método | `PUT` |
| URL | `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/gestionlibro/web/registroslibros/{perTributario}/eliminarreemplazo?codLibro={codLibro}` |
| Cabeceras | §0.3 |
| Cuerpo | No aplica |

| Parámetro | Formato-tipo | Obligatorio | Valores |
|---|---|---|---|
| `perTributario` (path) | alfanumérico-String | Sí | Periodo |
| `codLibro` (query) | alfanumérico-String | Sí | `140000` |

**Ejemplo:** `…/registroslibros/202302/eliminarreemplazo?codLibro=140000`.
**Salida:** HTTP 200, `application/json`. Captura: `"OK"`.
**Errores 422:** 1005, 1006, 1007, 1140.

---

## 5.16 Consultar estado de envío de ticket

| Campo | Valor (manual págs. 40-43) |
|---|---|
| Descripción | Permite consultar el estado de envío del ticket. |
| Método | `GET` |
| URL | `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/gestionprocesosmasivos/web/masivo/consultaestadotickets?perIni={perIni}&perFin={perFin}&page={page}&perPage={perPage}&numTicket={numTicket}` |
| Cabeceras | §0.3 |
| Cuerpo | No aplica |

> La ruta es `rvierce` (común a RVIE y RCE); **no lleva `codLibro`**.

**Parámetros (query)**

| Parámetro | Formato-tipo | Obligatorio | Descripción |
|---|---|---|---|
| `perIni` | alfanumérico-String | Sí | Periodo de consulta… Inicio (`yyyymm`, ver errores) |
| `perFin` | alfanumérico-String | Sí | Periodo de consulta… Final |
| `page` | numérico-int | Sí | Ejemplo: 1 |
| `perPage` | numérico-int | Sí | Ejemplo: 20 |
| `numTicket` | alfanumérico-String | **No** | Número de ticket `[AAAA99999999]` |

**Estructura de salida** (tabla del manual, campo a campo):

```
paginacion (Object)
  page            numérico-Int     Ejemplo: 1
  perPage         numérico-Int     Ejemplo: 20
  totalRegistros  numérico-Int     Total de registros
registros (array)
  showReportesDescarga  numérico-Integer  0 = no muestra icono de archivo de texto; 1 = muestra ícono
  perTributario         String            Periodo tributario
  numTicket             String            Número de ticket de envío
  fecCargaImportacion   dd/mm/yyyy,'T','hh:ii:ss'-Date  Fecha de la carga del archivo, o de solicitud de generación
  fecInicioProceso      yyyy-mm-dd-String Fecha de inicio de proceso
  codProceso            String            Código del indicador de carga masiva (Anexo I)
  desProceso            String            Descripción del indicador (Anexo I)
  codEstadoProceso      String            Código de estado de envío (Anexo III)
  desEstadoProceso      String            Descripción de estado de envío (Anexo III)
  nomArchivoImportacion String            Nombre del archivo de importación
  detalleTicket (Object)
    numTicket            String           [AAAA99999999]
    fecCargaImportacion  dd/mm/yyyy-Date
    horaCargaImportacion hh:mm:ss-Date
    codEstadoEnvio       String           Código del estado de envío
    desEstadoEnvio       String           Descripción del estado de envío
    nomArchivoReporte    String           Nombre del archivo reporte
    cntFilasvalidada     numérico-Integer Cantidad de filas validadas o total de registros
    cntCPError           numérico-Integer Cantidad de comprobantes con error
    cntCPInformados      numérico-Integer Cantidad de CP informados
  archivoReporte (Array)
    codTipoAchivoReporte  alfanumérico-String  Código del tipo de archivo de reporte
    nomArchivoReporte     alfanumérico-String  Nombre del archivo de reporte
    nomArchivoContenido   alfanumérico-String  Nombre del archivo contenido
```

> ⚠ El nombre de la clave es **`codTipoAchivoReporte`** (sin la «r» de «Archivo»), tanto en la tabla como en la
> respuesta real de la captura. En cambio, el parámetro de entrada de 5.17 se llama **`codTipoArchivoReporte`**.
> La tabla escribe `showReportesDescarga`; la captura muestra `showReporteDescarga`.

**Catálogo de `codTipoAchivoReporte`: el manual no lo indica.** Los únicos valores que aparecen son `"00"` (captura
de 5.16, para un archivo `…EXP2.txt`), `01` (URL de ejemplo de 5.17) y `null` (nota de 5.17: «Si el campo
codTipoAchivoReporte que devuelve el API 5.16 es null, colocar el mismo valor (null)»). El significado de cada
código: **el manual no lo indica**.

**Ejemplo** — URL `…/consultaestadotickets?perIni=202301&perFin=202305&page=1&perPage=20`.
Respuesta OK (captura, HTTP 200; el primer registro está plegado en la captura; transcripción):

```json
{
  "paginacion": { "page": 1, "perPage": 20, "totalRegistros": 6 },
  "registros": [
    { "…": "(registro plegado en la captura)" },
    {
      "showReporteDescarga": "1",
      "perTributario": "202302",
      "numTicket": "20230200000156",
      "fecCargaImportacion": null,
      "fecInicioProceso": "2023-08-14",
      "codProceso": "5",
      "desProceso": "Generación de Registros",
      "codEstadoProceso": "06",
      "desEstadoProceso": "Terminado",
      "nomArchivoImportacion": "",
      "detalleTicket": {
        "numTicket": "20230200000156",
        "fecCargaImportacion": "2023-08-14",
        "horaCargaImportacion": "13:49:07",
        "codEstadoEnvio": "06",
        "desEstadoEnvio": "Terminado",
        "nomArchivoReporte": "LE20563472678202302001404000…EXP2.txt",
        "cntFilasvalidada": 0,
        "cntCPError": 0,
        "cntCPInformados": 0
      },
      "archivoReporte": [
        {
          "codTipoAchivoReporte": "00",
          "nomArchivoReporte": "LE20563472678202302001404000…EXP2.txt",
          "nomArchivoContenido": null
        }
      ]
    }
  ]
}
```

(Captura de baja resolución: `totalRegistros` podría ser 6 u 8; el tramo central de `nomArchivoReporte` no se lee
con seguridad. Los tipos reales difieren de la tabla: `showReporteDescarga` llega como cadena `"1"`, y
`fecInicioProceso`/`fecCargaImportacion` del detalle llegan como `yyyy-mm-dd`.)

**Estados (Anexo III):** 01 Cargado (solicitado) · 02 Validando Archivo (en proceso) · 03 Procesado con Errores ·
04 Procesado sin errores (concluido) · 05 En proceso · 06 Terminado. La Guía de Uso (Funcionalidad 8, pág. 18)
recomienda descargar solo cuando el estado sea «Terminado».

**Errores 422:** 1067 El campo “perIni” no enviado o es vacío · 1068 Formato de perIni no cumple con el formato
“yyyymm” · 1069 El perIni de búsqueda no debe ser mayor a la fecha actual · 1070 No se ha encontrado información de
comprobantes de pago en Periodo Seleccionado · 1071/1072/1073 (ídem para perFin) · (sin código) El campo “page” no
enviado o es vacío · (sin código) El campo “page” debe ser numérico mayor a cero · (sin código) El campo “per_page” no
enviado o es vacío · (sin código) El campo “per_page” debe ser numérico mayor a cero · 1052 Formato no permitido o no
valido para el número de Ticket.

---

## 5.17 Descargar archivo

| Campo | Valor (manual págs. 43-45) |
|---|---|
| Descripción | Permite descargar los archivos generados zipeados y particionados guardados en el fileserver. |
| Método | `GET` |
| URL | `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/gestionprocesosmasivos/web/masivo/archivoreporte?nomArchivoReporte={nomArchivoReporte}&codTipoArchivoReporte={codTipoArchivoReporte}&codLibro={codLibro}` |
| Cabeceras | `Content-type: application/x-www-form-urlencoded`; tabla §0.3 |
| Cuerpo | No aplica |

| Parámetro (query) | Formato-tipo | Obligatorio | Descripción |
|---|---|---|---|
| `nomArchivoReporte` | alfanumérico-String | Sí | Salida de 5.16: `archivoReporte.nomArchivoReporte` |
| `codTipoArchivoReporte` | numérico-String | Sí | Salida de 5.16: `archivoReporte.codTipoArchivoReporte`. «Nota: Si el campo codTipoAchivoReporte que devuelve el API 5.16 es null, colocar el mismo valor (null)» |
| `codLibro` | numérico-String | Sí | `140000` |

**Salida:** `Buffer-binary-binary` («buffer: Arreglo de bits»).
**Ejemplo:** `…/archivoreporte?nomArchivoReporte=20100176450-CPF-202302-01.zip&codTipoArchivoReporte=01&codLibro=140000`.
Captura (texto de la query ilegible en parte): se ve `codTipoArchivoReporte` = `null`; la respuesta (HTTP 200,
vista «Text») es un ZIP binario (empieza por `PK`) que contiene `20100176450_INCONSISTENCIA_20230524.txt`.

**Errores 422:** 1134 El campo “nomArchivoReporte” no enviado o es vacío · 1140 El campo “codLibro” no enviado o es vacío.

---

## 5.20 Descargar resumen

| Campo | Valor (manual págs. 48-49) |
|---|---|
| Descripción | Permite descargar todos los tipos de resumen, propuesta, incluidos o excluidos, preliminar, RVIE generado, ajustes posteriores |
| Método | `GET` |
| URL | `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/resumen/web/resumencomprobantes/{perTributario}/{codTipoResumen}/{codTipoArchivo}/exporta?codLibro={codLibro}` |
| Cabeceras | `Content-type: application/x-www-form-urlencoded`; tabla §0.3 |
| Cuerpo | No aplica |

| Parámetro | Formato-tipo | Obligatorio | Valores |
|---|---|---|---|
| `perTributario` (path) | alfanumérico-String | Sí | Periodo |
| `codTipoResumen` (path) | alfanumérico-String | Sí | «Código de tipo resumen». Error 1056: numérico de 1 dígito. **Catálogo: el manual no lo indica** |
| `codTipoArchivo` (path) | numérico-Integer | Sí | Anexo IV: `0` txt, `1` excel, `2` csv |
| `codLibro` (query) | alfanumérico-String | Sí | `140000` |

**Salida:** `Buffer-binary-binary`.
**Ejemplo:** `…/resumencomprobantes/202301/1/0/exporta?codLibro=14000` (sic, el ejemplo dice `14000`).
Captura (HTTP 200, vista «Text»): texto separado por `|`:

```
Tipo de Documento|Total Documentos|Valor facturado la exportación|Base imponible de la operación gravada|Dscto. de la Base Imponible|Monto Total del IGV|Dscto. del IGV|Importe total de la operación exonerada|Importe total de la operación inafecta|ISC|Base imponible de la operación gravada con el Impuesto a las Ventas del Arroz Pilado|Impuesto a las Ventas del Arroz Pilado|ICBPER|Otros Trib/ Cargos|Total CP
TOTAL |0|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00
```

**Errores 422:** 1005, 1006 · 1070 · 1140 · 1059 Código tipo de Archivo no permitido o no valido · 1060 Solo se
permite dato numérico de 1 dígito para el codTipoArchivo · 1061 El campo "codTipoArchivo" es nulo o vacío · 1056 Solo
se permite dato numérico de 1 dígito para el codTipoResumen · 1057 El campo "codTipoResumen" es nulo o vacío.

---

## 5.21 Descargar resumen inconsistencias

| Campo | Valor (manual págs. 49-51) |
|---|---|
| Descripción | Retorna una lista con el resumen de inconsistencias de los comprobantes de pago de acuerdo al periodo y tipo de resumen, en formato json. |
| Método | `GET` |
| URL | `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/resumen/web/resumeninconsistencias/{perPeriodoTributario}?codTipoResumen={codTipoResumen}&codLibro={codLibro}` |
| Cabeceras | `Content-type: application/x-www-form-urlencoded`; tabla §0.3 |
| Cuerpo | No aplica |

| Parámetro | Formato-tipo | Obligatorio | Valores |
|---|---|---|---|
| `perPeriodoTributario` (path) | alfanumérico-String | Sí | Periodo |
| `codTipoResumen` (query) | numérico-Integer | Sí | «numérico de un carácter (1, 2, 3 ó 4)». Significado de cada valor: **el manual no lo indica** |
| `codLibro` (query) | alfanumérico-String | Sí | `140000` |

**Salida (tabla):** objeto con `numRuc`, `perPeriodoTributario`, `codTipoResumen` (Integer); `cantidad` (Object:
`porcentajeRelFiscal`, `porcentajeNoRelFiscal`, `porcentajeSinValidaciones`, `total`, todos decimal128) y `monto`
(Object con los mismos cuatro campos, sobre importes).

**Ejemplo:** `…/resumeninconsistencias/202304?codTipoResumen=1&codLibro=140000`. Captura (HTTP 200):

```json
{
  "numRuc": "20563472678",
  "perPeriodoTributario": "202304",
  "codTipoResumen": "1",
  "cantidad": { "porcentajeRelFiscal": 0, "porcentajeNoRelFiscal": 0, "porcentajeSinValidaciones": 100.00, "total": 5 },
  "monto":    { "porcentajeRelFiscal": 0, "porcentajeNoRelFiscal": 0, "porcentajeSinValidaciones": 100.00, "total": 799462465.690 }
}
```

(Valores numéricos transcritos de una captura de baja resolución; `codTipoResumen` llega como cadena.)

**Errores 422:** 1005, 1006 · 1070 · 1140 · 1056 · 1057.

---

## 5.24 Descargar inconsistencias en registros preliminar registrado

| Campo | Valor (manual págs. 54-55) |
|---|---|
| Descripción | Permite descargar inconsistencias |
| Método | `GET` |
| URL | `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/casillas/inconsistenciaslibros/{perTributario}/{numCas}/reporteinconsistencia?cntlimite={cntlimite}&mtoNoSustentado={mtoNoSustentado}&desMtoNoSustentado={desMtoNoSustentado}` |
| Cabeceras | `Content-type: application/x-www-form-urlencoded`; tabla §0.3 |
| Cuerpo | No aplica |

| Parámetro | Formato-tipo | Obligatorio | Descripción |
|---|---|---|---|
| `perTributario` (path) | alfanumérico-String | Sí | Periodo |
| `numCas` (path) | alfanumérico-String | Sí | Número de casilla (catálogo: **el manual no lo indica**) |
| `cntlimite` (query) | numérico-int | Sí | Cantidad de registros para validar el top |
| `mtoNoSustentado` (query) | numérico-decimal | No | Monto no sustentado en registros del fv0621 |
| `desMtoNoSustentado` (query) | alfanumérico-String | No | Descripción del monto no sustentado |

**Salida:** `Buffer-binary-binary`.
**Ejemplo:** `…/inconsistenciaslibros/202301/reporteinconsistencia/txt?cntlimite=10`.

> ⚠ El ejemplo no lleva `{numCas}` y añade `/txt` tras `reporteinconsistencia`, distinto de la plantilla.

Captura (HTTP 200, vista «Text»): texto plano con cabecera y filas separadas por `|`:

```
RUC Generador: 20100176450
Razón Social: REPSOL GAS DEL PERU S.A.
Periodo: 202301

Casilla|Tipo CDP|Serie|Numero|Fecha Emisión|RUC|Monto Base|Inconsistencia
107|01-Factura|0001|1|15/01/2023|20100176450|1000|La tasa del IGV aplicado al comprobante de pago no corresponde a lo aprobado por las normas legales.
…
```

**Errores 422:** 1005, 1006, 1007 · 1070 · (sin código) El campo “numCas” no enviado o es vacío · (sin código) El
campo “cntlimite” no enviado o es vacío.

---

## 5.26 Descargar constancia de recepción

| Campo | Valor (manual págs. 56-57) |
|---|---|
| Descripción | Permite descargar la constancia de recepción. |
| Método | `GET` |
| URL | `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/gestionlibro/web/registroslibros/constancia/archivo?nomArchivo={nomArchivo}` |
| Cabeceras | `Content-type: application/x-www-form-urlencoded`; tabla §0.3 |
| Cuerpo | No aplica |

| Parámetro (query) | Formato-tipo | Obligatorio | Descripción |
|---|---|---|---|
| `nomArchivo` | alfanumérico-String | Sí | Nombre de archivo |

De dónde se obtiene `nomArchivo`: **el manual no lo indica** (solo el ejemplo).
**Ejemplo:** `…/constancia/archivo?nomArchivo=LE2010017645020221200140400011112.pdf`.
**Salida:** `archivoPdf` — Base64-String («Archivo en base64»). Captura: `{ "archivoPdf": "JVBERi0xLjUKJeLjz9MK…" }`.
**Errores 422:** 1134 El campo “nomArchivo” no enviado o es vacío.

---

## 5.29 Descargar ajustes posteriores

| Campo | Valor (manual págs. 60-61) |
|---|---|
| Descripción | Permite exportar los ajustes posteriores del RVIE; si no se ha cargado ningún archivo descarga la propuesta informativa de ajustes posteriores de la SUNAT. |
| Método | `GET` |
| URL | `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/gestionlibro/web/registroslibros/descarga?perTributario={perTributario}&codOrigenEnvio={codOrigenEnvio}&codTipoArchivo={codTipoArchivo}&codProceso={codProceso}&codLibro={codLibro}` |
| Cabeceras | `Content-type: application/x-www-form-urlencoded`; tabla §0.3 |
| Cuerpo | No aplica |

| Parámetro (query) | Formato-tipo | Obligatorio | Valores |
|---|---|---|---|
| `perTributario` | alfanumérico-String | Sí | Periodo |
| `codOrigenEnvio` | alfanumérico-String | Sí | `2` Servicio web |
| `codTipoArchivo` | numérico-Integer | Sí | Anexo IV: `0` txt, `1` excel, `2` csv |
| `codProceso` | alfanumérico-String | Sí | «Código del indicador de carga masiva (Ver Anexo I)»; el valor concreto: **el manual no lo indica** |
| `codLibro` | alfanumérico-String | Sí | `140000` |

**Ejemplo:** `…/registroslibros/descarga?perTributario=202302&codOrigenEnvio=2&codTipoArchivo=0&codProceso=23&codLibro=140000`
(Anexo I 23 = «Generar reporte Libro RVIE»).
**Salida:** `numTicket` (asíncrono: luego 5.16 + 5.17). Captura: `{"numTicket":"20230300000049"}`.

**Errores 422:** 1005, 1006, 1007 · 1070 · 1028, 1029, 1030 (codOrigenEnvio) · 1059, 1060, 1061 (codTipoArchivo) ·
1138, 1139 (codProceso) · 1140 (codLibro).

---

## 5.30 Descargar ajustes posteriores de periodos anteriores

| Campo | Valor (manual págs. 61-62) |
|---|---|
| Descripción | Permite exportar los ajustes posteriores de periodos anteriores «del RC» (sic) en caso se hayan cargado ajustes por parte del generador. |
| Método | `GET` |
| URL | **idéntica a 5.29**: `…/rvierce/gestionlibro/web/registroslibros/descarga?perTributario=…&codOrigenEnvio=…&codTipoArchivo=…&codProceso=…&codLibro=…` |
| Cabeceras / Cuerpo | Igual que 5.29 |

Parámetros: idénticos a 5.29 (mismos tipos, obligatoriedad y valores).
**Ejemplo:** el mismo que 5.29, también con `codProceso=23`.
**Salida:** `numTicket`. Captura: `{"numTicket":"20230300000049"}`.
**Errores 422:** idénticos a 5.29.

> ⚠ 5.29 y 5.30 comparten URL y ejemplo (`codProceso=23`); el manual no dice qué `codProceso` distingue uno de otro.
> Candidatos del Anexo I (sin confirmación del manual): 18-21 (reportes de ajustes posteriores / de periodos
> anteriores, individual o consolidado), 71 («Reporte de ajustes posteriores del RVIE») y 72 («Reporte de Ajustes
> posteriores de periodos anteriores del RVIE»).

> Nota: a diferencia de los servicios TUS, estas descargas devuelven el ticket **en JSON** (`{"numTicket": "…"}`),
> mientras que las cargas TUS lo devuelven como texto plano.

---

## 5.36 Eliminar preliminar registrado

| Campo | Valor (manual págs. 69-70) |
|---|---|
| Descripción | Permite eliminar el preliminar registrado |
| Método | `PUT` |
| URL | `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/gestionlibro/web/registroslibros/{perTributario}/eliminapreliminar?codLibro={codLibro}` |
| Cabeceras | `Content-type: application/x-www-form-urlencoded`; tabla §0.3 |
| Cuerpo | JSON (objeto) |

| Parámetro | Formato-tipo | Obligatorio | Valores |
|---|---|---|---|
| `perTributario` (path) | alfanumérico-String | Sí | Periodo |
| `codLibro` (query) | alfanumérico-String | Sí | `140000` |
| `id` (cuerpo) | alfanumérico-String | **No** (cambio v22) | Id de registro. De dónde se obtiene: **el manual no lo indica** |
| `codTipoRegistro` (cuerpo) | alfanumérico-String | Sí | `14` |

**Ejemplo de cuerpo** (captura): `{ "id": "64dd597e224a836ab9432bee", "codTipoRegistro": "14" }`.
**Salida:** HTTP 200, `application/json`. Captura: `"OK"`.

**Errores 422:** 1005, 1006, 1007 · (sin código) El campo “codRegistroLibro” no enviado o es vacío · 1010 El libro
electronico con los siguientes datos: numero de RUC: XXXXXXXX periodo Tributario: AAAAMM y codigo de Libro:140000 no
existe.

---

## Anexo I — Indicador de carga masiva (`codProceso`) (pág. 71-72)

| Código | Descripción |
|---|---|
| 1 | Importar CP - Propuesta |
| 2 | Aceptar propuesta |
| 3 | Reemplazo de la Propuesta |
| 4 | Importa CP - Preliminar |
| 5 | Generar libro RVIE |
| 6 | Cargar Ajuste posteriores al periodo actual |
| 7 | Cargar Ajuste posteriores anteriores a la vigencia |
| 8 | Generar registro Ajustes Posterior RVIE |
| 9 | Generar registro Ajustes Posterior Anterior RVIE |
| 10 | Generar archivo exportar propuesta |
| 11 | Generar archivo exportar no incluidos |
| 12 | Generar archivo exportar preliminar |
| 13 | Generar archivo exportar inconsistencias |
| 14 | Generar archivo exportar propuesta ajustes posteriores |
| 15 | Generar archivo exportar CAR |
| 16 | Generar reporte de observaciones de comparación |
| 17 | Generar archivo exportar Libro Venta |
| 18 | Generar reporte de ajustes posteriores individual |
| 19 | Generar reporte de ajustes posteriores consolidado |
| 20 | Generar reporte de ajustes posteriores de periodos anteriores individual |
| 21 | Generar reporte de ajustes posteriores de periodos anteriores consolidado |
| 22 | Generar reporte consolidado del libro y ajustes |
| 23 | Generar reporte Libro RVIE |
| 24 | Generar Archivo personalizado Libros RVIE |
| 25 | Generar Archivo personalizado Propuesta RVIE |
| 26 | Generar Archivo personalizado Ajustes Posteriores RVIE |
| 27 | Carga archivo de comparación - validación |
| 28 | Generar archivo exportar preliminar registrado |
| 29 | Generar archivo exportar preliminar ajustes posteriores registrado |
| 30 | Generar reporte de inconsistencias generación del RVIE |
| 31 | Generar reporte de inconsistencias ajustes posteriores del RVIE |
| 32 | Generar libro RVIE - Archivo exportar Libro Venta |
| 33 | Generar libro RVIE - Archivo reporte inconsistencias |
| 34 | Generar libro RVIE - Achivo Reporte Exportadores |
| 35 | Generar libro RVIE - Archivo Propuesta Casillas |
| 36 | Generar Ajustes Posteriroes RVIE - Archivo exportar Ajuste |
| 37 | Generar Ajustes Posteriroes RVIE - Archivo reporte inconsistencias |
| 38 | Generar Ajustes Posteriores de periodos anteriores RVIE - Archivo exportar Ajuste |
| 39 | Aceptar propuesta sin Movimiento |
| 40 | Carga Tipo de Cambio |
| 41 | Generar reportes Estadisticos |
| 42 | Generar Reporte de comparación |
| 43 | Descargar Registros Electronicos RVIE |
| 44 | Descargar Registros Electronicos RCE |
| 45 | Descargar Constancia de Recepción RVIE |
| 46 | Descargar Constancia de Recepción RCE |
| 47 | Descargar Reporte de Inconcistencias RVIE |
| 48 | Descargar Reporte de Inconcistencias RCE |
| 49 | Descargar Reporte de Ajustes Posteriores RVIE |
| 50 | Descargar Reporte de Ajustes Posteriores RCE |
| 51 | Descargar Reporte de Casillas Vista Comparada |
| 52 | Descargar Reporte de Inconsistencias de Casillas |
| 53 | Generar Reporte de comparación RCE |
| 54 | Carga Complementar |
| 55 | Carga Incluir Excluir |
| 56 | Carga No Domiciliados |
| 57 | Carga Comparacion RCE |
| 58 | Carga Comparacion RVIE |
| 59 | importar CP en Ajustes Posteriores RCE |
| 60 | importar CP no domiciliados en Ajustes Posteriores |
| 61 | Reemplazo de la Propuesta |
| 62 | Generacion de Inconsistencia por Casilla |
| 63 | Generación de ventas por Casilla (100. 101) |
| 64 | Generacion Inconsistencias en Registros para Casillas |
| 65 | Validar Propuesta |
| 66 | Validar Preliminar |
| 67 | Validar No Domiciliados |
| 68 | Reporte de Ajustes posteriores de periodos anteriores del RCE |
| 69 | Descarga Consolidada de registros del RCE |
| 70 | Descarga RCE |
| 71 | Reporte de ajustes posteriores del RVIE |
| 72 | Reporte de Ajustes posteriores de periodos anteriores del RVIE |
| 73 | Descarga Consolidada de registros del RVIE |
| 74 | Descarga RVIE |
| 75 | Generación de ventas por Casilla (100. 101) |
| 76 | Generacion Inconsistencias en Registros para Casillas |
| 77 | Validar Propuesta |
| 78 | Validar Preliminar |
| 79 | Validar No Domiciliados |
| 80 | Generación de archivo personalizado Propuesta RCE). |
| 81 | Generación de archivo personalizado Preliminar RCE). |
| 82 | Generación de archivo personalizado Preliminar Registrado RCE). |
| 83 | Generación de archivo personalizado Registro Compras). |
| 84 | Generación de archivo personalizado Ajuste Posterior RCE). |
| 85 | Generacion de archivo del libro de Ajustes Posteriores RVIE). |
| 86 | Generacion de archivo de inconsistencias de libro de Ajustes Posteriores RVIE). |
| 87 | Importar CP en Ajustes Posteriores RVIE. |
| 88 | Importar CP en Ajustes Posteriores de periodos anteriores RVIE general. |
| 89 | Importar CP en Ajustes Posteriores de periodos anteriores RVIE simplificado. |
| 90 | Generación de documentos para Intranet). |
| 91 | Exportar detalle propuesta casilla - Registro). |
| 92 | Exportar inconsistencias en registro); |
| 93 | Importar CP en Ajustes Posteriores RCE de Periodos Anteriores Simplificado |
| 94 | Importar CP en Ajustes Posteriores RCE de Periodos Anteriores General |
| 95 | Importar CP no domiciliados en Ajustes Posteriores RCE de Periodos Anteriores |
| 96 | Generar archivo exportar preliminar - RCE No Domiciliados |
| 97 | Exportar comprobantes excluidos |

(Paréntesis y erratas copiados tal cual del manual.)

## Anexo II — Tipo de correlativo (`codTipoCorrelativo`) (pág. 72-73)

| Código | Descripción |
|---|---|
| 01 | Tipo envíos masivos |
| 02 | Número operación de generación RVIE |
| 03 | Solicitud de generación de archivo |
| 04 | Tipo carga archivo comparación |

## Anexo III — Código de estado de envío (pág. 73)

| Código | Descripción |
|---|---|
| 01 | Cargado (solicitado) |
| 02 | Validando Archivo (en proceso) |
| 03 | Procesado con Errores |
| 04 | Procesado sin errores (concluido) |
| 05 | En proceso |
| 06 | Terminado |

## Anexo IV — Extensión del archivo a descargar (`codTipoArchivo`) (pág. 73)

| Código | Descripción |
|---|---|
| 0 | txt |
| 1 | excel |
| 2 | csv |

## Códigos de libro

El manual solo usa **`140000`** (RVIE). No hay tabla de códigos de libro en los anexos. (En el texto de 5.36
`codTipoRegistro` = `14`, y la Guía de Uso, pág. 11, menciona «codTipoRegistro (2 Registro de Ventas)» para
aceptar propuesta.)

## Estructura de los archivos TXT a importar

**El manual NO incluye ningún anexo con la estructura (columnas, longitudes, separador) de los archivos TXT.** Solo
da el nombre del archivo y remite a la **tabla 6 del Anexo N° 1 de la R.S. 112-2021/SUNAT** y modificatorias:

| Carga | Nombre según la tabla del manual | Ejemplo real del manual | Columnas / separador |
|---|---|---|---|
| 5.3 Reemplazo de la propuesta (`codProceso` 3) | `LERRRRRRRRRRRAAAAMM0014040002OIM2.txt` | `LE2010017645020230200140400020112.zip` | el manual no lo indica (R.S. 112-2021) |
| 5.4 Nuevos CP en propuesta (`codProceso` 1) — CP físicos | `RRRRRRRRRRR-CPF-AAAAMM-Correlativo.txt` | `20100176450-CPF-202302-01.zip` | el manual no lo indica (R.S. 112-2021) |
| 5.5 Nuevos CP en preliminar (`codProceso` 4) | `LERRRRRRRRRRRAAAAMM0014040002OIM2.txt` | `LE2010017645020230200140400020112.zip` | el manual no lo indica (R.S. 112-2021) |
| 5.6 Ajustes posteriores | «la estructura dependerá de la descripción consignada» | `LE20100176450202302001404000311102.zip` | el manual no lo indica (R.S. 112-2021) |
| 5.7 Ajustes posteriores de periodos anteriores | «la estructura dependerá de la descripción consignada» | `LE201001764502023030014040004111202.zip` | el manual no lo indica (R.S. 112-2021) |
| 5.11 Tipo de cambio masivo | **No hay archivo**: es JSON en el cuerpo del POST | — | — |

Reglas de archivo que sí da el manual (errores 1348/1346/1350/1024): el envío debe ser **`.zip`**, de tamaño
mayor que 0 KB y menor o igual a 6 GB, y un mismo nombre no puede reenviarse («fue previamente enviado»).
Si el ZIP contiene un `.txt` con el mismo nombre base, si puede contener varios archivos y qué codificación usar:
**el manual no lo indica**.

---

## Tabla resumen

| § | Servicio | Método | Ruta (tras `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/`) | Entrada | Respuesta |
|---|---|---|---|---|---|
| 5.2 | Consultar año y mes | GET | `rvierce/padron/web/omisos/{codLibro}/periodos` | path `codLibro=140000` | JSON array ejercicios/periodos |
| 5.4 | Importar nuevos CP propuesta | TUS (POST+PATCH) | `rvierce/receptorpropuesta/web/propuesta/upload` | metadatos, `codProceso=1` | ticket en texto plano |
| 5.5 | Importar nuevos CP preliminar | TUS | `rvierce/receptorpreliminar/web/preliminar/upload` | metadatos, `codProceso=4` | ticket en texto plano |
| 5.6 | Importar ajustes posteriores | TUS | `rvierce/receptorajustesposteriores/web/ajustesposteriores/upload` | metadatos, `codProceso` 6 (tabla) / 87 (ejemplo) | ticket en texto plano |
| 5.7 | Importar ajustes posteriores periodos anteriores | TUS | `rvierce/receptorajustesposteriores/web/ajustesposteriores/upload` | metadatos, `codProceso` 7 (tabla) / 88 (ejemplo) | ticket en texto plano |
| 5.10 | Exclusión definitiva NC y facturas | POST | `rvie/propuesta/web/propuesta/{perTributario}/retiracomprobante?codCar=&codSituacion=0` | query | 200 `"OK"` |
| 5.11 | Tipo de cambio masivo | POST | `rvie/propuesta/web/masivo/{perTributario}/guardacomplementomasivo` | JSON array `fecEmision, codMoneda, mtoTipoCambio[, mtoCambioMonedaExt]` | 200 (cuerpo vacío) |
| 5.12 | Tipo de cambio individual | PUT | `rvie/propuesta/web/propuesta/{perTributario}/complementoindividual` | JSON objeto `codCar, codMoneda, mtoTipoCambio[, mtoCambioMonedaExt]` | 200 `"OK"` |
| 5.13 | Eliminar CP propuesta | POST | `rvie/propuesta/web/propuesta/{perTributario}/eliminacomprobante` | JSON array `numSerieCDP, numCDP, codCar, codTipoCDP` | 200 `"OK"` |
| 5.14 | Eliminar CP preliminar | PUT | `rvierce/gestionlibro/web/registroslibros/{perTributario}/comprobantepreliminar` | JSON array `codCar, codTipoCDP, numSerieCDP, numCDP` | 200 `"OK"` |
| 5.15 | Eliminar reemplazo propuesta | PUT | `rvierce/gestionlibro/web/registroslibros/{perTributario}/eliminarreemplazo?codLibro=140000` | — | 200 `"OK"` |
| 5.16 | Estado de ticket | GET | `rvierce/gestionprocesosmasivos/web/masivo/consultaestadotickets?perIni=&perFin=&page=&perPage=[&numTicket=]` | query | JSON `paginacion` + `registros[]` con `detalleTicket` y `archivoReporte[]` |
| 5.17 | Descargar archivo | GET | `rvierce/gestionprocesosmasivos/web/masivo/archivoreporte?nomArchivoReporte=&codTipoArchivoReporte=&codLibro=140000` | query (de 5.16) | binario (ZIP) |
| 5.20 | Descargar resumen | GET | `rvierce/resumen/web/resumencomprobantes/{perTributario}/{codTipoResumen}/{codTipoArchivo}/exporta?codLibro=140000` | path + query | binario (texto `|` en la captura) |
| 5.21 | Resumen inconsistencias | GET | `rvierce/resumen/web/resumeninconsistencias/{perPeriodoTributario}?codTipoResumen=1..4&codLibro=140000` | path + query | JSON `cantidad`/`monto` |
| 5.24 | Inconsistencias preliminar registrado | GET | `rvierce/casillas/inconsistenciaslibros/{perTributario}/{numCas}/reporteinconsistencia?cntlimite=[&mtoNoSustentado=&desMtoNoSustentado=]` | path + query | binario (texto `|`) |
| 5.26 | Constancia de recepción | GET | `rvierce/gestionlibro/web/registroslibros/constancia/archivo?nomArchivo=` | query | JSON `{archivoPdf: base64}` |
| 5.29 | Descargar ajustes posteriores | GET | `rvierce/gestionlibro/web/registroslibros/descarga?perTributario=&codOrigenEnvio=2&codTipoArchivo=&codProceso=&codLibro=140000` | query | JSON `{numTicket}` |
| 5.30 | Descargar ajustes posteriores periodos anteriores | GET | (idéntica a 5.29) | query | JSON `{numTicket}` |
| 5.36 | Eliminar preliminar registrado | PUT | `rvierce/gestionlibro/web/registroslibros/{perTributario}/eliminapreliminar?codLibro=140000` | JSON `{id?, codTipoRegistro:"14"}` | 200 `"OK"` |

## Lo que el manual NO especifica (resumen)

1. Catálogo y significado de `codTipoArchivoReporte` / `codTipoAchivoReporte` (solo aparecen `00`, `01`, `null`).
2. Estructura (columnas, separador, longitudes) de cualquier TXT a importar: remite a la R.S. 112-2021/SUNAT.
3. Qué `codProceso` usar en 5.29 frente a 5.30 (mismo ejemplo `23`), y si en 5.6/5.7 vale el de la tabla (6/7) o el del ejemplo (87/88).
4. Catálogos de `codTipoResumen` (5.20 y 5.21), `numCas` (5.24), `codEstado` de periodos (5.2) y monedas (5.11/5.12).
5. Origen del `id` de 5.36 y del `nomArchivo` de 5.26.
6. Validez del token y detalles del servidor TUS (tamaño de trozo exigido, `Location`, expiración), salvo lo que se ve en el código Java del Anexo V.
7. Formato de respuesta OK documentado en tabla (solo capturas): cargas TUS → ticket en texto plano; descargas asíncronas → `{"numTicket": …}`; operaciones → `"OK"`.
