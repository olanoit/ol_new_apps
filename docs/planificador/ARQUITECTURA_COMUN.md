# Planificación de obra — arquitectura común entre verticales

Versión 0.2 · 31-oct-2026. Borrador 0.1 del 26-oct-2026, actualizado al 31-oct
y subido al repositorio con el paquete 1.16 (anexo E).

Este documento fija qué es común al planificador de obra y qué pertenece a cada
vertical, para que el trabajo de una vertical no contradiga a la otra ni al
resto de la suite. Lo leen antes de proponer o programar un cambio en el
planificador: los chats de diseño de cada vertical, el Claude Code de
desarrollo y la revisión de coherencia.

Fuentes: el código de la rama 19.0 (commit `20fe665`, 26-oct-2026) y los
documentos de `docs/planificador/` y `docs/md/`. Lo verificado en el código
lleva su ruta. Cuando solo lo dice un documento, se cita el documento.

## 1. Qué documento manda

Si dos fuentes no coinciden, manda la primera de esta lista:

1. Este documento, en lo común y en las reglas de trabajo.
2. El código de la rama 19.0, en cómo funciona hoy el planificador.
3. El diseño de cada paquete (`DISENO_v1.7` a `DISENO_v1.12`,
   `DISENO_CREVAL_v1.0`, `DISENO_v1.16`), en lo que decidió ese paquete.
4. La especificación v1.4 (`ESPECIFICACION_v1.4.md`) y el diseño técnico
   (`DISENO_TECNICO.md`). Son la historia del núcleo. Desde el paquete 1.7 no
   describen:
   - las dependencias del núcleo (v1.4, línea 137; diseño técnico, §3);
   - los grupos de usuario: describen la escalera anterior de cinco grupos; hoy
     rigen los dos ejes, plan y ejecución (v1.4, «Seguridad y menús»; diseño
     técnico, §4);
   - dónde vive cada modelo: varios pasaron a los puentes.

## 2. Principios

**P1. Catálogos configurables sobre comportamientos fijos.** El código sabe qué
hacer con una etapa, un tipo de recurso o un nivel; no sabe cómo se llaman ni
cuántos hay (`DISENO_v1.7` §1). Cada catálogo tiene un campo de comportamiento
fijo:

- etapa: tipo `production`, `field` o `control`, más la casilla de consumo
  (`construction_stage.py`);
- tipo de recurso: comportamiento (`common.py`);
- nivel: función (`construction_level_template.py`).

El código pregunta por el comportamiento, nunca por el código de un registro
del catálogo.

**P2. La vertical es un perfil, no una condición en el código.** El perfil de
vertical (`construction.vertical.profile`) es un registro de datos: plantilla de
niveles, etapas, tipos de recurso, puentes, funciones y parámetros de la
compañía. No existe un campo «vertical» que el código consulte con un `if`, y
no debe crearse. Un perfil nuevo, por ejemplo instalaciones eléctricas, tiene
que funcionar sin desarrollo (requerimiento 1.7, M17-05).

**P3. Núcleo neutral, puentes por operación.** El núcleo
(`al_construction_planner`) depende solo del Gantt de la suite, de la validación
por niveles de OCA, de analítica y de producto (`__manifest__.py`). Cada
función que opera en otra aplicación vive en el puente de esa operación:
compras, fabricación, contratas, cuadrillas, presupuesto, ventas u hoja de
cálculo. Lo que solo sirve a una vertical vive en el puente de esa vertical
(`DISENO_v1.7` §2 y §4; `DISENO_v1.8` §1).

**P4. Sin configurar, todo se comporta como hoy.** Una opción nueva no cambia
montos ni flujos en una base existente mientras nadie la active (`DISENO_v1.8`
§1; `DISENO_CREVAL_v1.0`, Principios).

**P5. Se conservan los identificadores externos** de grupos, menús y acciones
(`DISENO_CREVAL_v1.0`, Principios).

**P6. Cada sobrescritura de un método nativo o de terceros respeta a los demás
módulos.** Ver sección 7.

**P7. Configuración antes que desarrollo.** Ver sección 3.

## 3. Regla: configuración antes que desarrollo

Antes de pedir o programar un desarrollo, se revisa en este orden si ya se
cumple:

