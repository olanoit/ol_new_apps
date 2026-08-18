# al_project_gantt_base — Gantt de Proyectos (módulo base)

Módulo **sin interfaz**: concentra la lógica, los datos y la seguridad que
comparten las dos interfaces de la suite.

| Módulo | Rol | Depende de |
|---|---|---|
| **`al_project_gantt_base`** | Capa de datos, mapeo de campos, seguridad, librería Gantt y adaptador JS | `project` |
| `al_project_gantt_backend` | Interfaz en el backend (client action OWL) | base + `web` |
| `al_project_gantt_website` | Interfaz en el sitio web, solo usuarios internos | base + `website` |

**Orden de instalación**: siempre el base primero (las UIs lo declaran en
`depends`, así que Odoo lo respeta solo). El base funciona instalado a solas:
expone el método de datos aunque no haya ninguna interfaz.

## Instalación

```bash
odoo-bin -c <config> -i al_project_gantt_base --stop-after-init
```

Sin dependencias externas de Python ni de npm: la librería ya viene
empaquetada en `static/lib/dhtmlx/`.

## Capa de datos

Punto de entrada único, llamado por las dos UIs:

```python
env['project.project'].get_gantt_data(project_ids=None, options=None)
```

`options` admite `date_from`, `date_to`, `user_ids`, `states`,
`include_undated` y `limit`. La respuesta:

```jsonc
{
  "contract_version": 2,
  "field_map": {"date_start": "planned_date_begin", "date_end": "date_deadline",
                "progress": null, "source": "auto", "mode": "planned"},
  "projects":   [{"id", "name", "date_start", "date_end", "company_id",
                  "company_name", "task_count"}],
  "tasks":      [{"id", "name", "project_id", "project_name", "parent_id",
                  "orphaned", "start", "end", "start_is_inferred", "undated",
                  "is_milestone", "progress", "progress_is_derived", "state",
                  "stage_id", "stage_name", "milestone_id", "milestone_name",
                  "color", "text_color", "user_ids", "allocated_hours", "editable"}],
  "links":      [{"id", "source", "target", "type"}],
  "milestones": [{"id", "name", "project_id", "project_name", "date", "is_reached"}],
  "colors":     {"states": {"<state>": {"color", "text_color"}}, "fallback": {}},
  "filters":    {"states": [{"value", "label"}],
                 "users":  [{"id", "name", "task_count"}]},
  "applied_filters": {"date_from", "date_to", "user_ids", "states", "include_undated"},
  "meta":       {"count", "total", "limit", "truncated", "undated_count", "tz", "editable"}
}
```

`filters` trae los **valores disponibles** para los desplegables y
`applied_filters` devuelve lo que se aplicó, de modo que las dos interfaces
pintan lo mismo sin hardcodear nada ni consultar el ORM.

Ojo con las **dos listas de personas**, que responden a preguntas distintas:

| Clave | Contenido | Para qué |
|---|---|---|
| `filters.users` | Quienes ya tienen tareas en los proyectos consultados | El **filtro**: ofrecer gente sin tareas solo daría resultados vacíos |
| `filters.assignable_users` | Todas las asignables, con el mismo dominio que el campo `user_ids` de la tarea (`share = False`, `active = True`), hasta 500 | El **formulario**: hay que poder asignar a alguien que aún no tiene nada |

Reglas del contrato:

- **Formato neutral**, no el de dhtmlxGantt. La traducción la hace
  `static/src/js/gantt_adapter.js`, compartido por las dos UIs; cambiar de
  librería no obliga a tocar Python.
- **Fechas en ISO 8601 UTC** (`2026-09-07T08:00:00Z`); `meta.tz` indica la zona
  del usuario y el adaptador hace la conversión en el cliente.
- **Tareas sin fecha de fin** no se emiten (no hay barra que dibujar) pero se
  cuentan **siempre** en `meta.undated_count`, aunque queden fuera del
  resultado; con `include_undated` se devuelven marcadas con `undated: true` y
  el adaptador las pinta como «no planificadas» (fila sin barra).
