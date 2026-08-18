# Plan de la suite `al_project_gantt_*` — Gantt de proyectos y tareas

> **Fecha:** 2026-08-17 · **Branch:** `19.0` · **Base de pruebas:** `ol_pe_v19`
> Sustituye a [`PLAN_MODULO_gantt_pro.md`](PLAN_MODULO_gantt_pro.md) (módulo
> único, sin código en el repositorio). Se conservan de aquel documento la
> elección de librería y el análisis de rendimiento.

## 1. Objetivo

Visibilidad e interacción con `project.project` / `project.task` mediante un
Gantt interactivo presentado como **aplicación propia**, no como vista Gantt
heredada del backend. Solo **usuarios internos** (`base.group_user`, `share =
False`). La arquitectura no debe cerrar la puerta a filtros avanzados, edición,
dependencias tipadas, hitos, línea base o exportación.

## 2. Los módulos

| Módulo | Rol | `depends` |
|---|---|---|
| `al_project_gantt_base` | Capa de datos única, mapeo de campos, colores, seguridad, librería vendorizada y adaptador JS | `project` |
| `al_project_gantt_backend` | UI A: `ir.actions.client` + menú raíz + componente OWL | base, `web` |
| `al_project_gantt_website` | UI B: controlador `auth='user'` + página QWeb | base, `website` |
| `al_project_gantt_ai` | Añadido opcional: panel de chat que consulta y propone cambios (§5.7) | backend |

**Regla de oro:** ninguna UI reimplementa lógica de datos ni seguridad. Instalar
el base + una sola UI debe bastar; las dos pueden convivir (prefijo CSS
`algantt-`, sin identificadores colisionantes).

## 3. Hechos del entorno que condicionan el diseño

Verificados el 2026-08-17 sobre `ol_pe_v19` y el código de Odoo 19:

- `project_enterprise` **instalado** ⇒ `project.task.planned_date_begin` existe;
  el fin planificado sigue siendo `date_deadline` (no hay `planned_date_end`).
- `project.task` **no tiene `date_start`** en Odoo 19; sí tiene `date_end`, pero
  es la fecha *real* de cierre (no se autodetecta como fin planificado).
- `progress` lo aporta `hr_timesheet`, hoy **desinstalado** ⇒ el avance se
  deriva del estado y se marca como derivado.
- `website` **desinstalado** ⇒ la UI B exigirá instalarlo.
- Estados de `project.task`: `01_in_progress`, `02_changes_requested`,
  `03_approved`, `04_waiting_normal`, `1_done`, `1_canceled`.
- Odoo 19: `res.users.groups_id` → `group_ids`; los grupos se agrupan por
  `res.groups.privilege`; `_sql_constraints` → `models.Constraint`.

## 4. Decisiones de arquitectura

1. **Formato neutral** en el backend; la traducción a dhtmlxGantt vive en el
   adaptador JS del base, compartido por las dos UIs. Cambiar de librería no
   toca Python.
2. **Sin `ir.rule` propias sobre `project.*`**: se lee sin `sudo()` y mandan las
   reglas nativas de `project`. Duplicarlas solo generaría divergencia.
3. **Librería fuera de los bundles**: `loadJS`/`loadCSS` perezosos al montar
   cada vista (627 KB de JS no deben penalizar el arranque del webclient).
4. **Nada hardcodeado**: mapeo de campos y colores por estado son datos
   configurables (`ir.config_parameter` y `al.gantt.state.color`).
5. **Truncado explícito**: `meta.truncated` + `meta.total`; nunca recortes
   silenciosos. Lo mismo con `meta.undated_count`: las tareas sin fecha límite
   se cuentan siempre, aunque queden fuera del resultado.

### 4.1 Trampas de maquetación (fase 4)

Dos ajustes hacen falta para que la librería reciba un alto real dentro del
webclient; sin ellos el diagrama se colapsa a **una sola fila** (la
virtualización de dhtmlxGantt solo pinta lo visible):

- La client action debe envolver el `Layout` en un contenedor propio flex
  column al 100 % de alto: `main.o_content` cuelga de `o_action_manager`, que es
  `display: block` y no reparte altura.
- El contenedor del Gantt necesita `position: absolute; inset: 0`; un
  `height: 100%` colapsa porque el padre resuelve su alto por flexbox.

### 4.2 Reparto del código compartido (tras la fase 5)