1. **Odoo nativo instalado en la base real.** Se comprueba con lo instalado en
   esa base, no con Odoo 19 genérico: ajustes, rutas y reglas de stock, tipos de
   operación, reabastecimiento, Aprobaciones, automatizaciones, propiedades,
   facturación por objetivos, Planificación, Asistencias.
2. **Módulos OCA o de terceros** presentes en `OL-THIRD-PARTY/`:
   `base_tier_validation`, `purchase_request`, `purchase_tier_validation` y los
   demás.
3. **Lo ya desarrollado en los módulos AL:** catálogos, perfiles, parámetros de
   la compañía, interruptores de Ajustes y puentes.
4. **Una combinación** de las anteriores como estrategia o ruta.

Solo si ninguna sirve, se pide desarrollo. Todo requerimiento de desarrollo
trae una sección «Alternativas descartadas» con:

- qué se revisó;
- dónde se comprobó: base y fecha, módulo y archivo, o pantalla;
- por qué no cumple. Si cumple a medias, la brecha exacta.

**Al programar:** si quien desarrolla encuentra una ruta nativa o configurable
que cumple el requerimiento, lo devuelve antes de escribir código y dice cuál
es.

**Hacia atrás:** si un desarrollo existente tiene una ruta nativa o
configurable equivalente, se propone retirarlo con su plan de migración de
datos. El retiro lo decide Vicente, uno por uno.

## 4. Reparto entre núcleo, puentes y verticales

| Capa | Módulos | Qué contiene |
|---|---|---|
| Núcleo | `al_construction_planner` | Plan de recursos y sus líneas, asignaciones, avance, metrado, etapas del cronograma, catálogos (etapas, tipos de recurso, plantillas de niveles, recetas, actividades y tarifas, reglas analíticas), perfiles de vertical, interruptores de función, grupos de plan y ejecución |
| Puentes de operación | `_purchase`, `_mrp`, `_subcontract`, `_crew`, `_budget`, `_sale`, `_spreadsheet`, `_approvals` | Lo que el plan hace en Compras, Fabricación, Contratas, Planificación, Presupuesto, Ventas, Documentos y Aprobaciones |
| Puentes de combinación (se instalan solos) | `_subcontract_purchase`, `_subcontract_sale`, `_mrp_request`, `_approvals_mrp`, `_production`, `_spreadsheet_furniture`, `_sale_furniture` | Lo que solo tiene sentido con dos puentes instalados |
| Vertical mobiliario | `_furniture`, `_sale_furniture`, `_spreadsheet_furniture`, `al_industry_furniture` | Tipologías, muebles, módulos, piezas, método de unión, receta real, despacho a obra por unidad, importación del maestro y del ETO |
| Vertical construcción | `al_industry_construction` y los perfiles «Construcción PROF 3» a «Construcción PROF 6» | Se resuelve con datos: plantillas Especialidad › Sub-especialidad › Partida › Subpartidas, «APU en cualquier nivel», etapas de obra, planes analíticos y parámetros. Tiene opciones propias en el puente de contratas (`DISENO_CREVAL_v1.0`) |
| Fuera del prefijo | `al_construction_material_request`, `al_construction_attendance`, `al_construction_portal` | Requerimiento de obra, asistencia de obra y portal de campo, comunes a las dos verticales |

Una función nueva se ubica con estas preguntas, en orden:

1. ¿Opera en otra aplicación? Va al puente de esa aplicación.
2. ¿Solo sirve a una vertical? Va al módulo de esa vertical.
3. ¿Sirve a cualquier rubro y no toca otra aplicación? Va al núcleo.

## 5. Vocabulario equivalente

El código guarda la función. La plantilla de niveles de la obra pone el nombre
que se ve en pantalla (`construction_level_labels.py`).

| Función en el código | Mobiliario | Construcción (PROF 3 a PROF 6) |
|---|---|---|
| Agrupador superior (`group`) | Torre | Especialidad (N1), Sub-especialidad (N2) |
| Último agrupador (`floor`) | Piso | — |
| Unidad de entrega (`unit`) | Departamento | No existe |
| Nivel con etapas (`space`) | Ambiente | Partida (N3) |
| Subnivel (`furniture`) | Mueble | No se usa |
| Nivel de detalle (`module`) | Módulo | No se usa (desde el 1.16) |
| Subnivel de obra (`work_sublevel`) | No se usa | Subpartida 1 a 3 (N4 a N6) |
| Etapas | 1 Producción (1.1 Producción de piezas, 1.2 Armado) · 2 Instalación (2.1 Instalación, 2.2 Acabado, 2.3 Limpieza) | Trazo y replanteo · Ejecución · Acabados · Pruebas y entrega |
| Receta | Tipología con módulos, piezas y lista de materiales | Plantilla de ejecución (APU) en el nodo que «Lleva APU» |
| Valorización al cliente | Hitos por unidad de entrega | Porcentaje de avance del nodo con APU |
| Valorización de contratas | Liquidación semanal | Valorizado por orden con condiciones de contrata |