- **Tareas sin fecha de inicio** reciben un inicio calculado hacia atrás desde
  el fin (`al_gantt.default_duration_hours`, 8 h por defecto) y se marcan con
  `start_is_inferred`.
- **Padre fuera del conjunto** (por filtro o por límite): la tarea se emite como
  raíz con `orphaned: true`, en lugar de desaparecer del árbol.
- **Dependencias**: solo las que tienen ambos extremos en el conjunto leído.
  El M2M nativo `depend_on_ids` no guarda tipo ni retraso, así que todas son
  fin-comienzo (`FS`).
- **Truncado explícito**: si hay más tareas que el límite, `meta.truncated` es
  `true` y `meta.total` da el número real. Nunca se recorta en silencio.

## Capa de escritura (versión 2)

```python
env['project.project'].apply_gantt_changes(changeset)
```

```jsonc
{
  "tasks": {
    "update": [{"id": 12, "start": "…Z", "end": "…Z", "name": "…",
                 "progress": 40.0, "parent_id": 8}],
    "create": [{"temp_id": "tmp1", "project_id": 5, "name": "…", "start": "…Z", "end": "…Z"}],
    "delete": [13]
  },
  "links": {"create": [{"source": 1, "target": 2}], "delete": [{"source": 1, "target": 2}]},
  "reschedule_chain": true
}
```

Devuelve `{ok, created: {temp_id: id}, updated, deleted, links_created,
links_deleted, rescheduled, warnings}`.

Reglas:

- **Permiso real por tarea.** Antes de escribir se comprueba
  `_filtered_access('write'/'unlink')`: mandan la ACL y las `ir.rule` de
  `project`, no un grupo propio. En la lectura, cada tarea trae `editable` con
  ese mismo criterio y la interfaz bloquea las que no lo son.
- **Solo campos del mapeo.** Las fechas se escriben en los campos que resuelve
  `al.gantt.field.map`; si la instalación no tiene campo de inicio, mover una
  barra se rechaza con un mensaje claro en vez de fallar a medias.
- **El avance solo se guarda si existe el campo** (`hr_timesheet`); si es
  derivado del estado, se ignora silenciosamente.
- **Los ciclos de dependencias no se reimplementan**: los rechaza la
  restricción nativa de `project`.

### Reprogramación en cadena

Con `reschedule_chain`, tras mover una tarea se empujan sus sucesoras: ninguna
empieza antes de que termine su predecesora y **mantienen su duración**. No se
adelanta nada —mover una tarea hacia atrás no comprime el plan— y se para a los
500 movimientos. Una sucesora sin permiso de escritura no se mueve y se informa
en `warnings`.

## Ruta crítica

`options.critical_path` añade a cada tarea `slack_hours` (holgura total) y
`critical`, y a `meta.critical_path` el resumen (`critical_count`,
`project_finish`). Se calcula en el servidor con CPM clásico (pasada hacia
delante y hacia atrás sobre las dependencias FS) porque **la edición MIT de la
librería no trae ruta crítica**. Entran las tareas con fechas y sin hijos; las
contenedoras heredan la marca de sus descendientes.

## Línea base

`al.gantt.baseline` + `al.gantt.baseline.line` guardan una foto **inmutable**
(las líneas rechazan `write`) de fechas y avance:

```python
env['al.gantt.data'].create_baseline(project_ids, name)
```

Con `options.baseline_id`, cada tarea trae `baseline_start`, `baseline_end` y
`baseline_variance_days`; el payload lista en `baselines` las disponibles.

## Mapeo de campos

Odoo no ofrece un juego de fechas único para las tareas, así que se detecta por
introspección:

| Concepto | Candidatos (en orden) | Notas |
|---|---|---|
| Inicio | `planned_date_begin`, `date_start` | `planned_date_begin` lo aporta `project_enterprise`. **`project.task` no tiene `date_start` en Odoo 19**; el candidato queda por si un módulo propio lo añade. |
| Fin | `date_deadline`, `planned_date_end` | `date_deadline` existe siempre. No hay `planned_date_end` en Odoo 19. |
| Avance | `progress` | Solo existe con `hr_timesheet`. Si falta, se deriva del estado (cerrada = 100 %) y se marca `progress_is_derived`. |

