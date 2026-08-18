# al_project_gantt_backend — Gantt de Proyectos (interfaz de backend)

Aplicación propia dentro del webclient de Odoo: menú raíz **Gantt** →
*Diagrama de Gantt*, que abre una `ir.actions.client` a pantalla completa con el
diagrama interactivo.

No es una vista Gantt heredada ni depende de `web_gantt` (Enterprise): es un
componente OWL que monta dhtmlxGantt en su propio contenedor.

## Instalación

```bash
odoo-bin -c <config> -i al_project_gantt_backend --stop-after-init
```

Arrastra `al_project_gantt_base` (que debe instalarse primero; Odoo lo resuelve
por `depends`). No necesita `website` ni ningún módulo de Enterprise.

Para ver el menú hay que pertenecer al grupo **Gantt de Proyectos / Usuario**;
los administradores de proyecto lo reciben automáticamente.

## Botón inteligente en el proyecto

El formulario de `project.project` gana un botón **Gantt** con el número de
tareas planificadas (`gantt_task_count`, del módulo base: cuenta solo las que
tienen fecha). Abre esta misma acción acotada a ese proyecto
(`action_open_gantt` pasa `gantt_project_ids` en el contexto) y la barra ofrece
**Ver todos los proyectos** para salir del acotado.

## Qué hace

- Selección múltiple de proyectos (botones con el número de tareas).
- Jerarquía proyecto → tarea → subtarea, dependencias fin-comienzo, hitos de
  `project.milestone` y tareas de duración cero como hitos.
- Color de barra según el estado de la tarea (configurable en el módulo base).
- Escalas de tiempo: día, semana, mes y trimestre.
- Panel de filtros plegable: responsable, estado, rango de fechas e «incluir
  tareas sin fecha», con contador de filtros activos y validación del rango.
  Los valores de los desplegables los aporta el servidor (`payload.filters`).
- Avisos explícitos cuando el resultado viene truncado por el límite o cuando
  hay tareas sin fecha límite que no se pueden dibujar.
- Tooltip con fechas, etapa y responsable.
- **Edición** (si el usuario tiene permiso real de escritura sobre la tarea):
  arrastrar y redimensionar barras, editar en el formulario emergente, mover el
  avance, crear y borrar tareas, y crear o quitar dependencias arrastrando.
  Cada cambio se guarda al momento y el indicador de la barra muestra la hora
  del último guardado; si el servidor rechaza algo, se avisa y se recarga para
  no dejar en pantalla nada que no esté guardado.
- **Ruta crítica** (botón con el número de tareas críticas), **línea base**
  (selector + botón de captura, con barra fantasma y columna de desvío) y
  **encadenar** (empuja las sucesoras al mover una tarea).
- Las tareas sin permiso de escritura se marcan con trama y no se pueden
  arrastrar.
- **Herramientas de vista**: búsqueda instantánea con contador, columna de
  código EDT, expandir/contraer todo, ocultar tareas terminadas, pantalla
  completa, marca del día de hoy y sombreado de días no laborables según el
  calendario del proyecto (visible en la escala Día).
- **Menú contextual** (clic derecho sobre una tarea): abrir la tarea en Odoo,
  **planificar actividad**, añadir subtarea, indentar, desindentar y eliminar.
- **Formulario de tarea completo** (doble clic): nombre; periodo con un campo
  de fecha y hora para el inicio y otro para el fin; etapa; responsables y
  etiquetas como *badges* con «×», al estilo del widget many2many —el desplegable
  de **Personas asignadas** ofrece a todo el personal interno activo, no solo a
  quien ya tiene tareas—; prioridad;
  horas asignadas y avance. Todo se guarda por el mismo contrato de escritura.
- **Exportar a Excel y PDF** desde la barra: el fichero lo compone el servidor
  con lo que se está viendo (filtros y escala incluidos), sin pasar por ningún
  servicio externo.
- **Indicador de actividades** en la rejilla: un punto rojo, naranja o verde
  según haya actividades atrasadas, para hoy o planificadas.

## Cómo se carga la librería

La librería vive en el módulo base y **no** está declarada en
`web.assets_backend`: son 627 KB que penalizarían el arranque de todo el
webclient. Se descarga con `loadJS`/`loadCSS` al montar la acción:

```js
await Promise.all([loadJS(GANTT_LIB.js), loadCSS(GANTT_LIB.css)]);
this.gantt = window.Gantt.getGanttInstance();
```

`getGanttInstance()` crea una instancia propia, de modo que esta interfaz y la
de website no comparten estado si ambas están instaladas. Un test comprueba que
la librería no se cuele en el bundle.

## Puntos de extensión

| Qué | Dónde |
|---|---|
| Filtros que se envían al servidor | `GanttAction.getOptions()` → `filtersToOptions` del base |
| Columnas de la rejilla | `configureGantt()` → `gantt.config.columns` |
| Escalas de tiempo | constante exportada `ZOOM_LEVELS` |
| Contenido del tooltip | `getTooltip(task)` |
| Clases CSS por tarea | `gantt.templates.task_class` |
| Traducción de eventos a *changeset* | `gantt_editing.js` → `GanttEditor` (módulo base) |
| Qué se puede editar | `enableEditing` + `meta.editable`/`task.editable` del contrato |

## Detalles de maquetación que conviene no romper

Dos ajustes son necesarios para que la librería reciba un alto real; si se
tocan, el diagrama se colapsa a una sola fila:

1. La plantilla envuelve el `Layout` en `.o_algantt_root` (flex column, alto
   100 %). Sin ese contenedor, `main.o_content` cuelga de `o_action_manager`
   (que es `display: block`) y no recibe altura.
2. `.algantt-container` se posiciona con `position: absolute; inset: 0`. Un
   `height: 100%` no sirve: el padre resuelve su alto por flexbox y el
   porcentaje colapsa al contenido.

Un `ResizeObserver` llama a `gantt.setSizes()` cuando cambia el tamaño del
contenedor (al plegarse un aviso o al redimensionar la ventana).

## Pruebas

```bash
odoo-bin -c <config> -u al_project_gantt_backend --test-enable \
         --test-tags /al_project_gantt_backend --stop-after-init
```

Los tests de Python cubren la acción, los menús y sus grupos, y que la librería
no esté en el bundle. La lógica de filtros vive en el módulo base y está cubierta
por sus tests. La verificación de render se hizo con Playwright sobre
`ol_pe_v19`; los datos de demostración están en
[`docs/gantt/pruebas/seed_gantt_demo.py`](../docs/gantt/pruebas/seed_gantt_demo.py).

## Limitaciones

Las del módulo base (dependencias solo `FS`, sin calendarios laborales) más:

- El idioma de la librería se traduce al español desde el adaptador; otros
  idiomas usan las etiquetas en inglés de dhtmlxGantt.