Con «APU en cualquier nivel» (opción de la plantilla, paquete 1.16, M116-11),
el nodo con APU puede estar en cualquier profundidad; los niveles de arriba
solo agrupan.

**Palabras con más de un sentido.** En un requerimiento se escriben con su
calificativo:

- «Partida»: en mobiliario es la línea del contrato por familia o el segmento
  analítico; en construcción es un nivel del árbol. En la regla analítica, el
  campo se rotula «Tipo de costo» desde el 1.16.
- «Actividad»: es una actividad del catálogo de contratas en las dos verticales.
- «Producción»: es la etapa padre, la sub etapa 1.1, un tipo de etapa y un tipo
  de recurso.
- «Acabado» y «Acabados»: son etapas distintas, cada una de su vertical
  (`finishing` y `works_finishing`).
- «Metrado»: en construcción es la medición con aprobación; el estado del
  ambiente medido de mobiliario se llama «Medido» (1.16, M116-02).

## 6. Qué se configura y dónde

| Palanca | Alcance | Dónde |
|---|---|---|
| Perfil de vertical | Compañía (y obra, que lo hereda) | `res.company.construction_profile_id`, `project.project.construction_profile_id` |
| Etapas que se ofrecen | Obra, por su perfil | `construction.vertical.profile.stage_ids` (1.16, M116-01) |
| Parámetros: semana, liquidación, pago, unidad de cuadrilla, sede automática | Compañía | Campos de `res.company`, escritos por el perfil |
| Motor de aprobación (`construction_approval_engine`: validación por niveles o Aprobaciones) | Compañía | `al_construction_planner_approvals`, `res_company.py` |
| Funciones: control, avance, metrado, entradas a la ejecución | Toda la base | Grupos implicados en «Usuario interno» (`res_config_settings.py`) |
| Catálogo de etapas | Toda la base, sin compañía | `construction.stage` (`construction_stage.py`) |
| Puentes | Toda la base | Módulos instalados |

**Consecuencia.** El caso que hay que soportar es una base con varias compañías
de verticales distintas: por ejemplo, la compañía 1 ejecuta proyectos de
construcción y la compañía 2 es contrata de mobiliario (decisión del
26-oct-2026). Desde el 1.16 (M116-01) las etapas se ofrecen por el perfil de la
obra; los interruptores de función siguen siendo de toda la base (C-01).

Lo que no se usa: `ir.config_parameter`. Toda la configuración del planificador
está en la compañía, la obra, los grupos y los perfiles. Una opción nueva sigue
esa misma regla.

## 7. Reglas para convivir con el resto de la suite

1. **Una sobrescritura de un método nativo o de terceros llama a `super()`.**
   Interceptar con un asistente es válido si el asistente vuelve a llamar al
   método con un contexto que evita repetir el control. Así lo hacen hoy la
   confirmación de la orden de fabricación y la de la OC con exceso sobre el
   plan: `construction_exceed_checked` en
   `al_construction_planner_mrp/models/plan_exceed_wizard.py` y
   `al_construction_planner_budget/models/plan_exceed_wizard.py`.
2. **Un reemplazo sin `super()` se documenta en este archivo, con su alcance.**
   Hoy hay uno: el cálculo de la cantidad comprada del requerimiento de compra
   (`al_construction_material_request/models/purchase_request.py`). Corrige el
   reparto de OCA cuando una línea de OC consolida varias solicitudes, y afecta a
   todos los requerimientos de compra de la base, no solo a los de obra. Con una
   sola solicitud por línea de OC da el mismo resultado que OCA. También se
   reemplazan los mensajes de OCA en `purchase_request_messages.py`.
3. **El código que corre en cada movimiento de stock, cada transferencia o cada
   apunte analítico filtra primero lo que es de obra y sale enseguida si no lo
   es.** La suite atiende también ventas, farmacia y punto de venta.
