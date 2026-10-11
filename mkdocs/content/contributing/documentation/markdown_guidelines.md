# Pautas de Markdown

El sitio usa [MkDocs](https://www.mkdocs.org/) con
[Material for MkDocs](https://squidfunk.github.io/mkdocs-material/). Esta tabla
traduce las directivas de RST de la documentación de Odoo a su equivalente
aquí.

| Odoo (RST) | Aquí (Markdown) | Ejemplo |
|---|---|---|
| `:menuselection:` | Negrita con `‣` | `**Contabilidad ‣ Configuración ‣ Ajustes**` |
| `:guilabel:` | Negrita | `**Guardar**` |
| `:kbd:` | Teclas | `++ctrl+k++` |
| `.. note::` | `!!! note "Nota"` | Información útil que no cambia el resultado |
| `.. tip::` | `!!! tip "Consejo"` | Un atajo o una buena práctica |
| `.. important::` | `!!! warning "Importante"` | Algo que hay que hacer para que funcione |
| `.. warning::` | `!!! danger "Advertencia"` | Algo que puede causar pérdida de datos o errores fiscales |
| `.. seealso::` | `!!! info "Ver también"` | Enlaces al final de la página |
| `.. image::` + `:alt:` | `![texto alternativo](pagina/imagen.png)` | |
| `:doc:` / `:ref:` | Enlace relativo `.md` (con `#ancla`) | `[Detracciones](peru/detractions.md#configuracion)` |
| `.. list-table::` | Tabla Markdown | |
| `|abbr|` | Abreviatura | `*[SPOT]: Sistema de Pago de Obligaciones Tributarias` |

## Avisos

```markdown
!!! warning "Importante"
    La cuenta de detracciones debe estar en el diario del Banco de la Nación.
```

El texto del aviso va sangrado con cuatro espacios. Use siempre el título en
español de la tabla.

## Encabezado de la página

```markdown
---
modulos: [al_l10n_pe_detraction]
---

# Detracciones (SPOT)
```

## Anclas

El ancla de un título es su texto en minúsculas con guiones, con tildes:
`## Configuración inicial` → `#configuración-inicial`.

## Diagramas

Los flujos se dibujan con Mermaid en un bloque ` ```mermaid `.
