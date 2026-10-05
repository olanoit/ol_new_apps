Servidor MCP para Odoo — Guía técnica
=====================================

.. contents:: Tabla de contenidos
   :depth: 3
   :local:

Descripción general
-------------------

Servidor MCP para Odoo expone tu instancia de Odoo 19 como un servidor
`Model Context Protocol (MCP) <https://modelcontextprotocol.io>`_.
Los clientes de IA — Claude, ChatGPT, Gemini, Cursor, n8n, LangChain, crewAI — se conectan
a datos en vivo de Odoo a través de un único endpoint HTTP con autenticación OAuth 2.0 o
token Bearer.

- **Protocolo:** MCP 2025-03-26 (Streamable HTTP) + SSE heredado
- **Autenticación:** OAuth 2.0 Código de autorización + PKCE S256, tokens Bearer PAT
- **Herramientas:** 34+ herramientas MCP (CRUD, analítica, BI, páginas de portal, trabajos asíncronos, generador de módulos)
- **Versión de Odoo:** 19.0 (Community y Enterprise)
- **Licencia:** OPL-1

Requisitos
----------

Requisitos del sistema
~~~~~~~~~~~~~~~~~~~~~~

- Odoo 19.0 (Community o Enterprise)
- Python 3.11+
- PostgreSQL 15+
- Odoo debe ser accesible por HTTPS en producción (obligatorio para las redirecciones de OAuth 2.0)

Paquetes de Python opcionales
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Estos se instalan por separado si quieres las funciones opcionales:

.. code-block:: bash

   # Para el límite de tasa distribuido con Redis
   pip install redis

   # Para la exportación XLSX (herramienta odoo_export_xlsx)
   pip install xlsxwriter

Ambos paquetes degradan de forma controlada si no están instalados:
``redis`` → limitador de tasa en memoria, ``xlsxwriter`` → respuesta de error solo para XLSX.

Dependencias del módulo Odoo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- ``base``
- ``web``
- ``mail``

No se requiere ningún módulo exclusivo de Enterprise.

Instalación
-----------

Instalar desde la tienda de Apps de Odoo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Inicia sesión en tu instancia de Odoo como Administrador.
2. Ve a **Aplicaciones** → busca **MCP Server**.
3. Haz clic en **Instalar**.
4. El módulo se instala automáticamente con todas sus dependencias.

Instalar desde el código fuente
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Clona o copia el módulo en tu ruta de addons
   cp -r al_mcp_server /path/to/your/addons/

   # Reinicia Odoo
   ./odoo-bin -c odoo.conf --stop-after-init

   # Instala el módulo
   ./odoo-bin -c odoo.conf -d your_db -i al_mcp_server --stop-after-init

Actualizar
~~~~~~~~~~

.. code-block:: bash

   ./odoo-bin -c odoo.conf -d your_db -u al_mcp_server --stop-after-init

Configuración
-------------

Accede a la configuración del Servidor MCP en **Ajustes → MCP Server** (sección Técnico).

Configuración general
~~~~~~~~~~~~~~~~~~~~~

+--------------------------------------+-------------------+---------------------------------------------------------------------+
| Parámetro                            | Valor por defecto | Descripción                                                         |
+======================================+===================+=====================================================================+
| Retención de sesiones (días)         | 90                | Purga automática de sesiones con más de N días                      |
+--------------------------------------+-------------------+---------------------------------------------------------------------+
| Retención de registros (días)        | 30                | Purga automática de entradas del registro de auditoría con más de N |
+--------------------------------------+-------------------+---------------------------------------------------------------------+
| Límite de tasa por minuto            | 60                | Máximo de solicitudes por token por ventana deslizante              |
+--------------------------------------+-------------------+---------------------------------------------------------------------+
| Ventana de límite de tasa (segundos) | 60                | Duración de la ventana deslizante                                   |
+--------------------------------------+-------------------+---------------------------------------------------------------------+

