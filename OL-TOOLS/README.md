OL-TOOLS
========

**Herramientas transversales.**

Para qué es esta carpeta
------------------------

Utilidades que usan varias áreas o que no son de negocio: información de módulos, servidor MCP para conectar asistentes de IA y licencia perpetua.

Qué va aquí
-----------

- Módulos técnicos reutilizables por otras áreas.
- Integraciones generales (servidor MCP) y utilidades de administración.

Qué no va aquí
--------------

- Módulos de terceros → `OL-THIRD-PARTY/`.
- Funcionalidad de negocio de un área concreta → su área.

Módulos disponibles
-------------------

Tabla generada desde los manifiestos con `python3 scripts/gen_addons_table.py`
(no editar a mano).

[//]: # (addons)
módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_base_module_info](al_base_module_info/) | 2.20261008 | OPL-1 | En Aplicaciones, el botón «Más información» de los módulos con ficha propia abre la ficha completa del módulo.
[al_docs_help](al_docs_help/) | 12.20261023 | OPL-1 | Botón «?» en cada pantalla y asistente de la suite que abre la página que la explica en el sitio de documentación.
[al_mcp_server](al_mcp_server/) | 9.20261013 | OPL-1 | Servidor MCP, Integración con IA, Claude, ChatGPT, Gemini, Grok, Cursor, n8n, LangChain, OAuth 2.0, PKCE, Token Bearer, Token de Acceso Personal, API REST, HTTP Streamable, SSE, Trabajos Asíncronos, Cola en Segundo Plano, Reportes BI, Tabla Dinámica, Series de Tiempo, Análisis de Cohortes, Embudo, Top N, Exportar CSV, Exportar XLSX, Páginas de Portal, Tablero Público, Tarjetas KPI, Generador de Módulos, Generación de Código con IA, LLM, Automatización, Registro de Auditoría, Límite de Tasa, Redis, Caché de Esquema, Tokens con Alcance, Lista de Campos Permitidos, Lista de IP Permitidas, API de Odoo, Conector de Odoo, Asistente de IA, Chatbot, Lenguaje Natural, Actualización Masiva, Creación Masiva, Eliminación Masiva
[al_report_base](al_report_base/) | 2.20261011 | OPL-1 | El formato del comprobante A4 para todos los documentos impresos de la suite: encabezado, pie, estilos y papel.
[ol_licencia_perpetua](ol_licencia_perpetua/) | 1.20260717 | OPL-1 | Override enterprise subscription for testing purposes
[//]: # (end addons)
