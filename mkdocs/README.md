# Documentación de la suite (MkDocs + Material, modelo de Odoo)

Sitio con toda la documentación de `ol_new_apps`, organizado como la
[documentación de Odoo](https://www.odoo.com/documentation/19.0/es_419/)
([odoo/documentation](https://github.com/odoo/documentation)):

| Sección | Carpeta | Se escribe |
|---|---|---|
| Documentación para usuarios | `content/applications/` | A mano, por área de negocio y funcionalidad |
| Instalación y mantenimiento | `content/administration/` | A mano |
| Desarrollador | `content/developer/` | A mano; la referencia de módulos y las especificaciones se generan |
| Aportando | `content/contributing/` | A mano: organización, pautas de contenido y de Markdown, plantilla |

Las pautas para escribir una página están en
[`content/contributing/`](content/contributing/index.md).

## Estructura

```
mkdocs/
├── mkdocs.yml              configuración (tema, plugins, versión de Odoo)
├── requirements.txt        dependencias con versiones fijas
├── content/                el contenido (docs_dir), como content/ de Odoo
│   ├── SUMMARY.md          menú raíz; cada carpeta tiene el suyo (mkdocs-literate-nav)
│   ├── applications/       documentación para usuarios, por área
│   ├── administration/     instalación y mantenimiento
│   ├── developer/          desarrollador
│   ├── contributing/       pautas de la documentación
│   └── assets/             estilos y scripts propios
├── scripts/gen_pages.py    genera lo que sale del código (mkdocs-gen-files)
├── scripts/preparar_imagen.py  captura a 933 px con paleta, como pide Odoo
├── plantillas/             portada, versiones y etiquetas, con marcadores
├── overrides/              ajustes de plantilla de Material
├── deploy/                 publicación en docs.altalatam.com
└── site/                   salida de la construcción (no se versiona)
```

| Generado en el sitio | Origen |
|---|---|
| Portada, versiones, etiquetas | `plantillas/*.md` (`{{ odoo_version }}`, `{{ cifras }}`…) |
| Desarrollador ▸ Referencia de módulos | Por área: `OL-<ÁREA>/README.md` y los manifiestos. Por módulo: ficha desde `__manifest__.py` y `docs/fichas/<módulo>.yml`, `README.md`, `CHANGELOG.md`, `docs/**/*.md` y `readme/*.md` (OCA), con enlaces a las páginas que lo documentan |
| Desarrollador ▸ Especificaciones y diseño | `docs/<carpeta>/**/*.md` |
| Desarrollador ▸ Repositorio y áreas | `README.md` raíz |
| Novedades de la suite | Las `novedades` de todas las fichas, por fecha |

**Módulos y páginas.** Cada página de usuarios declara los módulos que
documenta en su encabezado (`modulos: [al_l10n_pe_detraction]`). Con eso, la
referencia del módulo enlaza a su página, el `README.md` del módulo también, y
`scripts/gen_docs_help.py` arma el botón **?** de Odoo (`al_docs_help`).

**Cómo se resuelven los enlaces:**
- En las páginas generadas, los enlaces entre archivos del repositorio se
  reescriben a la página del sitio que los contiene.
- En las páginas de `content/`, los enlaces a archivos del repositorio (por
  ejemplo los Excel de ejemplo) se copian a `_media/` o apuntan a GitHub.
- Un enlace a un archivo que no existe se avisa y, con `--strict`, detiene la
  construcción.

**Nuevos documentos:**
- Una página nueva va en la carpeta de su área, con su línea en el `SUMMARY.md`
  de esa carpeta.
- Un módulo nuevo aparece solo en la referencia.
- Un área nueva del repositorio necesita su línea en `AREA_SITE` de
  `scripts/gen_pages.py`, además de `scripts/areas.py`.

## Construir y ver en local

Instale las dependencias solo en el venv del proyecto:

```bash
cd /home/och/odoo/ce19/myodoo/ol_new_apps
/home/och/odoo/ce19/.venv/bin/python -m pip install -r mkdocs/requirements.txt

export NO_MKDOCS_2_WARNING=1 DISABLE_MKDOCS_2_WARNING=true   # silencia el aviso sobre MkDocs 2.0
/home/och/odoo/ce19/.venv/bin/mkdocs serve -f mkdocs/mkdocs.yml        # http://127.0.0.1:8000
/home/och/odoo/ce19/.venv/bin/mkdocs build --strict -f mkdocs/mkdocs.yml   # deja el sitio en mkdocs/site/
```

`--strict` convierte cualquier advertencia en un error:
- un enlace roto;
- una página fuera de la navegación;
- un ancla inexistente queda solo como información.

La construcción tarda unos 40 s y el sitio ocupa unos 130 MB, sobre todo por las capturas.

## Versiones: 19.0 hoy, 20.0 mañana

Cada versión mayor de Odoo tiene su rama en el repositorio (`19.0`, `20.0`…)
y su documentación se genera desde esa rama. [mike](https://github.com/jimporter/mike)
publica cada versión en una carpeta de la rama `gh-pages`: `19.0/`, `20.0/` y
el alias `latest/`. El selector de la cabecera cambia entre ellas, y una
versión anterior muestra un aviso con el enlace a la más reciente.

### Qué depende de la versión

Todo sale de dos valores de `mkdocs.yml`, marcados con «VERSIÓN». Las variables de entorno los sobrescriben sin editar el archivo:

| Valor | Variable de entorno | Para qué |
|---|---|---|
| `extra.odoo_version` (`19.0`) | `ODOO_VERSION` | Portada, fichas («Odoo 19.0»), enlace a `odoo.com/documentation/<versión>/es/`, rama de los enlaces a GitHub |
| `edit_uri` (`edit/19.0/`) | `DOCS_EDIT_URI` | Botón «Editar» en GitHub |
| `extra.git_branch` (vacío = la versión) | `DOCS_BRANCH` | Rama de GitHub si no se llama como la versión |
| `site_url` | `DOCS_SITE_URL` | URL donde se publica (raíz de mike, sin la versión) |

### Publicar la 19.0 (preparado, sin publicar)

mike solo hace commits en la rama local `gh-pages`. Sin `--push` no sube nada.

```bash
cd /home/och/odoo/ce19/myodoo/ol_new_apps          # rama 19.0
export NO_MKDOCS_2_WARNING=1 DISABLE_MKDOCS_2_WARNING=true
MIKE=/home/och/odoo/ce19/.venv/bin/mike
$MIKE deploy --config-file mkdocs/mkdocs.yml --update-aliases 19.0 latest
$MIKE set-default --config-file mkdocs/mkdocs.yml latest
$MIKE serve --config-file mkdocs/mkdocs.yml        # revisar en http://127.0.0.1:8000
# Para publicar (GitHub Pages u otro servidor que sirva gh-pages):
# $MIKE deploy --config-file mkdocs/mkdocs.yml --update-aliases --push 19.0 latest
```

### Cuando exista la rama 20.0

1. En la rama `20.0`, cambie en `mkdocs.yml` los dos valores marcados con «VERSIÓN»: `odoo_version: "20.0"` y `edit_uri: "edit/20.0/"`.
2. Despliegue la 20.0 y mueva `latest`:
   ```bash
   git switch 20.0
   $MIKE deploy --config-file mkdocs/mkdocs.yml --update-aliases 20.0 latest
   ```
   La 19.0 sigue en `gh-pages/19.0/` y muestra el aviso «versión anterior».
3. Las correcciones de la 19.0 se siguen publicando desde su rama, sin tocar `latest`:
   ```bash
   git switch 19.0
   $MIKE deploy --config-file mkdocs/mkdocs.yml 19.0
   ```
4. Para retirar una versión: `$MIKE delete --config-file mkdocs/mkdocs.yml 18.0`.

Sin editar el archivo, el mismo despliegue funciona con variables:

```bash
ODOO_VERSION=20.0 DOCS_EDIT_URI=edit/20.0/ $MIKE deploy --config-file mkdocs/mkdocs.yml --update-aliases 20.0 latest
```

Este procedimiento está probado en un clon desechable: 19.0 y 20.0 desplegadas, `latest` → 20.0 y aviso visible en la 19.0.

## Notas

- **MkDocs 2.0.** Su autor anunció una versión que no admite los temas ni los plugins actuales. Por eso `requirements.txt` fija `mkdocs==1.6.1`. Si hiciera falta, [ProperDocs](https://properdocs.org/) es la continuación compatible de la 1.x.
- **Diagramas.** Los de las fichas (`flujos` del YAML) se dibujan con Mermaid en el navegador, en modo claro y oscuro. El navegador necesita acceso a unpkg.com.
- **Ficha HTML en Odoo.** La de Aplicaciones (`static/description/index.html`) sigue generándose con `docs/fichas/generar_fichas.py` desde el mismo YAML.

## Publicación en docs.altalatam.com

El sitio se publica en el servidor io-altaexperts, en Docker, con página de
inicio de sesión: https://docs.altalatam.com (`/` lleva a `/latest/`). La
configuración está en [`deploy/`](deploy/README.md).

Se reconstruye solo: cada 5 minutos el servidor mira si `origin/19.0` tiene
un commit nuevo y, si lo hay, publica la versión nueva (unos 2 minutos).
Para forzarlo:

```bash
ssh io-altaexperts 'cd /opt/odoo-infra/docs-site && ./build.sh'
```

Desde Odoo se llega por **Ajustes ▸ Perú ▸ Documentación**.
