# Publicar la documentación

## Ver el sitio en local

```bash
cd /home/och/odoo/ce19/myodoo/ol_new_apps
export NO_MKDOCS_2_WARNING=1 DISABLE_MKDOCS_2_WARNING=true
/home/och/odoo/ce19/.venv/bin/mkdocs serve -f mkdocs/mkdocs.yml      # http://127.0.0.1:8000
/home/och/odoo/ce19/.venv/bin/mkdocs build --strict -f mkdocs/mkdocs.yml
```

`--strict` detiene la construcción ante un enlace roto o una página que no
está en el menú.

## Publicación

Con cada push a la rama de la versión (`19.0`), el servidor reconstruye el
sitio en unos minutos y lo publica en
[docs.altalatam.com](https://docs.altalatam.com). Cada versión de Odoo tiene su
rama y su carpeta en el sitio, con un selector para cambiar entre ellas.

!!! info "Ver también"
    - [Sitio de documentación](../../administration/documentation_site.md)
