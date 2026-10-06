# SIRE Compras (RCE): especificación de servicios web API

Fuente única: *Manual de servicios Web Api - SIRE Compras*, versión **V22** (05/03/2024), en
`docs/sire/oficial/Manual_de_servicios_Web_Api_-_SIRE_Compras_v22.pdf` (155 páginas; las
partes II y III son extractos del mismo documento). Entre corchetes va la página del PDF.

Reglas de este documento:

- Todo se ha copiado del manual. Los nombres de campo conservan su grafía original, incluidas las erratas
  (por ejemplo `codTipoAchivoReporte`), que se marcan con **[sic]**.
- Las secciones «Evidencias» del manual son capturas de Postman, es decir, imágenes. Se han leído
  una por una y aquí se transcriben a texto.
- Lo que el manual no dice se marca como «el manual no lo indica». Las contradicciones internas
  se marcan como **⚠ Discrepancia en el manual** y se dejan sin resolver.

---

## 0. Elementos comunes

### 0.1 Host y token

- Host de los servicios: `https://api-sire.sunat.gob.pe`. Todas las rutas empiezan por
  `/v1/contribuyente/migeigv/libros/...`.
- Token (servicio 5.1) [39]: `POST https://api-seguridad.sunat.gob.pe/v1/clientessol/{client_id}/oauth2/token/`,
  con el cuerpo `application/x-www-form-urlencoded` y estos campos: `grant_type=password`,
  `scope=https://api-sire.sunat.gob.pe`, `client_id`, `client_secret`,
  `username={RUC}{USUARIO}` y `password={CLAVESOL}`.
- Los servicios no deben consumirse desde un cliente web, porque fallan por CORS [38]. Según el
  manual, los clientes TUS «deben ser desarrollados en el lenguaje JAVA (Ver Anexo 7.4)» [38].

### 0.2 Cabeceras de los servicios REST (no TUS)

El manual repite esta tabla en todos los servicios:

| Cabecera | Valor |
|---|---|
| `Content-Type` | `application/json` |
| `Accept` | `application/json` |
| `Authorization` | `Bearer` + token obtenido de la autenticación |

En muchos servicios aparece además la línea «Content-type: application/x-www-form-urlencoded»
junto a la tabla anterior, que dice `application/json`. El manual no aclara cuál de las dos prevalece.
En las capturas de Postman se ven `Authorization`, `Accept: application/json` y
`Content-Type: application/json` [81, 101].

### 0.3 Formato de error común (texto idéntico en todos los servicios)

- **Result Fail (500):**
  `{ "cod":"500", "msg":"Internal Server Error - Se presento una condicion inesperada que impidio completar el Request", "exc":"java.lang.NullPointerException at ..." }`
- **Mensaje Error (422):**
  `{ "cod":"422", "msg":"Unprocessable Entity - Se presentaron errores de validacion que impidieron completar el Request", "errors":[ { "cod":"1001", "msg":"El campo “numRuc” no enviado o es vacío" }] }`
- Errores 401 y 403: no aparecen en las tablas de los servicios. Solo se mencionan en el cliente
  Java del Anexo IV (`Http401And403CodeException`: «errores de autenticación o de autorización»).
- Ejemplo real de 422, tomado de la evidencia 2 del servicio 5.16 [60]:
  ```json
  { "cod": 422,
    "msg": "Unprocessable Entity - Se presentaron errores de validación que impidieron completar el Request",
    "errors": [ { "cod": 422,
                  "msg": "No se pudo eliminar el comprobante seleccionado CAR=1046342681901E0010000000009",
                  "exc": "No se encontro comprobante -> And Filter{filters=[Filter{fieldName='numRuc', value=20480072872}, Filter{fieldName='codTipoCDP', value=01}, Filter{fieldName='numSerieCDP', value=E001}, Filter{fieldName='numCDP', value=9}, Filter{fieldName='codCar', value=1046342681901E0010000000009}, Filter{fieldName='codSituacion', value=1}]}" } ] }
  ```
  En este ejemplo `cod` va como número (sin comillas), aunque la plantilla del manual lo muestra
  como cadena.

### 0.4 Subidas TUS: protocolo y metadatos comunes

Usan TUS los servicios 5.5, 5.6, 5.7, 5.8, 5.9, 5.18, 5.21, 5.24 y 5.27. En todos ellos el
manual dice «Tecnología: Uso de la librería TUS.io para cliente», «Parámetros[body]: No aplica» y,
en las cabeceras, «Content-type: application/x-www-form-urlencoded».

**Tabla de metadatos «Metadata Cliente TUS»**, igual en todos los servicios salvo `codProceso`:

| Metadato | Formato/tipo | Descripción (literal) |
|---|---|---|
| `filename` | alfanumérico, string | Nombre de archivo (Obligatorio) |
| `filetype` | alfanumérico, string | Tipo de archivo (Obligatorio) |
| `numRuc` | alfanumérico, string | Número de RUC del contribuyente (Obligatorio) |
| `perTributario` | alfanumérico, String | Periodo tributario (Obligatorio) |
| `codOrigenEnvio` | alfanumérico, string | Código de origen de envío: 2 Servicio web (Obligatorio) |
| `codProceso` | alfanumérico, String | Código del indicador de carga masiva; el valor de cada servicio está en su ficha (Ver Anexo I) (Obligatorio) |
| `codTipoCorrelativo` | alfanumérico, string | Tipo de correlativo: 01: Tipo envíos masivos (Ver Anexo II: Tipo de correlativo) (Obligatorio) |
| `nomArchivoImportacion` | alfanumérico, String | Nombre del archivo utilizado para la importación o nombre de archivo generado (Obligatorio) |
| `codLibro` | alfanumérico, String | Código de libro: 080000 RCE (Obligatorio) |

⚠ **Discrepancias en el manual sobre TUS:**

- El «Anexo II: Tipo de correlativo» al que remite la tabla no existe. El Anexo II real es «Tipo de
  ajuste posterior». La tabla dice `01`, pero la evidencia y el Demo.java envían `1`.
- La evidencia «Headers (metadata)» se repite casi igual en todos los servicios TUS. Es el formato
  TUS `Upload-Metadata`, con cada valor en base64, y sus valores proceden del manual de **ventas
  (RVIE)**:
  `filename TEUyMDEw…MDIuemlw` = `LE20100176450202302001404000311102.zip`,
  `filetype YXBwbGljYXRpb24vemlw` = `application/zip`, `numRuc` = `20100176450`,
  `perTributario` = `202302`, `codOrigenEnvio MQ==` = `1`, `codProceso ODc=` = `87`,
  `codTipoCorrelativo MQ==` = `1`, `codLibro MTQwMDAw` = `140000`.
  Ninguno coincide con lo que la tabla exige para RCE (`codOrigenEnvio=2`, `codLibro=080000`).
  En 5.7 cambian `filename` y `nomArchivoImportacion` (`20100176450-CPF-202302-01.zip`) y
  `codProceso` (`MQ==` = `1`).
- El Demo.java del Anexo IV [153–154] envía `filetype` igual a la extensión (`"zip"`), no un MIME;
  `codOrigenEnvio` igual a `"3"`, `codLibro` igual a `"140000"`, `codProceso` igual a `"1"` y
  `codTipoCorrelativo` igual a `"1"`.

**Protocolo, según el cliente Java del Anexo IV** [125–155]:

- Librería `io.tus:tus-java-client:0.5.0` con clases propias (`TusClientCustom`, `TusUploaderCustom`).
- `TUS_VERSION = "1.0.0"`, enviada en la cabecera `Tus-Resumable`.
- URL de creación: `HOST_PUBLICA = "https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/"` +
  endpoint, por ejemplo `libros/rvierce/receptorpropuesta/web/propuesta/upload`.
- Cabecera adicional: `authorization: Bearer <TOKEN>` (con minúscula en el ejemplo).
- Creación: `POST` con `Upload-Metadata` (valores en base64) y `Upload-Length`. La URL de subida
  se lee de la cabecera `Location` de la respuesta.
- Envío de trozos: `PATCH`, o `POST` con `X-HTTP-Method-Override: PATCH`, con
  `Upload-Offset` y `Content-Type: application/offset+octet-stream`. El uploader fija por defecto
  `setChunkSize(2 * 1024 * 1024)` y el Demo usa `uploader.setChunkSize(1024)`.
- Reanudación: `HEAD` y lectura de `Upload-Offset`.
- Códigos que el cliente trata: 401/403 (`Http401And403CodeException`) y 422
  (`Http422CodeException`). Cualquier código fuera de 2xx se trata como error de protocolo.
- Respuesta final: `uploader.finish()` devuelve `TusResponseBody` (`responseCode`,
  `responseMessage`, `responseBody`). El cuerpo es la respuesta del último PATCH, y el cliente exige
  `Upload-Offset` en ella. El ticket llega en ese cuerpo: en las evidencias se ve el texto plano
  `20230100000124` [44].
- El manual no indica el tamaño máximo de cada trozo ni la caducidad de la URL de subida.

**Lista común de errores 422 de TUS** (idéntica en 5.5–5.9, 5.18, 5.21, 5.24 y 5.27):

