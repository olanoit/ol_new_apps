---
hide:
  - navigation
  - toc
---

# Suite OL para Odoo {{ odoo_version }}

<p class="ol-lead">Localización peruana completa y módulos de negocio para Odoo
{{ odoo_version }} Community y Enterprise: contabilidad y tributación,
comprobantes electrónicos, planillas, punto de venta, inventario, proyectos y
obras.</p>

{{ cifras }}

## Áreas

Cada área es una pestaña de este sitio y una carpeta `OL-<ÁREA>/` del
repositorio.

<div class="grid cards" markdown>

{{ areas }}

</div>

## Cómo usar esta documentación

<div class="grid cards" markdown>

-   :material-account-tie:{ .lg .middle } **Consultor funcional**

    ---

    Empiece por las [guías funcionales](guias-funcionales.md): para qué sirve
    cada módulo, la norma que lo respalda y el proceso de inicio a fin con un
    ejemplo que cuadra.

-   :material-monitor-dashboard:{ .lg .middle } **Usuario o implementador**

    ---

    La **ficha** de cada módulo (primera página de su sección) tiene los
    destacados, los flujos, el paso a paso con capturas, la configuración y
    las preguntas frecuentes.

-   :material-code-braces:{ .lg .middle } **Desarrollador**

    ---

    La [documentación técnica](tecnica/index.md) reúne planes de desarrollo,
    especificaciones, estructuras SUNAT y validaciones; la
    [página del repositorio](tecnica/repositorio.md), la instalación y las
    convenciones.

-   :material-magnify:{ .lg .middle } **Buscar**

    ---

    La búsqueda (tecla ++s++ o ++slash++) recorre todas las páginas en
    español. Las [etiquetas](etiquetas.md) agrupan los módulos por tema
    (PLE, SUNAT, NIIF…).

</div>

## De dónde sale cada página

Nada se escribe dos veces: el sitio se genera en cada construcción desde los
archivos del repositorio.

| En el sitio | Archivo de origen |
|---|---|
| Página de un área | `OL-<ÁREA>/README.md` y los manifiestos de sus módulos |
| Ficha de un módulo | `__manifest__.py` y `docs/fichas/<módulo>.yml` |
| Guía funcional | `<módulo>/GUIA_FUNCIONAL.md` |
| Novedades | `<módulo>/CHANGELOG.md` (generado desde la ficha) |
| Descripción técnica y anexos | `<módulo>/README.md` y `<módulo>/docs/` |
| Documentación técnica | `docs/<carpeta>/` |

Cada página tiene el botón :material-pencil: para editar su origen en GitHub
(rama `{{ branch }}`). Documentación oficial de Odoo para esta versión:
[odoo.com/documentation/{{ odoo_version }}]({{ odoo_docs }}).