`mode` resume el resultado: `planned` (inicio y fin), `deadline_only` (solo fin)
o `none`.

Para forzar otro mapeo, sin tocar código:

```
Ajustes ▸ Técnico ▸ Parámetros del sistema
  al_gantt.field_map = {"date_start": "x_mi_fecha_inicio", "progress": null}
```

Un campo inexistente se ignora con un aviso en el log y se mantiene la
detección automática. Otros parámetros: `al_gantt.task_limit` (2000, tope duro
20000) y `al_gantt.default_duration_hours` (8).

## Seguridad

- Grupos: **Gantt de Proyectos / Usuario** (`group_gantt_user`) y
  **Administrador** (`group_gantt_manager`). Ambos implican
  `project.group_project_user`, es decir, son **usuarios internos**; los
  administradores de proyecto reciben el acceso al instalar.
- `get_gantt_data` rechaza con `AccessError` a los usuarios de portal/público
  (`user.share`) y a quien no tenga el grupo.
- **No se redefinen reglas sobre `project.project` / `project.task`** a
  propósito. Toda la lectura se hace **sin `sudo()`**, de modo que las reglas
  nativas de `project` —privacidad por seguidores, portal, multicompañía— se
  aplican sin duplicarse. Reimplementarlas aquí solo crearía divergencia.
- Único `sudo()` del módulo: la lectura del **nombre** de los responsables ya
  presentes en tareas visibles (con `active_test=False`, para que un empleado
  dado de baja no aparezca en blanco). Está acotado y comentado en el código.
- Los colores son de solo lectura para el grupo Usuario y editables para
  Administrador; su `ir.rule` los acota por compañía.

## Formulario de tarea (`gantt_lightbox.js`)

El formulario que abre el doble clic trae, además del nombre y el periodo:
**etapa**, **responsables**, **prioridad**, **horas asignadas**, **etiquetas** y
**avance** (este último solo si el campo `progress` existe de verdad, es decir,
con `hr_timesheet` instalado: `meta.can_edit_progress`). Las opciones de cada
desplegable las envía el servidor en `filters` — etapas de los proyectos
consultados, prioridades del propio campo y etiquetas existentes.

Notas de implementación — el formulario usa **dos bloques propios**, porque los
de la edición MIT no dan el resultado esperado:

| Bloque | Por qué |
|---|---|
| `algantt_daterange` | Los bloques `time` y `duration` editan la fecha con tres desplegables (día, mes, año) y no muestran el fin. Este usa un `datetime-local` para el inicio y otro para el fin. Si el rango queda invertido o incompleto, conserva las fechas que ya tenía la tarea. |
| `algantt_tokens` | No existe bloque `multiselect`, y `checkbox` deja casillas sueltas. Este dibuja *badges* con «×» y un desplegable «Añadir…», al estilo del widget many2many de Odoo. |

Al registrar un bloque propio, su `render()` debe devolver HTML **sin espacios
ni saltos iniciales**: la librería indexa los hijos del contenedor y un nodo de
texto suelto rompe el formulario (`C.querySelector is not a function`).
- Los estilos de Odoo ponen `display: block; width: 100%` a los `select`, lo que
  apilaba los tres desplegables de cada fecha; `gantt_common.scss` restaura el
  comportamiento en línea.
- La **descripción no se edita** en este formulario: es un campo HTML y
  guardarla como texto plano perdería el formato. El contrato de escritura sí
  acepta `description` (la escapa y la envuelve en `<p>`) para quien la necesite.

### Botón «Abrir en Odoo»

Como el formulario es corto a propósito —sin descripción, sin chatter, sin
adjuntos—, lleva un botón que abre la **ficha completa** de la tarea. Es la
salida natural cuando hace falta algo que aquí no está.

El módulo base no sabe navegar, así que la interfaz lo decide pasando
`openRecord` a `configureLightbox`:

```js
configureLightbox(gantt, { filters, canEditProgress, openRecord: (id) => ... });
```

Sin esa función el botón no aparece. El backend abre la acción con su miga de
pan; el website abre `/odoo/project.task/<id>` en otra pestaña. Pulsarlo
**descarta** lo tecleado en el formulario, igual que Cancelar: se va a editar a
la ficha.

Cómo se monta, por si hace falta otro botón: la librería toma los nombres de
`gantt.config.buttons_left` / `buttons_right`, saca la etiqueta de
`gantt.locale.labels[nombre]`, usa el nombre como **clase CSS** del icono y
dispara `onLightboxButton` con esa clase. Las filas de proyecto y los hitos no
son `project.task`: se marcan en `onBeforeLightbox` con la clase
`algantt-lb-no-open` en el contenedor y el botón se esconde por CSS (defensa en
profundidad: esas filas son `readonly` y su formulario no llega a abrirse).

## Actividades

Las tareas viajan con `activity_state`, `activity_summary` y `activity_icon` de
`mail.activity`: la rejilla muestra un punto de color (rojo atrasada, naranja
hoy, verde planificada) y el tooltip el resumen. Planificar una actividad se
hace con el asistente estándar `mail.activity.schedule`, que abre la interfaz de
backend desde el menú contextual.

## Exportación a Excel y PDF

Los dos formatos se generan **en el servidor**, desde la misma estructura
(`build_matrix`: filas en el orden del árbol y columnas de periodo), así que
dicen exactamente lo mismo y respetan los filtros que estén aplicados.

| Formato | Cómo | Contenido |
|---|---|---|
| Excel | `al.gantt.data.export_xlsx()`, servido por `/al_project_gantt/export/xlsx` | Hoja **Tareas** (EDT, nombre, proyecto, fechas, días, responsables, etapa, avance, horas, holgura y desvío) y hoja **Diagrama** (una columna por periodo con la barra pintada del color del estado) |
| PDF | Informe `al_project_gantt_base.report_gantt` (QWeb + wkhtmltopdf), A3 apaisado | Rejilla con EDT, tarea indentada, fechas, barras por periodo, marca de ruta crítica y leyenda de colores |

**Por qué en el servidor y no con la librería**: dhtmlxGantt sí trae
`exportToPDF`/`exportToExcel`, pero funcionan contra
`https://export.dhtmlx.com/gantt` — es decir, subirían la planificación del
cliente a un servicio del fabricante. Comprobado en el propio bundle.

La escala (día, semana, mes, trimestre) sale de la que esté puesta en pantalla y
**se agranda sola** si el plan no cabe en 60 columnas, para que el documento
siga siendo legible.

Dos trampas encontradas al montarlo, por si se toca la plantilla:

- En una cadena de formato QWeb, un `%` suelto rompe el render
  (`ValueError: incomplete format`): el ancho de columna se concatena, no se
  formatea.
- En los tests, Odoo no llama a wkhtmltopdf y `_render_qweb_pdf` devuelve HTML;
  el test acepta ambos resultados.

## Herramientas del diagrama (`gantt_tools.js`)

Funciones que las alternativas comerciales dan por hechas y que la edición MIT
de la librería **no incluye**, implementadas aquí sobre su API pública:

| Herramienta | Nota |
|---|---|
| Búsqueda rápida | `filterTask` es de pago; se filtra con el evento `onBeforeTaskDisplay`, conservando los ancestros para no romper el árbol |
| Código EDT (WBS) | `getWBSCode` es de pago; se numera recorriendo el árbol, reiniciando en cada proyecto |
| Días no laborables | Se sombrean según el `resource.calendar` del proyecto (`calendar` del contrato). Solo afecta al dibujo y se aprecia en la escala **Día** |
| Marca de hoy | Plugin `marker` (sí disponible); se ve cuando la fecha de hoy cae dentro del rango del plan |
| Pantalla completa | Plugin `fullscreen` |
| Expandir / contraer todo | Recorrido del árbol |
| Indentar / desindentar | Calcula el nuevo `parent_id` y lo guarda por el contrato de escritura |
| Menú contextual | La edición MIT no trae uno: se dibuja con DOM propio |