1001 El campo “numRuc” no enviado o es vacío · 1002 Solo se permite dato numérico de 11 dígitos
para el número de RUC · 1003 El RUC ingresado no existe o no es válido · 1005 El campo
“perTributario” no enviado o es vacío · 1006 Formato de perTributario no cumple con el formato
“yyyymm” · 1007 El perTributario de búsqueda no debe ser mayor a la fecha actual · 1014 Solo se
permite dato numérico de 6 dígitos para el perTributario · 1064 El periodo no debe ser mayor al
periodo de la fecha actual · 1093 Formato de período no cumple con el formato “yyyymm” · 1028 El
campo “codOrigenEnvio” no enviado o es vacío · 1029 Código tipo de Origen de Envio no permitido o
no valido · 1030 Solo se permite dato numérico de 1 dígito para el codOrigenEnvio · 1025 El campo
“codProceso” no enviado o es vacío · 1026 Código Proceso no permitido o no valido · 1027 Solo se
permite dato numérico para el codProceso · 1138 El campo "codProceso" es nulo o vacío · 1139
Código de Proceso no permitido o no valido · 1048 Solo se permite dato numérico de 1 dígito para el
codTipoOrigen · 1022 nombre del archivo no enviado o es vacio · 1024 El archivo <nombre del
archivo txt> fue previamente enviado · 1044 Error en la <<Posición - Descripción>> del nombre del
archivo plano, favor de corregir · 1348 La extensión del archivo es diferente a “.zip”, por favor
corregir · 1346 El tamaño del archivo comprimido en formato “.zip” debe ser menor o igual a 6GB ·
1350 El tamaño del archivo mayor a 0 Kb · 1351 Se ha producido un error al realizar el envío del
archivo, por favor volver a intentar el envío · 1048 Solo se permite dato numérico de 2 dígitos
para el codTipoCorrelativo · 1049 El campo “codTipoCorrelativo” no enviado o es vacio · 1050
Código tipo de Correlativo no permitido o no valido · 1140 El campo “codLibro” no enviado o es vacío.

(El código 1048 aparece dos veces en el manual, con dos textos distintos.)

Lo que se deduce de esta lista: el archivo subido debe ser un `.zip` (1348) de más de 0 KB y de 6 GB
como máximo (1346 y 1350). Su nombre se valida por posiciones (1044), pero **el manual no publica
la nomenclatura**. No puede reenviarse un archivo con el mismo nombre (1024).

---

## 5.5 Cargar registro de compra no domiciliados [43–45]

- **Nombre:** Servicio Web Api cargar no domiciliado. Permite importar el archivo de las operaciones con no domiciliados.
- **Tipo:** subida TUS. El manual no indica el método HTTP de forma explícita; ver §0.4.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/receptorpreliminar/web/preliminar/upload`
- **Parámetros path/query:** ninguno.
- **Metadatos TUS:** los de §0.4, con `codProceso` = **56** («Cargar no domiciliados»).
- **Salida:** `numTicket` (alfanumérico, String), con formato `[AAAA99999999]`: AAAA = año, 99 = tipo de correlativo y 99999999 = número correlativo de envío.
- **Respuesta de ejemplo** [44]: texto plano `20230100000124`.
- **Errores 422:** la lista común de §0.4.
- **Requisito previo** [17]: la propuesta debe estar aceptada o el preliminar registrado, en ambos casos con la opción «sí» para agregar comprobantes no domiciliados.

## 5.6 Importar datos complementarios de los CP de la propuesta [45–46]

- **Nombre:** Servicio Web Api importar complemento de la propuesta. Permite «complementar o completar datos de comprobantes propuestos por la administración».
- **Tipo:** subida TUS (§0.4).
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/receptorpropuesta/web/propuesta/upload`
- **Metadatos TUS:** los de §0.4, con `codProceso` = **54** («Complementar la Propuesta»).
- **Salida:** `numTicket`, con el mismo formato que en 5.5.
- **Respuesta de ejemplo** [46]: `20230100000124`.
- **Errores 422:** la lista común de §0.4.
- La Funcionalidad 2 [18] dice que se usa «un archivo de formato .txt zipeado».

## 5.7 Importar nuevos comprobantes preliminar [46–48]

- **Nombre:** Servicio Web Api importar nuevos comprobantes en el preliminar. Permite importar nuevos comprobantes en el preliminar de RCE.
- **Tipo:** subida TUS (§0.4).
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/receptorpreliminar/web/preliminar/upload`
- **Metadatos TUS:** los de §0.4, con `codProceso` = **4** («Importa CP - Preliminar»).
- **Ejemplo de metadatos:** `filename` y `nomArchivoImportacion` = `20100176450-CPF-202302-01.zip`; `codProceso` = `1` (no coincide con el 4 de la tabla); `codLibro` = `140000`.
- **Salida:** `numTicket`. **Respuesta de ejemplo** [47]: `20230100000124`.
- **Errores 422:** la lista común de §0.4.
- **Requisito previo** [21]: haber reemplazado la propuesta (5.3).

## 5.8 Incluir-excluir comprobantes de la propuesta [48–50]

- **Descripción:** permite al generador incluir o excluir comprobantes propuestos por la administración.
- **Tipo:** subida TUS (§0.4).
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/receptorpropuesta/web/propuesta/upload`
- **Metadatos TUS:** los de §0.4, con `codProceso` = **55** («Carga Incluir Excluir»).
- **Salida:** `numTicket`. **Respuesta de ejemplo** [49]: `20230100000124`.
- **Errores 422:** la lista común de §0.4.

## 5.9 Importar nuevos comprobantes de pago [50–51]

- **Nombre:** Servicio Web Api importar nuevos comprobantes en propuesta. Permite agregar comprobantes no propuestos por la administración.
- **Tipo:** subida TUS (§0.4).
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/receptorpropuesta/web/propuesta/upload`
- **Metadatos TUS:** los de §0.4, con `codProceso` = **1** («Importar CP - Propuesta»).
- **Salida:** `numTicket`. **Respuesta de ejemplo** [50]: `20230100000124`.
- **Errores 422:** la lista común de §0.4.

## 5.10 Importar tipo de cambio masivo [51–52]

- **Descripción:** actualiza en bloque los tipos de cambio de los comprobantes para los que la administración no encontró tipo de cambio propuesto, y recalcula los montos con los tipos ingresados.
- **Método:** `POST`.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rce/propuesta/web/{perTributario}/{codLibro}/resumenfechatipocambio`
- **Parámetros path:** `perTributario` (alfanumérico, String, obligatorio); `codLibro` (alfanumérico, String, «080000 RCE», obligatorio).
- **Cuerpo:** `archivo`, de tipo «multipart/form-data-formData», descrito como «archivo a procesar». La tabla de cabeceras pone `Content-Type: application/json`.
- **Salida (tabla):** `numRuc`, `perTributario`, `numTicket` (`[AAAA99999999]`) y `nomArchivoImportacion`, todos alfanuméricos.
- **Respuesta de ejemplo** [52], con la URL `.../rce/propuesta/web/202201/080000/resumenfechatipocambio`:
  ```json
  [ { "fecEmision": "2022-01-20", "codMoneda": "EUR", "mtoCambioMonedaExtranjera": 0.00, "mtoCambioMonedaDolares": 0.00 },
    { "fecEmision": "2022-01-06", "codMoneda": "EUR", "mtoCambioMonedaExtranjera": 0.00, "mtoCambioMonedaDolares": 0.00 } ]
  ```
  ⚠ El ejemplo no se corresponde con la tabla de salida, que habla de ticket. El cuerpo de la evidencia figura como «(No aplica)».
- **Errores 422:** 1005, 1006, 1007, 1014, 1064, 1093 (textos de §0.4); 1141 Código tipo de moneda no permitido o no valido; 1142 No se permite el tipo de dato para codMoneda; 1143 El campo "codMoneda" es nulo o vacío; 1144 El campo "mtoTipoCambio" es nulo o vacío; 1145 Solo se permite dato numérico y decimal para el mtoTipoCambio; 1140.
- **Formato del archivo:** la Funcionalidad 3 [19] dice «un archivo de formato .txt». **El manual no indica** la estructura, las columnas, el separador ni el nombre del archivo. Los errores 1141–1145 solo dejan ver que contiene, al menos, `codMoneda` y `mtoTipoCambio`.

## 5.11 Actualizar reintegro del crédito fiscal [52–53]

- **Nombre:** Servicio Web Api registrar reintegro del crédito fiscal (datos del FV0621).
- **Método:** `PUT`.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rce/propuesta/web/{perTributario}/grabacreditofiscal`
- **Parámetro path:** `perTributario` (alfanumérico, String, obligatorio).
- **Cuerpo (tabla):** `datosFV621.valorRCF` (numérico decimal128, «Reintegro de Crédito fiscal», obligatorio); `datosFV621.valorCFE` (numérico decimal128, también descrito como «Reintegro de Crédito fiscal», obligatorio); `datosFV621.factProrrata` (numérico decimal128, «Coefiente de Prorrata FV621», obligatorio).
- **Cuerpo de ejemplo** [53]: `{ "registros": { "valorRCF": 2 } }`. ⚠ La raíz es `registros`, no `datosFV621`, y solo se envía `valorRCF`.
- **Salida:** HTTP 200, `application/json`. **Respuesta de ejemplo:** `"OK"`.
- **Errores 422:** 1005, 1006, 1007; 1070 No se ha encontrado información de comprobantes de pago en Periodo Seleccionado; 1188 El campo "valorRCF" no enviado o es vacío.

## 5.12 Actualizar crédito fiscal especial [54]

- **Método:** `PUT`.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rce/propuesta/web/{perTributario}/grabacreditofiscalespecial`
- **Parámetro path:** `perTributario` (obligatorio).
- **Cuerpo (tabla):** `datosFV621.valorCFE` (numérico decimal128, obligatorio).
- **Cuerpo de ejemplo:** `{ "registros": { "valorCFE": 3 } }`.
- **Salida:** HTTP 200. **Respuesta de ejemplo:** `"OK"`.
- **Errores 422:** 1005, 1006, 1007; 1189 El campo "valorCFE" no enviado o es vacío.

## 5.13 Actualizar coeficiente de prorrata [55–56]