Al llegar la segunda interfaz se movió al base todo lo que ambas usan, para no
duplicarlo: `static/src/js/gantt_adapter.js` (traducción de datos y locale),
`static/src/js/gantt_setup.js` (columnas, escalas, tooltip, configuración de la
librería) y `static/src/scss/gantt_common.scss` (estilos de las barras). En cada
UI queda solo su maquetación y su forma de pedir datos (`orm.call` en el
backend, endpoint `/gantt/data` en el website). En la fase 6 se sumó
`static/src/js/gantt_filters.js` (estado de filtros, serialización a `options` y
validaciones) y el contrato pasó a la **versión 2**, que añade `filters` (los
valores disponibles, calculados en el servidor) y `applied_filters`.

Trampa de OWL: las expresiones de las plantillas **no ven los globales de
JavaScript** (`String`, `Number`…). Comparar `draft.userIds.includes(String(id))`
dentro de un `t-att` revienta el ciclo de vida del componente; hay que preparar
esos datos en un getter.

Nota sobre el 403 del endpoint JSON: `type='jsonrpc'` devuelve los errores en el
cuerpo con HTTP 200 (protocolo), no como código de estado. La página `/gantt` sí
responde 403 real. En Odoo 19, `type='json'` es un alias obsoleto de
`type='jsonrpc'`.

## 5. Fases

| # | Fase | Entregable verificable | Estado |
|---|---|---|---|
| 1 | Arquitectura y árbol de archivos | Este documento, validado con el cliente | ✅ |
| 2 | `al_project_gantt_base` | Módulo instalado en `ol_pe_v19`; **32 tests en verde**; contrato verificado con datos reales (16 tareas, 10 dependencias, 2 hitos, 15 consultas, 35 ms) | ✅ |
| 3 | Verificación del base aislado | Scripts [`pruebas/seed_gantt_demo.py`](pruebas/seed_gantt_demo.py) y [`pruebas/check_gantt_data.py`](pruebas/check_gantt_data.py) | ✅ |
| 4 | `al_project_gantt_backend` | Client action instalada en `ol_pe_v19`; **4 tests** propios; verificado con Playwright: 20 filas, 10 dependencias, 2 hitos, jerarquía de 3 niveles, cambio de escala y filtrado por proyecto, **sin errores de consola propios** — capturas [semana](img/fase4_backend_semana.png) y [mes](img/fase4_backend_mes.png) | ✅ |
| 5 | `al_project_gantt_website` | `website` instalado en `ol_pe_v19`; módulo con **8 tests** `HttpCase`; verificado con Playwright: interno con grupo 200 y render completo, portal **403**, anónimo redirigido al login, backend sin regresión — captura [website](img/fase5_website.png) | ✅ |
| 6 | Filtros en ambas UIs | Panel plegable con responsable, estado, rango de fechas e «incluir sin fecha»; contrato v2 con `filters`/`applied_filters`; **48 tests**; verificado con Playwright en las dos interfaces (19 → 15 → 9 → 6 barras según se acumulan filtros, rango invertido bloqueado, limpiar restaura) — capturas [backend](img/fase6_filtros_backend.png) y [website](img/fase6_filtros_website.png) | ✅ |

## 5.1 Versión 2 — edición y funciones «pro» (2026-08-17)

Encargada tras cerrar la v1: botón inteligente en el proyecto y diagrama
plenamente funcional, no de consulta.

| # | Fase | Entregable verificable | Estado |
|---|---|---|---|
| 7 | Botón inteligente en `project.project` | Botón «Gantt» con el contador de tareas planificadas que abre la acción acotada al proyecto, con salida a «Ver todos» — captura [botón](img/fase7_boton_inteligente.png) | ✅ |
| 8 | Capa de escritura (`apply_gantt_changes`) | Mover/redimensionar, renombrar, crear, borrar, reparentar, dependencias; permiso real por tarea; **20 tests** nuevos en el base | ✅ |
| 9 | Ruta crítica (CPM), línea base y reprogramación en cadena | CPM en Python con holguras y herencia a contenedoras; `al.gantt.baseline` inmutable con desvío; empuje de sucesoras sin comprimir el plan | ✅ |
| 10 | Edición en las dos interfaces | Verificado con Playwright: arrastre guardado en la base (backend y web), alta de tarea (13→14), ruta crítica (8 críticas), línea base con barra fantasma y columna de desvío — capturas [backend](img/fase7_pro_backend.png) y [website](img/fase7_pro_website.png) | ✅ |

