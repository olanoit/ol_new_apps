Historial de cambios — Servidor MCP para Odoo (AL)
==================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`). Este módulo no tiene ficha
en `docs/fichas/`: el historial se mantiene a mano y debe coincidir con el
de `static/description/index.html`.

## 5.20261005 — 05/10/2026

- Interfaz, comentarios, README y ficha completamente en español.
- Etiquetas heredadas de los mixins traducidas (`i18n/es.po`).
- Instalable en Odoo 19: búsquedas agrupadas sin `expand`, etiquetas de campo sin duplicados.
- El dueño de un token puede renombrarlo aunque no sea administrador.
- Las cabeceras de las tablas del portal usan la etiqueta del campo.

## 4.20260825 — 28/09/2026

- Los trabajos asíncronos se ejecutan como el usuario que los lanzó.
- Se aplican los alcances (scopes) y las restricciones del token.
- La gobernanza del token queda protegida.
- OAuth solo acepta la `redirect_uri` registrada.
- Escapado de HTML y XML en las respuestas.
- Reglas de acceso nuevas.

## 3.20260825 — 25/08/2026

- Incorporado a la suite (antes `lm_mcp_server`), con licencia OPL-1.
- OAuth 2.0 con PKCE y tokens de acceso personal.
- Transporte HTTP streamable y SSE.
- Herramientas CRUD y de BI, trabajos asíncronos, páginas de portal, artefactos HTML y generador de módulos.