- **Método:** `PUT`.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rce/propuesta/web/{perTributario}/grabacreditofiscal`. Es la **misma URL que 5.11**.
- **Parámetro path:** `perTributario` (obligatorio).
- **Cuerpo (tabla):** `datosFV621.factProrrata`, `datosFV621.valorRCF` y `datosFV621.valorCFE` (todos decimal128 y obligatorios).
- **Cuerpo de ejemplo:** `{ "registros": { "factProrrata": 6 } }`.
- **Salida:** HTTP 200. **Respuesta de ejemplo:** `"OK"`.
- **Errores 422:** 1005, 1006, 1007; 1187 El campo "factprorrata" no enviado o es vacío.

## 5.15 Eliminar comprobante de la propuesta [57–58]

- **Descripción:** permite eliminar de la propuesta un comprobante que agregó el contribuyente.
- **Método:** `DELETE`, con cuerpo JSON.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rce/propuesta/web/propuestarce/{perTributario}`
- **Parámetro path:** `perTributario` (obligatorio).
- **Cuerpo:** un array de objetos con `numSerieCDP`, `numCDP`, `codCar` (CAR SUNAT) y `codTipoCDP`, todos alfanuméricos y obligatorios. `codTipoCDP` solo admite 00, 01, 03, 05, 06, 07, 08, 11, 12, 13, 14, 15, 16, 18, 21, 24, 25, 27, 28, 30, 32, 34, 35, 36, 37, 42, 43, 44, 45, 48, 49, 55 y 56.
- **Cuerpo de ejemplo:** `[ { "codCar": "723638235", "codTipoCDP": "2", "numSerieCDP": "623737", "numCDP": "2323223" } ]`
- **Salida:** HTTP 200. **Respuesta de ejemplo:** `"OK"`.
- **Errores 422:** 1005, 1006, 1007, 1070; 1135 El campo “codCar” no enviado o es vacío; 1136 Solo se permite dato numérico de 27 dígitos para el Codigo CAR; 1323 El campo "numSerieCDP" es nulo o vacío; 1011 El campo “codTipoCDP” no enviado o es vacío; 1012 El codTipoCDP ingresado no existe o no es válido.

## 5.16 Eliminar comprobante del preliminar [58–60]

- **Descripción:** permite eliminar un comprobante del preliminar RCE o un comprobante no domiciliado del RCE.
- **Método:** `POST`.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rce/preliminar/web/comprobanteslibroscompras/{perTributario}/eliminacomprobante`
- **Parámetro path:** `perTributario` (obligatorio).
- **Cuerpo:** un array de objetos con `codTipoCDP` (misma lista que 5.15), `numSerieCDP`, `numCDP` y `codCar`, todos obligatorios.
- **Evidencia 1** (el comprobante existe):
  `[ { "codCar": "1046342681901E0010000000009", "codTipoCDP": "01", "numSerieCDP": "E001", "numCDP": "9" } ]` devuelve `"OK"`.
- **Evidencia 2** (el comprobante no existe): con `numSerieCDP` igual a `"E0045461"` devuelve el 422 transcrito en §0.3.
- **Errores 422:** 1005, 1006, 1007, 1135, 1136, 1323, 1011, 1012, 1070.

## 5.17 Eliminar preliminar [60–61]

- **Descripción:** permite eliminar todos los preliminares o solo el de no domiciliados.
- **Método:** `PUT`.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rce/preliminar/web/registroslibros/{perTributario}/{indEliminar}/eliminapreliminar`
- **Parámetros path:** `perTributario` (obligatorio); `indEliminar` (numérico, int, obligatorio): `1` = eliminar todo el preliminar; `2` = eliminar solo «No Domiciliados».
- **Cuerpo:** no aplica. Ejemplo de URL: `.../registroslibros/202203/1/eliminapreliminar`.
- **Salida:** HTTP 200. **Respuesta de ejemplo** [61]: `"OK"`.
- **Errores 422:** 1005, 1006, 1007; 2266 El campo 'indEliminar' no enviado o es vacío; 1140 El campo “codLibro” no enviado o vacío; 1014; 1009 El libro electrónico con los siguientes datos: numero de RUC … periodoTributario … y codigo de Libro … no existe.

---

## 5.18 – 5.29 Ajustes posteriores

Los tipos de ajuste posterior (Anexo II) se repiten en estos servicios: 1 Ajuste Posterior;
2 Ajuste Posterior con No Domiciliados; 3 Ajuste Posteriores de periodos anteriores general;
4 Ajuste Posteriores de periodos anteriores simplificado; 5 Ajuste Posteriores de periodos
anteriores con No Domiciliados.

Todas las cargas de ajustes (5.18, 5.21, 5.24 y 5.27) usan el **mismo endpoint TUS**:
`https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/receptorajustesposteriores/web/ajustesposteriores/upload`.
Lo que distingue cada carga es su `codProceso`.

### 5.18 Cargar ajustes posteriores [61–62]

- **Descripción:** importa un archivo con los ajustes posteriores.
- **Tipo:** subida TUS (§0.4), con el endpoint de arriba.
- **Metadatos TUS:** los de §0.4, con `codProceso` = **6** («Cargar Ajuste posteriores del SIRE»). ⚠ El Anexo I tiene dos códigos 6 («…al periodo actual» y «…de periodos del sire») y además el **59** («importar CP en Ajustes Posteriores RCE»).
- **Salida (tabla):** HTTP 200, `application/json`. A diferencia de las otras cargas, la tabla no menciona `numTicket`. **Respuesta de ejemplo** [62]: `"OK"`.
- **Errores 422:** la lista común de §0.4.
- **Requisito previo** [23]: haber generado el periodo que se quiere ajustar, con información en el registro.

### 5.19 Enviar ajustes posteriores [63–64]

- **Nombre:** Servicio Web Api enviar ajustes posteriores (registrar preliminar de ajustes posteriores).
- **Método:** `POST`.
- **URL (literal):** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rce/ajustesposteriores/web/comprobantesajuspost/{perTributario}/{codOrigenEnvio}/registrarajustesposterioresrc`
- **Parámetros URL (tabla):** `perTributario` (obligatorio); `numAjustePosterior` («Correlativo o numero de ajuste posterior», obligatorio); `codLibro` (080000, obligatorio); `numTicket` (`[AAAA99999999]`, obligatorio).
  ⚠ La plantilla de URL tiene `{codOrigenEnvio}`, pero la tabla no lo define. La tabla define `numAjustePosterior`, `codLibro` y `numTicket`, que no aparecen en la URL. Los servicios hermanos 5.22, 5.25 y 5.28 usan `{perTributario}/{numAjustePosterior}/{codLibro}/{numTicket}`.
- **Cuerpo (tabla):** «No aplica». **Cuerpo de ejemplo** [63]:
  `{ "controlProcesos": { "lisFases": [ { "codFase": "9" } ] }, "registrosLibros": { "indEnviadoAjuste": "1" } }`
- **Salida:** HTTP 200. **Respuesta de ejemplo** [64]: `"OK"`.
- **Errores 422:** 1005, 1006, 1007, 1140.

### 5.20 Eliminar comprobante de ajustes posteriores [64–65]

- **Método:** `DELETE`, con cuerpo JSON.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rce/ajustesposteriores/web/comprobantesajuspost/{perTributario}/{indTipoAjustePosterior}/eliminarcomprobanteaprc`
- **Parámetros path:** `perTributario` (obligatorio); `indTipoAjustePosterior` (numérico, int): `1` Ajuste Posterior (Anexo II), obligatorio.
- **Cuerpo (tabla):** `codAjustePosterior` («Identificador de la colección», obligatorio) y `detalleAjustes`, un array de objetos con `codTipoCDP` (lista de 5.15), `numSerieCDP`, `numCDP`, `codCar` e `Id` («Identificador del comprobante en la colleción»), todos obligatorios.
- **Cuerpo de ejemplo:** `{ "codAjustePosterior": "63659cbcd085da78d99a6cfe", "detalleAjustes": [ { "codTipoCDP": "01", "numSerieCDP": "FB98", "numCDP": "424101080" } ] }`. El ejemplo no incluye `codCar` ni `Id`.
- **Ejemplo de URL:** `.../comprobantesajuspost/202301/1/eliminarcomprobanteaprc`. **Respuesta de ejemplo:** `"OK"`.
- **Errores 422:** 1005, 1006, 1007, 1011, 1012; 1104 El código de tipo de comprobante de pago enviado no es válido; 1135 El campo codCar no enviado o es vacío; 1136; 1065 El periodo debe ser mayor o igual al <<año-mes>> de vigencia del módulo; 1066 No hay información para el periodo seleccionado debido a que ha superado el plazo de los 6 años…; 1323; 2000 El campo indTipoAjustePosterior no tiene asignado un valor válido.
- **De dónde sale `codAjustePosterior`:** el manual remite a 5.59, que no lo documenta (ver §5.59).

### 5.21 Cargar ajustes posteriores no domiciliados [65–67]

- **Tipo:** subida TUS (§0.4), con el endpoint común de ajustes.
- **Metadatos TUS:** los de §0.4, con `codProceso` = **60** («Importar CP no domiciliados en Ajustes Posteriores»).
- **Salida:** `numTicket`. **Respuesta de ejemplo** [66]: `20230100000119`.
- **Errores 422:** la lista común de §0.4.

### 5.22 Enviar ajustes posteriores no domiciliados [67–68]