4. **Si dos módulos tocan el mismo cálculo, se coordinan de forma explícita.**
   Ejemplo: el costo del retazo en `_cal_price`
   (`al_construction_planner_mrp/models/remnant.py`) se aparta cuando el costeo
   por pieza (`al_mrp_piece_costing`) está activo.
5. **Aprobaciones.** Conviven dos motores y cada compañía elige el suyo en
   `construction_approval_engine`. Todo cambio en aprobaciones se prueba con los
   dos.

## 8. Registro de decisiones

| Fecha | Decisión | Vertical de origen | Alcance |
|---|---|---|---|
| 15-oct-2026 | Catálogos configurables sobre comportamientos fijos; núcleo y puentes | Mobiliario (paquete 1.7) | Común |
| 16-oct-2026 | Cada función vive en el puente de su operación | Mobiliario (paquete 1.8) | Común |
| 23-oct-2026 | Todo se activa por configuración; se conservan los identificadores externos; grupos en dos ejes | Construcción (`DISENO_CREVAL_v1.0`) | Común |
| 26-oct-2026 | Regla de configuración antes que desarrollo (sección 3) | Las dos | Común |
| 26-oct-2026 | Una misma base puede tener compañías de verticales distintas. Mientras no se resuelvan C-01 y C-02, una base de una sola vertical archiva las etapas de la otra | Las dos | Común |
| 26-oct-2026 | Las casillas de comportamiento del nivel quedan como deuda conocida (D-01) | Las dos | Común |
| 26-oct-2026 | Se retira el campo «Rótulo» del alcance de 6.3: el nombre de la línea de la plantilla es el rótulo | Construcción | Común |
| 31-oct-2026 | La analítica es la nativa de Odoo: el planificador crea planes y cuentas y llena la distribución; sin analítica paralela. Cada nivel de la plantilla indica plan y modo de cuenta (compartida o por obra); mobiliario agrega el plan «Rubro» compartido por familia de tipología (paquete 1.16, M116-05) | Las dos | Común |
| 31-oct-2026 | Construcción: la plantilla puede marcar «APU en cualquier nivel»; etapas, receta, avance y valorización van en el nodo que lleva APU. Perfiles por profundidad (PROF 3 a PROF 6). Especialidad por catálogo compartido. Mobiliario mantiene el nivel fijo (paquete 1.16, M116-11) | Construcción | Común (opción de plantilla) |
| 31-oct-2026 | Las etapas se eligen entre las activas del perfil de la obra; el dato guardado sigue siendo el código. Las ayudas de etapa reciben la obra (paquete 1.16, M116-01; cierra C-02 y C-03) | Las dos | Común |
| 31-oct-2026 | «Requerimiento de obra sin regla» tiene un tercer valor, «Material fuera del plan si la obra no tiene plan». La regla 7.4 (jefe de la obra) da el mismo resultado con la aplicación Aprobaciones que con la validación por niveles (paquete 1.16, M116-03) | Las dos | Común (ajuste por compañía) |
| 31-oct-2026 | La ruta del nivel del requerimiento empieza en el «Primer nivel de la ruta» de la plantilla (por defecto, la unidad de entrega o el primer nivel). El aviso de modalidad de «Asignar contrata» sale solo con «Personal propio» guardado en la partida (paquete 1.16, M116-04 y M116-06) | Las dos | Común |
| 01-nov-2026 | Analítica por nivel: el núcleo crea y enlaza la cuenta de cada tarea según el plan y el modo de su nivel y suma las cuentas de la ruta en `_apply_analytic_rules`; las verticales agregan cuentas con el gancho `_construction_extra_analytic_accounts` (mobiliario: Rubro). El control de compras puede limitarse a «Planes que controla el presupuesto» (paquete 1.16, M116-05, D1 a D3) | Las dos | Común (configuración por plantilla y compañía) |
| 01-nov-2026 | El avance guarda la contrata que lo ejecutó (`construction.task.progress.partner_id` deja de ser un relacionado de la línea del plan: la toma al crearse y no cambia si la línea pierde o cambia de contrata). «Intervenir contrata» baja las líneas intervenidas de la orden a lo ejecutado, deja la línea del plan sin contrata y retiene el fondo; la liquidación final cobra contra el fondo, con nota de crédito del proveedor, los deductivos que superan lo pendiente (CREVAL, CR-20; paquete 1.16, I-13) | Las dos | Común (puente de contratas) |
| 01-nov-2026 | Barra de selección del Cronograma y del Árbol de recursos: el botón toma el nombre de su acción (se cambia con la traducción de la acción) y va en la fila de su grupo (Consultar, Programar, Ejecutar). El Gantt base acepta `group` y `groupLabel` en `extraToolbarButtons`; sin grupos, la barra queda como siempre. Nombres largos: ancho máximo por compañía en Ajustes y clase común `o_cp_wrap_names` en las vistas del planificador. Las ayudas del núcleo hablan de producción en taller; las que nombran la orden de fabricación van en el puente de Fabricación (paquetes 1.15 y 1.16, M115-01 a 03, M116-08; CREVAL, CR-25 y CR-26) | Las dos | Común |
| 01-nov-2026 | Etapa actual de cada ambiente: el núcleo la guarda en la tarea (estado de los ambientes que miden, etapas del catálogo en orden) y la recalcula con un método explícito desde el control de las líneas, las etapas del ambiente y los campos que declara cada puente (`_construction_current_stage_trigger_fields`). Una etapa sin contratas ni personal propio se da por terminada con los módulos producidos (fabricación) o con avance en una etapa siguiente. La carga semanal usa la semana de la obra (la de la liquidación) y los días hábiles de la compañía, y compara lo planificado con los avances validados (paquetes 1.15 y 1.16, M115-04 a 06, M116-02, M116-07) | Las dos | Común; Pendiente, Medido y Entregado solo con el perfil que mide ambientes |
| 01-nov-2026 | Hojas de trabajo (paquete 1.16, etapa 4): el perfil dice qué hoja abre la obra (`construction_spreadsheet_kind`; sin perfil, el puente de mobiliario sigue con su maestro), sin condiciones por código de perfil. Las dos hojas leen las columnas por su clave: pestaña oculta `_CLAVES` con `=COLUMN(<pestaña>!<encabezado>)` (la hoja de Odoo 19 no tiene notas ni rangos con nombre); al enviar, el encabezado se reemplaza por la clave y los dos importadores la aceptan. Pestaña ERRORES común (hoja, fila, columna, mensaje, tipo, «Ir»); cada vertical entrega sus filas (`_construction_validate_budget`, `_construction_validate_furniture`). Convención común: amarillo el dato, gris la fórmula; producto «nombre · unidad · código». La barra de la hoja muestra todos los menús raíz: un solo menú «Planificación de obra» con opciones visibles según el tipo de hoja. |