**Decisiones de la v2** (validadas con el cliente):

- **Permisos nativos, sin grupo de edición propio**: se edita lo que el ORM
  deja editar (`_filtered_access('write')`), y `editable` viaja por tarea en el
  contrato.
- **El servidor manda**: si una escritura falla, la interfaz avisa y recarga; no
  se deja el diagrama mostrando algo que no está guardado.
- **Reprogramación en cadena**: la sucesora no empieza antes de que acabe su
  predecesora y conserva su duración; nunca se adelanta trabajo.
- **Website también editable**, con las mismas reglas y endpoints propios
  (`/gantt/apply`, `/gantt/baseline`).

### 5.2 Trampas encontradas en la v2

- **La edición MIT no permite capas propias**: el bundle hace
  `e.mixin(e, i.layersApi)` y acto seguido `delete e.addTaskLayer`. La línea
  base se dibuja inyectando la barra en el contenido de la tarea, con
  `overflow: visible` en `.gantt_task_content`.
- **Las expresiones de las plantillas OWL no ven los globales de JS** (ya visto
  en la fase 6): comparar con `String(...)` dentro de un `t-att` rompe el
  componente.
- El botón inteligente no se localiza por `.oe_button_box` en Odoo 19; el
  contenedor no conserva esa clase, sí `button.oe_stat_button`.

## 5.3 Versión 3 — paridad con las alternativas comerciales (2026-08-17)

Analizadas dos apps de Odoo Apps para 19.0 —`bryntum_gantt` (€890) y
`zt_gantt_app_project` (€96,58)— y comparadas con la suite. Lo que faltaba y se
implementó:

| # | Fase | Entregable | Estado |
|---|---|---|---|
| 11 | Herramientas de vista | Búsqueda rápida con contador, código EDT, expandir/contraer todo, ocultar terminadas, pantalla completa, marca de hoy, sombreado de no laborables desde `resource.calendar` y menú contextual (abrir en Odoo, subtarea, indentar, desindentar, eliminar). **81 tests**; verificado con Playwright: búsqueda 21→3 filas, EDT `1 / 1.1 / 1.2 / 2 / 2.1`, 105 celdas no laborables en escala Día, menú con 5 acciones y los estados deshabilitados correctos | ✅ |
| 12 | Páginas de descripción | `static/description/index.html` profesional para los tres módulos, con el sistema visual del repo — captura [descripción](img/fase11_pagina_descripcion.png) | ✅ |

### 5.4 Formulario de tarea y actividades (2026-08-17)

| # | Fase | Entregable | Estado |
|---|---|---|---|
| 13 | Formulario de tarea usable | Arreglado el «Periodo» (los estilos de Odoo apilaban los desplegables de fecha) y ampliado con etapa, responsables, prioridad, horas, etiquetas y avance; contrato **v4** con esos campos y sus opciones. Verificado guardando desde el diagrama: prioridad 0→3, etapa asignada y horas 69→12 en la base | ✅ |
| 14 | Actividades | Indicador de color en la rejilla según `activity_state`, resumen en el tooltip y **Planificar actividad** en el menú contextual, con el asistente nativo `mail.activity.schedule` | ✅ |

| 15 | Formulario con bloques propios | `algantt_daterange` (un `datetime-local` para inicio y otro para fin, en vez de seis desplegables) y `algantt_tokens` (badges con «×» y desplegable «Añadir…», como el widget many2many). Verificado: quitar un responsable desde el badge dejó 3 → 2 en la base — captura [formulario](img/fase13_formulario_despues.png) | ✅ |

Más límites de la edición MIT encontrados aquí: los bloques `time` y `duration`
editan las fechas con desplegables de día/mes/año y no existe `multiselect`;
por eso el formulario usa bloques propios. Ojo al registrarlos: su `render()`
debe devolver HTML sin espacios iniciales, o la librería falla al indexar los
hijos (`C.querySelector is not a function`).

### 5.5 Exportación (2026-08-17)

| # | Fase | Entregable | Estado |
|---|---|---|---|
| 16 | Excel y PDF | `build_matrix` común, `export_xlsx` (hojas «Tareas» y «Diagrama»), informe QWeb A3 apaisado y botones en las dos interfaces. **95 tests**; verificado descargando de verdad: XLSX de 9,6 KB con las dos hojas y PDF de 64 KB en una página A3 — captura [PDF](img/fase16_pdf.png) | ✅ |

