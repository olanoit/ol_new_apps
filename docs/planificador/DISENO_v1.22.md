# Diseño del paquete 1.22 · Portal de obra según la vertical de la obra

Requerimiento: `docs/md/ALTA_Planificacion_Paquete_1.22_Portal_Obra_Vertical.pdf`
(versión 2, 17-nov-2026), M122-01 a M122-10 y el anexo A (D1 y D2 del 1.17).

Se entrega en el orden propuesto: etapa 1 (M122-01 a M122-04 y M122-10) con D1 y
D2, y etapa 2 (M122-05 a M122-09) en el puente nuevo
`al_construction_portal_furniture`.

## 1. Ubicación (ARQUITECTURA_COMUN, sección 4)

| Qué | Capa | Módulo |
|---|---|---|
| Funciones, nombres, «Avance» agrupado y ficha de la obra | Portal, común | `al_construction_portal` |
| Catálogo de motivos con el uso «Re-trabajo» y motivos por perfil | Núcleo | `al_construction_planner` |
| Líneas de re-trabajo de la liquidación | Puente de contratas | `al_construction_planner_subcontract` |
| Funciones de campo de mobiliario | Puente del portal con mobiliario | `al_construction_portal_furniture` |
| D1 y D2 | Puente de Ventas | `al_construction_planner_sale` |

No hay condiciones por vertical: el portal pregunta por las funciones del perfil de
la obra, por la función de cada nivel y por el catálogo de etapas.

## 2. Etapa 1

### M122-01 · Funciones según el perfil de la obra

| Qué | Dónde |
|---|---|
| Funciones activas de la obra: perfil de la obra; sin él, el de la compañía; sin ninguno, todas | `al_construction_portal/models/portal_service.py:133` (`_portal_features`) |
| Qué campo del perfil gobierna cada función; los puentes suman las suyas | `portal_service.py:118` (`_portal_feature_fields`) |
| Un servicio de una función apagada responde 422 con su mensaje | `portal_service.py:147` (`_portal_require`); lo llaman `progress`, `daily_report`, `crew_day`, `resident_progress`, `close_day` y `deduction` |
| `sync` envía `features` y omite `daily`, `crew`, la bandeja de avances y los deductivos y el fondo de `valuations` | `portal_service.py` (`sync`, `valuations`, `valuation`); `resident_service.py`, `resident_records.py` |
| Inicio y barra con los accesos de las funciones activas; registro de mosaicos, pantallas y acciones para los puentes | `static/app/app.js:507` (`portal`) y `:2850` (`window.ObraPortal`) |

### M122-02 · Nombres de la obra

| Qué | Dónde |
|---|---|
| `sync` envía `levels` (los nombres de la plantilla, sin la marca «(Nn)») y cada línea su `level_name` | `portal_service.py:327` (`_level_terms`) y `:350` (`_lines_tree`) |
| Textos sin «partida»: términos generales o el nombre del nivel con etapas de la obra | `app.js:82` (`levelName`, `itemLabel`, `itemTerm`) y las pantallas |
| Ajustes: «Avance en riesgo al terminar con menos de (%)» | `models/site_overview.py`, `views/portal_views.xml` |
| Ayuda del tareo; el paréntesis sale solo si alguna persona de la compañía tiene categoría de construcción civil | `portal_service.py:338` (`_crew_civil`); `app.js` (`screens.crew`) |

### M122-03 · Motivos del re-trabajo en el catálogo

| Qué | Dónde |
|---|---|
| El catálogo `construction.portal.reason` pasa al núcleo con el uso «Re-trabajo»; el portal le suma sus tres usos | `al_construction_planner/models/construction_reason.py`; `al_construction_portal/models/portal_reason.py` |
| `rework_reason_id` en el avance, en el registro de excesos y en la línea de liquidación | `construction_task_progress.py:136`, `construction_exceed.py`, `al_construction_planner_subcontract/models/construction_contract_settlement.py` |
| Motivos por perfil (`rework_reason_names`); la compañía los recibe al aplicar el perfil si no tiene ninguno | `construction_vertical_profile.py:119` y `:212`; `data/construction_vertical_profile_data.xml` |
| Migración: los perfiles estándar reciben su lista, cada compañía con perfil la suya, y cada valor anterior pasa al motivo del mismo nombre | `al_construction_planner/migrations/85.20261112/post-migrate.py`; `al_construction_planner_subcontract/migrations/27.20261112/post-migrate.py` |
| El celular envía el motivo del catálogo; se rechaza el de otra compañía | `portal_service.py:554` (`_rework_reason`) |
| Menú «Motivos del portal» con el filtro «Re-trabajo»; sin el portal, «Motivos de re-trabajo» en Configuración | `al_construction_portal/views/portal_views.xml`; `al_construction_planner/views/construction_reason_views.xml` |

### M122-04 · «Avance» agrupado

| Qué | Dónde |
|---|---|
| `sync` envía `groups` (agrupadores y unidad de entrega de las líneas) y en cada línea su grupo, su ambiente, su sub etapa con orden y si su fecha del plan ya pasó | `portal_service.py:350` (`_lines_tree`) |
| Grupos con contadores y %, abrir y cerrar con memoria por obra, filtros «Con saldo», «Atrasadas» y «Por validar», búsqueda que deja solo los grupos con resultados; solo se dibuja lo abierto | `app.js:1372` (`groupTree`) y `:1441` (`screens.partidas`) |
| El contador se actualiza al guardar, aunque el envío espere señal | `app.js` (`save-progress`) |