## 9. Conflictos abiertos

Tipo: C configuración · D desarrollo · P decisión pendiente.

| ID | Conflicto | Evidencia | Tipo | Estado |
|---|---|---|---|---|
| C-01 | El catálogo de etapas y los interruptores de función son de toda la base, y el perfil es por compañía. En una base con una compañía de construcción y otra de mobiliario, aplicar el perfil de una compañía apaga o enciende funciones (metrado, por ejemplo) para todas | `construction_stage.py` (sin `company_id`); interruptores con `implied_group` sobre `base.group_user` (`res_config_settings.py`); `construction_vertical_profile.py` | D | Etapas: resuelto en el 1.16 (M116-01), se ofrecen por el perfil de la obra. Interruptores de función: abierto; los grupos de Odoo no se separan por compañía. Por redactar |
| C-02 | Las ayudas que eligen la etapa de consumo en obra (`_consumption_code`, `_field_codes`) recorrían todo el catálogo por secuencia. En una base con las dos verticales, un consumo de construcción sin etapa caería en una etapa de mobiliario | `construction_stage.py` | D | Resuelto en el 1.16 (M116-01): las ayudas reciben la obra y buscan entre las etapas de su perfil |
| C-03 | «Generar plan» de mobiliario tenía escritas cuatro etapas (`production`, `assembly`, `installation`, `finishing`). Descartaba sin aviso cualquier otra, entre ellas 2.3 Limpieza | `al_construction_planner_furniture/wizards/plan_generate_wizard.py` | D | Resuelto en el 1.16 (M116-01): toma las etapas del perfil de la obra |
| C-04 | La hoja de cálculo de mobiliario se elige porque el código del perfil no es `construction`. Un tercer perfil recibiría la hoja de mobiliario | `al_construction_planner_spreadsheet_furniture/models/project_project.py` | D | Baja prioridad mientras haya dos perfiles |
| C-05 | Con el puente de mobiliario instalado, toda tipología tiene familia obligatoria (por defecto Cocina) | `al_construction_planner_furniture/models/construction_typology.py` | P | Sin efecto mientras las obras de construcción no usen tipologías: su receta es la plantilla de ejecución |
| C-06 | La industria Constructora no apaga el metrado, que el núcleo enciende al instalarse | `al_industry_construction/data/construction_data.xml`; `planner_groups.xml` | C | Se apaga en Ajustes. Corregir el dato de la industria es opcional |
| C-07 | La plantilla «Construcción por partidas» trae la compra masiva directa a la obra (`purchase_destination = project`). La decisión del 15 y 16-oct-2026 es stock general (requerimiento 1.8, «Decisiones») | `construction_vertical_profile_data.xml` | D menor | Corregir el dato a `general`. Cada obra puede cambiarlo en su propio campo de destino |
| C-08 | El campo «Rótulo» de la línea de plantilla, previsto en `DISENO_CREVAL_v1.0` 6.3, no existe. El nombre de la línea ya es el rótulo en pantallas e impresos (`construction_level_labels.py`; `construction_contract_valuation.py`), y una plantilla propia con sus nombres lo resuelve por configuración | `construction.level.template.line` | — | Cerrado el 26-oct-2026: se retira del alcance de 6.3. Queda por quitar la lectura condicional de `label` en el impreso |

