# Plan del módulo `ol_project_gantt_pro` — Vista de Gantt PRO

> ⚠️ **SUPERADO (2026-08-17).** Este plan describe un módulo único
> (`ol_project_gantt_pro`) que registraba su propio tipo de vista en el registry
> de OWL. **Su código no existe** en el repositorio: ni en `19.0`, ni en otra
> rama, ni instalado en `ol_pe_v19` — solo quedaron estos documentos.
> El desarrollo vigente es la suite de tres módulos
> [`PLAN_SUITE_al_project_gantt.md`](PLAN_SUITE_al_project_gantt.md)
> (`al_project_gantt_base` + `_backend` + `_website`).
> De aquí se conservan como válidos: la comparativa de librerías (§4), la
> decisión por dhtmlxGantt Community MIT, el benchmark de la Fase 0 y el
> análisis de rendimiento (§6).

> **Fecha:** 2026-08-03 · **Branch:** `19.0` · **Autor:** CRISTÓBAL OCH
> **Nombre técnico propuesto:** `ol_project_gantt_pro` (por confirmar — ver §9)
> **Referencia comercial:** [bryntum_gantt](https://apps.odoo.com/apps/modules/19.0/bryntum_gantt) (Bryntum AB, €890, Odoo 13-19)
> **Referencia de producto:** [Bryntum Gantt — ejemplo Advanced](https://bryntum.com/products/gantt/examples/#example-advanced)
> **Referencia de documentación:** [odoo-gantt-docs.bryntum.com](https://odoo-gantt-docs.bryntum.com/) — ver §8
> **Compatibilidad requerida: Community Y Enterprise.** El repo de trabajo (`odoo/ce19`) es
> Community, pero el módulo **no debe depender de nada exclusivo de CE ni de EE** — debe
> instalar y funcionar igual en ambas ediciones (y en Odoo.sh).

## 1. Contexto

Los clientes de proyectos/construcción (varios ya en cartera: `al_hr_pe_construction`,
`al_hr_pe`) necesitan planificar tareas con dependencias, ruta crítica y carga de recursos.
Odoo Community no ofrece vista Gantt (`web_gantt` es un addon de Enterprise); Enterprise sí
la trae, pero es limitada frente a lo que ofrece `bryntum_gantt`. La alternativa comercial
demuestra que el mercado paga por esto **como módulo nativo de Odoo**, no como app separada,
y que **funciona igual en las tres modalidades de despliegue**: Enterprise (vía Apps Store),
Community (instalación manual del addon) y Odoo.sh — las tres cubiertas en su guía de
instalación (§8.1, fila 2).

**Implicación de diseño**: el módulo no puede depender de `web_gantt` (EE) ni de ningún
otro addon exclusivo de Enterprise — debe registrar su **propia** vista/tipo de vista en
el registry de OWL, igual que hace `bryntum_gantt`. En una instalación Enterprise convive
sin conflicto con la vista Gantt nativa (son vistas distintas, con nombres de vista
distintos); no la reemplaza salvo que el usuario elija usarla en sus acciones.

Este documento analiza **dónde debe vivir el código** (acoplado al webclient de Odoo vs.
aplicación externa que consume la API de Odoo), qué **librería Gantt** usar, qué
**documentación** debe entregar el módulo (calcada de la referencia), y propone un
**desarrollo por fases** verificables, siguiendo el mismo formato que
[`docs/sire/PLAN_MODULO_al_l10n_pe_sire.md`](../sire/PLAN_MODULO_al_l10n_pe_sire.md).

## 2. Qué hace el módulo de referencia (`bryntum_gantt`)

Investigado en la ficha de Odoo Apps (2026-08-03):

- **Arquitectura**: se embebe **dentro del webclient de Odoo** como una vista JS más
  (no es una app externa ni un iframe a otro dominio). Antes usaba Vue, migrado a JS
  vanilla + la librería Bryntum Gantt (≥ 6.1.5).
- **Dependencias Odoo**: solo módulos **Community** — `project`, `hr`, `mail`. Nada de
  Enterprise. Esto confirma que **no hace falta** `web_gantt` (EE) para lograrlo.
- **Funciones**: edición inline y por popup, dependencias/restricciones/baselines/ruta
  crítica, multi-proyecto (máx. 5 simultáneos), scheduling automático con drag-drop en
  cadena, histograma de recursos, calendarios, export PDF/Excel/MSP, modo oscuro,
  toolbar configurable, estado de vista por usuario.
- **Tamaño**: 2.765 líneas de código propias (la librería Bryntum es aparte, cargada
  como asset).
- **Comercial**: Bryntum AB es *dueño de la librería y del módulo* — no hay problema de
  licencia porque el publisher y el fabricante son la misma empresa (ver §4.3).

## 3. Decisión de arquitectura: ¿acoplado a Odoo o app externa?

### 3.1 Opciones evaluadas

| | **A. Nativo en Odoo** (vista OWL embebida en el webclient) | **B. App externa** (SPA propia + API Odoo) | **C. Híbrido** (SPA en `<iframe>` dentro de una acción Odoo) |
|---|---|---|---|
| Autenticación | Reusa sesión Odoo (`session_id`), sin fricción | Hay que puentear login (cookie de sesión, API key u OAuth) | Iframe hereda cookies del mismo dominio; posible sin duplicar auth si se sirve bajo el mismo host/subpath |
| Permisos | `ir.rule`/`ir.model.access` nativos, multicompañía gratis | Hay que replicar la lógica de acceso en la capa externa (riesgo de divergencia) | Igual que A si las lecturas pasan por RPC/controladores Odoo |
| UX | Breadcrumbs, menú, systray, `discuss`, todo integrado | Salto de página, spinner propio, deep-linking manual | Integrado visualmente pero con "costura" de iframe (scroll, tamaño, atajos de teclado) |
| Stack / velocidad de desarrollo | JS vanilla o wrapper ligero sobre OWL; sin build propio si se usa `loadJS` | Libertad total (React/Vite, wrapper oficial de Bryntum para React) | Libertad total en el SPA, pero sigue atado al ciclo de despliegue de Odoo si se sirve desde el mismo módulo |
| Infraestructura | Cero: vive en el mismo `assets_backend` | Nuevo servicio, dominio/subdominio, CI/CD, TLS propios | Puede sea servido como asset estático del propio módulo (build embebido), sin infra nueva |
| Rendimiento | Los datos igual viajan por JSON-RPC al mismo Odoo; sin salto de red extra | Un hop adicional si la app externa no está co-ubicada con Odoo | Igual que A si el iframe llama a los mismos controladores |
| Empaquetado/venta como app Odoo | Directo (así vende `bryntum_gantt`) | No calza con "módulo de Odoo Apps" — sería otro producto | Posible, pero añade complejidad sin beneficio claro aquí |

### 3.2 Por qué el rendimiento **no** favorece la app externa

La preocupación de "por eficiencia, ¿mejor desacoplar?" parte de un supuesto que no aplica
aquí: **Bryntum Gantt (y sus alternativas) ya son motores de renderizado 100% client-side**
con virtualización de filas/columnas — soportan decenas de miles de tareas en el navegador
sin ayuda de un backend Node ni de un framework "moderno" particular. El renderizado no
mejora por sacarlo de Odoo.

El cuello de botella real, en cualquiera de las 3 opciones, es el **mismo**: la
transferencia de datos desde PostgreSQL/ORM de Odoo hacia el cliente (tareas, dependencias,
calendarios, recursos). Ese costo:

- Se paga igual si el fetch lo hace un componente OWL (`this.orm.call`) o un SPA externo
  (JSON-RPC/REST contra el mismo Odoo) — **es la misma consulta al mismo Postgres**.
- Solo empeora en la opción B si la app externa **no está co-ubicada** con el servidor Odoo
  (latencia de red adicional en cada operación de guardado/scroll de calendario).
- Se resuelve con las mismas técnicas sin importar dónde viva el cliente: `read_group`/
  `search_read` con `fields` acotados, evitar N+1 en dependencias/recursos, e índices en
  PostgreSQL — igual que se hizo en [`ol_stock_kardex_pe`](../kardex/ANALISIS_RENDIMIENTO.md)
  con vistas SQL y *window functions* para volumen alto.

**Conclusión: la Opción A (nativo, embebido en el webclient) es la correcta.** No sacrifica
rendimiento, evita duplicar autenticación/permisos/infraestructura, y es el patrón que ya
valida el mercado (`bryntum_gantt` funciona así). La Opción C queda como salida de escape
únicamente si en el Phase 0 (spike) se descubre que el bundle de la librería elegida es
inviable de cargar dentro de `assets_backend` incluso con *lazy load* — no se anticipa.
La Opción B solo tendría sentido si el objetivo cambiara a un **producto SaaS multi-tenant
independiente de Odoo**, que no es el caso planteado.

### 3.3 Consecuencia técnica de la Opción A

- Vista nueva registrada en el `registry` de OWL (`registry.category("views").add("gantt_pro", ...)`),
  con su propio *Renderer/Controller/ArchParser*, siguiendo el patrón de cualquier vista
  custom de Odoo (no depende de `web_gantt` de Enterprise).
- La librería Gantt se carga con `loadJS`/`loadCSS` **de forma perezosa**, solo cuando se
  monta esa vista — no entra en el bundle general de `web.assets_backend` para no penalizar
  el arranque del webclient en el resto de la instalación.
- Ya existe prior art de este patrón en Odoo Community: **OCA `web_timeline`** (repo
  `OCA/web`) registra un tipo de vista propio que envuelve `vis-timeline` sin depender de
  Enterprise. Sirve como referencia de *cómo engancharse al registry de vistas*, aunque su
  librería de base (vis-timeline) es mucho más simple que un Gantt con dependencias/ruta
  crítica.

## 4. Elección de librería Gantt

### 4.1 Comparativa

**Corregido en la Fase 0** (2026-08-03) tras verificar cada librería contra su npm/GitHub/
página de precios real — la primera versión de esta tabla tenía datos desactualizados,
en particular sobre SVAR y DHTMLX:

| Librería | Licencia edición libre | Framework | Dependencias/export en la edición libre | Ruta crítica/baselines/recursos/auto-scheduling/undo-redo | Costo PRO |
|---|---|---|---|---|---|
| **Bryntum Gantt** | Ninguna (100% comercial) | Vanilla/React/Vue/Angular, build UMD oficial | — | Sí, completo (es el estado del arte, incluye lo del ejemplo "Advanced") | ~$1.290+/dev/año |
| **DHTMLX Gantt** (`dhtmlx-gantt`, npm) | **MIT** (relicenciado desde GPLv2; confirmado en el paquete `10.0.0`) | **Vanilla**, `codebase/dhtmlxgantt.js` es un UMD real, `<script>`-listo, sin bundler | Sí: 4 tipos de dependencia (FS/SS/FF/SF) con lag, grid, drag-drop, **export PDF/PNG/Excel/iCal/MSP ya en la edición libre** | Solo PRO | ~$999+/dev |
| **SVAR Gantt** (`@svar-ui/*`, ex-equipo DHTMLX) | **MIT**, pero **sin build vanilla** — solo React/Vue/Svelte | React/Vue/Svelte únicamente (paquetes `@svar-ui/react-gantt` etc.) | Solo timeline básico + drag-drop | Ruta crítica, auto-scheduling, recursos y baselines son **PRO** (desde $749) | ~$749+ |
| **Frappe Gantt** | MIT | Vanilla, build UMD vía jsDelivr | Sin dependencias tipadas ni ruta crítica | No | — |

### 4.2 Recomendación (revisada tras la Fase 0)

**DHTMLX Gantt Community (MIT) es la mejor base para el PoC y el MVP (Fases 0-2)**: es la
única opción con build **vanilla real listo para `<script>`** (sin paso de build propio,
confirmado extrayendo el paquete npm — ver §0 más abajo) *y* con dependencias + export ya
en la edición gratuita, algo más rico que lo que ofrece el "MIT" de SVAR (que en su edición
libre es solo timeline básico) o Frappe (sin dependencias).

La brecha de **DHTMLX Community** frente al ejemplo "Advanced" de Bryntum —ruta crítica,
auto-scheduling, baselines, histograma de recursos, undo/redo— coincide exactamente con lo
que cubre la **Fase 3** del plan (§7). Esa fase es, por tanto, el punto natural donde se
decide y presupuesta la licencia PRO: **DHTMLX PRO (~$999+, mismo vendor, cero migración)**
o **Bryntum (~$1.290+, más completo pero requiere reescribir la capa de integración)**. No
hace falta cerrar esa decisión ahora — el PoC ya es útil y funcional con la edición libre.

**SVAR queda descartado como base por defecto**: su edición MIT es más limitada de lo que
parecía (sin ruta crítica ni recursos) y, al no tener build vanilla, habría exigido meter
React (o Vue/Svelte) + un bundler dentro de la arquitectura de carga perezosa — complejidad
extra sin compensación, ya que sus features PRO son pagas igual que las de DHTMLX/Bryntum.

### 4.3 Ojo con la reventa de Bryntum

`bryntum_gantt` no tiene fricción de licencia porque **Bryntum AB es el propio publisher**
en Odoo Apps. Si este módulo usa la librería Bryntum y se **vende a terceros**, hay que
respetar los términos de licencia de Bryntum (es por developer/deployment, no por "úsalo y
redistribúyelo libremente" dentro de un módulo que se revende). Lo mismo aplica a **DHTMLX
PRO** si en algún momento se activa (licencia comercial por developer). La edición
**DHTMLX Community (MIT)** sí se puede vendorizar y redistribuir libremente dentro del
módulo sin fricción — es la base elegida para el PoC precisamente por esto.

## 5. Arquitectura técnica propuesta

```
ol_project_gantt_pro/
├── __manifest__.py            # depends: web, project — 100% Community; no depende de web_gantt (EE)
├── models/
│   ├── project_task.py        # gantt_pro_date_start/end, gantt_pro_duration (compute+inverse), gantt_pro_progress
│   ├── gantt_pro_dependency.py    # gantt.pro.dependency: task_id/depends_on_id, type (FS/SS/FF/SF), lag — sincroniza depend_on_ids nativo
│   ├── gantt_pro_baseline.py      # gantt.pro.baseline (+ .baseline.line): snapshot inmutable de fechas/avance
│   └── project_project.py         # get_gantt_pro_data() / apply_gantt_pro_changeset() / action_gantt_pro_create_baseline()
├── controllers/
│   └── gantt_pro_data.py      # /ol_project_gantt_pro/spike_data — solo para el benchmark de la Fase 0, datos sintéticos
├── static/src/
│   ├── gantt_pro_spike_action.js  # client action OWL del spike (Fase 0), carga perezosa de dhtmlxGantt
│   ├── gantt_pro_spike_action.xml
│   └── lib/dhtmlx/             # dhtmlxGantt Community vendorizado (MIT) — ver docs/gantt/FASE0_SPIKE.md
├── views/gantt_pro_spike_menu.xml
├── security/ir.model.access.csv
├── tests/test_gantt_pro.py    # 5/5: serialización, round-trip de changeset, sync M2M, inmutabilidad de baseline
└── docs/  (pendiente: guía funcional del módulo, ver §8)
```

**Nota (Fase 1)**: Community ya trae `depend_on_ids`/`dependent_ids` (M2M nativo,
`task_dependencies_rel`) y `parent_id`/`child_ids` para el WBS — no hacía falta
reinventarlos. `gantt.pro.dependency` es solo la capa que agrega tipo (FS/SS/FF/SF) y
retraso, que el M2M nativo no tiene; sus `create`/`write`/`unlink` mantienen
`depend_on_ids` sincronizado para que el resto de Odoo (formulario de tarea, etc.) siga
viendo el mismo dato. `gantt_pro_calendar.py` (puente a `resource.calendar`) se pospuso:
no era necesario para el contrato de lectura/escritura de la Fase 1 y no hay todavía un
caso de uso concreto que lo requiera — se retoma si la Fase 3 (calendarios de no
laborables) lo necesita.

**Flujo de datos**: la vista llama `this.orm.call('project.project', 'get_gantt_pro_data',
[project_id])`, que devuelve el proyecto de datos en el formato que espera la librería.
Al guardar, la librería
emite un *changeset* (added/updated/removed por store) que se traduce a `write`/`create`/
`unlink` por lote sobre `project.task` y `gantt.pro.dependency` — sin tabla intermedia que
duplique el dato (mismo principio que kardex: **no poblar lo que se puede derivar/mapear al
vuelo**).

## 6. Análisis de rendimiento

| Capa | Riesgo | Mitigación |
|---|---|---|
| Bundle JS de la librería Gantt (~500 KB–2 MB minificado) | Si entra en `web.assets_backend`, penaliza el arranque de **todo** el webclient | `loadJS`/`loadCSS` diferido, solo al montar la vista `gantt_pro`; asset propio no incluido en el bundle general |
| Lectura de tareas + dependencias + recursos | N+1 si se resuelven relaciones una por una | `search_read`/`read_group` con `fields` acotados, `prefetch` por lote (mismo patrón que los campos calculados de `l10n_pe.kardex.line`) |
| Escritura (drag-drop / resize masivo) | Un `write` por tarea movida en cadena (auto-scheduling) genera muchas escrituras individuales | Traducir el *changeset* de la librería a `write` por lote (`browse(ids).write(...)` agrupado por los mismos valores, o `create`/`write` en una sola llamada RPC con el lote completo) |
| Multi-proyecto (portafolio, como el límite de 5 de `bryntum_gantt`) | Cargar N proyectos completos puede ser pesado si N y el volumen de tareas son grandes | Límite configurable de proyectos simultáneos (igual que la referencia) + paginación por fecha visible (rango de calendario) en vez de cargar todo el historial |
| Render en el navegador | Miles de tareas sin virtualización = UI congelada | Cubierto por la librería (SVAR/Bryntum ya virtualizan filas/columnas); no requiere trabajo propio |
| Volumen extremo (portafolio de toda la compañía, decenas de miles de tareas) | El ORM de Odoo empieza a doler para agregaciones amplias | Igual que en kardex: si se llega a ese punto, mover la agregación a una **vista SQL** (`_auto = False`) en vez de Python — no diseñar esto de entrada, solo si el spike de Fase 0 lo justifica |

**Techo esperado sin optimizaciones especiales**: cientos a pocos miles de tareas por
proyecto con fluidez (rango típico de un proyecto de construcción/servicios). Portafolios
más grandes requieren las mitigaciones de la fila anterior, a validar con datos reales en
la Fase 6.

## 7. Fases

| # | Fase | Entregable verificable | Estado |
| --- | --- | --- | --- |
| 0 | Spike: elegir librería, verificar formato de distribución, PoC de vista OWL con `loadJS` perezoso, benchmark con datos sintéticos (500/5.000/20.000 tareas) | [`docs/gantt/FASE0_SPIKE.md`](FASE0_SPIKE.md): DHTMLX Community (MIT) elegido, PoC instalado en `ol_pe_v19` sin depender de EE, 20.000 tareas renderizadas en 1,6 s, 0 errores de consola | ✅ |
| 1 | Modelo de datos y contrato backend (`gantt.pro.dependency`, `gantt.pro.baseline`, `project.get_gantt_pro_data()`/`apply_gantt_pro_changeset()`) | `tests/test_gantt_pro.py`: 5/5 tests en verde — serialización, round-trip de changeset sin pérdida de datos, sync con `depend_on_ids` nativo, inmutabilidad de baseline | ✅ |
| 2 | Vista MVP embebida (grid + timeline, drag/resize, edición inline, guardado) | Verificado con Playwright de punta a punta (login → botón "Gantt PRO" → crear tarea → guardar → recarga → `SELECT` en Postgres confirma la fila en `project_task`); 0 errores de consola | ✅ |
| 3 | Scheduling avanzado **sin licencia PRO** (decisión del negocio, ver abajo): ruta crítica propia (CPM en Python), comparación contra línea base | 12 tests nuevos en verde (CPM puro + integración); verificado con Playwright: cadena de dependencias resaltada en rojo con holgura 0, tarea sin conexión con holgura > 0 y sin resaltar, columnas de línea base/desvío correctas | ✅ (parcial — ver huecos) |
| 4 | Multi-proyecto y recursos (vista portafolio, histograma de recursos, `resource.calendar`) | Vista combinada de varios proyectos con carga de recursos visible | Pendiente |
| 5 | Exportables (PDF/PNG, Excel, impresión; MSP si el negocio lo pide) | Exportar un proyecto a PDF y Excel desde la UI | Pendiente |
| 6 | Endurecimiento de rendimiento a escala | Prueba de carga con dataset real grande; techo documentado y, si aplica, vista SQL de agregación | Pendiente |
| 7 | Pulido, theming, licenciamiento y empaquetado | Módulo listo para instalar (README, demo data); decisión de licencia (SVAR vs Bryntum) cerrada y documentada | Pendiente |
| 8 | Documentación completa (§8) para EE, CE y Odoo.sh | Los 9 bloques de §8.1 publicados en `docs/gantt/` y enlazados desde el README del módulo | Pendiente |

## 8. Documentación del módulo (calcada de la referencia)

`bryntum_gantt` publica su manual completo en un sitio dedicado
([odoo-gantt-docs.bryntum.com](https://odoo-gantt-docs.bryntum.com/)) y **no** como un único
README — es lo que hace que un usuario final pueda auto-servirse sin abrir un ticket. Este
módulo debe entregar el mismo nivel de detalle, adaptado a Community **y** Enterprise.

### 8.1 Estructura a replicar

Relevada de la referencia (2026-08-03):

| # | Bloque | Contenido | Dónde vive en este repo |
| --- | --- | --- | --- |
| 1 | **FAQ** | Licenciamiento, compra, upgrades de versión | `docs/gantt/FAQ.md` |
| 2 | **Guía de instalación** | 3 escenarios: **Enterprise** (Apps Store), **Community** (instalación manual del addon), **Odoo.sh** (deploy vía repo) | `docs/gantt/INSTALACION.md` |
| 3 | **Guía de usuario — primeros pasos** | Cómo entrar a la vista Gantt (2 caminos); layout de dos paneles: grid (metadata editable) a la izquierda, timeline visual a la derecha | `docs/gantt/GUIA_USUARIO.md` |
| 4 | **Referencia de la toolbar** | Cada ícono de la barra de herramientas (crear tarea, undo/redo, zoom, selector de proyecto, buscar, pantalla completa, ...) | `docs/gantt/GUIA_USUARIO.md#toolbar` |
| 5 | **Gestión de columnas del grid** | Reordenar (drag-drop), filtrar, ordenar, mostrar/ocultar columnas | `docs/gantt/GUIA_USUARIO.md#columnas` |
| 6 | **Ajustes de UI y features** | Altura de fila, márgenes de barra, duración de animación; toggles de features (dependencias, ruta crítica, baselines, rollups, export MSP/Excel, ...) | `docs/gantt/CONFIGURACION.md` |
| 7 | **Configuración de backend** | Auto-scheduling, modo solo-lectura, cálculo de WBS, calendario por defecto, JSON de configuración avanzada del Gantt y del calendario | `docs/gantt/CONFIGURACION.md#backend` |
| 8 | **Menú contextual** | Acciones de clic derecho en grid y en timeline: copiar/cortar/pegar con subtareas, filtrar por valor de columna, agregar hito/subtarea, indentar/desindentar, dividir tarea (timeline) | `docs/gantt/GUIA_USUARIO.md#menu-contextual` |
| 9 | **Diálogo de propiedades de tarea** | 5 pestañas: General (nombre, % completado, esfuerzo, fechas, duración), Predecesoras (tipo SS/SF/FS/FF + lag), Sucesoras, Recursos (asignación con % de unidad), Avanzado (calendario, modo de scheduling, 9 tipos de restricción, límites de proyecto, effort-driven, rollup, inactiva, manual) | `docs/gantt/GUIA_USUARIO.md#propiedades-de-tarea` |

### 8.2 Bloques adicionales (brecha detectada frente a la referencia)

La documentación de Bryntum es fuerte en UI/configuración pero floja en operación e
integración — se agregan estos bloques, útiles para un equipo que da soporte propio (a
diferencia de Bryntum, que deriva soporte a su foro):

- **Troubleshooting**: errores comunes (permisos, datos inconsistentes tras un `unlink`
  manual, conflictos de dependencias circulares) y cómo diagnosticarlos.
- **Integración con otros módulos**: `hr_timesheet` (horas reales vs. planificadas),
  `project` (milestones nativos), `resource` (calendarios de no-laborables).
- **Atajos de teclado**.
- **Matriz de permisos/accesos**: qué `ir.rule`/grupo ve o edita qué en el Gantt.
- **Guía de rendimiento**: el techo de tareas/proyecto documentado en §6, y cuándo activar
  las mitigaciones de escala.
- **Glosario**: WBS, ruta crítica, baseline, rollup, effort-driven, etc. (útil para el
  usuario final no familiarizado con jerga de gestión de proyectos).

### 8.3 Cuándo se escribe

No se redacta de una sola vez al final: cada fase de §7 que agrega una feature (3, 4, 5)
debe cerrar con la sección de documentación correspondiente ya actualizada (igual que el
resto de módulos de este repo — ver `al_l10n_pe_sire/docs/`). La Fase 8 es la consolidación
final, no el punto de partida.

## 9. Decisiones abiertas

- **Licencia PRO (DHTMLX ~$999+ o Bryntum ~$1.290+)**: decidido en la Fase 3 — **no
  comprar por ahora**. Se construyó lo posible con recursos propios (ruta crítica vía CPM
  en Python, comparación contra línea base por columnas) y quedan como huecos conocidos,
  pendientes de esa decisión de negocio: auto-scheduling real (mover tareas dependientes
  automáticamente al arrastrar), histograma de recursos, calendarios de no laborables,
  undo/redo nativo, selección múltiple con arrastre. Confirmado además con el propio
  código fuente MIT de `dhtmlx-gantt@10.0.0` (no solo la web de marketing): esas funciones
  ni siquiera están incluidas en el paquete Community — no es un candado de licencia, el
  código simplemente no está.
- **Nombre técnico del módulo**: `ol_project_gantt_pro` es tentativo; confirmar antes de
  la Fase 1 (afecta el prefijo de todos los modelos/vistas).
- **Alcance multi-compañía**: se asume que hereda las reglas de `project.project`/
  `project.task` sin reglas nuevas; confirmar si el negocio necesita algo distinto.
- **Convivencia con `web_gantt` en Enterprise**: por defecto el módulo no toca las acciones
  que ya usan la vista Gantt nativa de EE; confirmar si en algún momento se debe ofrecer
  reemplazarla (o dejar ambas como alternativas seleccionables).

## 10. Referencias

- Informe de la Fase 0 (spike, decisión de librería, benchmark): [`docs/gantt/FASE0_SPIKE.md`](FASE0_SPIKE.md)
- Ficha comercial: <https://apps.odoo.com/apps/modules/19.0/bryntum_gantt>
- Ejemplos de producto: <https://bryntum.com/products/gantt/examples/#example-advanced>
- Documentación técnica de la referencia: <https://odoo-gantt-docs.bryntum.com>
- Prior art de vista custom en Odoo Community: repo `OCA/web`, módulo `web_timeline`
- Análisis de rendimiento hermano (mismo patrón de razonamiento): [`docs/kardex/ANALISIS_RENDIMIENTO.md`](../kardex/ANALISIS_RENDIMIENTO.md)