Límite de tasa con Redis (opcional)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Para despliegues con múltiples workers o instancias, activa Redis para que el límite de tasa
se comparta entre todos los workers:

1. Marca **Activar límite de tasa con Redis**.
2. Introduce tu URL de Redis, p. ej. ``redis://localhost:6379/0`` o
   ``redis://:password@redis-host:6379/0``.
3. Haz clic en **Probar conexión con Redis** para verificar.

Si Redis no está accesible en tiempo de ejecución, el servidor recurre automáticamente al límite
de tasa en memoria — sin tiempo de inactividad.

Caché de esquema
~~~~~~~~~~~~~~~~

La caché de esquema almacena en memoria los resultados de ``fields_get``, ``get_models`` y
``get_views`` (LRU, 1000 entradas).

1. Marca **Activar caché de esquema**.
2. Establece el **TTL de la caché (segundos)** (por defecto: 3600).
3. Haz clic en **Limpiar caché de esquema** tras instalar módulos nuevos o cambiar
   definiciones de campos.

La caché se invalida automáticamente cuando cambian registros de ``ir.model`` o
``ir.model.fields``.

Generador de módulos (indicador de función)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

El generador de módulos con IA está desactivado por defecto. Para activarlo:

1. Marca **Activar generador de módulos**.
2. Establece la **Ruta de módulos generados** — una ruta absoluta a una carpeta de addons con
   permiso de escritura (p. ej. ``/opt/odoo/custom_addons``). El generador se niega a escribir en
   directorios ``community/`` o ``enterprise/``.
3. Reinicia Odoo tras cambiar la ruta de addons para que la nueva carpeta quede en el alcance.

Endpoints
---------

Endpoints MCP
~~~~~~~~~~~~~

+------------------------+---------------------------------------------+
| Endpoint               | Descripción                                 |
+========================+=============================================+
| ``POST /mcp``          | Transporte Streamable HTTP (MCP 2025-03-26) |
+------------------------+---------------------------------------------+
| ``POST /mcp/sse``      | Alias de Streamable HTTP (retrocompatible)  |
+------------------------+---------------------------------------------+
| ``GET  /mcp/sse``      | Transporte SSE — flujo de eventos           |
+------------------------+---------------------------------------------+
| ``POST /mcp/messages`` | Transporte SSE — endpoint de mensajes       |
+------------------------+---------------------------------------------+

Endpoints OAuth 2.0
~~~~~~~~~~~~~~~~~~~

+--------------------------------------------------+------------------------------------------+
| Endpoint                                         | Descripción                              |
+==================================================+==========================================+
| ``GET  /.well-known/oauth-authorization-server`` | Metadatos de autodescubrimiento          |
+--------------------------------------------------+------------------------------------------+
| ``POST /oauth/register``                         | Registro dinámico de clientes (RFC 7591) |
+--------------------------------------------------+------------------------------------------+
| ``GET  /oauth/authorize``                        | Inicio del Código de autorización        |
+--------------------------------------------------+------------------------------------------+
| ``POST /oauth/token``                            | Intercambio y refresco de tokens         |
+--------------------------------------------------+------------------------------------------+
| ``POST /oauth/revoke``                           | Revocación de tokens (RFC 7009)          |
+--------------------------------------------------+------------------------------------------+

Endpoints del portal
~~~~~~~~~~~~~~~~~~~~

+--------------------------------+---------------------------------------------+
| Endpoint                       | Descripción                                 |
+================================+=============================================+
| ``GET /mcp-page/<slug>``       | Página de portal pública (HTML)             |
+--------------------------------+---------------------------------------------+
| ``GET /mcp-page/<slug>/data``  | Datos de la página de portal (JSON)         |
+--------------------------------+---------------------------------------------+
| ``GET /mcp-page/<slug>/embed`` | Página incrustable (requiere token firmado) |
+--------------------------------+---------------------------------------------+

Autenticación
-------------

Token de Acceso Personal (PAT)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Los PAT son el método de autenticación más simple para herramientas de CLI, scripts e
integraciones servidor a servidor.

