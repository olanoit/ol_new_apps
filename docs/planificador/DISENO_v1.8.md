# Planificación de obra — diseño técnico del paquete 1.8

Requerimiento: [`docs/md/Planificación de obra — requerimiento de configurabilidad (paquete 1.8).md`](../md/Planificación%20de%20obra%20—%20requerimiento%20de%20configurabilidad%20%28paquete%201.8%29.md).
Parte de la versión 33 del planificador (paquete 1.7 completo). Fecha: 16/10/2026.

## 1. Principios

* Se mantiene la regla de la 1.7: catálogos configurables (datos) sobre
  comportamientos fijos (código). Las sub etapas, los tipos de módulo, los
  métodos de unión y las listas de tarifas son datos; el código solo conoce
  su comportamiento.
* Nada cambia de monto en una base existente: los campos `stage` siguen
  guardando el código de la etapa; una sub etapa es una etapa del catálogo
  con etapa padre. Las líneas, las recetas, los avances y las etapas del
  cronograma se asignan siempre a etapas **hoja**; la etapa padre solo suma.
* Cada función nueva vive donde vive su operación: el núcleo (etapas,
  paneles, matriz, avance, visibilidad de montos), el puente de contratas
  (liquidación manual y re-trabajo), el de cuadrillas (jornales), el de
  ventas (valorización manual), el de mobiliario (modelo del mueble, piezas,
  productos por módulo, envíos, metrado como receta real, importador) y el de
  la hoja de cálculo (plantilla de la oficina técnica).

## 2. Decisiones de diseño (propuesta)

| Tema | Decisión | Motivo |
|---|---|---|
| Sub etapas (M18-02) | `construction.stage.parent_id` + `number` calculado («1.1»). La lista de los campos `stage` sigue siendo el catálogo completo, pero `_check_codes` rechaza una etapa padre en líneas, actividades, recetas y etapas del cronograma | La columna no cambia y la etapa padre nunca tiene datos propios: suma lo de sus hijas en cualquier vista |
| Etapa padre en el cronograma | Fila resumen por nivel con etapas (tipo `project` de dhtmlxGantt) con sus sub etapas como hijas encadenadas | Es la misma técnica que ya usa el cronograma para pisos y ambientes |
| Filtro de etapas | Árbol con casillas en el árbol de recursos y en el cronograma; el servidor recibe solo códigos hoja | Reusa la selección en cascada del árbol (`selection.js`) |
| Migración de mobiliario (M18-14) | Script de la v34: crea «1 Producción» y «2 Instalación» como padres, renombra las cuatro etapas actuales (mismos códigos) y crea «2.3 Limpieza» vacía | Los datos guardan códigos: no se toca ni una línea |
| Avance y metrado (M18-01) | El interruptor se separa en dos grupos técnicos (`feature_progress`, `feature_measurement`); la migración deja ambos como estaban. El perfil de construcción apaga el metrado | Misma técnica de la 1.7 (grupos implicados por `base.group_user`) |
| Términos por vertical | El árbol y los paneles toman el nombre de los niveles de la plantilla de la obra (módulos, ambientes, ML solo con el puente de mobiliario) | Ya existe `construction_level_name`; falta llevarlo a encabezados y resúmenes |
| Matriz insumo-producto (M18-04) | Acción cliente OWL propia, servidor con un solo `_read_group` por consulta; exportación con `xlsxwriter` | Las celdas son la suma de líneas del plan por (elemento, etapa, tipo, insumo) |
| Visibilidad de montos (M18-10) | Grupo `group_planner_amounts` con `groups=` en los campos de monto del plan, sus líneas, avances y tareas. Los métodos de los paneles calculan con `sudo()` acotado al plan que el usuario ya puede leer y quitan los montos de la respuesta. La migración da el grupo a quienes hoy son planificadores | La restricción por campo cubre exportaciones y API; la migración no le quita nada a nadie |
| Avance por driver (M18-12) | El avance de la partida es lo ejecutado en el driver de la partida (líneas de contrata y personal propio en su unidad, ponderadas por valor) entre su metrado; los niveles superiores se ponderan por valor | Con una sola actividad en el driver da exactamente «48 de 120 m² = 40 %» |
| Work Items (M18-13) | Vínculo `work_item_id` (entero) + huella del contenido a cada lado; acción programada y botón «Revisar» marcan la diferencia; asistente con vista previa aplica en uno u otro sentido | Los Work Items son modelos `x_` del paquete de industria: no se heredan en Python |
| Jornales (M18-07) | Unidad del perfil y de la obra: hora, medio día o día; el redondeo es el de `hr.work.entry.type` (`round_days`, `round_days_type`) | El requerimiento pide reutilizarlo |
| Productos por módulo (M18-15) | Un `product.product` fabricado por módulo de tipología y posición, con atributos tipo de módulo y método de unión, seguimiento por lote (uno por departamento) | Decidido por Vicente el 16-oct-2026; el lote por departamento permite saber qué módulo va a qué ambiente sin una serie por pieza |

## 3. Fases

| Fase | Requerimientos | Contenido |
|---|---|---|
| 35 | M18-02, M18-14 | Etapas con sub etapas, numeración y orden de árbol en todas las vistas; filtro jerárquico; barras resumen en el cronograma; migración de las etapas de mobiliario |
| 36 | M18-01 | Interruptores «Avance» y «Metrado»; menús, botones y asistentes por función; términos de la plantilla; aviso al aplicar un perfil a una compañía con obras |
| 37 | M18-03, M18-04 | Panel de recursos por tipo con subtotales y sub agrupación por etapa; matriz insumo-producto con exportación a Excel |
| 38 | M18-11, M18-12 | Avance en lista y formulario con chatter (portal, evaluación del supervisor, validación y rechazo); avance por driver de la partida y de la actividad |
| 39 | M18-13 | Sincronización en los dos sentidos entre recetas y Work Items |
| 40 | M18-06 a M18-08 | Cuadrillas por categoría o puesto con costo de referencia; jornales; sede de obra creada con la obra |
| 41 | M18-05, M18-21 | Política de exceso por perfil, obra y tipo de recurso; control por nivel y sub etapa; registro de excesos; pago repetido y re-trabajo de contratas |
| 42 | M18-09 | Porcentaje manual con motivo en la valorización de proyecto y en la liquidación de contratas |
| 43 | M18-17 a M18-20 | Modelo del mueble (tipo de mueble y de módulo), método de unión con reglas, catálogo de actividades y listas de tarifas por familia y obra, líneas de contrata desde las piezas |
| 44 | M18-15, M18-16, M17-15, M17-20 | Productos por módulo con su lista de materiales y lote por departamento; envíos de planta a obra; metrado como receta real; versus y autorización en producción |
| 45 | M17-18, M17-19, M18-22 | Importador de la proyección de materiales, validación de códigos y plantilla de la hoja de trabajo de la oficina técnica |
| 46 | M18-10 | Visibilidad de montos en todo el aplicativo; documentación, casos de prueba por vertical y criterios de aceptación |

Cada fase se cierra con la batería completa en verde en `ol_pe_v19`, sin
cambiar las cifras de las pruebas de los paquetes 1.6 y 1.7 ni de
`ACEPTACION.md`, y con un commit local.
