ol-tools
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

- Módulos de terceros → `ol-third-party/`.
- Funcionalidad de negocio de un área concreta → su área.

Módulos disponibles
-------------------

Tabla generada desde los manifiestos con `python3 scripts/gen_addons_table.py`
(no editar a mano).

[//]: # (addons)
módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_base_module_info](al_base_module_info/) | 1.20260914 | OPL-1 | En Aplicaciones, el botón «Más información» de los módulos con ficha propia abre la ficha completa del módulo.
[al_mcp_server](al_mcp_server/) | 5.20261005 | OPL-1 | Servidor MCP, Integración con IA, Claude, ChatGPT, Gemini, Grok, Cursor, n8n, LangChain, OAuth 2.0, PKCE, Token Bearer, Token de Acceso Personal, API REST, HTTP Streamable, SSE, Trabajos Asíncronos, Cola en Segundo Plano, Reportes BI, Tabla Dinámica, Series de Tiempo, Análisis de Cohortes, Embudo, Top N, Exportar CSV, Exportar XLSX, Páginas de Portal, Tablero Público, Tarjetas KPI, Generador de Módulos, Generación de Código con IA, LLM, Automatización, Registro de Auditoría, Límite de Tasa, Redis, Caché de Esquema, Tokens con Alcance, Lista de Campos Permitidos, Lista de IP Permitidas, API de Odoo, Conector de Odoo, Asistente de IA, Chatbot, Lenguaje Natural, Actualización Masiva, Creación Masiva, Eliminación Masiva
[ol_licencia_perpetua](ol_licencia_perpetua/) | 1.20260717 | OPL-1 | Override enterprise subscription for testing purposes
[//]: # (end addons)