- **Método:** `POST`.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rce/ajustesposteriores/web/comprobantesajuspost/{perTributario}/{numAjustePosterior}/{codLibro}/{numTicket}/registrarajustesposterioresrcnd`
- **Parámetros path:** `perTributario`, `numAjustePosterior`, `codLibro` (080000) y `numTicket`, todos obligatorios.
- **Ejemplo de URL:** `.../comprobantesajuspost/202301/2/080000/20210300000001/registrarajustesposterioresrcnd`
- **Cuerpo (tabla):** «No aplica». **Cuerpo de ejemplo** [68]:
  `{ "controlProcesos": { "lisFases": [ { "codFase": "10" } ] }, "registrosLibros": { "indEnviadoAjuste": "1" } }`
- **Salida:** HTTP 200. **Respuesta de ejemplo:** `"OK"`.
- **Errores 422:** 1006, 1007; 1051 El campo 'numTicket' no enviado o es vacío; 1052 Formato no permitido o no valido para el número de Ticket; 2002 Solo se permite valor númerico para el campo "codFase"; 2003 El valor enviado para el campo "codFase" no es el correcto; 2004 Solo se permite valor númerico para el campo "indEnviadoAjuste"; 2005 El valor enviado para el campo "indEnviadoAjuste" no es el correcto; 1140.

### 5.23 Eliminar comprobante de ajustes posteriores no domiciliados [68–70]

- **Método:** `DELETE`, con cuerpo JSON.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rce/ajustesposteriores/web/comprobantesajuspost/{perTributario}/{indTipoAjustePosterior}/eliminarcomprobanteaprcnd`
- **Parámetros path:** `perTributario` (obligatorio); `indTipoAjustePosterior` (int): `2`, «Ajuste Posterior con No Domiciliados», obligatorio. ⚠ La URL de ejemplo usa `5`: `.../comprobantesajuspost/202301/5/eliminarcomprobanteaprcnd`.
- **Cuerpo (tabla):** `codAjustePosterior` (obligatorio) y `detalleAjustes`, un array de objetos con `codTipoCDP` (obligatorio), `numSerieCDP` (**opcional**), `numCDP` (obligatorio), `codCar` (obligatorio) e `id` (obligatorio).
- **Cuerpo de ejemplo** [69]: `{ "codAjustePosterior": "6362eb208f9abedcdf739282", "detalleAjustes": [ { "codTipoCDP": "07", "numSerieCDP": "EB01", "numCDP": "514", "numTicket": "20209200000001" }, { "codTipoCDP": "08", "numSerieCDP": "EB02", "numCDP": "519", "numTicket": "20209200000002" } ] }`. El ejemplo lleva `numTicket` en lugar de `codCar` e `id`.
- **Respuesta de ejemplo** [70]: `"OK"`.
- **Errores 422:** 1005, 1006, 1007, 2000, 1104, 1323, 1011, 1012.

### 5.24 Cargar ajustes posteriores de periodos anteriores [70–71]

- **Tipo:** subida TUS (§0.4), con el endpoint común de ajustes.
- **Metadatos TUS:** los de §0.4, con `codProceso` = **6** («Cargar Ajuste posteriores del SIRE»). ⚠ El Anexo I tiene además el 7 («Cargar Ajuste posteriores anteriores a la vigencia»), el 93 («…RCE de Periodos Anteriores Simplificado») y el 94 («…RCE de Periodos Anteriores General»).
- **Salida:** `numTicket`. **Respuesta de ejemplo** [71]: `20230100000119`.
- **Errores 422:** la lista común de §0.4.
- **Requisito previo** [28]: la carga debe hacerse «referenciando al último periodo generado en el SIRE».

### 5.25 Enviar ajustes posteriores de periodos anteriores [71–73]

- **Método:** `POST`.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rce/ajustesposteriores/web/comprobantesajuspost/{perTributario}/{numAjustePosterior}/{codLibro}/{numTicket}/registrarajustesposterioresparc`
- **Parámetros path:** `perTributario`, `numAjustePosterior`, `codLibro` y `numTicket`, todos obligatorios.
- **Cuerpo (tabla):** `codAjustePosterior` y `detalleAjustes`, un array de objetos con `codTipoCDP`, `numSerieCDP`, `numCDP` y `numTicket`, todos obligatorios.
- **Cuerpo de ejemplo** [73]: `{ "controlProcesos": { "lisFases": [ { "codFase": "9" } ] }, "registrosLibros": { "indEnviadoAjuste": "1" } }`. ⚠ No coincide con la tabla.
- **Respuesta de ejemplo:** `"OK"`.
- **Errores 422:** 1005, 1006, 1007, 1051, 1052, 2002, 2003, 2004, 2005, 1140.

### 5.26 Eliminar comprobante de ajustes posteriores de periodos anteriores [73–74]

- **Método:** `DELETE`, con cuerpo JSON.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rce/ajustesposteriores/web/ajustesposteriores/{indTipoAjustePosterior}/{perTributario}/eliminarcomprobanteapparc`. El orden aquí es tipo y luego periodo.
- **Parámetros path:** `perTributario` (obligatorio); `indTipoAjustePosterior` (int): `3`, «Ajuste Posteriores de periodos anteriores general», obligatorio.
- **Cuerpo:** `codAjustePosterior` y `detalleAjustes`, un array de objetos con `codTipoCDP`, `numSerieCDP` y `numCDP`, todos obligatorios.
- **Cuerpo de ejemplo** [74]: `{ "codAjustePosterior": "6323f041896dfc292768cc55", "detalleAjustes": [ { "codTipoCDP": "07", "numSerieCDP": "EB01", "numCDP": "519" }, { "codTipoCDP": "08", "numSerieCDP": "EB02", "numCDP": "519" } ] }`
- **Respuesta de ejemplo:** `"OK"`.
- **Errores 422:** 1005, 1006, 1007, 2000, 1104, 1323, 1011, 1012.

### 5.27 Cargar ajustes posteriores de periodos anteriores no domiciliados [75–76]

- **Tipo:** subida TUS (§0.4), con el endpoint común de ajustes.
- **Metadatos TUS:** los de §0.4, con `codProceso` = **60**. ⚠ El Anexo I tiene además el 95 («Importar CP no domiciliados en Ajustes Posteriores RCE de Periodos Anteriores»).
- **Salida:** `numTicket`. **Respuesta de ejemplo** [75]: `20230100000119`.
- **Errores 422:** la lista común de §0.4.

### 5.28 Enviar ajustes posteriores de periodos anteriores no domiciliados [76–77]

- **Método:** `POST`.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rce/ajustesposteriores/web/comprobantesajuspost/{perTributario}/{numAjustePosterior}/{codLibro}/{numTicket}/registrarajustesposterioresparcnd`
- **Parámetros path:** `perTributario`, `numAjustePosterior`, `codLibro` y `numTicket`, todos obligatorios.
- **Cuerpo (tabla):** «No aplica». **Cuerpo de ejemplo** [77]:
  `{ "controlProcesos": { "lisFases": [ { "codFase": "13" } ] }, "registrosLibros": { "indEnviadoAjuste": "1" } }`
- **Respuesta de ejemplo:** `"OK"`.
- **Errores 422:** 1005, 1006, 1007, 1051, 1052, 2002, 2003, 2004, 2005, 1140.

### 5.29 Eliminar comprobante de ajustes posteriores de periodos anteriores no domiciliados [78–79]

- **Método:** `DELETE`, con cuerpo JSON.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rce/ajustesposteriores/web/{numAjustePosterior}/{perTributario}/eliminarcomprobanteapparcnd`
- **Parámetros path:** `perTributario` y `numAjustePosterior`, ambos obligatorios. Ejemplo de URL: `.../ajustesposteriores/web/1/202301/eliminarcomprobanteapparcnd`.
- **Cuerpo:** `codAjustePosterior` y `detalleAjustes`, un array de objetos con `codTipoCDP`, `numSerieCDP`, `numCDP` y `numTicket`, todos obligatorios.
- **Cuerpo de ejemplo** [79]: `{ "codAjustePosterior": "636a9ae23ca7a82c2079f615", "detalleAjustes": [ { "codTipoCDP": "11", "numSerieCDP": "EB01", "numCDP": "514", "numTicket": "20210200000010" }, { "codTipoCDP": "08", "numSerieCDP": "EB02", "numCDP": "519", "numTicket": "20210200000011" } ] }`
- **Respuesta de ejemplo:** `"OK"`.
- **Errores 422:** 1005, 1006, 1007, 2000, 1104, 1323, 1011, 1012.

**Valores de `codFase` que aparecen en el manual (solo en ejemplos; no hay tabla de fases):**
9 en 5.19 y 5.25, 10 en 5.22 y 13 en 5.28. `indEnviadoAjuste` vale siempre "1".

---

## 5.31 Consultar estado ticket [79–82]

