# Sitio de documentación

Esta documentación se publica en [docs.altalatam.com](https://docs.altalatam.com),
con inicio de sesión. Se reconstruye sola después de cada cambio en la rama de la
versión.

## Configuración

La configuración está en `mkdocs/deploy/` del repositorio y se instala en
`/opt/odoo-infra/docs-site/` del servidor:

| Pieza | Qué hace |
|---|---|
| `odoo_docs` | nginx que sirve el sitio construido y exige sesión |
| `odoo_docs_auth` | Página de inicio de sesión y validación de la sesión |
| `build.sh` | Construye una versión desde la rama del repositorio y la publica |
| Tarea programada | Cada 5 minutos, `build.sh --if-changed`: solo reconstruye si hay un commit nuevo |

Los pasos para instalarlo desde cero están en `mkdocs/deploy/README.md`.

## Dar acceso

En el servidor, desde `/opt/odoo-infra/docs-site`:

```bash
docker compose exec docs_auth python3 /app/auth_server.py passwd <usuario>    # crear o cambiar
docker compose exec docs_auth python3 /app/auth_server.py deluser <usuario>   # quitar
```

Cambiar la contraseña de un usuario cierra sus sesiones abiertas.

## Enlazar desde Odoo

1. Vaya a **Ajustes ‣ Perú ‣ Documentación**.
2. Escriba la dirección del sitio con su versión
   (`https://docs.altalatam.com/latest/`) y guarde.

Los accesos directos de esa sección y el botón **?** de las pantallas usan esa
dirección.

!!! info "Ver también"
    - [Versiones de la documentación](versions.md)
    - [Publicar la documentación](../contributing/documentation/publishing.md)
