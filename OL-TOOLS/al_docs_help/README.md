# Ayuda contextual de la suite (AL)

Documentación funcional: [Ayuda contextual](../../mkdocs/content/applications/general/contextual_help.md)

Módulo `al_docs_help` para Odoo 19.

Botón **?** en la barra superior (pantallas) y en la cabecera de los
asistentes que abre la página de la documentación de la suite (MkDocs) que
explica esa pantalla, en su sección.

- Modelo `al.docs.help` (pantalla → ruta del sitio), generado por
  `scripts/gen_docs_help.py` en `data/al_docs_help_data.xml` desde el código
  de cada módulo y las páginas de `mkdocs/content/applications/` que lo
  declaran (`modulos:`); las pantallas oficiales ampliadas, en
  `docs/ayuda/ayuda_contextual.yml`.
- `get_help_map()`: el mapa para el cliente web, solo con los módulos
  instalados; la base es el parámetro `al_account_base.docs_url` o
  `https://docs.altalatam.com/latest/`.
- Cliente web: servicio `al_docs_help` (carga el mapa una vez), elemento de
  la barra superior que sigue la pantalla actual (`ACTION_MANAGER:UI-UPDATED`)
  y botón en `web.ActionDialog.header`.

Solo depende de `web`. Al cambiar páginas o modelos:
`python3 scripts/gen_docs_help.py` (con `--check` en la revisión).