**Generar un PAT:**

1. Ve a **MCP Server → Tokens**.
2. Haz clic en **Generar PAT**.
3. Copia el token del diálogo — se muestra **solo una vez**.
4. Guárdalo de forma segura (gestor de contraseñas, secretos de CI/CD).

**Propiedades del token:**

- Se almacena con hash SHA-256 en reposo; el token en texto plano nunca se guarda
- Válido 30 días por defecto
- Sin token de refresco; genera uno nuevo cuando caduque
- Se puede revocar en cualquier momento desde la lista de Tokens

**Uso de un PAT en las solicitudes:**

.. code-block:: http

   POST /mcp HTTP/1.1
   Host: your-odoo.com
   Authorization: Bearer <your-PAT>
   Content-Type: application/json

OAuth 2.0 Código de autorización + PKCE
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

OAuth 2.0 lo usan los clientes con interfaz gráfica (Claude Web, Claude Desktop, Cursor) que
muestran una ventana de inicio de sesión en el navegador. No requiere que los usuarios generen
tokens manualmente.

**Flujo:**

.. code-block:: text

   1. Cliente → GET /.well-known/oauth-authorization-server → descubre endpoints
   2. Cliente → POST /oauth/register → obtiene client_id (registro dinámico)
   3. Usuario → navegador → GET /oauth/authorize?code_challenge=S256&...
   4. Odoo    → el usuario inicia sesión → redirige con authorization_code
   5. Cliente → POST /oauth/token (code + verificador PKCE) → access_token + refresh_token
   6. Cliente → POST /mcp con access_token Bearer

**Duración de los tokens:**

- Token de acceso: 30 días
- Token de refresco: 90 días (renueva el token de acceso de forma transparente)

Gobernanza de tokens
~~~~~~~~~~~~~~~~~~~~

Cada token admite restricciones granulares, configurables en
**MCP Server → Tokens → [token]**:

+-----------------------------+-----------------------------------------------------------------------------------------+
| Ajuste                      | Efecto                                                                                  |
+=============================+=========================================================================================+
| Alcance                     | ``read`` — solo herramientas de solo lectura                                            |
|                             | ``write`` — lectura + escritura (por defecto)                                           |
|                             | ``admin`` — todas las herramientas, incluido el generador de módulos                    |
+-----------------------------+-----------------------------------------------------------------------------------------+
| Lista de modelos permitidos | El token solo puede acceder a los modelos listados                                      |
+-----------------------------+-----------------------------------------------------------------------------------------+
| Lista de modelos denegados  | El token no puede acceder a los modelos listados                                        |
+-----------------------------+-----------------------------------------------------------------------------------------+
| Lista de campos permitidos  | Restricciones de campos por modelo en JSON                                              |
+-----------------------------+-----------------------------------------------------------------------------------------+
| Lista de IP permitidas      | Rangos CIDR desde los que el token es válido                                            |
+-----------------------------+-----------------------------------------------------------------------------------------+
| Lista de IP denegadas       | Rangos CIDR desde los que el token está bloqueado                                       |
+-----------------------------+-----------------------------------------------------------------------------------------+
| Capturar cargas útiles      | Almacena la solicitud/respuesta completa en el registro de auditoría (con PII ocultada) |
+-----------------------------+-----------------------------------------------------------------------------------------+

Conexión de clientes de IA
--------------------------

Claude CLI / Claude Code
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   claude mcp add odoo --transport http https://your-odoo.com/mcp \
     --header "Authorization: Bearer <your-PAT>"

O mediante ``~/.claude.json``:

.. code-block:: json

   {
     "mcpServers": {
       "odoo": {
         "type": "http",
         "url": "https://your-odoo.com/mcp",
         "headers": { "Authorization": "Bearer <your-PAT>" }
       }
     }
   }

Claude Desktop
~~~~~~~~~~~~~~

Edita ``claude_desktop_config.json``
(``~/Library/Application Support/Claude/`` en macOS,
``%APPDATA%\Claude\`` en Windows):