- **Método:** `GET`.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/gestionprocesosmasivos/web/masivo/consultaestadotickets?perIni={perIni}&perFin={perFin}&page={page}&perPage={perPage}&numTicket={numTicket}`
- **Parámetros query:**

  | Parámetro | Tipo | Obligatorio | Descripción |
  |---|---|---|---|
  | `perIni` | alfanumérico, string | Sí | Periodo de consulta de documentos de comprobantes del RCE preliminar Inicio |
  | `perFin` | alfanumérico, string | Sí | Periodo de consulta … Final |
  | `numTicket` | alfanumérico, string | **No** | `[AAAA99999999]` |
  | `page` | numérico, int | Sí | Ejemplo: 1 |
  | `perPage` | numérico, int | Sí | Ejemplo: 20 |

- **Cabeceras:** las de §0.2. **Cuerpo:** no aplica.
- **Estructura de salida completa** (tabla del manual, nombres literales):

  ```
  paginacion            (array)   page (Int) · perPage (Int) · totalRegistros (Int)
  registros             (array)
    showReportesDescarga  String  "0" no muestra icono de archivo de texto / "1" muestra ícono
    perTributario         String
    numTicket             String  [AAAA99999999]
    fecCargaImportacion   yyyy-mm-dd'T'hh:ii:ss  (Obligatorio) fecha de carga o de solicitud de generación
    fecInicioProceso      yyyy-mm-dd             (Obligatorio)
    codProceso            String  (Anexo I)
    desProceso            String  (Anexo I)
    codEstadoProceso      String  Código de estado de envio
    desEstadoProceso      String  Descripción de estado de envio
    nomArchivoImportacion String
    detalleTicket         (array)
      numTicket               String
      fecCargaImportacion     yyyy-mm-dd
      horaCargaImportacion    hh:mm:ss
      codEstadoEnvio          String
      desEstadoEnvio          String
      nomArchivoReporte       String  («Nombre del a» — descripción truncada en el manual)
      cntFilasvalidada        Integer Cantidad de filas validadas o total de registros
      cntCPError              Integer Cantidad de comprobantes con error
      cntCPInformados         Integer Cantidad de CP informados
    archivoReporte        (array)
      nomArchivoReporte       String  Nombre del archivo de reporte
      codTipoAchivoReporte    String  Código del tipo de archivo de reporte   [sic]
  ```

  Notas literales:
  - La tabla dice `showReportesDescarga`, pero la respuesta de ejemplo trae `showReporteDescarga` **[sic]**.
  - La tabla lista el campo como `codTipoAchivoReporte` **[sic]**, sin la «r» de «Archivo», y sin el prefijo `archivoReporte.`. En 5.32 el manual lo cita como `archivoReporte.codTipoArchivoReporte`.
  - **El manual no enumera los valores de `codTipoArchivoReporte`**, solo pone un ejemplo (`01`, en 5.32). La única regla es la nota de 5.32: «Si el campo codTipoAchivoReporte que devuelve el API 5.31 es null, colocar el mismo valor(null)».
  - **El manual no enumera los valores de `codEstadoProceso` ni de `codEstadoEnvio`.** El único valor que aparece es `"06"` = `"Terminado"`. La guía [35] pide que el ticket esté «Terminado» antes de descargar.
- **Respuesta de ejemplo** [81]. Es la única que da el manual, y está recortada en la captura:
  ```json
  { "paginacion": { "page": 1, "perPage": 20, "totalRegistros": 11 },
    "registros": [ {
        "showReporteDescarga": "1", "perTributario": "202301", "numTicket": "20230300000083",
        "fecCargaImportacion": null, "fecInicioProceso": "2023-06-07",
        "codProceso": "13", "desProceso": "Generar archivo exportar inconsistencias",
        "codEstadoProceso": "06", "desEstadoProceso": "Terminado", "nomArchivoImportacion": "",
        "detalleTicket": { "numTicket": "20230300000083", "fecCargaImportacion": "2023-06-07",
                           "horaCargaImportacion": "17:20:36", "codEstadoEnvio": "06",
                           "desEstadoEnvio": "Terminado", … } } ] }
  ```
  En el ejemplo `detalleTicket` es un **objeto**, aunque la tabla lo declara como array. La captura se corta antes de `archivoReporte`, así que el manual no muestra un ejemplo de esa lista.
- **Errores 422:** 1067 El campo “perIni” no enviado o es vacío; 1068 Formato de perIni no cumple con el formato “yyyymm”; 1069 El perIni de búsqueda no debe ser mayor a la fecha actual; 1071 El campo “perFin” no enviado o es vacío; 1072 Formato de perFin no cumple con el formato “yyyymm”; 1073 El perFin de búsqueda no debe ser mayor a la fecha actual; 1076 El campo 'page' no enviado o es vacío; 1077 El campo “page” debe ser numérico mayor a cero; 1079 El campo 'perPage' no enviado o es vacío; 1078 El campo “per_page” debe ser numérico mayor a cero; 1052 Formato no permitido o no valido para el número de Ticket; 1138 El numTicket enviado en la URI debe ser igual al numTicket enviado en el Body.

## 5.32 Descargar archivo [82–83]

- **Descripción:** descarga los archivos generados (zipeados y particionados) que están en el *fileserver*.
- **Método:** `GET`.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/gestionprocesosmasivos/web/masivo/archivoreporte?nomArchivoReporte={nomArchivoReporte}&codTipoArchivoReporte={codTipoArchivoReporte}`
- **Parámetros query:**
  - `nomArchivoReporte` (alfanumérico, String, obligatorio): nombre o ruta del archivo generado. Sale de `archivoReporte.nomArchivoReporte` en 5.31.
  - `codTipoArchivoReporte` («numérico-String», obligatorio): sale de `archivoReporte.codTipoArchivoReporte` en 5.31. Si 5.31 lo devuelve null, se envía `null`.
- **Ejemplo de URL:** `...archivoreporte?nomArchivoReporte=20100176450-CPF-202302-01.zip&codTipoArchivoReporte=01`
- La captura incluida (sacada del manual RVIE, «5.17 Servicio Web Api descargar archivo») envía tres parámetros: `nomArchivoReporte=6549278a1275a57884e56184__LE2038882945220231100014040000…`, `codTipoArchivoReporte=null` y **`codLibro=140000`**. La tabla del RCE no incluye `codLibro`.
- **Salida (tabla):** HTTP 200, `application/json`. **Respuesta de ejemplo** [83]: el contenido binario de un ZIP (`PK…`) que contiene `20100176450_INCONSISTENCIA_20230524.txt`.
- **Errores 422:** 1134 El campo “nomArchivoReporte” no enviado o es vacío; 2278 El campo 'codTipoArchivoReporte' no enviado o es vacío.

## 5.33 Consultar año y mes del RCE [83–84]

- **Método:** `GET`.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/padron/web/omisos/{codLibro}/periodos`
- **Parámetro path:** `codLibro` (alfanumérico, string, `080000`, obligatorio).
- **Salida:** un array de ejercicios con `numEjercicio`, `desEstado` y `lisPeriodos[]`. Cada elemento de `lisPeriodos` tiene `perTributario`, `codEstado` y `desEstado`.
- **Respuesta de ejemplo** (URL `.../omisos/080000/periodos`):
  ```json
  [ { "numEjercicio": "2023", "desEstado": "Presentado",
      "lisPeriodos": [ { "perTributario": "202305", "codEstado": "01", "desEstado": "Presentado" },
                       { "perTributario": "202304", "codEstado": "01", "desEstado": "Presentado" }, … ] } ]
  ```
  El manual no lista otros valores de `codEstado` aparte de `01` = Presentado.
- **Errores 422:** 1140 El campo “codLibro” no enviado o es vacío; 1161 Código de Libro no permitido o no válido.

## 5.35 Descargar resumen [86–87]

- **Descripción:** descarga todos los tipos de resumen: propuesta, incluidos o excluidos, preliminar, RCE generado y ajustes posteriores.
- **Método:** `GET`.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/resumen/web/resumencomprobantes/{perTributario}/{codTipoResumen}/{codTipoArchivo}/exporta?codLibro={codLibro}`
- **Parámetros** (la tabla los llama `tipoReporte` y `tipoDescarga`, y la URL `codTipoResumen` y `codTipoArchivo`):
  - `perTributario` (obligatorio).
  - `codTipoResumen`/`tipoReporte` (obligatorio): 1 Resumen de propuesta · 2 Resumen de preliminar · 3 Resumen no Incluidos (V) o Excluidos (C) · 4 Resumen de registro · 5 Resumen de preliminar registrado · 6 Resumen ajustes posteriores · 7 Resumen no domiciliados.
  - `codTipoArchivo`/`tipoDescarga` (int, obligatorio): según el Anexo III, 0 txt, 1 csv o 2 excel.
  - `codLibro` (query, `080000`, obligatorio).
- **Salida:** `buffer` (binario, «Arreglo de bits»).
- **Respuesta de ejemplo** (URL `.../resumencomprobantes/202301/1/0/exporta?codLibro=080000`), texto separado por `|`:
  ```
  Tipo de Documento|Total Documentos|BI Gravado DG|IGV / IPM DG|BI Gravado DGNG|IGV / IPM DGNG|BI Gravado DNG|IGV / IPM DNG|Valor Adq. NG|ISC|ICBPER|Otros Trib/ Cargos|Total CP
  01-Factura|101|101000.00|20200.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|121200.00
  TOTAL |101|101000.00|20200.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|121200.00
  ```
- **Errores 422:** 1005, 1006; 1070; 1140; 1518 No existen documentos para exportar; 1059 Código tipo de Archivo no permitido o no valido; 1060 Solo se permite dato numérico de 1 dígito para el codTipoArchivo; 1061 El campo "codTipoArchivo" es nulo o vacío; 1056 Solo se permite dato numérico de 1 dígito para el codTipoResumen; 1057 El campo "codTipoResumen" es nulo o vacío.

## 5.36 Descargar resumen inconsistencias RCE [88–89]

