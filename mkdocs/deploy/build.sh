#!/usr/bin/env bash
# Construye la documentación de ol_new_apps desde origin/<rama> y la publica
# en www/<versión>/ (estructura de mike: versions.json y alias «latest»).
#   ./build.sh            → rama 19.0, versión 19.0 y alias latest
#   ./build.sh 20.0       → rama 20.0, versión 20.0 y alias latest
#   ./build.sh 19.0 nolatest → reconstruye 19.0 sin moverle el alias
#   ./build.sh --if-changed [versión] [latest|nolatest]
#                         → solo si origin/<versión> tiene un commit nuevo
#                           (lo usa cron cada 5 minutos: /etc/cron.d/ol-docs)
# No toca el árbol de addons que usan los contenedores de Odoo: exporta el
# commit con git archive a un directorio temporal.
set -euo pipefail
umask 022   # el nginx del contenedor (usuario nginx) debe poder leer www/
cd "$(dirname "$0")"
IF_CHANGED=0
if [ "${1:-}" = --if-changed ]; then IF_CHANGED=1; shift; fi
VERSION="${1:-19.0}"
LATEST="${2:-latest}"
# Una sola construcción a la vez (cron y manual).
exec 9>.build.lock
if ! flock -n 9; then
  [ "$IF_CHANGED" = 1 ] && exit 0
  echo "Otra construcción en curso; esperando…"; flock 9
fi
REPO=/opt/odoo-infra/shared-addons/19/ol_new_apps
SITE_URL=https://docs.altalatam.com/

git -C "$REPO" fetch -q origin "$VERSION"
COMMIT=$(git -C "$REPO" rev-parse FETCH_HEAD)
if [ "$IF_CHANGED" = 1 ] && [ "$(cat "www/${VERSION}/.commit" 2>/dev/null)" = "$COMMIT" ]; then
  exit 0
fi
echo "$(date '+%F %T') construyendo ${VERSION} (${COMMIT:0:7})"
SRC=$(mktemp -d /tmp/ol-docs-src.XXXXXX)
trap 'rm -rf "$SRC"' EXIT
git -C "$REPO" archive "$COMMIT" | tar -x -C "$SRC"

cp "$SRC/mkdocs/requirements.txt" requirements.txt
docker build -q -t ol-docs-builder . >/dev/null

mkdir -p www
OUT="www/.${VERSION}.new"
rm -rf "$OUT"
docker run --rm \
  -v "$SRC":/src:ro -v "$PWD/www":/www \
  -e DOCS_SITE_URL="$SITE_URL" -e ODOO_VERSION="$VERSION" \
  -e DOCS_EDIT_URI="edit/${VERSION}/" -e DOCS_BRANCH="$VERSION" \
  -e DOCS_LOGOUT_URL=/_login/logout \
  ol-docs-builder mkdocs build --strict -q -f /src/mkdocs/mkdocs.yml -d "/www/.${VERSION}.new"

# Cambio atómico de la versión publicada.
rm -rf "www/.${VERSION}.old"
[ -d "www/${VERSION}" ] && mv "www/${VERSION}" "www/.${VERSION}.old"
mv "$OUT" "www/${VERSION}"
rm -rf "www/.${VERSION}.old"
echo "$COMMIT" > "www/${VERSION}/.commit"

if [ "$LATEST" = latest ]; then
  ln -sfn "$VERSION" www/latest
fi
# versions.json como lo escribe mike: la más nueva primero y el alias en la
# versión a la que apunta latest.
python3 - "$PWD/www" <<'PY'
import json, os, sys
www = sys.argv[1]
latest = os.path.realpath(os.path.join(www, 'latest'))
versions = sorted((d for d in os.listdir(www)
                   if not d.startswith('.') and d != 'latest'
                   and os.path.isdir(os.path.join(www, d))),
                  key=lambda v: [int(p) if p.isdigit() else p for p in v.split('.')], reverse=True)
data = [{'version': v, 'title': v,
         'aliases': ['latest'] if os.path.join(www, v) == latest else []} for v in versions]
with open(os.path.join(www, 'versions.json'), 'w') as f:
    json.dump(data, f)
print('versions.json:', data)
PY
echo "$(date '+%F %T') publicada ${VERSION} (${COMMIT:0:7}) en ${SITE_URL}${VERSION}/"
