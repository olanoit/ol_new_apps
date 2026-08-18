# Fase 0 — Informe del spike (Gantt PRO)

> **Fecha:** 2026-08-03 · **Branch:** `19.0` · **Autor:** CRISTÓBAL OCH
> Contexto y arquitectura completa en [`PLAN_MODULO_gantt_pro.md`](PLAN_MODULO_gantt_pro.md).
> Este documento cierra la **Fase 0** de esa tabla: decisión de librería + PoC + benchmark.

## 1. Resultado en una frase

**Confirmado**: una vista Gantt nativa embebida en el webclient de Odoo (Opción A del
plan), cargada de forma perezosa con **dhtmlxGantt Community (MIT)**, renderiza 20.000
tareas en **~1,6 s** dentro del propio Odoo, sin errores de consola y sin depender de
Enterprise. La arquitectura propuesta en el plan queda validada; se corrigen dos datos
de la comparativa de librerías que estaban desactualizados (§2).

## 2. Corrección a la comparativa de librerías del plan

Al bajar el paquete real de cada librería (no solo su página de marketing) aparecieron
dos correcciones importantes, ya aplicadas en `PLAN_MODULO_gantt_pro.md` §4:

- **SVAR Gantt** (candidato original por defecto) **no tiene build vanilla**: solo se
  distribuye como `@svar-ui/react-gantt` / `vue-gantt` / `svelte-gantt` (paquetes npm
  ESM, sin bundle `<script>`). Además su edición MIT es más limitada de lo que parecía:
  solo timeline básico + drag-drop; ruta crítica, auto-scheduling, recursos y baselines
  son **PRO** (desde $749).
- **DHTMLX Gantt** se **relicenció de GPLv2 a MIT** (confirmado en el paquete
  `dhtmlx-gantt@10.0.0`, `LICENSE.md`) y su edición Community **sí** trae un build
  vanilla real: `codebase/dhtmlxgantt.js` es un UMD que expone `window.gantt` con un
  simple `<script>`, sin bundler. Su edición libre ya incluye dependencias (4 tipos +
  lag), grid, drag-drop y export PDF/PNG/Excel/iCal/MSP. Ruta crítica, auto-scheduling,
  recursos y baselines siguen siendo PRO (~$999+), igual que en SVAR.

**Decisión**: se usa **DHTMLX Gantt Community (MIT)** como base del PoC y de las
Fases 1-2 (MVP). La decisión de pagar PRO (DHTMLX o Bryntum) se pospone a la Fase 3,
que es exactamente donde el plan ya preveía necesitar ruta crítica/baselines/recursos/
auto-scheduling — ver `PLAN_MODULO_gantt_pro.md` §4.2 y §9.

## 3. Qué se construyó

