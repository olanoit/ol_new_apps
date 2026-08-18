# Búsqueda RUC/DNI desde SUNAT — configurable por datos

Consulta y autocompletado de datos de RUC/DNI peruanos en el contacto, con una
arquitectura **config-driven**: las APIs se configuran como registros, no como
código. Agregar un proveedor nuevo es cuestión de crear una conexión y su mapeo
de campos.

## Arquitectura

```
res.company
  └─ l10n_pe_api_connection_ids  (One2many)
       l10n_pe.api.connection            ← una por API, con prioridad
         ├─ cómo llamar: base_url, endpoint_{ruc,dni}, auth, token
         ├─ cómo leer:   success_path, data_root
         ├─ ubigeo:       ubigeo/district/province/department paths
         └─ mapping_ids  (One2many)
              l10n_pe.api.field.mapping   ← atributo API → campo Odoo
                source_path → field_id (+ transform, for_document)
```

**Motor unificado** (`l10n_pe.api.connection.run`): normaliza *cualquier*
respuesta a un `dict` — sea JSON de una API REST o el resultado de un scraper de
SUNAT (vía `dataclasses.asdict`) — y le aplica el mismo mapeo genérico. Así el
scraping y las APIs REST comparten el mismo mecanismo de mapeo.

### Mapeo dinámico

Cada fila de `l10n_pe.api.field.mapping` indica:

- **`source_path`**: ruta en la respuesta, con puntos e índices de lista
  (`data.direccion`, `ubigeo.2`), o **plantilla** con marcadores para
  concatenar (`{nombres} {apellido_paterno} {apellido_materno}`).
- **`field_id`**: campo de `res.partner` destino (`ir.model.fields`, genérico —
  cualquier campo char/text/boolean/selection, incluso de otros módulos).
- **`transform`**: mayúsculas / minúsculas / título / capitalizar / quitar
  espacios.
- **`for_document`**: si aplica a RUC, DNI o ambos.

### Prioridad y fallback

Las conexiones se ordenan por `sequence`. La consulta usa la primera conexión
activa que responda; si falla (HTTP, sin datos), pasa a la siguiente. Si todas
fallan, marca `alert_warning_vat` para que el usuario complete manualmente.

## Uso

1. **Configuración**: *Contactos ▸ Configuración ▸ Conexiones RUC/DNI* (o la
   pestaña "Validación RUC/DNI (PE)" en la compañía). Se siembran por defecto
   `SUNAT (oficial)`, `apiperu.dev`, `json.pe`, `apis.net.pe` y `Decolecta`;
   edita URL/token/mapeo o agrega nuevas.
2. **Activar validación** en la compañía (`Validación de RUC` / `de DNI`).
3. Al escribir un RUC/DNI en un contacto (o con el botón *Actualizar RUC/DNI*),
   el sistema consulta las conexiones y autocompleta los campos según el mapeo.

### Decolecta

Consulta el RUC contra SUNAT (`/v1/sunat/ruc`) y el DNI contra RENIEC
(`/v1/reniec/dni`), con autenticación Bearer. Su respuesta es plana —sin
envoltorio de datos ni indicador de éxito— y devuelve el nombre de la persona
partido en `first_name`, `first_last_name` y `second_last_name`, que el mapeo
recompone con los apellidos delante, como los ordena SUNAT.

El **mismo token** lo reutiliza `al_l10n_pe_currency` para traer el tipo de
cambio de compra y venta: se configura una sola vez aquí.

## Agregar una API nueva (sin código)

1. Crear un registro en *Conexiones RUC/DNI*: engine REST/JSON, URL base,
   endpoint (`/ruc/{doc}`), autenticación y token.
2. Indicar `data_root` / `success_path` según la forma de la respuesta.
3. Añadir filas de mapeo: por cada dato que devuelve la API, la ruta y el campo
   de Odoo destino.
4. Ajustar la `sequence` para su prioridad. Listo — sin tocar Python.

**APIs que reciben el número en el body (POST)**: si la API es POST y espera el
documento en el cuerpo JSON (como `json.pe`, con `{"ruc": "..."}`), poner
`http_method = POST` y una plantilla en `body_ruc` / `body_dni`, p. ej.
`{"ruc": "{doc}"}`. El endpoint queda fijo (`/ruc`) y el número va en el body.

## Scrapers SUNAT

Los proveedores `SUNAT (oficial)` y `SUNAT multi` hacen scraping HTML (no
devuelven JSON). Se modelan como un `engine` especial: obtienen los datos con su
parser incorporado y luego pasan por el **mismo** mapeo (las claves del
resultado —`name`, `address`, `condition`, `ubigeo`…— son las rutas del mapeo).

## Padrón SUNAT

Buenos contribuyentes y agentes de retención se verifican contra el padrón
cacheado en BD (`l10n_pe.sunat.padron`), sincronizado a diario vía `ir.cron` —
no se descargan los ZIP de SUNAT en cada consulta.

## Servicios (`services/`)

Lógica pura sin ORM, testeable de forma aislada:

- `engine.py` — extracción por ruta, plantillas, transformaciones.
- `http.py` — HTTP con timeouts y reintentos.
- `sunat_oficial.py` — scrapers del portal SUNAT.
- `results.py` — dataclasses de resultado de los scrapers.
- `sunat_padron.py` — sincronización y consulta del padrón.
- `ubigeo.py` — resolución de ubigeo → distrito/ciudad/departamento.

## Migración desde 19.0.1.0.0

La versión previa usaba proveedores hardcodeados + tokens en
`ir.config_parameter`. La migración `19.0.2.0.0/post-migrate.py` siembra las
conexiones por defecto y transfiere los tokens antiguos a las conexiones
`apiperu.dev` / `apis.net.pe` correspondientes.