La librería **sí** trae `exportToPDF`/`exportToExcel`, pero contra
`https://export.dhtmlx.com/gantt` (servicio del fabricante): se descartó por
privacidad y ambos formatos se componen en el servidor.

Trampas: un `%` suelto en una cadena de formato de QWeb rompe el render
(`incomplete format`) — el ancho de columna se concatena; y en los tests Odoo no
usa wkhtmltopdf, así que `_render_qweb_pdf` devuelve HTML.

### 5.6 Personas asignadas (2026-08-17)

Contrato **v5**: `filters.assignable_users` con **todas** las personas
asignables (mismo dominio que el campo `user_ids` de la tarea), separado de
`filters.users` —quienes ya tienen tareas—, que es lo que alimenta el filtro. El
formulario usa la primera y la etiqueta pasa a **«Personas asignadas»** en toda
la suite (formulario, filtro, tooltip y Excel). Verificado en pantalla: de 3
personas ofrecidas a las 15 internas activas. **98 tests**.

### 5.7 Asistente de IA (2026-08-17)

Cuarto módulo, **`al_project_gantt_ai`**: panel de chat lateral en el Gantt del
backend, opcional y desacoplado (parche + `t-inherit`; desinstalarlo deja el
diagrama intacto).

| # | Fase | Entregable | Estado |
|---|---|---|---|
| 17 | Chat y propuestas | `al.gantt.ai.ask()` (contexto resumido, prompt, validación), conector HTTP a **Anthropic u OpenAI**, panel OWL con propuestas revisables y ajustes en *Ajustes ▸ Gantt IA*. **129 tests** en la suite (35 nuevos) | ✅ |
| 18 | DeepSeek y acceso a los ajustes | Tercer proveedor (**DeepSeek**, compatible con *Chat Completions*), enlaces por proveedor a donde se crea la clave y a su lista de modelos, y menú **Gantt ▸ Configuración ▸ Ajustes**. **139 tests** en la suite (12 nuevos) | ✅ |

Las tres decisiones que definen el módulo:

1. **La IA no escribe.** Solo propone; el usuario marca y aplica, y la escritura
   pasa por `apply_gantt_changes()` — mismos permisos que arrastrar la barra.
2. **Solo lo que se ve, resumido.** El cliente manda ids; el servidor relee las
   tareas **sin `sudo`** y arma el resumen (nombre, fechas, estado, avance,
   dependencias y, opcionalmente, personas asignadas). Nada de descripciones,
   adjuntos ni datos de cliente.
3. **La salida del modelo es entrada no confiable.** `_normalize_proposal`
   descarta ids fuera del contexto, tareas sin permiso, fechas inválidas,
   inicio > fin, avances fuera de rango y personas inexistentes.

Las propuestas se piden con **tool use** (`propose_changes`, mismo esquema JSON
en los dos proveedores) para que lleguen estructuradas. Sin `strict`: cada API
lo compila con reglas distintas y la garantía la da la validación del servidor.

HTTP directo con `requests` en vez de los SDK de pip: el addon se despliega
copiando la carpeta y no obliga a tocar el entorno del servidor.

Verificado de extremo a extremo con un proveedor falso local que imita la
Messages API: pregunta → respuesta → propuesta → aplicar → dato guardado
— capturas [panel](img/gantt_ai_panel_abierto.png),
[propuesta](img/gantt_ai_propuesta.png) y [aplicado](img/gantt_ai_aplicado.png).
Comprobado también el caso «sin clave»: el botón no se pinta.

Sobre la fase 18: DeepSeek expone la misma interfaz que OpenAI, así que
comparten conector; lo único que cambia son la URL base y el nombre del campo
que limita la respuesta (OpenAI renombró `max_tokens` a
`max_completion_tokens`; DeepSeek conservó el original). Ambas cosas están
declaradas en constantes y hay un test que exige que **todo** proveedor del
`Selection` tenga sus metadatos, para que añadir uno nuevo no rompa los ajustes
en silencio. El modelo por defecto es `deepseek-chat` y no `deepseek-reasoner`:
todo depende de *function calling* y el de razonamiento no lo ha soportado de
forma estable.

Los enlaces de los ajustes usan el widget nativo `documentation_link`, que
acepta URL absoluta además de rutas de la doc de Odoo; se muestran u ocultan con
`invisible` según el proveedor elegido. El menú de ajustes sigue el patrón de
`crm.crm_config_settings_action` (contexto `{'module': ...}`); ojo, en v19
`target="inline"` ya **no** es un valor válido de `ir.actions.act_window`.