.. code-block:: json

   {
     "mcpServers": {
       "odoo": {
         "type": "http",
         "url": "https://your-odoo.com/mcp",
         "headers": { "Authorization": "Bearer <your-PAT>" }
       }
     }
   }

Claude Web (OAuth 2.0)
~~~~~~~~~~~~~~~~~~~~~~

1. Abre `claude.ai <https://claude.ai>`_ → **Settings → Integrations → Add MCP Server**.
2. Introduce: ``https://your-odoo.com/mcp``
3. Haz clic en **Connect** — Claude Web abre una ventana del navegador para iniciar sesión en Odoo.
4. Autoriza la conexión. Claude Web gestiona el almacenamiento y la renovación del token.

Extensión de VSCode
~~~~~~~~~~~~~~~~~~~

Añade a ``settings.json``:

.. code-block:: json

   {
     "claude.mcpServers": {
       "odoo": {
         "type": "http",
         "url": "https://your-odoo.com/mcp",
         "headers": { "Authorization": "Bearer <your-PAT>" }
       }
     }
   }

Cursor
~~~~~~

Ve a **Cursor Settings → MCP → Add Server**:

.. code-block:: json

   {
     "mcpServers": {
       "odoo": {
         "type": "http",
         "url": "https://your-odoo.com/mcp",
         "headers": { "Authorization": "Bearer <your-PAT>" }
       }
     }
   }

ChatGPT (conector)
~~~~~~~~~~~~~~~~~~

1. Ve a **ChatGPT Settings → Connectors → Add MCP Server**.
2. Introduce la URL MCP de tu Odoo: ``https://your-odoo.com/mcp``.
3. Introduce tu token Bearer (PAT o token de acceso OAuth).
4. ChatGPT descubre automáticamente todas las herramientas mediante ``tools/list``.

Grok
~~~~

1. Ve a **Grok Settings → Tools → Add MCP Server**.
2. Introduce la URL: ``https://your-odoo.com/mcp``.
3. Introduce tu token Bearer.
4. Confirma la conexión — Grok lista todas las herramientas de Odoo disponibles.

Continue.dev
~~~~~~~~~~~~

Edita ``~/.continue/config.json``:

.. code-block:: json

   {
     "experimental": {
       "modelContextProtocolServers": [
         {
           "transport": {
             "type": "sse",
             "url": "https://your-odoo.com/mcp/sse",
             "requestOptions": {
               "headers": { "Authorization": "Bearer <your-PAT>" }
             }
           }
         }
       ]
     }
   }

Vercel AI SDK (TypeScript)
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: typescript

   import { experimental_createMCPClient as createMCPClient } from 'ai';

   const mcpClient = await createMCPClient({
     transport: {
       type: 'http',
       url: 'https://your-odoo.com/mcp',
       headers: { Authorization: 'Bearer <your-PAT>' },
     },
   });
   const tools = await mcpClient.tools();

Clientes solo stdio (Jan, Msty) mediante mcp-remote
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Los clientes que solo admiten stdio necesitan el puente ``mcp-remote``:

.. code-block:: bash

   npm install -g mcp-remote

Luego configura:

.. code-block:: json

   {
     "mcpServers": {
       "odoo": {
         "command": "npx",
         "args": [
           "mcp-remote",
           "https://your-odoo.com/mcp/sse",
           "--header",
           "Authorization: Bearer <your-PAT>"
         ]
       }
     }
   }

Despliegue en producción
------------------------

Proxy inverso Nginx
~~~~~~~~~~~~~~~~~~~

El Servidor MCP usa streaming HTTP (SSE / transferencia por fragmentos) y requiere cabeceras CORS
para que los clientes de IA basados en navegador (Claude Web, ChatGPT, etc.) puedan conectarse. La
configuración siguiente es la referencia probada en producción.

