# Organización de la documentación

La documentación vive en `mkdocs/content/` del repositorio, en un árbol por
áreas de negocio como el de Odoo (`content/` de
[odoo/documentation](https://github.com/odoo/documentation)). Los módulos no
guardan su documentación funcional: cada uno enlaza desde su `README.md` a su
página del sitio.

## Secciones

| Sección | Carpeta | Contenido |
|---|---|---|
| Documentación para usuarios | `applications/` | Cómo configurar y usar cada funcionalidad, por área de negocio |
| Instalación y mantenimiento | `administration/` | Instalar la suite, actualizar módulos, servidores y publicación de la documentación |
| Desarrollador | `developer/` | Convenciones, herramientas, pruebas, referencia de cada módulo y especificaciones |
| Aportando | `contributing/` | Estas pautas |

## Áreas de negocio

Las de Odoo, con lo que la suite agrega en cada una:

| Área | Carpeta | Ejemplos |
|---|---|---|
| Finanzas | `applications/finance/` | Localización peruana, letras, factoring, proveedores de pago |
| Ventas | `applications/sales/` | Punto de venta |
| Cadena de suministro | `applications/inventory_and_mrp/` | Kárdex, traslados |
| Recursos humanos | `applications/hr/` | Nómina peruana |
| Servicios | `applications/services/` | Gantt, requerimientos y planificación de obra |
| Ajustes generales | `applications/general/` | Ayuda contextual, ficha del módulo, servidor MCP |

## Dónde va algo nuevo

Elija la opción más liviana que cubra el tema, en este orden:

1. Ampliar una sección de una página existente.
2. Agregar una sección (H2) a una página existente.
3. Crear una página nueva en el área que corresponde.
4. Crear una página con subpáginas (carpeta con el mismo nombre de la página),
   cuando el tema es demasiado grande para una sola, como la planificación de
   obra.

No duplique contenido: enlace a la página que ya lo explica.

## Archivos y carpetas

- Nombres en inglés, en minúsculas y con guion bajo, como en Odoo
  (`fiscal_localizations/peru/detractions.md`). Los títulos van en español.
- Las imágenes de una página van en una carpeta con su mismo nombre
  (`detractions.md` → `detractions/`). Esa carpeta guarda también las
  subpáginas, si las tiene.
- Cada carpeta tiene un `index.md` y un `SUMMARY.md` con el orden del menú
  lateral.

## Módulos y páginas

Cada página declara en su encabezado los módulos que documenta:

```yaml
---
modulos: [al_l10n_pe_detraction]
---
```

Con ese dato:

- la referencia técnica de cada módulo enlaza a sus páginas;
- el botón **?** de Odoo (módulo `al_docs_help`) abre la página de la pantalla;
- `README.md` del módulo enlaza a su página principal.

La parte de **Desarrollador ▸ Referencia de módulos** y las **Novedades** se
generan solas desde los módulos (manifiesto, ficha, `README.md`,
`CHANGELOG.md`). No se escriben a mano.
