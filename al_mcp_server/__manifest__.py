# -*- coding: utf-8 -*-
# Parte de al_mcp_server. Ver LICENSE del repositorio para detalles.
{
    'name': 'Servidor MCP para Odoo (AL)',
    'version': '3.20260825',
    'summary': 'Servidor MCP, Integración con IA, Claude, ChatGPT, Gemini, Grok, Cursor, n8n, LangChain, OAuth 2.0, PKCE, Token Bearer, Token de Acceso Personal, API REST, HTTP Streamable, SSE, Trabajos Asíncronos, Cola en Segundo Plano, Reportes BI, Tabla Dinámica, Series de Tiempo, Análisis de Cohortes, Embudo, Top N, Exportar CSV, Exportar XLSX, Páginas de Portal, Tablero Público, Tarjetas KPI, Generador de Módulos, Generación de Código con IA, LLM, Automatización, Registro de Auditoría, Límite de Tasa, Redis, Caché de Esquema, Tokens con Alcance, Lista de Campos Permitidos, Lista de IP Permitidas, API de Odoo, Conector de Odoo, Asistente de IA, Chatbot, Lenguaje Natural, Actualización Masiva, Creación Masiva, Eliminación Masiva',
    'description': """
Servidor MCP Odoo
===================

Convierta Odoo en un servidor de herramientas listo para IA. Conecte Claude Desktop,
ChatGPT, Cursor, Gemini, n8n, LangChain y cualquier cliente compatible con MCP a
datos en vivo de Odoo, con gobernanza de nivel empresarial y rastro de auditoría.

Capacidades principales
-----------------------
* Flujo de Código de Autorización OAuth 2.0 con PKCE (S256), registro dinámico de clientes
* Tokens de Acceso Personal (PAT) — autoservicio
* Autenticación con token Bearer, hash SHA-256, caducidad de 30 días, rotación de token de refresco
* Transporte HTTP Streamable (MCP 2025-03-26) + transporte SSE heredado
* Autodescubrimiento vía /.well-known/oauth-authorization-server

Gobernanza y auditoría
----------------------
* Alcance por token: solo lectura, lectura+escritura o administrador
* Lista de modelos permitidos / denegados por token
* Lista de campos permitidos por token
* Lista de IP permitidas / denegadas por token (CIDR)
* Registro de auditoría con captura opcional de la carga útil (con datos personales ocultados)
* Retención configurable para sesiones y registros

Rendimiento
-----------
* Caché de esquema para fields_get / get_models / get_views (TTL configurable)
* Límite de tasa distribuido respaldado por Redis (con reserva en memoria)
* Expulsión LRU, invalidación automática al cambiar el esquema

Herramientas (24+)
------------------
* CRUD: get_models, fields_get, search_read, create, write, unlink, call_method
* Flujo de trabajo: message_post, default_get, onchange, get_views, print_report, create_attachment
* Analítica: count, name_search, read_group
* Reportes BI: pivot, time_series, top_n, cohort, funnel
* Exportaciones: export_csv, export_xlsx
* Trabajos asíncronos: submit_job, job_status, job_list, job_cancel
* Páginas de portal: create_portal_page, list_portal_pages, update_portal_page
* Constructor de módulos: generate_module, validate_module_spec, list_generated_modules, install_generated_module

Recursos
--------
* odoo://context — compañía, usuario, módulos, fecha del servidor
* odoo://catalog — todos los modelos instalados
* odoo://model/{name} — esquema completo de campos
* odoo://chatter/{model}/{id} — últimos 20 mensajes del chatter
* odoo://attachment/{id} — metadatos + vista previa

Páginas de portal
-----------------
Páginas públicas compartibles con tarjetas KPI, visualizaciones ECharts y tablas
respaldadas por datos en vivo de Odoo. Adaptables a móvil, incrustables.

Cola de trabajos asíncronos
---------------------------
Envíe operaciones pesadas (actualización masiva, exportaciones de más de 100k registros)
y consulte el estado. Un cron en segundo plano procesa los trabajos respetando el alcance
y las restricciones del token.

Generador de módulos
--------------------
La IA genera una especificación JSON → validar → ZIP → instalar. Desactivado por
bandera de función de forma predeterminada. Aislado a la ruta de addons configurada.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-TOOLS/Apps',
    'license': 'OPL-1',
    'depends': ['base', 'web', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/mcp_security.xml',
        'data/mcp_cron.xml',
        'views/mcp_session_views.xml',
        'views/mcp_token_views.xml',
        'views/mcp_job_views.xml',
        'views/mcp_portal_page_views.xml',
        'views/portal_templates.xml',
        'views/mcp_html_artifact_views.xml',
        'views/mcp_generated_module_views.xml',
        'views/res_users_views.xml',
        'views/res_config_settings_views.xml',
        'views/mcp_menus.xml',
    ],
    'external_dependencies': {
        'python': [],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/assets/banner.gif', 'static/description/assets/banner.png'],
    'price': 169.9,
    'currency': 'USD',
}
