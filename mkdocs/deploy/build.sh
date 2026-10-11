#!/usr/bin/env bash
# Construye la documentación de ol_new_apps desde origin/<rama> y la publica
# en www/<versión>/ (estructura de mike: versions.json y alias «latest»).
#   ./build.sh            → rama 19.0, versión 19.0 y alias latest
#   ./build.sh 20.0       → rama 20.0, versión 20.0 y alias latest
#   ./build.sh 19.0 nolatest → reconstruye 19.0 sin moverle el alias
# No toca el árbol de addons que usan los contenedores de Odoo: exporta el
# commit con git archive a un directorio temporal.
set -euo pipefail
umask 022   # el nginx del contenedor (usuario nginx) debe poder leer www/
cd "$(dirname "$0")"
VERSION="${1:-19.0}"
LATEST="${2:-latest}"
REPO=/opt/odoo-infra/shared-addons/19/ol_new_apps
SITE_URL=https://docs.altalatam.com/

git -C "$REPO" fetch -q origin "$VERSION"
COMMIT=$(git -C "$REPO" rev-parse FETCH_HEAD)
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
echo "Publicada ${VERSION} (${COMMIT:0:7}) en ${SITE_URL}${VERSION}/"