Módulo `ol_project_gantt_pro/` (marcado en su manifest como spike, "no usar en
producción"):

```
ol_project_gantt_pro/
├── __manifest__.py                        # depends: ['web'] únicamente
├── controllers/gantt_pro_data.py          # /ol_project_gantt_pro/spike_data?size=N
├── static/src/
│   ├── gantt_pro_spike_action.js          # registry.category("actions"), loadJS/loadCSS perezoso
│   ├── gantt_pro_spike_action.xml
│   └── lib/dhtmlx/dhtmlxgantt.{js,css}    # vendorizado desde npm dhtmlx-gantt@10.0.0 (MIT)
└── views/gantt_pro_spike_menu.xml         # action + menú de prueba
```

- La vista es una **client action de OWL** (no un tipo de vista de modelo todavía —
  eso llega en la Fase 2 cuando haya que editar `project.task` real). Suficiente para
  validar el mecanismo de carga y medir rendimiento puro de renderizado.
- El controlador genera datos **sintéticos en memoria** (sin tocar el ORM/Postgres a
  propósito, para aislar el costo de renderizado del costo de lectura — ver plan §6).
- **Ningún dato ni dependencia de Enterprise**: `depends: ['web']`, cero referencias a
  `web_gantt`.

## 4. Instalación (verificación de compatibilidad)

Instalado con `odoo-bin -i ol_project_gantt_pro --stop-after-init` sobre `ol_pe_v19`
(BD de pruebas del repo, `addons_path` incluye Community + `ee19` + este repo): **0
errores**, 34 queries, módulo cargado en 0,75 s. El único warning en el log es de
`al_l10n_pe_account_letter` (preexistente, no relacionado).

No se probó instalación con Enterprise *activado* en la BD (la Fase 0 no lo requería:
basta con que el módulo no dependa de nada EE-exclusivo, lo cual está garantizado por
`depends: ['web']`). Queda como parte de la Fase 8 (documentación/instalación) probar
explícitamente sobre una BD con `web_gantt` instalado, para confirmar que ambas vistas
conviven sin colisión de nombres.

## 5. Benchmark

Metodología: usuario de prueba desechable creado y luego eliminado en `ol_pe_v19`;
servidor Odoo temporal en un puerto aparte (no se tocó el servidor de desarrollo que
ya tenías corriendo); navegador Chromium headless (Playwright) automatizando clics
reales sobre el botón de cada tamaño; sin caché de librería entre mediciones de la
primera carga.

| Tamaño | Fetch datos sintéticos | `gantt.parse` (construcción interna) | Hasta el próximo frame pintado |
|---:|---:|---:|---:|
| 500 tareas | 32 ms | 236 ms | 246 ms |
| 5.000 tareas | 190 ms | 556 ms | 563 ms |
| 20.000 tareas | 425 ms | 1.637 ms | **1.645 ms** |

- Carga de la librería (`loadJS`+`loadCSS`, ~627 KB JS + 143 KB CSS sin minimizar aparte):
  **~1-70 ms** una vez cacheada por el navegador; el costo real está en la primera
  descarga (tamaño de bundle), no en el parseo/ejecución.
- **0 errores de consola** en las tres corridas.
- Captura de pantalla del caso más pesado (20.000 tareas, WBS de 2 niveles, grid +
  timeline + dependencias dibujadas) en [`img/fase0_poc_20000_tareas.png`](img/fase0_poc_20000_tareas.png).

### Lectura de los números

Confirma lo que argumentaba el plan en §3.2 y §6: **el renderizado no es el cuello de
botella** — dhtmlxGantt virtualiza filas/columnas y pinta 20k tareas en menos de 2
segundos corriendo dentro del webclient de Odoo, sin ayuda de ningún backend Node ni
framework aparte. El crecimiento del *fetch* (32→190→425 ms) es lineal con el tamaño
del JSON, coherente con lo esperado; en producción ese tramo es el que hay que vigilar
cuando la fuente sea `project.task` real vía ORM en vez de datos sintéticos en memoria
(Fase 1).

## 6. Riesgos confirmados / descartados

| Riesgo (del plan §6) | Estado tras el spike |
|---|---|
| Bundle JS penaliza el arranque del webclient | **Descartado**: `loadJS`/`loadCSS` perezoso funciona tal cual estaba diseñado; el bundle solo se pide al montar la acción |
| Formato de distribución de la librería (¿hace falta build propio?) | **Resuelto a favor**: dhtmlxGantt Community trae UMD real, cero bundler necesario (a diferencia de SVAR, descartado por esto — ver §2) |
| Render sin virtualización = UI congelada | **Descartado**: 20k tareas en 1,6 s, confirma que la virtualización de la librería alcanza |
| Techo de tareas por proyecto "cientos a pocos miles" (estimado en el plan) | **Ajustar al alza**: el render puro aguanta 20k+ sin problema; el techo real dependerá del *fetch* desde Postgres/ORM con datos reales, no del cliente — a medir en la Fase 6 con datos reales |

## 7. Siguiente paso

Fase 1 del plan: modelo de datos (`gantt.pro.dependency`, `gantt.pro.baseline`) y
contrato de lectura/escritura contra `project.task` real, reemplazando el generador
sintético del controlador de este spike.
