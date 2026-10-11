# Herramientas del repositorio

| Herramienta | Para qué |
|---|---|
| `scripts/gen_addons_table.py` | Regenera las tablas de módulos de los README desde los manifiestos. Con `--check` comprueba también categoría, licencia y `LICENSE`. |
| `scripts/addons_path.py` | Imprime las rutas de las áreas para el `addons_path`. |
| `scripts/gen_changelog.py` | Genera el `CHANGELOG.md` de cada módulo desde las `novedades` de su ficha. |
| `scripts/gen_docs_help.py` | Genera la ayuda contextual (botón **?**) desde las páginas de la documentación y los modelos de cada módulo. Con `--check` comprueba. |
| `scripts/areas.py` | Lista de áreas y excepciones de licencia. |
| `docs/fichas/generar_fichas.py` | Genera la ficha `static/description/index.html` de cada módulo desde `docs/fichas/<módulo>.yml`. |
| `docs/fichas/capturar.py` | Ayudante de Playwright para las capturas de las fichas y de la documentación. |
| `docs/validacion/fichas_modulos.py` | Valida las fichas. |
| `docs/validacion/generar_es_po.py` | Genera `i18n/es.po` de un módulo con modelos nuevos. |
| `docs/validacion/etiquetas_espanol.py` | Audita que las etiquetas de los módulos propios estén en español. |
| `docs/validacion/verificar_enlaces.py` | Verifica los enlaces externos de páginas Markdown. |
| `mkdocs/scripts/preparar_imagen.py` | Recorta, reduce a 933 px y comprime una captura para la documentación. |
| `mkdocs/scripts/gen_pages.py` | Genera la referencia de módulos, las especificaciones y las novedades de este sitio. |