## Puntos de extensión

| Qué | Dónde |
|---|---|
| Filtros adicionales en el dominio de tareas | `al.gantt.data._get_task_domain` |
| Campos extra en la respuesta | `al.gantt.data._get_task_fields` + `_read_tasks` |
| Reglas de acceso propias | `al.gantt.data._check_gantt_access` |
| Habilitar escritura (versión 2) | `al.gantt.data._is_task_editable` — hoy devuelve `False` siempre |
| Colorear por etapa o etiqueta en vez de por estado | `al.gantt.state.color.get_color_map` |
| Otros candidatos de campos de fecha | `al.gantt.field.map._get_candidates` |
| Valores de los filtros de la interfaz | `al.gantt.data._read_filter_options` |
| Aspecto de las filas del Gantt | `gantt_adapter.js` → `taskToRow` / `projectToRow` |
| Configuración de la librería (columnas, escalas, tooltip) | `gantt_setup.js` |
| Estado y serialización de los filtros | `gantt_filters.js` → `filtersToOptions` |
| Herramientas de vista (búsqueda, EDT, calendario…) | `gantt_tools.js` |
| Días laborables y feriados | `al.gantt.data._read_calendar` |

## Librería

`static/lib/dhtmlx/` contiene **dhtmlxGantt 10.0.1** (edición Standard,
licencia MIT, `LICENSE.md` incluido) tomada del paquete npm `dhtmlx-gantt`.

El base **no** la declara en ningún *bundle* de assets: son 627 KB de JS y
143 KB de CSS que no deben penalizar el arranque del webclient. Cada UI la carga
de forma perezosa al montar su vista, usando las rutas que exporta el adaptador:

```js
import { GANTT_LIB, toDhtmlxData } from "@al_project_gantt_base/js/gantt_adapter";
await loadJS(GANTT_LIB.js);
await loadCSS(GANTT_LIB.css);
```

El módulo base aporta tres piezas de JavaScript compartidas, todas puras y sin
dependencias de OWL para poder usarse igual en `web.assets_backend` y en
`web.assets_frontend`:

| Fichero | Qué contiene |
|---|---|
| `js/gantt_adapter.js` | Traducción del contrato neutral al formato de la librería, conversión de zona horaria y traducción al español de sus etiquetas |
| `js/gantt_setup.js` | Configuración de la librería: columnas, escalas de zoom, tooltip, clases por tarea |
| `js/gantt_filters.js` | Estado de los filtros, su serialización a `options` y las validaciones (rango invertido, recuento de filtros activos) |
| `scss/gantt_common.scss` | Estilos de las barras (proyecto, inicio inferido, huérfana) |

Cada interfaz los declara en su propio *bundle*; el base no los mete en ninguno.

## Limitaciones conocidas

- Un solo tipo de dependencia (`FS`), por la forma del M2M nativo
  `depend_on_ids` (no guarda tipo ni retraso).
- El avance es derivado del estado mientras no esté instalado `hr_timesheet`.
- Sin calendarios laborales ni histograma de recursos: la reprogramación en
  cadena trabaja en tiempo natural, no en días hábiles.
- **La edición MIT de la librería no permite capas propias**: elimina
  `addTaskLayer` del bundle. La línea base se dibuja inyectando la barra dentro
  del contenido de la tarea (`enableBaselineBars`), no como capa.

## Pruebas

```bash
odoo-bin -c <config> -u al_project_gantt_base --test-enable \
         --test-tags /al_project_gantt_base --stop-after-init
```

Cubren el contrato de datos, el mapeo de campos con sus sobreescrituras, los
casos límite (tareas sin fecha, huérfanas, dependencias cortadas, truncado) y la
seguridad (portal, usuario sin grupo, otra compañía, proyecto privado).

Datos de demostración y verificación funcional:
[`docs/gantt/pruebas/`](../docs/gantt/pruebas/).