.. code-block:: nginx

   # Upstream — ajusta host/puerto para que coincidan con tu instancia de Odoo
   upstream odoo_mcp {
       server 127.0.0.1:8069;
       keepalive 32;
   }

   # Restringe CORS a los orígenes conocidos de clientes de IA.
   # Añade más orígenes con entradas de map adicionales según sea necesario.
   map $http_origin $cors_origin {
       default                      "";
       "https://claude.ai"          $http_origin;
       "https://chatgpt.com"        $http_origin;
       "https://app.grok.com"       $http_origin;
   }

   server {
       listen 443 ssl http2;
       server_name your-odoo.com;

       ssl_certificate     /etc/ssl/your-odoo.com/fullchain.pem;
       ssl_certificate_key /etc/ssl/your-odoo.com/privkey.pem;

       # ── Endpoints MCP (SSE + Streamable HTTP) ────────────────────────────
       location ~ ^/mcp {
           # Preflight OPTIONS — responder directamente desde nginx
           if ($request_method = OPTIONS) {
               add_header Access-Control-Allow-Origin  $cors_origin always;
               add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
               add_header Access-Control-Allow-Headers "Content-Type, Authorization, Mcp-Session-Id, Last-Event-ID" always;
               add_header Access-Control-Max-Age       86400 always;
               return 204;
           }

           proxy_pass http://odoo_mcp;
           proxy_http_version 1.1;
           proxy_set_header Connection        "";
           proxy_set_header Host              $host;
           proxy_set_header X-Real-IP         $remote_addr;
           proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;

           # SSE — hay que desactivar el buffering para que funcione el streaming
           proxy_buffering    off;
           proxy_cache        off;
           proxy_read_timeout 3600s;
           proxy_send_timeout 3600s;
           add_header X-Accel-Buffering no always;

           # Cabeceras de respuesta CORS
           add_header Access-Control-Allow-Origin  $cors_origin always;
           add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
           add_header Access-Control-Allow-Headers "Content-Type, Authorization, Mcp-Session-Id, Last-Event-ID" always;
       }

       # ── Endpoints OAuth 2.0 + Well-Known de descubrimiento ────────────────
       location ~ ^/(oauth|\.well-known)/ {
           # Preflight OPTIONS — necesario para POST /oauth/register desde clientes de navegador
           if ($request_method = OPTIONS) {
               add_header Access-Control-Allow-Origin  $cors_origin always;
               add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
               add_header Access-Control-Allow-Headers "Content-Type, Authorization" always;
               add_header Access-Control-Max-Age       86400 always;
               return 204;
           }

           proxy_pass http://odoo_mcp;
           proxy_http_version 1.1;
           proxy_set_header Connection        "";
           proxy_set_header Host              $host;
           proxy_set_header X-Real-IP         $remote_addr;
           proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;

           # CORS — necesario para que los clientes de IA en navegador puedan leer la respuesta
           add_header Access-Control-Allow-Origin  $cors_origin always;
           add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
           add_header Access-Control-Allow-Headers "Content-Type, Authorization" always;
       }

       # ── Aplicación principal de Odoo ──────────────────────────────────────
       location / {
           proxy_pass http://odoo_mcp;
           proxy_http_version 1.1;
           proxy_set_header Connection        "";
           proxy_set_header Host              $host;
           proxy_set_header X-Real-IP         $remote_addr;
           proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           proxy_redirect off;
       }

       gzip on;
       gzip_vary on;
       gzip_types text/css text/javascript application/json application/javascript text/plain text/xml;

       error_page 404 /404.html;
       error_page 500 502 503 504 /50x.html;
   }

.. note::

   **¿Por qué ``proxy_read_timeout 3600s``?**
   Las conexiones SSE son de larga duración. Claude Desktop y otros clientes MCP mantienen un
   flujo de eventos persistente abierto durante toda la sesión. Un timeout corto
   (p. ej. 300s) hace que el cliente se desconecte y reconecte repetidamente.