Trampas del entorno, las dos del mismo tipo: `ir.config_parameter` está cacheado
en el registro, así que borrar la clave por SQL no basta para ver el efecto; y
recargar el registro (`orm_signaling_registry`) **no** reimporta Python, de modo
que un `Selection` ampliado sigue rechazando el valor nuevo hasta reiniciar el
proceso. En ambos casos: reiniciar.

### 5.8 Salida a la ficha desde el formulario (2026-08-18)

| # | Fase | Entregable | Estado |
|---|---|---|---|
| 19 | Botón «Abrir en Odoo» en el formulario | El formulario del diagrama gana un botón que abre la ficha completa de la tarea; el backend navega con miga de pan y el website abre otra pestaña. **140 tests**; verificado con Playwright: botón visible, formulario cerrado y ficha abierta en `Gantt de Proyectos / Expediente técnico` — captura [formulario](img/gantt_lightbox_abrir_odoo.png) | ✅ |

El formulario del diagrama es corto a propósito (sin descripción —es HTML—, sin
chatter y sin adjuntos), así que necesitaba una salida explícita a la ficha en
vez de obligar a buscarla por el menú contextual. El módulo base no navega: la
interfaz pasa `openRecord` a `configureLightbox` y sin esa función el botón ni
se pinta.

Cómo se añade un botón al lightbox de la edición MIT, por si hace falta otro:
los nombres salen de `gantt.config.buttons_left` / `buttons_right`, la etiqueta
de `gantt.locale.labels[nombre]`, el nombre se usa además como **clase CSS** del
icono, y el clic llega por el evento público `onLightboxButton`. El id de la
tarea abierta está en `gantt.getState().lightbox`.

Trampa al verificar: el formulario se abre con doble clic **sobre la barra**, no
sobre la fila de la rejilla (ahí el doble clic despliega el árbol). Las filas de
proyecto y los hitos son `readonly` y no lo abren, así que esconder el botón en
ellas (clase `algantt-lb-no-open` desde `onBeforeLightbox`) es defensa en
profundidad, no el caso normal.

### Comparativa con las referencias

| Función | bryntum_gantt | zt_gantt | Esta suite |
|---|---|---|---|
| Edición inline y por popup | Sí | Sí | Sí |
| Dependencias | Sí (4 tipos) | — | Sí (solo FS, límite del M2M nativo) |
| Ruta crítica / línea base | Sí | — | Sí (CPM y baseline propios, en Python) |
| Auto-scheduling | Sí | — | Reprogramación en cadena en el servidor |
| Multiproyecto | Sí (máx. 5) | — | Sí, sin límite fijo |
| Búsqueda, EDT, pantalla completa | Sí | Parcial | Sí |
| Agrupar / favoritos | Sí | Sí | **No** |
| Recursos y calendarios laborales | Sí | — | Solo sombreado visual |
| Copiar/pegar, tareas divididas | Sí | — | **No** |
| Export PDF / Excel | Sí | — | **Sí**, generados en el servidor (el de la librería pasa por su servicio en la nube) |
| Export MS Project | Sí | — | No |
| Interfaz en el sitio web | — | — | Sí |
| Asistente de IA | — | — | Sí (opcional, Claude u OpenAI) |
| Coste de licencia | €890 | €96,58 | Propio (LGPL-3) |

Límites de la edición MIT confirmados leyendo el bundle: no trae `filterTask`,
`getWBSCode`, `addTaskLayer`, grouping, undo ni export; los plugins disponibles
son solo `tooltip`, `marker` y `fullscreen`. Lo que se pudo suplir se
implementó; lo que no, está declarado arriba.

## 6. Fuera del alcance actual

Un único tipo de dependencia (`FS`, límite del M2M nativo); sin calendarios
laborales (la cadena trabaja en tiempo natural, no en días hábiles) ni
histograma de recursos; sin *undo/redo* nativo ni exportación (el export de
dhtmlx Community va contra un servicio en la nube del fabricante, que enviaría
los datos del cliente a un tercero: descartado a propósito).

## 7. Referencias

- Contrato de datos y puntos de extensión: [`al_project_gantt_base/README.md`](../../al_project_gantt_base/README.md)
- Elección de librería y benchmark: [`FASE0_SPIKE.md`](FASE0_SPIKE.md)