### M122-10 · Personal del portal desde la ficha de la obra

Botón «Portal de obra · N» en «Ejecutar» de la ficha de la obra
(`views/portal_views.xml:103`), que abre una ficha con lo mismo que la pestaña
(`:52`; `models/portal_member.py:115`). La pestaña de la ficha del proyecto no cambia.

## 3. Etapa 2 · `al_construction_portal_furniture`

Se instala solo con el portal, el puente de mobiliario y la reposición a planta.
Agrega cinco funciones al perfil (`portal_module_reception`, `portal_replacement`,
`portal_measure`, `portal_stage_progress`, `portal_contractor_units`), apagadas por
defecto y encendidas al instalar solo en el perfil Mobiliario.

| Código | Servidor (`models/portal_service.py`) | Celular (`static/app/furniture.js`) |
|---|---|---|
| Ficha del departamento | `sync` agrega `furniture`: etapa actual de cada ambiente, módulos, reposiciones abiertas y contadores | `screens.furapt`, botón en el grupo del departamento |
| M122-05 | `_deliveries` agrega los departamentos de un despacho de módulos; `module_reception` valida con `reception` y ajusta módulo por módulo | recepción por departamento, «Llegó todo» |
| M122-06 | `replacement`: reposición en borrador con foto y «Pedida por» | `screens.furrepl` |
| M122-07 | `measure`: el asistente del escritorio con una marca del servidor (`PORTAL_MEASURE`, `models/project_task.py`) | `screens.furmeasure` |
| M122-08 | `stage_progress`: un avance por línea del ambiente y sub etapa, con las reglas del avance | `screens.furstage` |
| M122-09 | driver por departamento, liquidado y «Esta semana» en `sync` | tarjeta del driver y «Esta semana» |

Rutas: `/construction/api/v1/furniture/{module-reception,replacement,measure,stage-progress}`.

Las sub etapas de instalación son las etapas de campo del perfil de la obra que no
consume la orden de fabricación; no se nombra ningún código de etapa.

## 4. Anexo · D1 y D2 (`al_construction_planner_sale`)

- **D1.** La valorización por hitos que lleva una partida a su 100 % toma el precio
  de su línea en la orden menos lo ya valorizado
  (`models/construction_valuation.py`, `_create_from_milestones` y
  `_construction_milestones_complete`).
- **D2.** Con dos líneas de la misma partida en la orden, el hito de cada unidad se
  parte: lo que ya estaba queda en la línea original y la diferencia va en otra
  parte del mismo hito, en la línea del adicional (`part_sale_line_id`; negativa en
  un deductivo). Las partes comparten el avance
  (`models/construction_contract.py`, `action_generate_milestones`).

## 5. Integración

- Inventario: la recepción de módulos valida con `button_validate` y la entrega
  parcial; no hay movimientos nuevos y se confirma hasta lo enviado.
- Fabricación: la reposición nace en borrador y sigue su flujo.
- Contratas: M122-09 solo lee; lo validado entra a la liquidación como siempre.
- Aprobaciones: el avance por sub etapa pasa por las reglas de exceso y la
  validación del residente.
- Sobrescrituras: todas llaman a `super()`.

## Diferencias frente al requerimiento

1. **Valorizaciones de la contrata y «Valorización por avance».** La tabla de
   M122-01 las liga. No se programó ese candado: el perfil Mobiliario trae esa
   función apagada (1.20) y la contrata de mobiliario perdería «Valorizaciones y
   pagos», que M122-09 muestra. La función viaja en `features`; el candado es una
   línea si Vicente lo confirma.
2. **Motivo anterior que el perfil no trae.** Si la compañía ya recibió la lista de
   su perfil, el motivo migrado («Mal armado» en construcción) se crea archivado:
   los avances lo conservan y el celular ofrece solo los del perfil. Sin lista, se
   crea activo.
3. **Filtro «Por validar» de «Avance».** Se conserva como cuarto filtro.
4. **D1, guarda de redondeo.** El cierre al céntimo se aplica si la diferencia
   entre los hitos y la línea es de redondeo (0.001 % del precio más un céntimo por
   hito); una diferencia mayor se deja como estaba.
5. **D2, lo ya procesado.** Un adicional procesado antes del paquete no se
   reconstruye: sus hitos siguen en la línea original hasta el siguiente adicional
   o una corrección manual.
6. **Recepción de módulos.** El estado por módulo son tres botones de texto y
   ninguno viene marcado. La reposición es por módulo, no por pieza, y su foto
   queda en el historial.
7. **Dos pasos (1.21).** Un módulo que no llegó y ya figuraba «En obra» desde la
   salida al tránsito vuelve a «Producido».
8. **Pruebas de pantalla (tour).** No se escribieron: la aplicación del portal no
   usa el cliente web de Odoo. Las pantallas se revisan en las instancias.

## Pendientes de decisión (del requerimiento)

- Motivos de re-trabajo de cada perfil: se cargó la propuesta de M122-03.
- Texto de Ajustes «Avance en riesgo»: se usó el propuesto.
- Nombre del puente: `al_construction_portal_furniture`.