- **Método:** `POST`, según el manual.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/resumen/web/resumeninconsistencias/{perPeriodoTributario}?codTipoResumen={codTipoResumen}&codLibro={codLibro}`
- **Parámetros:** `perPeriodoTributario` (path, obligatorio); `codLibro` (080000, obligatorio); `codTipoResumen` (obligatorio): 1 propuesta · 2 preliminar · 3 Incluidos o Excluidos · 4 registro · 5 preliminar registrado · 6 ajustes posteriores. El valor 7 no figura aquí.
- **Cuerpo:** no aplica.
- **Salida (tabla):** `numRuc`, `perTributario`, `codTipoResumen`, `cantidad` {`porcentajeRelFiscal`, `porcentajeNoRelFiscal`, `porcentajeSinValidaciones` (decimal128), `total` (int)} y `monto` {los mismos tres porcentajes y `total`, todos decimal128}.
- **Respuesta de ejemplo** (URL `.../resumeninconsistencias/202301?codTipoResumen=1&codLibro=080000`):
  ```json
  { "numRuc": "20100176450", "perPeriodoTributario": "202301", "codTipoResumen": "1",
    "cantidad": { "porcentajeRelFiscal": 100.00, "porcentajeNoRelFiscal": 0, "porcentajeSinValidaciones": 0, "total": 101 },
    "monto":    { "porcentajeRelFiscal": 100.00, "porcentajeNoRelFiscal": 0, "porcentajeSinValidaciones": 0, "total": 121200.0 } }
  ```
  En el ejemplo la clave es `perPeriodoTributario`; en la tabla, `perTributario`.
- **Errores 422:** 1005, 1006, 1140, 1518, 1056, 1057.

## 5.38 Eliminar comprobante no domiciliado [91–92]

- **Descripción:** elimina un comprobante del preliminar del RC de operaciones con no domiciliados.
- **Método:** `PUT`.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rce/libronodomiciliado/web/nodomiciliados/{perTributario}/eliminarcomprobantepreliminarnd`
- **Parámetro path:** `perTributario` (obligatorio).
- **Cuerpo:** `noDomiciliados`, un array de objetos con `codCar`, `codTipoCDP` (lista de 5.15), `numSerieCDP` y `numCDP`, todos obligatorios.
- **Cuerpo de ejemplo:** `{ "noDomiciliados": [ { "codCar": "3456789123500E0010000000210", "codTipoCDP": "00", "numSerieCDP": "E001", "numCDP": "210" } ] }`
- **Respuesta de ejemplo:** `"OK"`.
- **Errores 422:** 1005, 1006, 1007, 1104, 1323, 1011, 1012.

## 5.39 Exportar preliminar de registro de compras no domiciliados [92–94]

- **Método:** `GET`.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rce/preliminar/web/nodomiciliados/{perTributario}/exportapreliminarnd?codTipoArchivo={codTipoArchivo}&codOrigenEnvio={codOrigenEnvio}&mtoTotalDesde={mtoTotalDesde}&mtoTotalHasta={mtoTotalHasta}&fecEmisionIni={fecEmisionIni}&fecEmisionFin={fecEmisionFin}&numDocIdentidadClienteProveedor={numDocIdentidadClienteProveedor}&numSerieCDP={numSerieCDP}&numCDP={numCDP}&codTipoCDP={codTipoCDP}&numDocAdquiriente={numDocAdquiriente}`
- **Parámetros:**

  | Parámetro | Tipo | Oblig. | Nota |
  |---|---|---|---|
  | `perTributario` (path) | String | Sí | |
  | `codTipoArchivo` | Integer | Sí | «Ver Anexo IV: Extension del archivo a descargar»; ⚠ es el Anexo III (0 txt, 1 csv, 2 excel) |
  | `mtoTotalDesde` / `mtoTotalHasta` | decimal128 | No | si se usa uno, se exigen los dos (error 1113) |
  | `codTipoCDP` | String | No | tabla 03 del anexo 1 de la R.S. 112-2021/SUNAT |
  | `numSerieCDP` | String | **Sí** según la tabla | |
  | `numCDP` | String | **Sí** según la tabla | |
  | `fecEmisionIni` / `fecEmisionFin` | «dd/mm/aaaa» | No | el ejemplo usa `2022-06-02`; el error 1115 aparece con los dos formatos |
  | `numDocAdquiriente` | String | No | |
  | `numDocIdentidadClienteProveedor` | String | No | |
  | `codOrigenEnvio` | String | Sí | 2 Servicio web |

- **Ejemplo de URL:** `.../nodomiciliados/202206/exportapreliminarnd?codTipoArchivo=0&codOrigenEnvio=2&mtoTotalDesde=1000&mtoTotalHasta=6000&fecEmisionIni=2022-06-02&fecEmisionFin=2022-06-18&numDocIdentidadClienteProveedor=1234567891235&numSerieCDP=E001&numCDP=210&codTipoCDP=00&numDocAdquiriente=1234567891235`
- **Salida:** `numTicket`. **Respuesta de ejemplo** [94]: `{ "numTicket": "20220300000242" }`. El archivo se recupera después con 5.31 y 5.32.
- **Errores 422:** 1005, 1006, 1007; 1112 El Monto Total Desde debe ser mayor o igual al Monto Total Hasta; 1113; 1059, 1060, 1061; 1114 Fecha Documento Desde debe estar dentro del Periodo seleccionado; 1115 (formato de fecha); 1116 Fecha de documento Hasta debe ser mayor o igual al Fecha de documento Desde; 1117 Si se realiza busqueda por Fecha Documento, se debe ingresar los campos Fecha Documento Desde, Fecha Documento Hasta; 1118; 1104; 1119 El código de tipo de inconsistencia enviado no es válido; 1002; 1003.

## 5.42 Descargar inconsistencias en registros preliminar registrado [98–99]

- **Método:** `GET`.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/casillas/inconsistenciaslibros/{perTributario}/reporteinconsistencia/{codTipoArchivo}?cntlimite={cntlimite}`
- **Parámetros:** `perTributario` (path, obligatorio); `codTipoArchivo` (path, integer, Anexo III, obligatorio); `cntlimite` (query, int, «Cantidad de registros para validar el top», obligatorio).
- **Ejemplo de URL:** `.../inconsistenciaslibros/202205/reporteinconsistencia/xls?cntlimite=20`. ⚠ El ejemplo envía `xls` en lugar de un código numérico.
- **Salida:** `Buffer`, binario. **Respuesta de ejemplo** [99]: el contenido binario de una hoja Excel.
- **Errores 422:** 1005, 1006, 1007, 1059, 1060, 1061, 1070.

## 5.44 Descargar inconsistencias por comprobante pago [100–102]

- **Método:** `GET`.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rce/inconsistencias/web/periodoinconsistencias/{perTributario}/{codLibro}/exportarinconsistenciasporcomprobantes?fecEmisionInicio={fecEmisionInicio}&fecEmisionFin={fecEmisionFin}&codInconsistencia={codInconsistencia}&numDocIdentidadClienteProveedor={numDocIdentidadClienteProveedor}&codTipoCDP={codTipoCDP}&numSerieCDP={numSerieCDP}&numCDP={numCDP}&codTipoArchivo={codTipoArchivo}&mtoTotalDesde={mtoTotalDesde}&mtoTotalHasta={mtoTotalHasta}&codEstado={codEstado}&codOrigenEnvio={codOrigenEnvio}`
- **Parámetros:** `perTributario` y `codLibro` (path, obligatorios); `fecEmisionIni` y `fecEmisionFin` («dd/mm/aaaa», opcionales; ⚠ la URL usa `fecEmisionInicio`); `codInconsistencia` (opcional; ejemplo: «301 - Fecha de emisión del comprobante de pago o fecha de pago del impuesto se anota luego de los doce meses siguientes…»); `numDocIdentidadClienteProveedor` (opcional); `codTipoCDP` (opcional, lista de 5.15); `numSerieCDP` y `numCDP` (opcionales); `codTipoArchivo` (int, Anexo III, **obligatorio**); `mtoTotalDesde` y `mtoTotalHasta` (opcionales); `codEstado` (opcional, sin valores definidos); `codOrigenEnvio` (2, obligatorio).
- **Ejemplo de URL:** `.../periodoinconsistencias/202201/080000/exportarinconsistenciasporcomprobantes?codOrigenEnvio=2&codTipoArchivo=0`
- **Salida:** `numTicket`. **Respuesta de ejemplo** [102]: `{ "numTicket": "20230300000060" }`.
- **Errores 422:** 1005, 1006, 1007; 1098 y 1100 (formato de fecha inicial o final); 1102 La Fecha de Emisión Final debe ser mayor o igual a la Fecha de Emisión Inicial; 1422 Se debe seleccionar una inconsistencia; 1324 El campo "numDocIdentidadClienteProveedor" es nulo o vacío; 1345 (solo letras y números, 15 caracteres); 1104; 1140; 1161 Código de libro no existe; 1112; 1113.
- **Catálogo de `codInconsistencia`:** el manual no lo incluye; solo da el ejemplo 301.

## 5.46 Descargar ajustes posteriores no domiciliados [103–104]

- **Descripción:** exporta los ajustes posteriores de operaciones con no domiciliados, si el generador ha cargado ajustes.
- **Método:** `POST`, según el manual.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rce/ajustesposteriores/web/comprobantesajuspost/{perTributario}/exportarajustesposterioresrcnd?codTipoArchivo={codTipoArchivo}`
- **Parámetros:** `perTributario` (path, obligatorio); `codTipoArchivo` (query, int, Anexo III, obligatorio).
- **Ejemplo de URL:** `.../comprobantesajuspost/202301/exportarajustesposterioresrcnd?codTipoArchivo=1`
- **Salida:** `numTicket`. **Respuesta de ejemplo** [104]: `{ "numTicket": "20230300000060" }`.
- **Errores 422:** 1005, 1006, 1007, 1059, 1060, 1061.

## 5.49 Descargar constancia de recepción [107–108]