## 10. Deuda conocida

| ID | Deuda | Evidencia | Decisión |
|---|---|---|---|
| D-01 | Casillas de comportamiento del nivel. «Lleva receta», «Se mide con metrado», «Se valoriza o factura», «Lleva etapas» y «Unidad de entrega» se muestran y se exportan, pero el código no las lee; el comportamiento lo decide la función del nivel. Solo «Recibe avance» tiene efecto, en el portal de contratas | `construction_level_template.py`; `al_construction_planner_subcontract/controllers/portal.py` | 26-oct-2026: se dejan y se anotan. No se configuran creyendo que cambian el comportamiento. Con «APU en cualquier nivel» (1.16), el comportamiento lo decide «Lleva APU» de la tarea |
| D-02 | Restos de mobiliario en el núcleo. Ancestros piso, departamento, ambiente, mueble y módulo en tarea y línea; estados del módulo; tipos de unidad; metro lineal en la actividad; dependencias de encimera y electrodomésticos con etapa por defecto `installation`; semana de jueves y pago el sábado como valores por defecto de la compañía; categorías de armado e instalación | `common.py`; `construction_labor.py`; `construction_dependency.py`; `res_company.py` | Sin acción mientras construcción no necesite un comportamiento distinto. No se agrega más |
| D-03 | Funciones de nivel con nombres de edificio. En construcción, las funciones `group` y `space` llevan nombres de obra | `construction_vertical_profile_data.xml` | Es el diseño de P1. Los requerimientos usan el nombre de pantalla y, entre paréntesis, la función |

## 11. Posibles duplicados de funciones nativas

Los revisa el chat de coherencia con la regla de la sección 3, en las bases
reales. Mientras no se prueben, son hipótesis:

- Dos motores de aprobación: Aprobaciones y validación por niveles.
- Personal de contrata en la asistencia de obra, frente a empleados de tipo
  «Contratista» en el quiosco nativo.
- División entre stock y compra del requerimiento de obra, frente a la regla
  «Tomar del stock y, si no hay, activar otra regla».
- Hitos de cobro del puente de ventas, frente a la facturación basada en
  objetivos.
- Tablero de abastecimiento, frente a reabastecimiento y MPS.
- Informe de precios de compra, frente al análisis de compras.
- Versiones de la hoja de obra, frente al historial de Documentos.

## 12. Mantenimiento de este documento

- Se actualiza en el mismo cambio que lo afecta: una decisión nueva va a la
  sección 8; un conflicto resuelto cambia de estado en la sección 9.
- Lo que no puede contradecir: los principios de la sección 2 y la regla de la
  sección 3. Cambiarlos requiere la aprobación de Vicente.
- No lleva datos de clientes: nombres, cifras, obras ni usuarios. El
  repositorio es público.