.. note::

   **¿Por qué separar las ubicaciones ``/mcp`` y ``/(oauth|.well-known)/``?**
   La ubicación ``/mcp`` necesita ``Mcp-Session-Id`` y ``Last-Event-ID`` en
   ``Access-Control-Allow-Headers``. Mantener OAuth/descubrimiento en su propio bloque
   conserva mínimo el conjunto de cabeceras CORS y evita filtrar cabeceras internas.

Configuración multi-worker
~~~~~~~~~~~~~~~~~~~~~~~~~~

El Servidor MCP es sin estado por diseño — no requiere sesiones persistentes (sticky sessions).

**Configuración de Odoo (``odoo.conf``):**

.. code-block:: ini

   [options]
   workers = 4
   limit_time_real = 120
   limit_time_cpu = 60

   # Para el límite de tasa distribuido y la caché de esquema
   # (añade primero redis-py a los requisitos)

**Redis para el límite de tasa distribuido:**

.. code-block:: ini

   # No hace falta cambiar odoo.conf — configúralo en Ajustes → MCP Server
   # Ejemplo de URL de Redis:
   # redis://localhost:6379/0
   # redis://:password@redis-cluster:6379/0

Consideraciones sobre Cloudflare / CDN
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Si Cloudflare (u otra CDN) está delante de Odoo:

1. **Desactiva** el buffering de respuesta en las rutas ``/mcp`` y ``/mcp/sse``.
   En Cloudflare, configura una **Cache Rule** con *Bypass Cache* para ``/mcp*``.
2. **Aumenta** el timeout de lectura a al menos 300s en la ruta
   (Cloudflare Pro+: añade una Page Rule con ``SSL = Full (Strict)``
   y ``Origin Response Timeout = 300``).
3. Para SSE en particular, asegúrate de que Cloudflare no elimine las cabeceras
   ``Transfer-Encoding: chunked`` — usa HTTP/2 entre Cloudflare y tu origen.

Trabajos programados
--------------------

Se instalan automáticamente dos trabajos cron:

+-------------------------------------+-----------------------+----------------------------------------------------------------+
| Trabajo                             | Intervalo por defecto | Acción                                                         |
+=====================================+=======================+================================================================+
| MCP Server: Purge expired sessions  | Diario                | Elimina sesiones con más antigüedad que el ajuste de retención |
+-------------------------------------+-----------------------+----------------------------------------------------------------+
| MCP Server: Process async job queue | Cada 5 minutos        | Ejecuta los registros ``mcp.job`` pendientes                   |
+-------------------------------------+-----------------------+----------------------------------------------------------------+

Configura los intervalos de cron en **Ajustes → Técnico → Acciones planificadas**.

Mantenimiento
-------------

Revocar tokens
~~~~~~~~~~~~~~

Ve a **MCP Server → Tokens**, abre el token y haz clic en **Revocar**. El token
se rechaza en la siguiente solicitud. Las sesiones activas que usen ese token no se
terminan de inmediato, pero todas las solicitudes posteriores fallan.

Limpiar registros de auditoría
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

La retención de sesiones y registros se aplica cada noche mediante el cron de purga. Para una
purga inmediata, ejecuta desde un shell de Odoo:

.. code-block:: python

   env['mcp.session'].sudo()._purge_expired()

Limpiar la caché de esquema
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tras instalar o actualizar módulos:

1. Ve a **Ajustes → MCP Server**.
2. Haz clic en **Limpiar caché de esquema**.

O desde un shell de Odoo:

.. code-block:: python

   from odoo.addons.al_mcp_server.services import schema_cache
   schema_cache.invalidate("")

Resolución de problemas
-----------------------

Restricciones de base de datos: ``models.Constraint``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

En Odoo 19 el atributo ``_sql_constraints`` quedó obsoleto y ya no es
compatible. El módulo define sus restricciones únicas con el patrón
``models.Constraint('SQL', 'mensaje')`` a nivel de modelo, tal como exige
Odoo 19.

Solución: usa la versión 19.0.3.0.0 del módulo o posterior.

La redirección OAuth falla (localhost o URL HTTP)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