- **Método:** `GET`.
- **URL:** `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rvierce/gestionlibro/web/registroslibros/constancia/constanciarecepcion?nomConstanciaRecepcion={nomConstanciaRecepcion}`
- **Parámetro query:** `nomConstanciaRecepcion` (alfanumérico, string, «Nombre o ruta del archivo generado», obligatorio).
- **Ejemplo de URL:** `...constanciarecepcion?nomConstanciaRecepcion=LE2019592375320221100080400011022.pdf`
- **Salida:** `archivoPdf`, como «Arreglo de Bytes». En la V22 cambió de Base64-String a Bytes [8].
- **Respuesta de ejemplo** [108]: el PDF renderizado («Constancia de Recepción del Registro de Compras Electrónico»: transacción «Generación del Registro de Compras Electrónico(RCE)», Nro. de operación, RUC, periodo 2022/11, «Propuesta Aceptada» y un detalle de resúmenes con el código `080400` «Registro de Compras»).
- **Errores 422:** 1080 El campo 'nomConstanciaRecepcion' no enviado o es vacío.
- **De dónde sale `nomConstanciaRecepcion`:** el manual no lo indica.

## 5.59 Consultar ajustes posteriores RCE [121–122]

- **Descripción:** «Permite consultar el código de ajuste posterior y comprobantes del ajustes posterior RCE».
- **Método:** `PUT`, según el manual.
- **URL:** el manual lista **dos**:
  1. `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rce/propuesta/web?periodoSeleccionado={periodoSeleccionado}&tipoInfo={tipoInfo}`
  2. `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/rce/ajustesposteriores/web/comprobantesajuspost/{periodoSeleccionado}/listarcap?page={page}&perPage={perPage}`
- **Parámetros:** `periodoSeleccionado` (String, obligatorio); `page` (entero, número de página); `perPage` (entero, número de registros).
- **Salida (tabla) y ejemplo:** copiados de 5.14 (FV0621). La evidencia usa la URL 1 con `tipoInfo=FV0621` y devuelve `{ "registros": { "factProrrata": 3.2567, "valorRCF": 3.22, "valorCFE": 3.33 } }`.
  ⚠ **El manual no documenta la respuesta de `listarcap`**, que es la que contendría `codAjustePosterior` y la lista de comprobantes.
- **Errores 422:** 1005, 1006, 1007.

---

## 7. Anexos

### 7.1 Anexo I: Indicador de carga masiva (`codProceso`) [123–125], transcripción completa

| Cód. | Descripción | Cód. | Descripción |
|---|---|---|---|
| 1 | Importar CP - Propuesta | 50 | Descargar Reporte de Ajustes Posteriores RCE |
| 2 | Aceptar propuesta | 51 | Descargar Reporte de Casillas Vista Comparada |
| 3 | Reemplazo de la Propuesta | 52 | Descargar Reporte de Inconsistencias de Casillas |
| 4 | Importa CP - Preliminar | 53 | Generar Reporte de comparación RCE |
| 5 | Generar libro RVIE | 54 | Carga Complementar |
| 6 | Cargar Ajuste posteriores al periodo actual | 55 | Carga Incluir Excluir |
| 6 | Cargar Ajuste posteriores de periodos del sire | 56 | Carga No Domiciliados |
| 7 | Cargar Ajuste posteriores anteriores a la vigencia | 57 | Carga Comparacion RCE |
| 8 | Generar registro Ajustes Posterior RVIE | 58 | Carga Comparacion RVIE |
| 9 | Generar registro Ajustes Posterior Anterior RVIE | 59 | importar CP en Ajustes Posteriores RCE |
| 10 | Generar archivo exportar propuesta | 60 | importar CP no domiciliados en Ajustes Posteriores |
| 11 | Generar archivo exportar no incluidos | 61 | Reemplazo de la Propuesta |
| 12 | Generar archivo exportar preliminar | 62 | Generacion de Inconsistencia por Casilla |
| 13 | Generar archivo exportar inconsistencias | 63 | Generación de ventas por Casilla (100. 101) |
| 14 | Generar archivo exportar propuesta ajustes posteriores | 64 | Generacion Inconsistencias en Registros para Casillas |
| 15 | Generar archivo exportar CAR | 65 | Validar Propuesta |
| 16 | Generar reporte de observaciones de comparación | 66 | Validar Preliminar |
| 17 | Generar archivo exportar Libro Venta | 67 | Validar No Domiciliados |
| 18 | Generar reporte de ajustes posteriores individual | 68 | Reporte de Ajustes posteriores de periodos anteriores del RCE |
| 19 | Generar reporte de ajustes posteriores consolidado | 69 | Descarga Consolidada de registros del RCE |
| 20 | Generar reporte de ajustes posteriores de periodos anteriores individual | 70 | Descarga RCE |
| 21 | Generar reporte de ajustes posteriores de periodos anteriores consolidado | 71 | Reporte de ajustes posteriores del RVIE |
| 22 | Generar reporte consolidado del libro y ajustes | 72 | Reporte de Ajustes posteriores de periodos anteriores del RVIE |
| 23 | Generar reporte Libro RVIE | 73 | Descarga Consolidada de registros del RVIE |
| 24 | Generar Archivo personalizado Libros RVIE | 74 | Descarga RVIE |
| 25 | Generar Archivo personalizado Propuesta RVIE | 75 | Generación de ventas por Casilla (100. 101) |
| 26 | Generar Archivo personalizado Ajustes Posteriores RVIE | 76 | Generacion Inconsistencias en Registros para Casillas |
| 27 | Carga archivo de comparación - validación | 77 | Validar Propuesta |
| 28 | Generar archivo exportar preliminar registrado | 78 | Validar Preliminar |
| 29 | Generar archivo exportar preliminar ajustes posteriores registrado | 79 | Validar No Domiciliados |
| 30 | Generar reporte de inconsistencias generación del RVIE | 80 | Generación de archivo personalizado Propuesta RCE |
| 31 | Generar reporte de inconsistencias ajustes posteriores del RVIE | 81 | Generación de archivo personalizado Preliminar RCE |
| 32 | Generar libro RVIE - Archivo exportar Libro Venta | 82 | Generación de archivo personalizado Preliminar Registrado RCE |
| 33 | Generar libro RVIE - Archivo reporte inconsistencias | 83 | Generación de archivo personalizado Registro Compras |
| 34 | Generar libro RVIE - Achivo Reporte Exportadores | 84 | Generación de archivo personalizado Ajuste Posterior RCE |
| 35 | Generar libro RVIE - Archivo Propuesta Casillas | 85 | Generacion de archivo del libro de Ajustes Posteriores RVIE |
| 36 | Generar Ajustes Posteriroes RVIE - Archivo exportar Ajuste | 86 | Generacion de archivo de inconsistencias de libro de Ajustes Posteriores RVIE |
| 37 | Generar Ajustes Posteriroes RVIE - Archivo reporte inconsistencias | 87 | Importar CP en Ajustes Posteriores RVIE |
| 38 | Generar Ajustes Posteriores de periodos anteriores RVIE - Archivo exportar Ajuste | 88 | Importar CP en Ajustes Posteriores de periodos anteriores RVIE general |
| 39 | Aceptar propuesta sin Movimiento | 89 | Importar CP en Ajustes Posteriores de periodos anteriores RVIE simplificado |
| 40 | Carga Tipo de Cambio | 90 | Generación de documentos para Intranet |
| 41 | Generar reportes Estadisticos | 91 | Exportar detalle propuesta casilla - Registro |
| 42 | Generar Reporte de comparación | 92 | Exportar inconsistencias en registro |
| 43 | Descargar Registros Electronicos RVIE | 93 | Importar CP en Ajustes Posteriores RCE de Periodos Anteriores Simplificado |
| 44 | Descargar Registros Electronicos RCE | 94 | Importar CP en Ajustes Posteriores RCE de Periodos Anteriores General |
| 45 | Descargar Constancia de Recepción RVIE | 95 | Importar CP no domiciliados en Ajustes Posteriores RCE de Periodos Anteriores |
| 46 | Descargar Constancia de Recepción RCE | 96 | Generar archivo exportar preliminar - RCE No Domiciliados |
| 47 | Descargar Reporte de Inconcistencias RVIE | 97 | Exportar comprobantes excluidos |
| 48 | Descargar Reporte de Inconcistencias RCE | | |
| 49 | Descargar Reporte de Ajustes Posteriores RVIE | | |

**`codProceso` por servicio, según la ficha de cada uno:** 5.3 → 61; 5.5 → 56; 5.6 → 54; 5.7 → 4;
5.8 → 55; 5.9 → 1; 5.18 → 6; 5.21 → 60; 5.24 → 6; 5.27 → 60. Las fichas no usan los códigos 59,
93, 94 ni 95 del anexo, aunque sus descripciones corresponden a esos procesos. Para 5.10, el
anexo tiene el 40 («Carga Tipo de Cambio»), pero el servicio no es TUS y no lleva `codProceso`.

**Indicadores de carga masiva:** el anexo es la tabla anterior. El manual no define otros
indicadores, como un «indicador de carga» separado.

### 7.2 Anexo II: Tipo de ajuste posterior [125]

1 Ajuste Posterior · 2 Ajuste Posterior con No Domiciliados · 3 Ajuste Posteriores de periodos
anteriores general · 4 Ajuste Posteriores de periodos anteriores simplificado · 5 Ajuste
Posteriores de periodos anteriores con No Domiciliados.

(El «Anexo II: Tipo de correlativo» que citan las fichas TUS **no existe**.)

### 7.3 Anexo III: Extensión del archivo a descargar [125]

0 txt · 1 csv · 2 excel.

### 7.4 Anexo IV: Ejemplo de cliente TUS en Java [125–155]

Resumido en §0.4.

### Códigos de libro

El manual solo usa **`080000` («RCE»)**. Las capturas copiadas del manual de ventas llevan
`140000`, y la constancia de 5.49 muestra `080400` («Registro de Compras») en el detalle de
resúmenes. **El manual no contiene ninguna tabla de códigos de libro**: no aparecen `080500`,
`080100` ni otros, y no define un código propio para no domiciliados.

### Estructura de los archivos TXT a importar: el manual NO la incluye

