# Documentación de ol_new_apps — https://docs.altalatam.com

Sitio MkDocs (Material) de `mkdocs/` del repositorio ol_new_apps, servido con
autenticación básica.

| Pieza | Qué hace |
|---|---|
| `build.sh [versión] [latest\|nolatest]` | Exporta `origin/<versión>` con `git archive` (no toca el árbol de addons), construye con la imagen `ol-docs-builder` y publica en `www/<versión>/` con cambio atómico; mantiene `versions.json` y el enlace `latest` como mike. |
| `docker-compose.yml` | Contenedor `odoo_docs` (nginx) en la red `odoo_internal_net`, sin puertos publicados. |
| `nginx/default.conf` | Sitio estático, `/` → `/latest/`, caché de estáticos, 404 del sitio. |
| `nginx/htpasswd` | Usuarios de la autenticación básica (credenciales en `CREDENCIALES.txt`, solo root). |
| `/opt/odoo-infra/nginx/conf.d/docs-altalatam.conf` | vhost de docs.altalatam.com en el nginx principal: TLS (Let's Encrypt, renovado por odoo_certbot) y proxy a `odoo_docs`. |

Copia versionada de lo instalado en `/opt/odoo-infra/docs-site/` del servidor
io-altaexperts (`nginx/docs-altalatam.conf` va en `/opt/odoo-infra/nginx/conf.d/`).
`nginx/htpasswd` y `CREDENCIALES.txt` solo existen en el servidor.

## Instalación desde cero

1. DNS: `docs.altalatam.com` apuntando al servidor.
2. Copiar esta carpeta a `/opt/odoo-infra/docs-site/` y crear el usuario
   (ver «Agregar o cambiar un usuario»).
3. `./build.sh && docker compose up -d`.
4. vhost solo con el bloque del puerto 80, `nginx -s reload`, certificado con
   `docker compose run --rm -T --entrypoint certbot certbot certonly --webroot
   --webroot-path=/var/www/certbot -d docs.altalatam.com` (desde
   `/opt/odoo-infra`), luego el vhost completo y `nginx -s reload`. La
   renovación la hace el contenedor `odoo_certbot`.
5. En Odoo: Ajustes ▸ Perú ▸ Documentación → `https://docs.altalatam.com/latest/`.

**Cuidado con el `umask`:** `build.sh` hace `git fetch` en el clon de addons
que copian los contenedores de Odoo al arrancar; objetos de `.git` sin lectura
para otros hacen que Odoo no arranque (`cp: cannot open … Permission denied`).
Por eso el script fija `umask 022`.

## Operación

```bash
cd /opt/odoo-infra/docs-site
./build.sh                    # reconstruye 19.0 tras un push
./build.sh 20.0               # primera publicación de la 20.0 (pasa a ser latest)
./build.sh 19.0 nolatest      # actualiza la 19.0 sin quitarle latest a la 20.0
docker compose up -d          # levantar o recrear el contenedor

# Agregar o cambiar un usuario (pide la contraseña):
printf 'usuario:%s\n' "$(openssl passwd -apr1)" >> nginx/htpasswd
docker compose restart docs
```
