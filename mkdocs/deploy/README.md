# Documentación de ol_new_apps — https://docs.altalatam.com

Sitio MkDocs (Material) de `mkdocs/` del repositorio ol_new_apps, con página
de inicio de sesión propia y reconstrucción automática tras cada push.

| Pieza | Qué hace |
|---|---|
| `build.sh [--if-changed] [versión] [latest\|nolatest]` | Exporta `origin/<versión>` con `git archive` (no toca el árbol de addons), construye con la imagen `ol-docs-builder` y publica en `www/<versión>/` con cambio atómico; mantiene `versions.json` y el enlace `latest` como mike. |
| `docker-compose.yml` | `odoo_docs` (nginx, sitio estático) y `odoo_docs_auth` (sesión), en la red `odoo_internal_net`, sin puertos publicados. |
| `nginx/default.conf` | `auth_request` en todo el sitio; sin sesión → `/_login/`; límite de 10 intentos por minuto e IP; `/` → `/latest/`; caché privada. |
| `auth/auth_server.py` | Página de inicio de sesión con la marca de la suite (claro/oscuro, móvil), contraseñas PBKDF2 en `auth/data/users.json`, cookie firmada (12 h o 30 días con «Mantener la sesión»), cambiar la contraseña cierra las sesiones, «Cerrar sesión» en la cabecera del sitio. Solo biblioteca estándar. |
| `ol-docs.cron` → `/etc/cron.d/ol-docs` | Cada 5 minutos `build.sh --if-changed`: reconstruye solo si `origin/19.0` tiene un commit nuevo (registro en `build.log`, rotado por `ol-docs.logrotate`). |
| `/opt/odoo-infra/nginx/conf.d/docs-altalatam.conf` | vhost de docs.altalatam.com en el nginx principal: TLS (Let's Encrypt, renovado por odoo_certbot) y proxy a `odoo_docs`. |

Copia versionada de lo instalado en `/opt/odoo-infra/docs-site/` del servidor
io-altaexperts (`nginx/docs-altalatam.conf` va en `/opt/odoo-infra/nginx/conf.d/`).
`auth/data/` (usuarios y clave de firma) y `CREDENCIALES.txt` solo existen en el servidor.

## Instalación desde cero

1. DNS: `docs.altalatam.com` apuntando al servidor.
2. Copiar esta carpeta a `/opt/odoo-infra/docs-site/`, instalar
   `ol-docs.cron` en `/etc/cron.d/ol-docs` y `ol-docs.logrotate` en
   `/etc/logrotate.d/ol-docs`, y crear el usuario (ver «Usuarios»).
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

tail -f build.log              # reconstrucciones automáticas
```

## Usuarios

```bash
cd /opt/odoo-infra/docs-site
docker compose exec docs_auth python3 /app/auth_server.py passwd <usuario>   # crea o cambia (pide la contraseña)
docker compose exec docs_auth python3 /app/auth_server.py deluser <usuario>
```

No hace falta reiniciar nada. Cambiar la contraseña de un usuario cierra sus
sesiones abiertas.