La validación de redirección OAuth de Odoo requiere HTTPS en producción. Para desarrollo
local, añade a ``odoo.conf``:

.. code-block:: ini

   [options]
   proxy_mode = True

Y accede a Odoo a través de un proxy inverso que establezca ``X-Forwarded-Proto: https``,
o usa ``ngrok`` / ``localtunnel`` para un túnel HTTPS temporal.

Límite de tasa excedido (HTTP 429)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

El límite por defecto es de 60 solicitudes por cada 60 segundos por token. Auméntalo en
**Ajustes → MCP Server → Límite de tasa por minuto**, o configura Redis para
un estado compartido entre workers.

La conexión SSE se cae tras 60 segundos
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

El ``proxy_read_timeout`` de Nginx es demasiado corto. Establécelo en 300s en la ubicación
``/mcp/sse`` (ver la configuración de Nginx más arriba).

El cliente MCP informa "transport error"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Verifica la URL del endpoint: ``https://your-odoo.com/mcp`` (sin barra final).
2. Comprueba que la cabecera ``Authorization`` esté presente y que el token no haya caducado.
3. Para clientes SSE, usa ``/mcp/sse`` (no ``/mcp``).
4. Comprueba que Nginx no esté haciendo buffering de la respuesta (``proxy_buffering off``).

Extensión y desarrollo
----------------------

Añadir herramientas personalizadas
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Extiende el registro de herramientas heredando de ``mcp.tool.registry``:

.. code-block:: python

   from odoo import api, models

   class MyCustomTools(models.AbstractModel):
       _inherit = "mcp.tool.registry"

       @api.model
       def get_tools(self) -> list:
           base_tools = super().get_tools()
           return base_tools + [
               {
                   "name": "odoo_my_custom_tool",
                   "description": "My custom tool description",
                   "inputSchema": {
                       "type": "object",
                       "properties": {
                           "param": {"type": "string"}
                       },
                       "required": ["param"],
                   },
               }
           ]

Luego gestiona la ejecución sobrescribiendo ``tool_executor.execute_tool`` o añadiendo un
manejador en tu propio módulo.

Estructura del módulo
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   al_mcp_server/
   ├── __manifest__.py
   ├── controllers/
   │   ├── mcp_controller.py       # POST /mcp, GET/POST /mcp/sse
   │   ├── oauth_controller.py     # Endpoints OAuth 2.0
   │   └── portal_controller.py    # /mcp-page/<slug>
   ├── models/
   │   ├── mcp_session.py          # mcp.session — registro de auditoría
   │   ├── mcp_token.py            # mcp.token — tokens PAT + OAuth
   │   ├── mcp_job.py              # mcp.job — cola de trabajos asíncronos
   │   ├── mcp_portal_page.py      # mcp.portal.page — tableros compartibles
   │   ├── mcp_generated_module.py # mcp.generated.module — constructor de módulos con IA
   │   ├── mcp_tool_registry.py    # mcp.tool.registry — definiciones de herramientas
   │   └── res_config_settings.py  # Extensión de configuración
   └── services/
       ├── mcp_protocol.py         # Envoltorio JSON-RPC, tools/list, tools/call
       ├── tool_executor.py        # Despacho de herramientas + aplicación de alcance
       ├── schema_cache.py         # Caché de esquema LRU
       ├── rate_limiter.py         # Limitador de tasa en memoria
       ├── redis_rate_limiter.py   # Limitador de tasa Redis con ventana deslizante
       ├── redaction.py            # Ocultación de PII para la captura de cargas útiles
       ├── bi_tools.py             # Herramientas de informes BI (7 herramientas)
       ├── job_tools.py            # Herramientas de trabajos asíncronos (4 herramientas)
       ├── portal_tools.py         # Herramientas de páginas de portal (3 herramientas)
       ├── module_tools.py         # Herramientas del generador de módulos (4 herramientas)
       └── module_generator.py     # Constructor de ZIP + validador de especificaciones