En todo el manual (incluidas las partes II y III) **no hay ningún anexo con la estructura de los
archivos** para no domiciliados, datos complementarios, incluir/excluir, nuevos comprobantes,
ajustes posteriores ni tipo de cambio. Faltan la nomenclatura del nombre del archivo, las columnas,
el separador y la codificación. Lo único que el manual deja ver es esto:

- Se sube un `.zip` (error 1348) con un `.txt` dentro («archivo de formato .txt zipeado», [18]).
  El tamaño va de más de 0 KB hasta 6 GB.
- El nombre se valida por posiciones (1044) y no puede repetirse (1024).
- Nombres que aparecen en los ejemplos: `LE20100176450202302001404000311102.zip` (formato LE del
  RVIE), `20100176450-CPF-202302-01.zip` (5.7 y 5.32) y
  `LE2010001749120231100140400 03111201.zip` (Demo.java, RVIE).
- Para el tipo de cambio (5.10): `.txt` enviado como multipart, con los campos `codMoneda` y
  `mtoTipoCambio` según los errores.

La estructura de los archivos está en la normativa de SUNAT (los anexos de la R.S. 112-2021/SUNAT
y sus modificatorias, que el manual cita en 5.39), no en este manual de API.

---

## Tabla resumen

| § | Servicio | Método | Ruta (tras `https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv/libros/`) | Entrada | Salida |
|---|---|---|---|---|---|
| 5.5 | Cargar no domiciliados | TUS | `rvierce/receptorpreliminar/web/preliminar/upload` | metadatos, codProceso 56 | numTicket |
| 5.6 | Complementar propuesta | TUS | `rvierce/receptorpropuesta/web/propuesta/upload` | codProceso 54 | numTicket |
| 5.7 | Nuevos CP en preliminar | TUS | `rvierce/receptorpreliminar/web/preliminar/upload` | codProceso 4 | numTicket |
| 5.8 | Incluir/excluir | TUS | `rvierce/receptorpropuesta/web/propuesta/upload` | codProceso 55 | numTicket |
| 5.9 | Nuevos CP en propuesta | TUS | `rvierce/receptorpropuesta/web/propuesta/upload` | codProceso 1 | numTicket |
| 5.10 | Tipo de cambio masivo | POST | `rce/propuesta/web/{perTributario}/{codLibro}/resumenfechatipocambio` | multipart `archivo` | ticket (tabla) / array (ejemplo) |
| 5.11 | Reintegro CF | PUT | `rce/propuesta/web/{perTributario}/grabacreditofiscal` | JSON valorRCF | "OK" |
| 5.12 | CF especial | PUT | `rce/propuesta/web/{perTributario}/grabacreditofiscalespecial` | JSON valorCFE | "OK" |
| 5.13 | Prorrata | PUT | `rce/propuesta/web/{perTributario}/grabacreditofiscal` | JSON factProrrata | "OK" |
| 5.15 | Eliminar CP propuesta | DELETE | `rce/propuesta/web/propuestarce/{perTributario}` | array JSON | "OK" |
| 5.16 | Eliminar CP preliminar | POST | `rce/preliminar/web/comprobanteslibroscompras/{perTributario}/eliminacomprobante` | array JSON | "OK" |
| 5.17 | Eliminar preliminar | PUT | `rce/preliminar/web/registroslibros/{perTributario}/{indEliminar}/eliminapreliminar` | — | "OK" |
| 5.18 | Cargar AP | TUS | `rvierce/receptorajustesposteriores/web/ajustesposteriores/upload` | codProceso 6 | "OK" (ejemplo) |
| 5.19 | Enviar AP | POST | `rce/ajustesposteriores/web/comprobantesajuspost/{perTributario}/{codOrigenEnvio}/registrarajustesposterioresrc` ⚠ | JSON codFase 9 | "OK" |
| 5.20 | Eliminar CP de AP | DELETE | `rce/ajustesposteriores/web/comprobantesajuspost/{perTributario}/{indTipoAjustePosterior}/eliminarcomprobanteaprc` | JSON | "OK" |
| 5.21 | Cargar AP ND | TUS | `rvierce/receptorajustesposteriores/web/ajustesposteriores/upload` | codProceso 60 | numTicket |
| 5.22 | Enviar AP ND | POST | `rce/ajustesposteriores/web/comprobantesajuspost/{perTributario}/{numAjustePosterior}/{codLibro}/{numTicket}/registrarajustesposterioresrcnd` | JSON codFase 10 | "OK" |
| 5.23 | Eliminar CP de AP ND | DELETE | `rce/ajustesposteriores/web/comprobantesajuspost/{perTributario}/{indTipoAjustePosterior}/eliminarcomprobanteaprcnd` | JSON | "OK" |
| 5.24 | Cargar AP periodos ant. | TUS | `rvierce/receptorajustesposteriores/web/ajustesposteriores/upload` | codProceso 6 | numTicket |
| 5.25 | Enviar AP periodos ant. | POST | `rce/ajustesposteriores/web/comprobantesajuspost/{perTributario}/{numAjustePosterior}/{codLibro}/{numTicket}/registrarajustesposterioresparc` | JSON codFase 9 | "OK" |
| 5.26 | Eliminar CP AP periodos ant. | DELETE | `rce/ajustesposteriores/web/ajustesposteriores/{indTipoAjustePosterior}/{perTributario}/eliminarcomprobanteapparc` | JSON | "OK" |
| 5.27 | Cargar AP periodos ant. ND | TUS | `rvierce/receptorajustesposteriores/web/ajustesposteriores/upload` | codProceso 60 | numTicket |
| 5.28 | Enviar AP periodos ant. ND | POST | `rce/ajustesposteriores/web/comprobantesajuspost/{perTributario}/{numAjustePosterior}/{codLibro}/{numTicket}/registrarajustesposterioresparcnd` | JSON codFase 13 | "OK" |
| 5.29 | Eliminar CP AP periodos ant. ND | DELETE | `rce/ajustesposteriores/web/{numAjustePosterior}/{perTributario}/eliminarcomprobanteapparcnd` | JSON | "OK" |
| 5.31 | Estado de ticket | GET | `rvierce/gestionprocesosmasivos/web/masivo/consultaestadotickets?perIni&perFin&page&perPage&numTicket` | query | paginacion + registros |
| 5.32 | Descargar archivo | GET | `rvierce/gestionprocesosmasivos/web/masivo/archivoreporte?nomArchivoReporte&codTipoArchivoReporte` | query | binario (zip) |
| 5.33 | Años y meses | GET | `rvierce/padron/web/omisos/{codLibro}/periodos` | — | array de ejercicios |
| 5.35 | Descargar resumen | GET | `rvierce/resumen/web/resumencomprobantes/{perTributario}/{codTipoResumen}/{codTipoArchivo}/exporta?codLibro` | — | buffer (txt con `\|`) |
| 5.36 | Resumen de inconsistencias | POST | `rvierce/resumen/web/resumeninconsistencias/{perPeriodoTributario}?codTipoResumen&codLibro` | — | JSON cantidad/monto |
| 5.38 | Eliminar CP ND | PUT | `rce/libronodomiciliado/web/nodomiciliados/{perTributario}/eliminarcomprobantepreliminarnd` | JSON noDomiciliados | "OK" |
| 5.39 | Exportar preliminar ND | GET | `rce/preliminar/web/nodomiciliados/{perTributario}/exportapreliminarnd?…` | query | numTicket |
| 5.42 | Inconsistencias del preliminar registrado | GET | `rvierce/casillas/inconsistenciaslibros/{perTributario}/reporteinconsistencia/{codTipoArchivo}?cntlimite` | — | buffer |
| 5.44 | Inconsistencias por CP | GET | `rce/inconsistencias/web/periodoinconsistencias/{perTributario}/{codLibro}/exportarinconsistenciasporcomprobantes?…` | query | numTicket |
| 5.46 | Descargar AP ND | POST | `rce/ajustesposteriores/web/comprobantesajuspost/{perTributario}/exportarajustesposterioresrcnd?codTipoArchivo` | — | numTicket |
| 5.49 | Constancia de recepción | GET | `rvierce/gestionlibro/web/registroslibros/constancia/constanciarecepcion?nomConstanciaRecepcion` | — | archivoPdf (bytes) |
| 5.59 | Consultar AP | PUT (manual) | `rce/ajustesposteriores/web/comprobantesajuspost/{periodoSeleccionado}/listarcap?page&perPage` | — | no documentada |

## Lo que el manual NO especifica

1. La estructura de **ningún** archivo TXT a importar (no domiciliados, complementar,
   incluir/excluir, nuevos CP, ajustes posteriores, tipo de cambio): nombre, columnas, separador y
   codificación.
2. El catálogo de `codTipoArchivoReporte` (solo hay un ejemplo, `01`, y la regla de enviar `null`),
   de `codEstadoProceso` y `codEstadoEnvio` (solo aparece `06` = Terminado) y de `codEstado` en 5.33
   (solo `01`) y en 5.44.
3. Un ejemplo de la lista `archivoReporte` en la respuesta de 5.31, porque la captura está recortada.
4. La respuesta de `listarcap` (5.59). Es decir, cómo obtener `codAjustePosterior`, `id` y
   `numAjustePosterior` para 5.19–5.29.
5. Una tabla de códigos de libro (solo aparece `080000`) y la tabla de `codFase` (solo aparecen
   9, 10 y 13 en ejemplos).
6. El «Anexo II: Tipo de correlativo», que se cita y no existe.
7. La procedencia de `nomConstanciaRecepcion` (5.49).
8. Los códigos 401 y 403 en las fichas de los servicios, el tamaño de trozo TUS que exige el
   servidor y la caducidad del token.
