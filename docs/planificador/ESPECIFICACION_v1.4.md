<!-- Especificación «Planificador de recursos de obra» v1.4 (10-oct-2026), extraída del artefacto https://claude.ai/artifact/FUUUmFdbaWxs47fJqAMYfs. Fuente de verdad para al_construction_planner. -->

ALTA Latam · New Allcenter · Indicación de desarrollo

# Planificador de recursos de obra
Aplicación de Odoo, construida sobre el Gantt de proyectos, para planificar módulo por módulo todo lo que la obra va a consumir: materiales, servicios, contratas a destajo, horas de personal propio y órdenes de fabricación. El plan se ve como un árbol de obra, piso, departamento, ambiente y módulo, y también sobre el Gantt, con los recursos acumulados en cada nivel. Al seleccionar un nivel se seleccionan todos sus hijos, y las asignaciones y acciones se aplican a todo el grupo. Cada semana muestra el costo y el ingreso valorizados de la obra, desde la entrega interna hasta la cobranza.
Contenido

## Propósito
Un proyecto de Allcenter es rentable cuando se controlan a la vez tiempo, alcance y costo. En New Allcenter el tiempo y el alcance ya viven en Proyectos (tareas, subtareas, dependencias y Gantt), y el costo financiero vive en los presupuestos analíticos por partida. Falta la capa del medio: qué recursos consume cada módulo, en qué cantidad, a qué costo y para qué fecha.
El módulo agrega esa capa y le da tres usos:
- Línea base. El plan valorizado alimenta el presupuesto analítico del proyecto y queda como referencia contra la que se mide todo.
- Pase a ejecución por grupo. Se selecciona un piso, un departamento o un conjunto de módulos en el árbol y se lanza sobre todo el grupo la compra masiva, el requerimiento de obra, la orden de fabricación, la asignación de contrata o de cuadrilla, o el registro de avance.
- Control. Cada línea lleva su saldo (planificado, pedido, comprado, despachado, consumido, ejecutado) y cada pedido que lo excede se detiene o se alerta. El avance se calcula comparando las unidades de driver presupuestadas con las reportadas, y la contrata cobra cada sábado lo que liquidó el jueves.
Cada afirmación del documento lleva una de estas marcas. Lo marcado C o E es propuesta, no dato del cliente ni del sistema. En las maquetas de pantalla, cada una indica arriba qué datos son reales y cuáles de ejemplo.

## Punto de partida en Odoo
Lectura de la base de desarrollo del 09-oct-2026, por RPC y en solo lectura. Nada se modificó.
| Pieza | Qué hace hoy | Qué le falta para planificar recursos |
| Tareas y Gantt | Proyectos nativo más el Gantt propio (al_project_gantt_base, al_project_gantt_backend) N | Programa tareas, no recursos. No acumula recursos por nivel ni selecciona en cascada |
| Avance de tarea | El campo progress de hr_timesheet mide horas registradas contra horas asignadas. Hay además subtask_completion_percentage y portal_progress N | No existe avance por unidades de driver (módulos armados, ML instalados) |
| Planificación | planning y project_forecast instalados. El turno lleva proyecto, rol, recurso y horas asignadas N | El turno no tiene tarea. Solo programa personas |
| Presupuesto analítico | account_budget y project_account_budget instalados. La línea budget.line lleva account_id, budget_amount, fechas y los planes adicionales x_plan8_id, x_plan9_id, x_plan10_id. Hay 2 presupuestos cargados N | Se carga en soles. No sabe de cantidades ni de tareas |
| Requerimiento de obra | Tu módulo al_construction_material_request. Su línea ya trae project_id, task_id, analytic_distribution, supply_mode, line_state y el ciclo qty_to_dispatch, qty_to_purchase, qty_dispatched, qty_purchased, qty_received_on_site N | Nace a mano. No sabe cuánto quedaba planificado |
| Requerimiento de compra | purchase_request (OCA) y purchase_requisition instalados N | Sin origen en un plan |
| Aprobaciones | base_tier_validation instalado N | Disponible para el plan, los excesos y la liquidación |
| Fabricación | project_mrp y mrp_mps instalados N | Sin vínculo con el plan del proyecto |
| Nómina | hr_payroll, la planilla AL y el régimen de construcción civil (al_hr_pe_construction) instalados N | Nada asigna horas de planilla a un proyecto antes de que ocurran |

## Unidad mínima y jerarquía
Vicente pidió planificar por la mínima unidad fabricada, módulo o mueble, y revisar cuál es V. La respuesta es el módulo. Las fuentes:
- Despiece real. La carga de Patio La Paz, piso 7, torre A en la base de pruebas armó la jerarquía material → mueble terminado → módulo → pieza con 5 materiales, 13 muebles terminados, 135 módulos y 1,729 piezas. Los 13 muebles terminados son los 13 departamentos: el «mueble terminado» es la cocina completa del departamento N.
- Identidad de la pieza. Cada pieza lleva su departamento y su módulo, por ejemplo «DPTO-0709 - MB02:1 - ZOCALO» N. El módulo (MB02, MA01, CAMPANA, LAVADERO, CAJONERA) es la unidad que se arma, se despacha y se instala.
- Drivers de pago. El armado se paga por módulo según su tipo (tornillo, tarugo, microondas, campana, cajonera, esquinero) y la instalación y la limpieza por metro lineal de mueble bajo y alto, que es la suma de los anchos de los módulos X.
- Lectura del ETO. La biblioteca de tipologías del motor de costeo guarda los ML bajo y alto y el conteo de módulos por tipo: el módulo es la unidad de la que salen los dos drivers.
La pieza es más chica, pero es un componente cortado: su costo y su trazabilidad ya están resueltos en el costeo de piezas CNC y en el flujo de manufactura. El plan no baja a pieza.
Obra
El proyecto
MOMEN-35-26
Piso
Agrupa departamentos
Piso 05
Departamento
Unidad de venta
Dpto 501
Ambiente
Mueble terminado con tipología
Cocina tipo 01
Módulo
Se arma, despacha e instala
Tarugo 2 · MB02
El nivel Ambiente permite que un departamento tenga cocina, closet, baño y lavandería, cada uno con su tipología. En MOMEN cada departamento tiene solo cocina X.

### Dónde cuelga cada línea del plan
Regla: la línea cuelga del nivel más bajo donde su driver está definido. El árbol suma hacia arriba, así que en pantalla todo se ve acumulado en cada nivel.
| Recurso | Nivel | Por qué |
| Armado del módulo | Módulo | Una unidad por módulo, con la tarifa de su tipo |
| Instalación y limpieza por ML | Módulo si se conoce su ancho; si no, Ambiente | El ancho viene del ETO. El maestro de MOMEN solo trae los ML por tipología, así que en MOMEN cuelgan del ambiente X |
| Otras actividades de contrata | Ambiente | Colocación de puertas, entarugado, tapas y armado de cajón, correderas, recortes, pines y repisas, push: el maestro las da por cocina X |
| Materiales | Ambiente, o módulo si hay BOM por módulo | La BOM de MOMEN es por tipología de cocina X; con despiece por módulo bajaría al módulo |
| Personal propio | Ambiente o superior | Las cuadrillas trabajan por piso y semana |
| Servicios y fletes | Piso u obra | No pertenecen a un módulo |
Volumen en MOMEN con esta regla: 1,589 tareas (20 pisos, 153 departamentos, 153 ambientes y 1,263 módulos), 3,806 líneas de material y 4,014 líneas de contrata (1,263 de armado por módulo y 2,751 por ambiente) X. El árbol carga por niveles a demanda para que este volumen sea operable.

## La aplicación
El planificador es una aplicación propia, «Planificación de obra», construida sobre la aplicación Gantt de Cristóbal V. Los documentos que genera (requerimientos, órdenes de compra, órdenes de fabricación, facturas) siguen viviendo en sus aplicaciones y se abren desde botones inteligentes.

### Qué es hoy el Gantt
Leído en New Allcenter el 10-oct-2026 N:
| Módulo | Qué hace |
| al_project_gantt_backend19.0.14.20261009 | Aplicación con menú raíz y acción de cliente. Componente OWL propio que monta dhtmlxGantt (627 KB, carga perezosa al abrir la vista), sin depender de web_gantt de Enterprise. Selección de proyectos, zoom de día a trimestre, edición en el diagrama (arrastrar, formulario, dependencias, sangría), ruta crítica, líneas base y exportación a Excel y PDF |
| al_project_gantt_base | Sin interfaz. Capa de datos única al.gantt.data, expuesta como project.project.get_gantt_data(), que devuelve proyectos, tareas, dependencias e hitos en un formato neutral. Mapeo de campos configurable (al.gantt.field.map). Ninguna interfaz consulta el ORM por su cuenta |

### Cómo se monta encima
- Módulo nuevo al_construction_planner, con application = True y menú raíz «Planificación de obra». Depende de al_project_gantt_base y al_project_gantt_backend, además de los módulos del modelo de datos.
- Sin tocar archivos del Gantt. Hereda al.gantt.data para que cada tarea traiga monto planificado, avance, contrata asignada, estado del módulo y alertas, y para devolver como filas adicionales las etapas de cada ambiente (ver construction.space.stage).
- Reutiliza el componente dentro de su pantalla Cronograma y le agrega una columna de selección, un panel lateral con los recursos de la selección y la barra de acciones del árbol. Desde ahí el gestor del proyecto pide y asigna recursos V.
- Lo que hay que acordar con Cristóbal. Que su componente exponga puntos de extensión (columnas adicionales, panel lateral, evento de selección múltiple, botones de barra) para no parchear su código, y una regla de compatibilidad de versiones, porque su módulo cambia seguido C.
- Librería. La selección múltiple usa la extensión multiselect de dhtmlxGantt. Según la documentación de la librería, la vista de carga de recursos es de la edición PRO; es conocimiento previo mío, por verificar contra la licencia de Cristóbal. Si no la tiene, la carga semanal se dibuja con un panel OWL propio debajo del diagrama C.

### Menú de la aplicación
| Menú | Pantallas | Quién lo usa |
| Obras | Inicio con obras y pendientes (P-01), formulario del plan con resumen por etapa (P-03), calendario e ingresos de la obra (P-21) | Oficina Técnica, Jefatura de Proyectos |
| Cronograma | Gantt con recursos y acciones (P-15) | Jefatura y asistentes de proyectos |
| Árbol de recursos | Árbol con selección en cascada (P-02) | Oficina Técnica, Proyectos, Logística |
| Abastecimiento | Tablero de compra para la obra (P-18), precios de compra (P-16), requerimientos de obra (P-11) | Logística |
| Avance | Registrar (P-06), por validar (P-07) | Contratas, capataces, supervisores |
| Contratas | Asignaciones (P-05), liquidaciones semanales (P-08) | Proyectos, Jefatura |
| Ingresos | Entregas semanales (P-19), valorizaciones (P-20), cobranza de la obra | Proyectos, Administración y Finanzas |
| Reportes | Cronograma valorizado (P-22), control de saldo (P-13), precios de compra (P-16) | Gerencia, Finanzas, Jefatura |
| Configuración | Tipologías (P-12), actividades, tarifas (P-14), valores por defecto del calendario, parámetros | Administrador |

## Beneficios para Allcenter
Lo que la aplicación hace más fácil para quien la usa y lo que hace sola. Cada fila remite a la pantalla o la regla de este documento que lo implementa. Las cifras son del maestro de MOMEN X. No se estiman horas ahorradas: se pueden medir en el piloto comparando el tiempo del cierre semanal y de la valorización con el actual C.

### Usabilidad
| Beneficio | Cómo lo da la aplicación | Dónde |
| La obra completa en un menú | Plan, cronograma, abastecimiento, avance, contratas, ingresos y reportes están en «Planificación de obra». Requerimientos, OC, OF y facturas se abren con botones inteligentes desde el registro que los originó | La aplicación |
| Un paso para todo un grupo | Marcar un piso marca sus departamentos, ambientes y módulos, y la acción se aplica a todos. En MOMEN, asignar la instalación del piso 05 a Leandro pone la contrata en 59 líneas y agrega 8 líneas a su OC de servicio con una sola confirmación | Árbol del plan (P-02), Asignar contrata (P-05) |
| Recursos pedidos desde el Gantt | El gestor del proyecto asigna contratas, pide materiales o lanza la OF sobre las barras que marca, con los mismos asistentes del árbol | Cronograma con recursos (P-15) |
| Costo de cualquier nivel a la vista | Cada nodo muestra lo planificado, comprometido, real y el saldo de todo lo que tiene debajo. El piso 05 de MOMEN: 66 módulos, 41.33 ML, S/ 8,944.44 | Árbol del plan (P-02), Resumen por etapa (P-03) |
| Revisión antes de crear | Cada asistente muestra una vista previa editable, crea los documentos en borrador y dice qué líneas dejó fuera y por qué | Asistentes (W-01 a W-14) |
| La contrata reporta lo que conoce | Unidades de su driver (módulos armados, metros lineales, tapas) con foto. El porcentaje lo calcula el sistema | Registrar avance (P-06) |
| Precio de compra con contexto | Seis meses de compras en soles por semana, mes y proveedor, con las compras atípicas a la vista, antes de escribir el costo | Precios de compra del producto (P-16) |
| La compra del proyecto en una tabla | Necesidad por semana, stock, OC abiertas, cantidad a comprar y costo por producto; la compra masiva sale de la misma pantalla | Abastecimiento de la obra (P-18) |
| Pendientes del día por rol | Al entrar, cada usuario ve lo que le toca atender y entra a la lista filtrada con un clic | Inicio de la aplicación (P-01) |
| Fechas propias de cada obra | Semana, días de liquidación y pago, frecuencia de valorización, plazos de confirmación, factura y cobro, adelanto y fondo de garantía se configuran en la obra, sin programación | Calendario e ingresos de la obra (P-21) |
| Trazabilidad con el cliente | Cada valorización guarda sus entregas, envíos, observaciones, quién confirmó, su cargo y el documento de conformidad, y la factura apunta a ella | Valorización con el cliente (P-20) |

### Automatización
| Qué hace el sistema | Cuándo | Resultado | Dónde |
| Genera el plan | Al pulsar Generar | Tareas de módulo y líneas de material y contrata con su monto, desde las tipologías. MOMEN: 1,263 tareas de módulo, 3,806 líneas de material y 4,014 de contrata | Generar plan (P-04) |
| Crea el presupuesto | Al aprobar el plan | Presupuesto analítico con una línea por combinación de cuentas; la versión anterior se archiva | Reglas de cálculo |
| Calcula el avance | Al validar un avance | Porcentaje por actividad, por nivel y por partida; el módulo pasa solo a Producido o Instalado | Avance por driver |
| Prepara las liquidaciones | Cada día de liquidación, a primera hora | Una liquidación en borrador por contrata con los avances validados de la semana. Al aprobarla, recepción en la OC y factura con vencimiento el día de pago | Liquidación semanal de contrata (P-08) |
| Prepara la entrega semanal | El mismo día | Ingreso y costo devengados de la semana por partida | Entrega semanal (P-19) |
| Calcula las fechas del ingreso | Al cambiar el calendario de la obra o el cronograma | Corte, presentación, confirmación, factura y cobro previstos, corridos al siguiente día hábil | Calendario e ingresos de la obra (P-21) |
| Factura lo confirmado | Al crear la factura desde la valorización | Cantidad entregada de la OV al % acumulado confirmado y factura enlazada a su valorización | Valorización con el cliente (P-20) |
| Mueve las necesidades con el cronograma | Al arrastrar una etapa | Nueva fecha de necesidad de sus líneas y aviso a Logística de los requerimientos u OC que quedan adelantados | Cronograma con recursos (P-15) |
| Calcula qué comprar | Al abrir el tablero | Necesidad del horizonte menos stock y OC abiertas, redondeada a la unidad de compra | Abastecimiento de la obra (P-18) |
| Convierte y resume precios | Al consultar un producto | Cada compra en soles al tipo de cambio de su fecha, con promedios, mediana, medias móviles y resumen por proveedor | Precios de compra del producto (P-16) |
| Contrasta con el saldo | En requerimiento, OF, OC con analítica, avance, liquidación y factura | Aviso, aprobación adicional o bloqueo, según la política del plan | Control de saldo |
| Avisa | Al cumplirse la condición | Último precio 5 % sobre el plan, necesidad sin OC a menos de una semana, etapa sin contrata, línea sin costo o sin etapa | Inicio de la aplicación (P-01), Abastecimiento de la obra (P-18) |
| Lleva el cronograma valorizado | Con cada documento confirmado | Plan y real por semana de costo, ingreso, valorización, factura y cobro, sin carga manual | Cronograma valorizado de la obra (P-22) |
| Codifica el producto nuevo | Al crearlo desde el plan | Código según su familia, producto activo y actividad a Logística para completarlo | Crear producto desde el plan (P-17) |
Lo que sigue siendo decisión de una persona: aprobar el plan, escribir el costo, validar avances, aprobar liquidaciones, enviar la valorización, registrar la conformidad del cliente y facturar. El sistema prepara cada uno de esos pasos y deja el registro de quién lo hizo y cuándo.

## Arquitectura
Cuatro bloques de izquierda a derecha. Lo de la izquierda ya existe o se configura; el plan de recursos es lo nuevo; lo de la derecha son los documentos de Odoo que el plan genera y contra los que mide.
El plan es la única fuente de cantidades. Todo documento generado guarda el vínculo a sus líneas a través de asignaciones, y lo que se ejecuta actualiza esas líneas.

## Ciclo del proyecto
Cinco etapas en orden. Cada una se detalla como proceso en la sección de flujos.
Roles tomados del organigrama vigente de Allcenter (Oficina Técnica, Jefatura de Operaciones, Proyectos). La asignación exacta por etapa es propuesta C.

## Modelo de datos
Módulo de la aplicación: al_construction_planner. Depende de al_project_gantt_base, al_project_gantt_backend, al_construction_material_request, purchase_request, base_tier_validation, project_mrp, project_forecast, hr_timesheet y account_budget. Los modelos nuevos usan tu mismo espacio de nombres construction.*. Nombres técnicos propuestos C: tú decides la nomenclatura final.
Se sigue la anatomía de tu requerimiento de obra: documento numerado con secuencia propia, barra de estados lineal, línea con su ciclo completo en columnas, estado propio por línea, pocos botones visibles según el estado y botones inteligentes hacia lo generado.

### Entidades y relaciones

#### Núcleo del plan y ejecución

erDiagram
  project_project ||--o{ construction_resource_plan : "versiones del plan"
  construction_resource_plan |o--o| construction_resource_plan : "versión anterior"
  construction_resource_plan ||--|{ construction_resource_plan_line : "líneas"
  construction_resource_plan |o--o| budget_analytic : "presupuesto generado"
  project_task |o--o{ construction_resource_plan_line : "recursos del nivel"
  project_task |o--o{ project_task : "padre e hijos"
  construction_resource_plan_line ||--o{ construction_resource_plan_allocation : "asignaciones"
  construction_resource_plan_allocation }o--o| purchase_request_line : "compra masiva"
  construction_resource_plan_allocation }o--o| construction_material_request_line : "requerimiento de obra"
  construction_resource_plan_allocation }o--o| mrp_production : "orden de fabricación"
  construction_resource_plan_allocation }o--o| purchase_order_line : "OC de servicio"
  construction_resource_plan_allocation }o--o| planning_slot : "turno"
  construction_resource_plan {
    char name "PLR/2026/00001"
    many2one project_id
    integer version
    selection state
    selection exceed_policy
  }
  construction_resource_plan_line {
    many2one task_id
    selection resource_type
    selection stage
    many2one activity_id
    float qty_planned
    float qty_executed
    float progress_pct
    selection line_state
  }


#### Catálogo, avance y liquidación

erDiagram
  project_project ||--o{ construction_typology : "tipologías de la obra"
  construction_typology ||--o{ construction_typology_module : "módulos"
  construction_typology ||--o{ construction_typology_activity : "actividades por ambiente"
  construction_typology ||--|| mrp_bom : "lista de materiales"
  construction_typology_module }o--|| construction_labor_activity : "actividad de armado"
  construction_labor_activity ||--o{ construction_labor_rate : "tarifas"
  project_task ||--o{ construction_task_progress : "avances reportados"
  construction_task_progress }o--|| construction_labor_activity : "driver"
  construction_contract_settlement ||--o{ construction_contract_settlement_line : "líneas por actividad"
  construction_contract_settlement ||--o{ construction_task_progress : "avances liquidados"
  construction_contract_settlement }o--|| purchase_order : "OC de la contrata"
  construction_contract_settlement |o--o| account_move : "factura"
  construction_contract_settlement {
    char name "LIQ/2026/00014"
    many2one partner_id
    date period_start "jueves"
    date period_end "miércoles"
    date payment_date "sábado"
    selection state
  }

Si el diagrama no se dibuja en tu visor, la misma información está en las tablas de campos que siguen.

### Modelos nuevos
Columnas: campo técnico, etiqueta en pantalla, tipo, relación o valores, obligatorio (●) y regla. «calc.» indica campo calculado y almacenado.

#### Plan de recursos
| Campo | Etiqueta | Tipo | Relación o valores | Oblig. | Regla |
| name | Número | char | — | ● | Secuencia PLR/%(year)s/00000 |
| project_id | Obra | many2one | project.project, dominio is_construction_site = True | ● | Una sola versión no reemplazada ni cancelada por obra |
| company_id · currency_id | Compañía · Moneda | many2one | — | ● | Relacionados al proyecto, almacenados |
| user_id | Responsable | many2one | res.users | ● | Por defecto el usuario |
| version · parent_id · replan_reason | Versión · Anterior · Motivo | integer · many2one · text | construction.resource.plan | ● | Motivo obligatorio desde la versión 2 |
| state | Estado | selection | draft Borrador · to_approve En aprobación · approved Aprobado · in_progress En ejecución · closed Cerrado · replaced Reemplazado · cancel Cancelado | ● | Ver diagrama de estados |
| date_start · date_end | Inicio · Fin | date | — | ● | Por defecto las del proyecto |
| exceed_policy · exceed_tolerance | Si se excede el saldo · Tolerancia | selection · float (%) | warn Solo alerta · approval Aprobación adicional · block Bloquear | ● | Por defecto approval y 0 % C |
| lead_days_material · lead_days_contract · lead_days_production | Anticipación (días) | integer | — |  | Para la fecha de necesidad. Por defecto 7 · 3 · 7 E |
| budget_analytic_id | Presupuesto analítico | many2one | budget.analytic |  | Lo crea la aprobación |
| line_ids · allocation_ids | Líneas · Asignaciones | one2many | — |  | Líneas editables solo en Borrador |
| amount_material · amount_service · amount_contract · amount_labor · amount_total | Planificado por tipo | monetary | — |  | calc. |
| amount_committed · amount_actual · amount_remaining | Comprometido · Real · Saldo | monetary | — |  | calc. |
| progress_pct | Avance | float (%) | — |  | calc. Valorizado ejecutado de contratas y personal propio ÷ valorizado planificado |
| *_count | Contadores | integer | — |  | Uno por botón inteligente |

#### Línea del plan
| Campo | Etiqueta | Tipo | Relación o valores | Oblig. | Regla |
| plan_id | Plan | many2one | construction.resource.plan, ondelete=cascade | ● | — |
| task_id | Nivel | many2one | project.task |  | Tarea de piso, departamento, ambiente o módulo. Vacío = obra |
| task_level | Tipo de nivel | selection | Relacionado a task_id.x_level |  | Almacenado |
| floor_task_id · apartment_task_id · space_task_id · module_task_id | Piso · Dpto · Ambiente · Módulo | many2one | project.task |  | calc. Ancestros de task_id por nivel. Son la base de la acumulación y del filtro por selección |
| resource_type | Tipo de recurso | selection | material · service Servicio · contract Contrata · labor Personal propio · production Producción | ● | Decide qué acción puede tomar la línea |
| stage | Etapa | selection | production Producción · assembly Armado · installation Instalación · finishing Acabado y entrega | ● | — |
| product_id | Producto | many2one | product.product |  | Material, servicio o producto de servicio de la actividad |
| activity_id | Actividad (driver) | many2one | construction.labor.activity |  | Obligatorio en contrata y personal propio. Su unidad es el driver de pago |
| partner_id | Contrata o proveedor | many2one | res.partner |  | Lo fija el asistente Asignar contrata |
| role_id | Rol | many2one | planning.role |  | Personal propio |
| typology_id | Tipología | many2one | construction.typology |  | Trazabilidad |
| product_uom_id | Unidad | many2one | uom.uom | ● | Del producto o de la actividad |
| qty_planned · price_unit_planned · amount_planned | Cantidad · Costo unit. · Monto | float · monetary · monetary | — | ● | El costo lo escribe el planificador después de revisar los precios de compra; no hay valor por defecto V. En contratas se muestra la tarifa vigente como referencia. Monto calc. |
| price_basis · price_basis_date | Base del costo · Fecha | char · date | — |  | Qué miró el planificador al fijar el costo (ej. «media móvil 4 semanas al 28/09: 122.84») C |
| date_needed | Fecha de necesidad | date | — | ● | calc. editable. Inicio de la tarea menos la anticipación |
| analytic_distribution · supply_mode | Analítica · Abastecimiento | json · selection | central · direct | ● | Analítica por defecto de la obra, etapa y partida |
| source · source_ref · previous_line_id | Origen · Referencia · Línea anterior | selection · char · many2one | generated · manual · replan |  | Trazabilidad y comparación de versiones |
| qty_requested · qty_purchased · qty_dispatched · qty_consumed | Pedido · Comprado · Despachado · Consumido | float | — |  | calc. Ver reglas |
| qty_executed | Driver acumulado | float | — |  | calc. Contrata: suma de avances validados de esa tarea y actividad. Personal propio: horas registradas |
| qty_settled | Driver liquidado | float | — |  | calc. Avances incluidos en liquidaciones aprobadas |
| progress_pct | Avance | float (%) | — |  | calc. qty_executed ÷ qty_planned, automático V |
| qty_remaining | Saldo | float | — |  | calc. Material: planificado − pedido. Contrata: planificado − acumulado |
| amount_committed · amount_actual · amount_remaining | Comprometido · Real · Saldo | monetary | — |  | calc. |
| line_state | Estado | selection | planned · partial · purchasing · done · exceeded · cancel |  | calc. |

#### Asignación del plan
Un documento cubre varias líneas: una línea de requerimiento de compra de melamina blanca cubre seis pisos, una OF cubre varias cocinas, una línea de la OC de servicio cubre la instalación de mueble bajo de todo un piso. La asignación guarda qué parte del documento corresponde a cada línea del plan.
| Campo | Etiqueta | Tipo | Relación o valores | Oblig. | Regla |
| plan_line_id · plan_id | Línea · Plan | many2one | ondelete=cascade | ● | — |
| kind | Documento | selection | purchase_request · material_request · production · service_order · planning_slot | ● | Exactamente uno de los cinco campos siguientes lleno |
| purchase_request_line_id · material_request_line_id · production_id · purchase_line_id · slot_id | Documento enlazado | many2one | Modelos del documento |  | — |
| qty_allocated · qty_done | Asignado · Ejecutado | float | — | ● | Ejecutado calc., repartido por fecha de necesidad |
| state | Estado | selection | open · done · cancel |  | calc. Sigue al documento |

#### Avance reportado
| Campo | Etiqueta | Tipo | Relación o valores | Oblig. | Regla |
| name | Número | char | — | ● | Secuencia AVN/%(year)s/00000 |
| task_id | Módulo o ambiente | many2one | project.task | ● | Debe tener una línea de plan con esa actividad |
| activity_id | Actividad (driver) | many2one | construction.labor.activity | ● | — |
| plan_line_id | Línea del plan | many2one | construction.resource.plan.line | ● | calc. Línea de la tarea y la actividad en el plan vigente |
| partner_id · project_id | Contrata · Obra | many2one | — |  | Relacionados, almacenados |
| date | Fecha de ejecución | date | — | ● | Decide a qué semana de liquidación pertenece |
| qty | Unidades de driver | float | — | ● | Lo que reporta la contrata, en la unidad de la actividad V |
| uom_id | Unidad | many2one | — |  | Relacionado a la actividad |
| attachment_ids | Fotos | many2many | ir.attachment | ● | Al menos una C |
| reported_by_id | Reportado por | many2one | res.users | ● | Capataz de la contrata o supervisor que transcribe |
| state | Estado | selection | draft Reportado · validated Validado · rejected Rechazado | ● | — |
| validator_id · validation_date · reject_reason | Validación | many2one · datetime · text | — |  | Motivo obligatorio al rechazar |
| settlement_id | Liquidación | many2one | construction.contract.settlement |  | La llena la liquidación semanal |

#### Liquidación semanal de contrata
| Campo | Etiqueta | Tipo | Relación o valores | Oblig. | Regla |
| name | Número | char | — | ● | Secuencia LIQ/%(year)s/00000 |
| partner_id · project_id | Contrata · Obra | many2one | — | ● | Una liquidación por contrata, obra y semana |
| purchase_order_id | OC de servicio | many2one | purchase.order | ● | La OC abierta de la contrata en la obra |
| period_start · period_end | Periodo | date | — | ● | Jueves a miércoles V. Restricción: period_start es jueves y period_end = period_start + 6 |
| settlement_date | Fecha de liquidación | date | — | ● | Jueves siguiente al cierre: period_end + 1 V |
| payment_date | Fecha de pago | date | — | ● | Sábado: period_end + 3 V. Va como vencimiento de la factura |
| state | Estado | selection | draft Borrador · submitted Presentada · validated Validada · approved Aprobada · paid Pagada · cancel Anulada | ● | Ver diagrama de estados |
| progress_ids | Avances liquidados | one2many | construction.task.progress / settlement_id |  | Validados del periodo más rezagados no liquidados |
| line_ids | Líneas | one2many | construction.contract.settlement.line |  | Una por actividad, calculadas de los avances |
| amount_gross · retention_amount · amount_net | Bruto · Retención · Neto | monetary | — |  | calc. Retención según la tarifa (10 % en MOMEN X) |
| invoice_id | Factura | many2one | account.move |  | Creada al aprobar, con vencimiento el sábado |

#### Línea de liquidación
| Campo | Etiqueta | Tipo | Relación o valores | Oblig. | Regla |
| settlement_id · activity_id · uom_id | Liquidación · Actividad · Unidad | many2one | — | ● | — |
| purchase_line_id | Línea de la OC | many2one | purchase.order.line | ● | Línea de la OC con esa actividad |
| qty_period | Driver de la semana | float | — |  | calc. Suma de los avances liquidados de la actividad |
| price_unit · amount | Tarifa · Monto | monetary | — |  | Tarifa de la línea de la OC |
| qty_cumulative · qty_planned · progress_pct | Acumulado · Presupuestado · Avance | float | — |  | Informativo, de las líneas del plan de la contrata |

#### Tipología de la obra
| Campo | Etiqueta | Tipo | Relación o valores | Oblig. | Regla |
| project_id | Obra | many2one | project.project | ● | Código único por obra y familia |
| code · name · family | Código · Nombre · Familia | char · char · selection | kitchen Cocina · closet · bathroom Baño · laundry Lavandería · other | ● | Ej. «01», «Cocina tipo 01» |
| product_tmpl_id · bom_id | Producto · Lista de materiales | many2one | product.template · mrp.bom | ● | La BOM de la tipología es la que usa la OF V |
| module_line_ids | Módulos | one2many | construction.typology.module |  | Plantilla de los módulos de cada ambiente con esta tipología |
| activity_line_ids | Actividades por ambiente | one2many | construction.typology.activity |  | Drivers que no se definen por módulo |
| module_count · ml_low · ml_high | Módulos · ML bajo · ML alto | integer · float · float | — |  | calc. Tipología 01 de MOMEN: 7 módulos, 2.12 ML bajo, 2.10 ML alto X |

#### Módulo de la tipología
| Campo | Etiqueta | Tipo | Relación o valores | Oblig. | Regla |
| typology_id · sequence | Tipología · Orden | many2one · integer | ondelete=cascade | ● | — |
| code | Código del módulo | char | — | ● | Del ETO (MB01, MA01, CAMPANA). Sin ETO, generado por tipo («Tarugo 2») |
| module_type | Tipo | selection | low Bajo · high Alto · drawer Cajonera · hood Campana · shelf Repisero · other Otro | ● | Clasificación del motor de costeo |
| width_mm · ml_group | Ancho · Grupo ML | integer · selection | low · high · none |  | Con ancho, las actividades por ML cuelgan del módulo |
| assembly_activity_id | Actividad de armado | many2one | construction.labor.activity | ● | Tornillo, tarugo, microondas, campana, cajonera, esquinero |
| bom_id | BOM del módulo | many2one | mrp.bom |  | Opcional. Si existe, los materiales cuelgan del módulo |

#### Actividad por ambiente · Actividad · Tarifa
| Campo | Etiqueta | Tipo | Relación o valores | Oblig. | Regla |
| construction.typology.activity |
| typology_id · activity_id · qty | Tipología · Actividad · Cantidad por ambiente | many2one · many2one · float | — | ● | Ej. tipología 01: colocación de puertas 1.93; instalación mueble bajo 2.12 ML X |
| construction.labor.activity |
| code · name · stage · uom_id | Código · Nombre · Etapa · Unidad del driver | char · char · selection · many2one | UND · ML | ● | — |
| product_id | Producto de servicio | many2one | Servicio, recepción manual | ● | Va en la OC de servicio |
| module_level · ml_based | Se mide por módulo · Se mide por ML | boolean | — |  | Deciden el nivel donde cuelga la línea |
| default_price · role_id · productivity · productivity_source | Tarifa base · Rol · Rendimiento · Origen | monetary · many2one · float · selection | estimated · measured |  | Rendimientos de MOMEN: solo estimados X |
| construction.labor.rate |
| activity_id · partner_id · project_id | Actividad · Contrata · Obra | many2one | Contrata y obra opcionales | ● | Búsqueda: obra y contrata, solo obra, solo contrata, tarifa base |
| price · retention_pct · date_from · date_to | Tarifa · Retención · Vigencia | monetary · float · date · date | — | ● | Sin superposición de vigencias |

#### Etapa del ambiente
| Campo | Etiqueta | Tipo | Relación o valores | Oblig. | Regla |
| space_task_id · stage | Ambiente · Etapa | many2one · selection | project.task nivel ambiente | ● | Única por ambiente y etapa |
| date_start · date_end | Inicio · Fin | date | — | ● | Se editan arrastrando la barra en el Gantt. Recalculan date_needed de las líneas de esa etapa y el cronograma valorizado |
| partner_id · role_id | Contrata · Cuadrilla | many2one | — |  | Calculados desde las líneas; se muestran en la barra |
| predecessor_id | Etapa anterior | many2one | construction.space.stage |  | Producción → Armado → Instalación → Acabado; son los vínculos del Gantt |
| progress_pct | Avance | float (%) | — |  | calc. Avance valorizado de las líneas de la etapa en el ambiente y sus módulos |

#### Entrega semanal
| Campo | Etiqueta | Tipo | Relación o valores | Oblig. | Regla |
| name · project_id | Número · Obra | char · many2one | Secuencia ENT/%(year)s/00000 | ● | Una por obra y semana |
| period_start · period_end | Semana | date | — | ● | Según el día de inicio de semana de la obra; jueves a miércoles por defecto V |
| state | Estado | selection | draft Borrador · confirmed Confirmada · valued Valorizada | ● | Confirma la Jefatura de Proyectos |
| progress_ids | Avances de la semana | many2many | construction.task.progress |  | Validados con fecha en la semana |
| line_ids | Líneas por partida | one2many | construction.weekly.delivery.line |  | Ver abajo |
| cost_amount · revenue_amount · margin_amount | Costo · Ingreso · Margen devengados | monetary | — |  | calc. |
| valuation_id | Valorización | many2one | construction.valuation |  | La que la incluyó |
| Campo | Etiqueta | Tipo | Relación o valores | Oblig. | Regla |
| construction.weekly.delivery.line |
| sale_line_id | Partida del contrato | many2one | sale.order.line | ● | Una línea de la orden de venta por partida, como se cargaron las 86 órdenes (D23) |
| progress_prev · progress_end | Avance anterior · Avance al cierre | float (%) | — |  | Avance valorizado acumulado de la partida, con material V |
| revenue_amount | Ingreso devengado | monetary | — |  | precio de la partida × (avance al cierre − anterior) V |
| cost_amount | Costo devengado | monetary | — |  | Contratas y personal propio ejecutados en la semana más materiales consumidos de la partida |

#### Valorización
| Campo | Etiqueta | Tipo | Relación o valores | Oblig. | Regla |
| name · project_id · sale_order_id | Número · Obra · Contrato | char · many2one · many2one | Secuencia VAL/%(year)s/00000 | ● | Numeración también por obra (Valorización 1, 2…) |
| delivery_ids | Entregas incluidas | one2many | construction.weekly.delivery | ● | Entregas confirmadas no valorizadas |
| cutoff_date · planned_submit_date · planned_confirm_date | Corte · Presentación prevista · Confirmación prevista | date | — | ● | Según el calendario de la obra |
| submit_date | Enviada al cliente | date | — |  | — |
| state | Estado | selection | draft Borrador · sent Enviada · observed Observada · confirmed Confirmada · invoiced Facturada · cancel Anulada | ● | Ver diagrama de estados |
| confirm_date · confirm_name · confirm_role · confirm_attachment_ids | Confirmación del cliente | date · char · char · many2many | ir.attachment |  | Obligatorios para pasar a Confirmada: fecha, quién confirma, su cargo y el documento de conformidad V |
| observation_ids | Observaciones del cliente | one2many | mail.message con subtipo propio |  | Cada observación queda con fecha y autor |
| line_ids | Líneas por partida | one2many | construction.valuation.line |  | % anterior, % del periodo, % acumulado, monto entregado, monto confirmado, amortización de adelanto, fondo de garantía |
| amount_delivered · amount_confirmed · amount_pending | Entregado · Confirmado · Por valorizar | monetary | — |  | Lo no confirmado queda pendiente para la siguiente valorización C |
| invoice_id · planned_invoice_date · planned_collection_date | Factura · Facturación prevista · Cobro previsto | many2one · date · date | account.move |  | Fechas según el calendario de la obra |

#### Reportes
| Campo | Etiqueta | Tipo | Relación o valores | Oblig. | Regla |
| construction.purchase.price.report · una fila por línea de OC confirmada |
| product_id · partner_id · date · week_start · month | Producto · Proveedor · Fecha · Semana · Mes | many2one · date | — |  | Fecha = date_approve de la OC; semana según el día de inicio configurado |
| qty · uom_id · price_currency · currency_id | Cantidad · Unidad · Precio · Moneda | float · many2one · float · many2one | — |  | Precio en la moneda de la OC, convertido a la unidad de compra del producto |
| rate · price_pen · amount_pen | Tipo de cambio · Precio S/ · Monto S/ | float · monetary | — |  | Tipo de cambio de Odoo a la fecha de la OC |
| construction.schedule.report · una fila por obra, semana y concepto |
| project_id · week_start · concept · scenario · amount | Obra · Semana · Concepto · Plan o real · Monto | many2one · date · selection · selection · monetary | cost Costo · delivery Entrega · valuation Valorización · invoice Facturación · collection Cobranza |  | Plan: de las etapas, las líneas y el calendario de la obra. Real: entregas, valorizaciones confirmadas, facturas y pagos conciliados. Permite pivote y gráfico nativos por semana |

### Modelos heredados
| Campo | Etiqueta | Tipo | Relación o valores | Oblig. | Regla |
| project.task |
| x_level | Nivel | selection | floor Piso · apartment Departamento · space Ambiente · module Módulo |  | Define la jerarquía del árbol |
| x_floor_task_id · x_apartment_task_id · x_space_task_id | Ancestros | many2one | project.task |  | calc. Recorren parent_id hasta el nivel correspondiente |
| x_typology_id | Tipología | many2one | construction.typology |  | En el ambiente |
| x_module_code · x_module_type · x_width_mm · x_ml_group | Código · Tipo · Ancho · Grupo ML | char · selection · integer · selection | — |  | En el módulo, copiados de la plantilla de la tipología |
| x_unit_state | Estado del módulo | selection | planned Planificado · production En producción · produced Producido · on_site En obra · installed Instalado · delivered Entregado |  | Los mismos estados del diseño Paquetes de obra |
| x_plan_amount · x_progress_pct | Monto planificado · Avance | monetary · float | — |  | calc. Suma de las líneas del nodo y sus descendientes; avance valorizado |
| x_plan_line_ids · x_progress_ids | Recursos · Avances | one2many | — |  | Pestaña «Recursos y avance» |
| mrp.bom.line |
| x_consumption_stage | Etapa de consumo | selection | Mismos valores que stage |  | Obligatorio en BOM de tipología. Columna ETAPA CONSUMO del maestro |
| construction.material.request · .line (tu módulo) |
| x_resource_plan_id · x_exceed_state · x_exceed_reason | Plan · Control de plan · Justificación | many2one · selection · text | ok · exceeded · approved |  | En cabecera |
| x_allocation_ids · x_plan_remaining · x_out_of_plan | Asignaciones · Saldo del plan · Fuera de plan | one2many · float · boolean | — |  | En la línea; saldo y fuera de plan no almacenados |
| purchase.request.line · purchase.order · purchase.order.line |
| x_allocation_ids · x_plan_mode | Asignaciones · Modo de compra masiva | one2many · selection | project · general |  | Línea del requerimiento de compra |
| x_resource_plan_id · x_is_service_order · x_settlement_ids | Plan · OC de servicio · Liquidaciones | many2one · boolean · one2many | — |  | Cabecera de la OC. Una OC de servicio abierta por contrata y obra C |
| x_allocation_ids | Asignaciones | one2many | — |  | Línea de la OC |
| mrp.production · planning.slot |
| x_resource_plan_id · x_space_task_ids · x_allocation_ids | Plan · Ambientes incluidos · Asignaciones | many2one · many2many · one2many | — |  | OF; sus componentes salen de la BOM V |
| x_task_id · x_plan_line_id | Tarea · Línea del plan | many2one | — |  | Turno; el nativo no tiene tarea N |
| res.company (valores por defecto) y project.project (configuración de cada obra) |
| x_week_start_day | Inicio de semana | selection (día) | — |  | Jueves por defecto; configurable por obra V. Rige entregas, liquidaciones y cronograma |
| x_settlement_day · x_payment_day | Liquidación · Pago de contratas | selection (día) | — |  | Jueves · sábado V |
| x_valuation_every · x_valuation_unit | Valorizar cada | integer · selection | semanas · fechas fijas |  | Con «fechas fijas» se carga la lista de cortes de la obra |
| x_valuation_submit_days · x_client_confirm_days · x_invoice_days | Días para presentar · para confirmación del cliente · para facturar | integer | — |  | Desde el corte, desde la presentación y desde la confirmación |
| x_collection_days | Plazo de cobro | integer | — |  | Por defecto el plazo de pago del cliente |
| x_advance_pct · x_advance_amortization_pct | Adelanto · Amortización por valorización | float (%) | — |  | La amortización la decide el cliente en la práctica; el % es la previsión N (análisis del CXC del 13-ago) |
| x_guarantee_pct · x_guarantee_release | Fondo de garantía · Cobro del fondo | float (%) · selection | al cierre · fecha fija |  | Se retiene por factura y se cobra al final |
| product.template |
| x_created_from_plan_id | Creado desde el plan | many2one | construction.resource.plan |  | Trazabilidad de productos creados por el planificador; el producto queda activo en el acto V |
| account.move · sale.order.line |
| x_valuation_id · x_valuation_line_ids | Valorización | many2one · one2many | — |  | La factura sabe de qué valorización nace; la línea de venta, qué valorizaciones la movieron |

### Asistentes
Todos son TransientModel. Los de acción reciben la selección del árbol como lista de tareas: cada asistente expande la selección a sus descendientes y filtra las líneas del plan que le corresponden. Muestran una vista previa editable y crean los documentos en borrador.
| Asistente | Modelo | Campos de cabecera | Vista previa | Crea o cambia |
| Generar plan (W-01) | construction.plan.generate.wizard | plan, ambientes, crear módulos faltantes desde la tipología (sí/no), tipos de recurso, etapas, reemplazar o agregar | Tareas a crear por nivel; líneas y monto por tipo y etapa; advertencias | Tareas de módulo y líneas del plan |
| Compra masiva (W-02) | construction.plan.purchase.wizard | selección, modo (con analítica / stock general), destino, rango de necesidad, etapas, agrupar por | producto, necesidad, libre en central, a comprar | purchase.request y asignaciones |
| Requerimiento de obra (W-03) | construction.plan.request.wizard | selección, etapas, agrupar por (ambiente / departamento / piso), origen, fecha | producto, planificado, pedido, saldo, disponible, a pedir | construction.material.request y asignaciones |
| Orden de fabricación (W-04) | construction.plan.production.wizard | selección, agrupar por (piso / selección), planta, fecha | OF propuesta, producto de la tipología, cantidad de ambientes | mrp.production con componentes de la BOM V |
| Asignar contrata (W-05) | construction.plan.contract.wizard | selección, etapa, actividades, contrata, fechas de ejecución | actividad, driver total, tarifa, monto, retención | partner_id en las líneas; líneas en la OC de servicio de la contrata en la obra |
| Asignar cuadrilla (W-06) | construction.plan.crew.wizard | selección, rol, recursos, semanas, horas por semana | recurso, semana, nivel, horas | planning.slot con tarea y línea |
| Registrar avance (W-07) | construction.plan.progress.wizard | selección, actividad, fecha, fotos | módulo o ambiente, presupuestado, acumulado, saldo, unidades a reportar | construction.task.progress en Reportado |
| Cambiar fechas (W-08) | construction.plan.reschedule.wizard | selección, desplazar n días o fecha nueva, etapas | tareas y líneas afectadas | Fechas de tareas y date_needed |
| Replanificar (W-09) | construction.plan.replan.wizard | motivo, copiar todo o solo saldos | — | Versión nueva en borrador |
| Exceso sobre plan (W-10) | construction.plan.exceed.wizard | documento, política, justificación | producto, saldo, pedido, exceso | Revisión adicional o bloqueo |
| Crear producto (W-11) | construction.product.create.wizard | familia, nombre, código propuesto, unidad de compra y de consumo, proveedor y precio de referencia | productos de nombre parecido | product.product activo y asignado a la línea V |
| Aplicar costo (W-12) | construction.plan.price.wizard | producto, costo que escribe el planificador, base usada, líneas destino | líneas del plan con ese producto y su costo actual | price_unit_planned, price_basis en las líneas en borrador |
| Preparar valorización (W-13) | construction.valuation.prepare.wizard | obra, corte | entregas confirmadas no valorizadas, monto por partida | construction.valuation en borrador |
| Confirmar valorización (W-14) | construction.valuation.confirm.wizard | fecha, quién confirma, cargo, documento, monto confirmado por partida | diferencia entre entregado y confirmado | Valorización Confirmada; habilita la factura |

### Reglas de cálculo
| Campo o regla | Cálculo |
| Acumulación en el árbol | Cada nodo muestra la suma de las líneas que cuelgan de él y de todos sus descendientes. Se resuelve con read_group sobre las líneas agrupando por floor_task_id, apartment_task_id, space_task_id o module_task_id según el nivel que se expande, más las líneas propias del nodo. Sin cálculo recursivo en Python. |
| Selección en cascada | Marcar un nodo marca todos sus descendientes. Desmarcar un hijo deja al padre en estado parcial. La selección que se envía a un asistente es la lista de nodos marcados de más arriba; el asistente expande con child_of. |
| qty_requested | Material: asignaciones de requerimiento de obra y de OF. Contrata: asignaciones a la OC de servicio. Personal propio: horas de turnos. |
| qty_purchased · qty_dispatched · qty_consumed | Comprado: compras confirmadas de la compra masiva y del faltante de los requerimientos. Despachado: qty_dispatched de tu línea y entregas a planta de las OF. Consumido: movimientos «Consumo en obra» (CON) y componentes consumidos de las OF. Todo repartido por fecha de necesidad. |
| qty_executed | Contrata: suma de qty de los avances validados con la misma tarea y actividad. Personal propio: horas de la hoja de horas de la tarea y sus descendientes con empleados del rol. |
| progress_pct de la línea | min(1, qty_executed ÷ qty_planned). Es la comparación automática de unidades de driver presupuestadas contra acumuladas V. |
| Avance de un nodo | Suma de qty_executed × price_unit_planned de sus líneas de contrata y personal propio, entre la suma de amount_planned de esas líneas. Pondera por valor porque las actividades tienen unidades distintas C. Ej.: Dpto 504 con mueble bajo instalado (2.76 ML de 2.76) y nada más de la etapa: 49.68 ÷ 131.06 = 37.9 % de instalación X. |
| amount_committed · amount_actual | Comprometido: pedido no consumido, OC confirmada no facturada, turnos no registrados. Real: consumos valorizados, facturas de las liquidaciones, costo de hojas de horas, costo de OF cerradas. |
| Presupuesto al aprobar | Agrupa líneas por combinación de cuentas analíticas y crea un budget.analytic con una budget.line por combinación (account_id y x_plan8_id, x_plan9_id, x_plan10_id; correspondencia por confirmar N). Cada versión aprobada crea el suyo y archiva el anterior C. |
| Liquidación semanal | Toma los avances validados de la contrata en la obra con date entre period_start y period_end, más los validados de semanas anteriores que no entraron a ninguna liquidación. Agrupa por actividad: driver × tarifa de la línea de la OC. |
| Recepción en la OC | Al aprobar la liquidación se suma qty_period a qty_received de cada línea de la OC de servicio y se crea la factura desde lo recibido, con vencimiento el sábado. No se puede recibir más que lo ordenado. |
| Semana | Todas las semanas de la aplicación (entregas, liquidaciones, cronograma, estadísticas de precios) empiezan el día configurado en la obra; jueves por defecto V. |
| Avance de la partida e ingreso devengado | Avance de la partida = (Σ driver acumulado × tarifa + Σ horas registradas × costo hora + Σ material consumido × costo del plan) ÷ Σ monto planificado de todas las líneas de los ambientes de esa familia en la obra V. Es distinto del avance de un nodo del árbol, que solo mide contratas y personal propio y sirve para pagar y controlar la ejecución. Ingreso devengado de la semana = precio de la línea de venta de la partida × (avance al cierre − avance al inicio) V. |
| Costo devengado de la semana | Real: avances validados × tarifa, horas registradas × costo hora, consumos de material de la semana. Plan: monto de cada línea repartido en partes iguales entre los días hábiles de su etapa (construction.space.stage) C. |
| Fechas previstas del ingreso | Corte de valorización según la frecuencia de la obra; presentación = corte + días para presentar; confirmación = presentación + días del cliente; factura = confirmación + días para facturar; cobro = factura + plazo de cobro. Cobro neto del fondo de garantía y de la amortización de adelanto. |
| Estadísticos de precio | Sobre construction.purchase.price.report en la ventana elegida (6 meses por defecto): promedio ponderado (Σ precio × cantidad ÷ Σ cantidad), promedio simple, mediana, mínimo, máximo, desviación estándar, último precio, promedio ponderado por semana y por mes, media móvil de 4 semanas (ponderada de la semana y las 3 anteriores) y de 3 meses calendario, y el mismo resumen por proveedor. Todo en soles. |

### Seguridad y menús
| Grupo | Para quién | Puede |
| Planificación de obra / Reporte de avance | Capataces de contrata y supervisores | Ver el árbol de sus obras. Registrar avances en Reportado. Ver sus liquidaciones |
| Planificación de obra / Usuario | Proyectos, Logística, Producción | Lanzar los asistentes de acción sobre planes aprobados |
| Planificación de obra / Planificador | Oficina Técnica, supervisores de obra | Editar planes en Borrador, generar, replanificar. Crear productos desde el plan y aplicar costos. Validar avances. Validar liquidaciones |
| Planificación de obra / Ingresos | Administración y Finanzas | Confirmar valorizaciones, crear facturas desde la valorización, ver el cronograma valorizado |
| Planificación de obra / Administrador | Jefatura de Proyectos | Configuración, políticas, aprobar liquidaciones, cerrar planes |
Aprobaciones con tier.definition sobre el plan, sobre el requerimiento con x_exceed_state = 'exceeded' y sobre la liquidación. Regla de registro por compañía.
Menús de la aplicación «Planificación de obra», según la tabla de La aplicación. En Proyecto queda solo el botón inteligente «Plan de recursos» en el formulario de la obra.

## Pantallas
Maquetas con el aspecto de Odoo 19. Los círculos numerados remiten a las notas debajo de cada una. Las cantidades y montos salen del maestro de MOMEN para el piso 05 (departamentos 501 a 508, tipologías 01 a 08) X. Estados, avances, compras y existencias son datos de ejemplo E. Cada maqueta lleva la barra de la aplicación con su menú activo; los asistentes se abren como ventana sobre la pantalla de ese menú.

### Inicio de la aplicación: obras y pendientes (P-01)
Primera pantalla al abrir la aplicación. Lista las obras con su saldo y su próximo hito, y al costado lo que el usuario tiene que atender hoy según su grupo.
| Obra · plan | Planificado | Saldo | Avance | Próximo hito 1 | Estado |
| MOMEN-35-26PLR/2026/00001 · v1 · 12/10 → 18/12 | 170,764.10 | 100,994.10 | 18.4 % | Valorización 1 · factura 06/11 | En ejecución |
| ZZDEMO-99-26PLR/2026/00002 · v1 · 02/11 → 27/11 | — | — | — | Aprobar el plan | Borrador |

##### Pendientes de hoy · jueves 05/11/2026 2
| Qué | Cant. | Dónde |
| Avances reportados por validar | 12 | Avance |
| Liquidaciones del jueves por validar | 3 | Contratas |
| Entrega semanal por confirmar | 1 | Ingresos |
| Valorización confirmada por facturar | 1 | Ingresos |
| Necesidades sin OC en menos de 7 días | 3 | Abastecimiento |
| Último precio sobre el costo del plan | 2 | Abastecimiento |
| Etapas sin contrata que empiezan en 2 semanas | 1 | Cronograma |
| Líneas sin costo en planes en borrador | 3 | Obras |
- 1Sale del calendario de ingresos de la obra y del cronograma: el hito más cercano entre corte, presentación, confirmación, factura, cobro y fin de etapa.
- 2Cada fila es un filtro guardado sobre los documentos que las reglas del sistema dejan pendientes; al pulsarla abre la lista filtrada. Se muestran solo las filas que el grupo del usuario puede atender: el supervisor ve avances, Logística ve compras, Finanzas ve facturas. Las cantidades son de ejemplo E.

### Árbol del plan con selección en cascada (P-02)
Menú Árbol de recursos. Es una acción de cliente OWL; también se abre como pestaña del plan y desde el nodo elegido en el cronograma.
| Nivel | Tipología | Módulos | ML | Material | Contrata | Total | Avance 4 |
| ▾MOMEN-35-26OBRA |  | 1,263 | — | 126,854.54 | 43,909.56 | 170,764.10 | 18.4 % |
| ▸Piso 04PISO |  | 66 | 41.33 | 6,642.91 | 2,301.53 | 8,944.44 | 62.0 % |
| ▾Piso 05PISO |  | 66 | 41.33 | 6,642.91 | 2,301.53 | 8,944.44 | 50.7 % |
| ▾Dpto 501DPTO | 01 | 7 | 4.22 | 735.29 | 258.37 | 993.66 | 74.4 % |
| ▾CocinaAMBIENTE | 01 | 7 | 4.22 | 735.29 | 258.37 | 993.66 | 74.4 % |
| Tornillo 1MÓDULO |  | 1 |  |  | 6.00 | 6.00 | Instalado |
| Tarugo 1MÓDULO |  | 1 |  |  | 8.00 | 8.00 | Instalado |
| Tarugo 2MÓDULO |  | 1 |  |  | 8.00 | 8.00 | Instalado |
| Tarugo 3 · Microondas · Campana · Cajonera4 MÓDULOS |  | 4 |  |  | 32.00 | 32.00 | Instalado |
| ▸Dpto 502DPTO | 02 | 8 | 5.00 | 795.84 | 272.80 | 1,068.64 | 74.8 % |
| ▸Dpto 503DPTO | 03 | 10 | 5.52 | 897.68 | 307.30 | 1,204.98 | 75.4 % |
| ▸Dptos 504 a 5085 DPTOS |  | 41 | 26.59 | 4,214.10 | 1,463.06 | 5,677.16 | 36.9 % |
| ▸Piso 06PISO |  | 66 | 41.33 | 6,642.91 | 2,301.53 | 8,944.44 | 0.0 % |

##### Recursos acumulados de la selección 5
| Actividad | Driver | Acum. | S/ | Contrata |
| Armado módulo tarugo | 29 und | 29 | 232.00 | Armado Gonza |
| Armado módulo tornillo | 14 und | 14 | 84.00 | Armado Gonza |
| Entarugado de muebles | 45 und | 45 | 135.00 | Armado Gonza |
| Instalación mueble bajo | 21.27 ML | 10.14 | 382.86 | Leandro |
| Instalación mueble alto | 20.06 ML | 7.36 | 361.08 | Leandro |
| Limpieza mueble bajo | 21.27 ML | 0.00 | 127.62 | sin asignar |
| 27 actividades |  |  | 2,301.53 |  |
- 1Filtros que cambian lo acumulado: etapa, tipo de recurso, estado del módulo, contrata. Interruptor de medida: soles, cantidad de driver o avance.
- 2Al marcar «Piso 05» quedan marcados sus 8 departamentos, 8 ambientes y 66 módulos. Si se desmarca un módulo, su ambiente, su departamento y el piso pasan a parcial (casilla con guion, como la obra). La barra resume siempre la selección efectiva.
- 3Cada botón abre su asistente con la selección. El asistente toma solo las líneas que le aplican (la compra masiva ignora contratas, la asignación de contrata ignora materiales) y avisa cuántas dejó fuera y por qué.
- 4Avance valorizado de contratas y personal propio del nodo; en el módulo se muestra su estado (x_unit_state). Ejemplo E: armado completo en todo el piso, instalación según la liquidación del 05-nov (501 a 503 completos, 504 solo mueble bajo) y entrega pendiente. Dpto 501: (85.29 + 106.96) ÷ 258.37 = 74.4 %. Piso 05: (786.64 + 380.88) ÷ 2,301.53 = 50.7 %. Tarifas y drivers X.
- 5Panel lateral con lo acumulado de la selección por actividad, producto o rol, con su driver, lo acumulado y la contrata asignada. Cifras del piso 05 X; el acumulado es el de la liquidación de ejemplo del 05-nov E. Desde el panel se puede filtrar el árbol a los nodos que tienen una actividad sin contrata.

### Resumen por etapa (P-03)
| Etapa | Material | Contrata | Planificado | Presupuesto | Diferencia | Comprometido | Real | Saldo |
| Producción | 105,991.94 | — | 105,991.94 | 105,991.94 | 0.00 | 31,400.00 | 18,900.00 | 55,691.94 |
| Armado | 7,532.28 | 15,007.50 | 22,539.78 | 22,539.78 | 0.00 | 9,100.00 | 2,660.00 | 10,779.78 |
| Instalación | 1,328.65 | 17,952.10 | 19,280.75 | 19,280.75 | 0.00 | 7,710.00 | 0.00 | 11,570.75 |
| Acabado y entrega | 1,292.47 | 10,949.96 | 12,242.43 | 12,242.43 | 0.00 | 0.00 | 0.00 | 12,242.43 |
| Sin etapa | 10,709.20 | — | 10,709.20 | — | 10,709.20 | — | — | 10,709.20 |
| Total | 126,854.54 | 43,909.56 | 170,764.10 | 160,054.90 | 10,709.20 | 48,210.00 | 21,560.00 | 100,994.10 |
«Sin etapa» no puede existir en un plan aprobado: la aprobación se bloquea mientras haya líneas sin etapa. En el maestro de MOMEN la melamina blanco RH (3101305) y la rejilla de ventilación (62011239) no tienen etapa en ninguna tipología X.

### Generar plan (P-04)
| Se creará | Nivel | Cantidad | Monto |
| Tareas de módulo | Módulo | 1,263 | — |
| Líneas de armado por módulo | Módulo | 1,263 | — |
| Líneas de contrata por ambiente | Ambiente | 2,751 | — |
| Contratas | 4,014 | 43,909.56 |
| Líneas de material con etapa | Ambiente | 3,500 | 116,145.34 |
| Líneas de material sin etapa | Ambiente | 306 | 10,709.20 |
| Materiales | 3,806 | 126,854.54 |
- 1Crea bajo cada ambiente una tarea por módulo de la plantilla de su tipología, con código, tipo, ancho y estado Planificado. Si el ambiente ya tiene módulos (cargados del ETO), no los duplica.
- 2Las advertencias no impiden generar; impiden aprobar. La última no es error: se resuelve cargando los anchos del ETO por módulo.

### Asignar contrata a la selección (P-05)
| Actividad | Und | Driver presupuestado | Tarifa | Monto | Retención |
| Instalación mueble bajo | ML | 21.27 | 18.00 | 382.86 | 38.29 |
| Regulación puerta mueble bajo | ML | 16.12 | 2.50 | 40.30 | 4.03 |
| Instalación mueble alto | ML | 20.06 | 18.00 | 361.08 | 36.11 |
| Regulación puertas mueble alto | ML | 13.17 | 2.50 | 32.93 | 3.29 |
| Colocación tapas de cajones | Und | 24.00 | 1.50 | 36.00 | 3.60 |
| Recortes de muebles | Und | 12.00 | 4.00 | 48.00 | 4.80 |
| Colocación pines y repisas | Und | 24.00 | 1.00 | 24.00 | 2.40 |
| Instalación sistema push tip on | Und | 16.00 | 1.00 | 16.00 | 1.60 |
| Total · neto S/ 847.05 · se agrega a la OC P00142 de Leandro en MOMEN-35-26 1 | 941.17 | 94.12 |
- 1Pone partner_id en las 59 líneas del plan de instalación del piso 05 y suma las cantidades a las líneas de la OC de servicio abierta de la contrata en la obra; si no existe, la crea en borrador. Una OC por contrata y obra concentra todas las asignaciones y recibe cada liquidación semanal C. Montos iguales al costo de instalación por cocina del maestro X.

### Registrar avance de la selección (P-06)
| Ambiente | Tipología | Presupuestado | Acumulado | Saldo | Reportar hoy 2 | Avance resultante |
| Dpto 501 · Cocina | 01 | 2.12 | 0.00 | 2.12 | 2.12 | 100 % |
| Dpto 502 · Cocina | 02 | 2.50 | 0.00 | 2.50 | 2.50 | 100 % |
| Dpto 503 · Cocina | 03 | 2.76 | 0.00 | 2.76 | 2.76 | 100 % |
| Dpto 504 · Cocina | 04 | 2.76 | 0.00 | 2.76 | 2.76 | 100 % |
| 4 avances en Reportado · 10.14 ML | 10.14 |  |
- 1Lista solo las actividades que tienen líneas en la selección. Si las actividades cuelgan del módulo (armado), las filas son módulos; si cuelgan del ambiente, ambientes.
- 2Por defecto el saldo; se edita fila por fila. El número que se reporta son unidades de driver, las mismas que se pagan V. No acepta más que el saldo más la tolerancia. El mismo asistente funciona en el móvil del capataz con la cámara.

### Avances por validar (P-07)
|  | Número | Nivel | Actividad | Fecha | Driver | Acum. / presup. | Fotos | Semana de liquidación |
| MOMEN-35-26 › Leandro › 29/10 a 04/11 (12) |
|  | AVN/2026/00211 | Dpto 501 · Cocina | Instalación mueble bajo | 03/11 | 2.12 ML | 2.12 / 2.12 | 2 | LIQ del 05/11 |
|  | AVN/2026/00212 | Dpto 501 · Cocina | Instalación mueble alto | 03/11 | 2.10 ML | 2.10 / 2.10 | 2 | LIQ del 05/11 |
|  | AVN/2026/00219 | Dpto 504 · Cocina | Instalación mueble alto | 05/11 | 2.76 ML | 2.76 / 2.76 | 1 | LIQ del 12/11 1 |
- 1La semana de liquidación sale de la fecha de ejecución: lo ejecutado el jueves 05/11 ya pertenece al periodo 05/11 a 11/11 y se liquida el 12/11.

### Liquidación semanal de contrata (P-08)
| Actividad | Und | Driver de la semana | Tarifa | Monto | Acumulado | Presupuestado | Avance 3 |
| Instalación mueble bajo | ML | 10.14 | 18.00 | 182.52 | 10.14 | 21.27 | 47.7 % |
| Regulación puerta mueble bajo | ML | 6.02 | 2.50 | 15.05 | 6.02 | 16.12 | 37.3 % |
| Instalación mueble alto | ML | 7.36 | 18.00 | 132.48 | 7.36 | 20.06 | 36.7 % |
| Regulación puertas mueble alto | ML | 5.33 | 2.50 | 13.33 | 5.33 | 13.17 | 40.5 % |
| Colocación tapas de cajones | Und | 9 | 1.50 | 13.50 | 9 | 24 | 37.5 % |
| Recortes de muebles | Und | 3 | 4.00 | 12.00 | 3 | 12 | 25.0 % |
| Colocación pines y repisas | Und | 6 | 1.00 | 6.00 | 6 | 24 | 25.0 % |
| Instalación sistema push tip on | Und | 6 | 1.00 | 6.00 | 6 | 16 | 37.5 % |
| Bruto · retención 10 % S/ 38.09 · neto a pagar el sábado S/ 342.79 | 380.88 | 941.17 | 40.5 % |
- 1Botones por estado. Borrador: «Presentar». Presentada: «Validar» (supervisor) y «Devolver a la contrata» con motivo. Validada: los de la validación por niveles. Aprobada: se recibe en la OC y se crea la factura; el pago la deja en Pagada al conciliarse.
- 2Fechas calculadas desde el periodo; no se editan. Una acción programada crea cada jueves a primera hora las liquidaciones en borrador de toda contrata con avances validados del periodo.
- 3Avance por actividad: acumulado ÷ presupuestado, automático. El total de la fila final es valorizado: 380.88 ÷ 941.17. Ejemplo: departamentos 501 a 503 con la instalación completa y el 504 con mueble bajo instalado; drivers y tarifas del maestro X.

### Ambiente, pestaña Recursos y avance (P-09)
| Etapa | Actividad o producto | Contrata | Presupuestado | Und | Acumulado | Monto | Avance |
| Instalación · avance valorizado 37.9 % |
| Instalación | Instalación mueble bajo | Leandro | 2.76 | ML | 2.76 | 49.68 | 100 % |
| Instalación | Regulación puerta mueble bajo | Leandro | 2.30 | ML | 0.00 | 5.75 | 0 % |
| Instalación | Instalación mueble alto | Leandro | 2.76 | ML | 0.00 | 49.68 | 0 % |
| Instalación | Regulación puertas mueble alto | Leandro | 1.78 | ML | 0.00 | 4.45 | 0 % |
| Instalación | Tapas de cajones · recortes · pines · push | Leandro | — | Und | 0 | 21.50 | 0 % |
| Instalación de la cocina | 131.06 | 37.9 % |

### Compra masiva (P-10)
| Producto | Und | Necesidad | Libre en central | A comprar | Requerido |
| [3101508] Melamina MDP blanco fantasía 18 mm | Plancha | 88.08 | 20.00 | 89.00 | 12/10/2026 |
| [3101318] Melamina coñac 18 mm | Plancha | 44.24 | 0.00 | 45.00 | 12/10/2026 |
| [3103002] MDP aglomerado tropicalizado 18 mm | Plancha | 15.68 | 6.00 | 16.00 | 12/10/2026 |
| [3104048] MDF tropicalizado blanco 3 mm | Plancha | 50.75 | 12.00 | 51.00 | 12/10/2026 |
| [3106287] Tapacanto grueso coñac 22×3 mm | m | 786.50 | 150.00 | 786.50 | 12/10/2026 |
| [3105073] Corredera telescópica 50 cm | Juego | 108.00 | 40.00 | 108.00 | 19/10/2026 |
| 15 productos · S/ 30,283.79 de necesidad a costo del maestro |
- 1Con analítica: cada línea lleva la distribución de la obra y «A comprar» parte de la necesidad completa. Stock general: sin analítica de obra y «A comprar» parte de la necesidad menos lo libre. En los dos sube el comprado de las líneas del plan V. Planchas redondeadas a entero.

### Requerimiento de obra con control de plan (P-11)
| Material | Nivel | Cantidad | Und | A despachar | A comprar | Saldo del plan | Control |
| [3105983] Tornillos 4×50 | Piso 05 · 8 ambientes | 1,100 | Und | 1,100 | 0 | 974 | Excede 126 |
| [3105018] Soporte pin transparente | Piso 05 · 8 ambientes | 212 | Und | 212 | 0 | 212 | En plan |
| [3200018] Tapatornillo blanco | Piso 05 · 8 ambientes | 700 | Und | 700 | 0 | 614 | Excede 86 |
| [3105606] Bisagra push open copa 35 mm | Piso 05 · 8 ambientes | 10 | Und | 10 | 0 | — | Fuera de etapa |
Columnas nuevas al final de tu lista de líneas; el resto es tu formulario actual. Se abre desde Abastecimiento › Requerimientos de obra de esta aplicación, y el documento sigue siendo de tu módulo. La bisagra push open está planificada en Armado, no en Instalación X. Un requerimiento creado desde la selección de un piso lleva en cada línea la tarea del piso y asignaciones a las líneas de cada ambiente.

### Tipología de la obra (P-12)
| Código 1 | Tipo | Ancho | Armado | Tarifa |
| Tornillo 1 | — | — | Módulo tornillo | 6.00 |
| Tarugo 1 a 3 | — | — | Módulo tarugo | 8.00 |
| Microondas | — | — | Microondas | 10.00 |
| Campana | Campana | — | Módulo de campana | 7.00 |
| Cajonera | Cajonera | — | Cajonera | 7.00 |
| 7 módulos · armado por módulo S/ 54.00 · por ambiente S/ 31.29 | 85.29 |
| Componente | Cant. | Etapa de consumo |
| [3101508] Melamina MDP blanco fantasía | 1.9591 | Producción |
| [3101318] Melamina coñac | 0.9360 | Producción |
| [3101305] Melamina blanco RH fantasía | 0.2544 | Sin etapa |
| [3105001] Bisagra lateral Danco | 10 | Armado |
| [3105983] Tornillos 4×50 | 121 | Instalación |
| [3200018] Tapatornillo blanco | 78 | Acabado y entrega |
- 1MOMEN no trae códigos ni anchos por módulo: los nombres salen del tipo de armado X. Con el ETO leído (biblioteca de tipologías del motor de costeo) se cargan MB01, MA01, CAMPANA, con su ancho, y la instalación baja al módulo.

### Análisis de control (P-13)
| Etapa › Tipo de recurso | Planificado | Comprometido | Real | Saldo | % ejecutado |
| Producción | 105,991.94 | 31,400.00 | 18,900.00 | 55,691.94 | 17.8 % |
| Armado | 22,539.78 | 9,100.00 | 2,660.00 | 10,779.78 | 11.8 % |
| Instalación | 19,280.75 | 7,710.00 | 0.00 | 11,570.75 | 0.0 % |
| Acabado y entrega | 12,242.43 | 0.00 | 0.00 | 12,242.43 | 0.0 % |
| Sin etapa | 10,709.20 | 0.00 | 0.00 | 10,709.20 | 0.0 % |
| Total obra | 170,764.10 | 48,210.00 | 21,560.00 | 100,994.10 | 12.6 % |

### Tarifas de contratas (P-14)
| Actividad | Unidad del driver | Obra | Contrata | Tarifa | Retención |
| Instalación mueble bajo | ML | MOMEN-35-26 | (cualquiera) | 18.00 | 10 % |
| Armado módulo tarugo | Und | (cualquiera) | (cualquiera) | 8.00 | 10 % |
| Limpieza mueble bajo | ML | MOMEN-35-26 | (cualquiera) | 6.00 | 10 % |
| Marco de closet | Und | Masías | (cualquiera) | 19.50 | 10 % |
| Marco de closet | Und | T. Marsano | (cualquiera) | 18.50 | 10 % |
| Marco de closet | Und | Affinity | (cualquiera) | 15.00 | 10 % |

### Cronograma con recursos (P-15)
Pantalla del menú Cronograma. Es el componente Gantt de Cristóbal con tres agregados de esta aplicación: la columna de selección, el panel de recursos y la carga semanal debajo del diagrama. Desde aquí el gestor del proyecto pide y asigna recursos sin pasar por el árbol V.
Tarea · etapa · recurso
12/10
19/10
26/10
02/11
09/11

##### Recursos de la selección
| Recurso | Plan S/ | Avance |
| 8 actividades de contrata · Leandro | 941.17 | 40.5 % |
| Materiales de instalación | 69.54 | — |
| Personal propio | 0.00 | — |
| Total de la selección | 1,010.71 |  |
OC de servicio P00142 · requerimiento RQO/2026/00031 · liquidación del 05/11
| Contrata · etapa 4 | 12/10 | 19/10 | 26/10 | 02/11 | 09/11 |
| Armado Gonza · Armado | — | 1,627.62 | 2,359.92 | 2,359.92 | 2,359.92 |
| Leandro · Instalación | — | — | 1,952.29 | 2,823.50 | 2,823.50 |
| Sin asignar · Acabado y entrega | — | — | — | 1,196.72 | 1,721.16 |
| Total | 0.00 | 1,627.62 | 4,312.21 | 6,380.14 | 6,904.58 |
- 1Escala, línea base, ruta crítica y exportación son del Gantt de Cristóbal y no se repiten. «Filas» alterna entre las tareas del proyecto y las etapas de cada ambiente (construction.space.stage), que la capa de datos heredada entrega como filas hijas.
- 2Selección múltiple con la extensión multiselect. Marcar un piso marca sus filas hijas, igual que en el árbol (P-02). La barra y los botones son los del árbol: abren los asistentes W-02 a W-08 con la selección.
- 3Barra clara: etapa sin contrata ni cuadrilla. Arrastrar una barra cambia las fechas de la etapa; el sistema recalcula date_needed de sus líneas, avisa qué requerimientos y OC quedan con fecha anterior a la nueva necesidad y actualiza el cronograma valorizado.
- 4Montos de contrata por semana calendario con el supuesto del ejemplo: cada grupo de tres pisos hace una etapa por semana desde el lunes 12/10 C. Montos por piso del maestro X; las contratas asignadas a todo el armado y a toda la instalación son de ejemplo E. Si la licencia de dhtmlxGantt no trae la vista de recursos, este panel es una tabla OWL propia.

### Precios de compra del producto (P-16)
Se abre desde la línea del plan, desde el abastecimiento o desde el menú. El planificador la mira antes de escribir el costo de la línea V.
Soles por plancha. Cada punto es una semana con compras 4
| Mes | Compras | Planchas | Ponderado | Media 3 meses |
| abr-2026 | 2 | 896 | 116.86 | 116.86 |
| may-2026 | 5 | 1,639 | 122.07 | 120.23 |
| jun-2026 | 6 | 1,792 | 125.53 | 122.42 |
| jul-2026 | 5 | 1,344 | 122.08 | 123.37 |
| ago-2026 | 3 | 1,344 | 121.22 | 123.20 |
| set-2026 | 6 | 2,016 | 123.32 | 122.37 |
| Proveedor | Moneda | Compras | Planchas | Ponderado |
| Novopan Perú S.A.C. | US$ | 24 | 8,864 | 121.61 |
| Mavicch S.A.C. | S/ | 1 | 7 | 174.50 |
| Carpicentro S.A.C. | S/ | 1 | 64 | 162.00 |
| Soc. Import. de Prod. Ferreteros | S/ | 1 | 96 | 165.00 |
- 1Ventana de 6 meses por defecto, editable. Las semanas empiezan el día configurado en la obra; en la maqueta, jueves.
- 2Todo en soles. Las compras en dólares se convierten con el tipo de cambio de Odoo a la fecha de aprobación de la OC (res.currency.rate, inverse_company_rate). La melamina tuvo 24 compras a Novopan en dólares (US$ 34.20 a 35.91 y una a US$ 42.37) y 3 a otros proveedores en soles N.
- 3El costo del producto en producción es 35.91, la cifra del precio en dólares. Es probable que se haya cargado sin convertir C. Por eso el plan no toma el costo del producto por defecto: lo escribe el planificador V.
- 4Los dos picos son compras chicas en soles: 7 planchas a Mavicch el 28/05 y la semana del 11/06 con Carpicentro (S/ 162) y SIPFSA (S/ 165) junto a una de Novopan. El ponderado los diluye; el promedio simple no (127.34). Pasando el cursor sobre un punto se ven compras, planchas y media móvil.
- 5Abre W-12 con la base elegida (ponderado de 6 o 3 meses, media móvil, último precio o manual). La base y su fecha quedan en price_basis y price_basis_date de las líneas.

### Crear producto desde el plan (P-17)
| Productos parecidos 2 | Unidad | Coincidencia | Último precio |
| [3105606] Bisagra push open copa 35 mm | Und | 68 % | — |
| [3105001] Bisagra lateral Danco | Und | 41 % | — |
- 1El código sale de la regla del maestro: familia de 4 dígitos más correlativo (decisión del 17-set). El número de la maqueta es de ejemplo E; se asigna al guardar, para que dos planificadores no tomen el mismo.
- 2Antes de crear busca por nombre y atributos, porque el maestro ya tiene 116 pares de productos probablemente duplicados N. El producto se crea activo en el acto y queda marcado con el plan que lo creó V; Logística recibe una actividad para completar marca, proveedor y cuentas C. Sin costo, la línea impide aprobar el plan hasta que se aplique W-12.

### Abastecimiento de la obra (P-18)
Tablero para cargar el almacén de la obra antes de que las etapas lo pidan. Desde aquí se lanza la compra masiva para el proyecto.
| Producto | Und | Obra | 12/10 | 19/10 | 26/10 | 02/11 | Stock | En OC | A comprar | Costo plan | Último | Monto |
| [3101508] Melamina MDP blanco fantasía 18 mm | Plancha | 330.82 | 36.07 | 52.02 | 52.02 | 52.02 | 40.00 | 96.00 | 57 | 122.79 | 123.89 | 6,999.03 |
| [3101318] Melamina coñac 18 mm | Plancha | 165.58 | 18.24 | 26.00 | 26.00 | 26.00 | 0.00 | 0.00 | 97 | 228.07 | 239.42 +5.0 % | 22,122.79 |
| [3103002] MDP aglomerado tropicalizado 18 mm | Plancha | 58.59 | 6.48 | 9.20 | 9.20 | 9.20 | 10.00 | 0.00 | 25 | 168.84 | 168.84 | 4,221.00 |
| [3104048] MDF tropicalizado blanco 3 mm | Plancha | 191.01 | 20.70 | 30.06 | 30.06 | 30.06 | 0.00 | 0.00 | 111 | 44.30 | 43.37 | 4,917.30 |
| [3106287] Tapacanto grueso coñac 22×3 mm | m | 2,944.00 | 324.18 | 462.32 | 462.32 | 462.32 | 500.00 | 0.00 | 1,212 | 0.99 | 0.99 | 1,199.88 |
| [3105073] Corredera telescópica 50 cm | Juego | 402.00 | 0.00 | 45.00 | 63.00 | 63.00 | 20.00 | 0.00 | 151 | 9.19 | 10.20 +11.0 % | 1,387.69 |
| Total de lo marcado | 40,847.69 |
- 1Necesidad por semana de inicio de la etapa que consume el material (x_consumption_stage) en cada ambiente, con el calendario de P-15. «Obra» es la necesidad total del plan X; la repartición semanal usa el supuesto de tres pisos por semana C.
- 2«Stock» es lo libre en el almacén de la obra y en central; «En OC», lo pedido y no recibido con la analítica de la obra. En la maqueta son de ejemplo E.
- 3A comprar = necesidad del horizonte − stock − en OC, redondeado hacia arriba a la unidad de compra. Ej.: melamina blanca 192.13 − 40 − 96 = 56.13 → 57 planchas.
- 4«Costo plan» es el que escribió el planificador con W-12; en la maqueta, la media móvil de 4 semanas para la melamina blanca y el ponderado de 3 meses para el resto E, sobre precios reales N. La alerta aparece cuando el último precio supera al del plan en 5 % o más; el umbral es parámetro C. El tapacanto está a 1.69 en la BOM del maestro y se compra a 0.99: revisar la unidad antes de aprobar X.
- 5«Compra masiva» abre W-02 (P-10) con las filas marcadas; el modo, con analítica de la obra o stock general, se elige en cada lanzamiento V.

### Entrega semanal (P-19)
| Partida | Precio | Avance anterior | Avance al cierre 2 | Del periodo | Ingreso devengado 3 | Costo devengado | Margen |
| Cocinas · línea 1 de la OV 4 | 159,231.23 | 28.10 % | 42.94 % | 14.84 % | 23,627.65 | 25,338.96 | −1,711.31 |
| Total de la semana · costo: contratas 5,552.96 · materiales 19,786.00 · personal propio 0.00 | 23,627.65 | 25,338.96 | −1,711.31 |
- 1La genera la acción programada del día de liquidación, junto con las liquidaciones de las contratas, y la confirma la Jefatura de Proyectos. Toma los avances validados con fecha dentro de la semana configurada de la obra V.
- 2Avance valorizado de toda la partida: lo ejecutado de contratas y personal propio a tarifa más el material consumido a costo del plan, entre el monto planificado de la partida V. En el plan, cada semana devenga ingreso en la misma proporción que su costo.
- 3Precio de la partida × avance del periodo: 159,231.23 × (42.94 % − 28.10 %) = 23,627.65; el sistema calcula con el avance sin redondear. El costo es lo ejecutado en la semana: avances × tarifa, horas registradas y consumos de material.
- 4El ejemplo trata el contrato de MOMEN como una sola partida «Cocinas» E. El monto es el adjudicado que figura en la carpeta MOMEN; no está en New Allcenter ni en producción y no se sabe si incluye IGV. Las cifras de la semana son las del plan para ese periodo, a modo de ejemplo.

### Valorización con el cliente (P-20)
| Partida | Precio | % anterior | % periodo | % acumulado | Entregado | Confirmado | Fondo de garantía 5 % | Neto |
| Cocinas | 159,231.23 | 28.10 % | 30.42 % | 58.51 % | 48,430.32 | 48,430.32 | 2,421.52 | 46,008.80 |
Historial: 13/11 enviada · 16/11 el cliente observa dos cocinas del piso 06 con puertas por regular · 17/11 observación levantada con fotos · 18/11 conformidad recibida.
- 1Sin fecha, nombre, cargo y documento del cliente no pasa a Confirmada, y sin Confirmada no se factura. Cada envío, observación y conformidad queda con fecha y autor en el historial, y el documento como adjunto de la valorización V.
- 2Si el cliente confirma menos de lo entregado, la diferencia queda «por valorizar» y entra en la siguiente C. «Crear factura» lleva la cantidad entregada de la línea de la OV al % acumulado confirmado (OV por partida con cantidad 1, D23) y factura lo entregado; la factura guarda x_valuation_id. Cómo se registra el fondo de garantía en la factura se acuerda con contabilidad C.

### Calendario e ingresos de la obra (P-21)
Pestaña del formulario de la obra. Cada obra lleva sus fechas de valorización, facturación y cobranza V.
| Val. | Corte | Presentación | Confirmación | Factura | Cobro | Monto previsto | Fondo de garantía | Neto a cobrar |
| 1 | 28/10 | 30/10 | 04/11 | 06/11 | 07/12 | 44,743.63 | 2,237.18 | 42,506.45 |
| 2 | 11/11 | 13/11 | 18/11 | 20/11 | 21/12 | 48,430.32 | 2,421.52 | 46,008.80 |
| 3 | 25/11 | 27/11 | 02/12 | 04/12 | 04/01/2027 | 46,622.87 | 2,331.14 | 44,291.73 |
| 4 | 09/12 | 11/12 | 16/12 | 18/12 | 18/01/2027 | 16,766.59 | 838.33 | 15,928.26 |
| 5 | 23/12 | 28/12 | 04/01/2027 | 06/01/2027 | 05/02/2027 | 2,667.82 | 133.39 | 2,534.43 |
| Total · el fondo de garantía se cobra al cierre de obra | 159,231.23 | 7,961.56 | 151,269.67 |
- 1MOMEN, según su carpeta: el contrato dice que el adelanto no aplica y el correo de adjudicación hablaba de 30 % con carta fianza. La maqueta usa 0 % hasta aclararlo. En la práctica la amortización la decide el cliente en cada valorización; el % es la previsión.
- 2Una fecha que cae en día no hábil pasa al siguiente día hábil C. Ej.: la presentación de la valorización 5 caería el viernes 25/12 y pasa al lunes 28/12; los cobros que caen domingo pasan al lunes. La tabla se recalcula al cambiar cualquier parámetro o el cronograma.

### Cronograma valorizado de la obra (P-22)
Reporte semanal de costo e ingreso por obra, plan contra real. Sale de construction.schedule.report y también se puede ver como pivote o gráfico nativo de Odoo.
Soles acumulados por semana 1
| Semana | Costo | Costo acum. | Ingreso devengado | Ingreso acum. | Margen acum. | Valorización confirmada | Facturado | Cobrado | Cobrado acum. |
| 08/10 – 14/10 | 7,682.94 | 7,682.94 | 7,164.06 | 7,164.06 | −518.88 | — | — | — | 0.00 |
| 15/10 – 21/10 | 17,598.35 | 25,281.29 | 16,409.81 | 23,573.87 | −1,707.42 | — | — | — | 0.00 |
| 22/10 – 28/10 | 22,703.05 | 47,984.34 | 21,169.76 | 44,743.63 | −3,240.71 | — | — | — | 0.00 |
| 29/10 – 04/11 | 25,338.96 | 73,323.30 | 23,627.65 | 68,371.28 | −4,952.02 | 44,743.63 | — | — | 0.00 |
| 05/11 – 11/11 | 26,599.09 | 99,922.39 | 24,802.67 | 93,173.95 | −6,748.44 | — | 44,743.63 | — | 0.00 |
| 12/11 – 18/11 | 26,833.31 | 126,755.70 | 25,021.07 | 118,195.02 | −8,560.68 | 48,430.32 | — | — | 0.00 |
| 19/11 – 25/11 | 23,166.39 | 149,922.09 | 21,601.80 | 139,796.82 | −10,125.27 | — | 48,430.32 | — | 0.00 |
| 26/11 – 02/12 | 12,683.64 | 162,605.73 | 11,827.03 | 151,623.85 | −10,981.88 | 46,622.87 | — | — | 0.00 |
| 03/12 – 09/12 | 5,297.32 | 167,903.05 | 4,939.56 | 156,563.41 | −11,339.64 | — | 46,622.87 | 42,506.45 | 42,506.45 |
| 10/12 – 16/12 | 2,347.92 | 170,250.97 | 2,189.35 | 158,752.76 | −11,498.21 | 16,766.59 | — | — | 42,506.45 |
| 17/12 – 23/12 | 513.13 | 170,764.10 | 478.47 | 159,231.23 | −11,532.87 | — | 16,766.59 | 46,008.80 | 88,515.25 |
| 24/12 – 30/12 | — | 170,764.10 | — | 159,231.23 | −11,532.87 | — | — | — | 88,515.25 |
| 31/12 – 06/01 | — | 170,764.10 | — | 159,231.23 | −11,532.87 | 2,667.82 | 2,667.82 | 44,291.73 | 132,806.98 |
| 07/01 – 13/01 | — | 170,764.10 | — | 159,231.23 | −11,532.87 | — | — | — | 132,806.98 |
| 14/01 – 20/01 | — | 170,764.10 | — | 159,231.23 | −11,532.87 | — | — | 15,928.26 | 148,735.24 |
| 21/01 – 27/01 | — | 170,764.10 | — | 159,231.23 | −11,532.87 | — | — | — | 148,735.24 |
| 28/01 – 03/02 | — | 170,764.10 | — | 159,231.23 | −11,532.87 | — | — | — | 148,735.24 |
| 04/02 – 10/02 | — | 170,764.10 | — | 159,231.23 | −11,532.87 | — | — | 2,534.43 | 151,269.67 |
| Fondo de garantía, al cierre |  |  |  |  |  |  |  | 7,961.56 | 159,231.23 |
- 1Costo plan: cada línea del plan repartida en los días hábiles de su etapa; los S/ 10,709.20 de material sin etapa se asignaron a producción para el ejemplo C. Ingreso plan: precio de la partida × avance previsto de la partida, con material. Con escenario «real» toma entregas confirmadas, valorizaciones confirmadas, facturas y pagos conciliados. La última semana absorbe el redondeo para cerrar en el precio y en el costo del plan.

## Flujos de trabajo

### Estados de los documentos

#### Plan de recursos

stateDiagram-v2
  direction LR
  state "Borrador" as draft
  state "En aprobación" as to_approve
  state "Aprobado" as approved
  state "En ejecución" as in_progress
  state "Cerrado" as closed
  state "Reemplazado" as replaced
  state "Cancelado" as cancel
  [*] --> draft
  draft --> to_approve : Solicitar aprobación
  to_approve --> draft : Rechazo
  to_approve --> approved : Última aprobación
  approved --> in_progress : Primer documento generado
  in_progress --> closed : Cerrar
  approved --> replaced : Nueva versión aprobada
  in_progress --> replaced : Nueva versión aprobada
  draft --> cancel : Cancelar

| Transición | Quién | Condiciones | Efecto |
| Solicitar aprobación | Planificador | Ninguna línea sin etapa, sin costo, o de contrata sin actividad | Revisiones por monto |
| Última aprobación | Aprobador | Todas las revisiones aprobadas | Presupuesto analítico; líneas bloqueadas; la versión anterior pasa a Reemplazado y sus asignaciones abiertas a la nueva |
| Cerrar | Administrador | Sin asignaciones abiertas ni liquidaciones pendientes, o confirmación | Solo lectura |

#### Avance reportado

stateDiagram-v2
  direction LR
  state "Reportado" as draft
  state "Validado" as validated
  state "Rechazado" as rejected
  state "Liquidado" as settled
  [*] --> draft : Contrata reporta unidades de driver
  draft --> validated : Supervisor valida
  draft --> rejected : Supervisor rechaza con motivo
  rejected --> draft : Contrata corrige
  validated --> settled : Entra a una liquidación aprobada
  validated --> draft : Supervisor revierte, si no está liquidado

«Liquidado» no es un valor de state; es tener settlement_id en una liquidación aprobada. Un avance liquidado no se revierte.

#### Liquidación semanal

stateDiagram-v2
  direction LR
  state "Borrador" as draft
  state "Presentada" as submitted
  state "Validada" as validated
  state "Aprobada" as approved
  state "Pagada" as paid
  [*] --> draft : Jueves, acción programada
  draft --> submitted : Contrata o supervisor presenta
  submitted --> draft : Devuelta con motivo
  submitted --> validated : Supervisor valida cantidades
  validated --> approved : Jefatura aprueba
  approved --> paid : Pago del sábado conciliado


#### Entrega semanal

stateDiagram-v2
  direction LR
  state "Borrador" as draft
  state "Confirmada" as confirmed
  state "Valorizada" as valued
  [*] --> draft : Día de liquidación, acción programada
  draft --> confirmed : Jefatura de Proyectos confirma
  confirmed --> draft : Se reabre, si no está valorizada
  confirmed --> valued : Entra a una valorización confirmada
  valued --> confirmed : Se anula la valorización

Una entrega confirmada fija el ingreso y el costo devengados de la semana. Un avance validado después de confirmar la entrega cae en la entrega siguiente, igual que en las liquidaciones C.

#### Valorización

stateDiagram-v2
  direction LR
  state "Borrador" as draft
  state "Enviada" as sent
  state "Observada" as observed
  state "Confirmada" as confirmed
  state "Facturada" as invoiced
  state "Anulada" as cancel
  [*] --> draft : Preparar valorización en el corte
  draft --> sent : Proyectos envía al cliente
  sent --> observed : El cliente observa
  observed --> sent : Observación levantada y reenviada
  sent --> confirmed : Conformidad con fecha, nombre, cargo y documento
  confirmed --> invoiced : Factura publicada
  draft --> cancel : Anular
  sent --> cancel : Anular
  observed --> cancel : Anular

| Transición | Quién | Condiciones | Efecto |
| Enviar | Proyectos | Al menos una entrega confirmada | Fecha de envío; PDF de la valorización en el historial |
| Confirmar (W-14) | Proyectos o Administración y Finanzas | Fecha, nombre, cargo y documento del cliente V | Entregas a Valorizada; habilita la factura; lo no confirmado queda por valorizar |
| Facturar | Administración y Finanzas | Valorización confirmada | Cantidad entregada de la OV al % acumulado; factura con x_valuation_id |
| Anular | Administrador | Sin factura | Las entregas vuelven a Confirmada |

#### Línea del plan
Estado calculado, en este orden de prioridad: Excedida, Completa, En compra, Parcial, Planificada. En contratas, «Completa» es driver acumulado igual al presupuestado y todo liquidado; «Excedida» es acumulado mayor al presupuestado más la tolerancia.

### Procesos por rol

#### Carga y aprobación del plan (F-01)

flowchart LR
  subgraph OT["Oficina Técnica"]
    A1["Carga tipologías de la obra: módulos, BOM, actividades"] --> A2["Genera plan y módulos"]
    A2 --> A3{"¿Advertencias que bloquean?"}
    A3 -- "Sí" --> A4["Corrige tipología o tarifa"]
    A4 --> A2
    A3 -- "No" --> A5["Revisa el árbol acumulado y agrega servicios y fletes"]
    A5 --> A6["Solicita aprobación"]
  end
  subgraph AP["Jefatura de Proyectos y Gerencia"]
    B1{"¿Aprueba?"}
  end
  subgraph SY["Sistema"]
    C1["Crea el presupuesto analítico"]
  end
  A6 --> B1
  B1 -- "No" --> A4
  B1 -- "Sí" --> C1


#### Acción sobre una selección (F-02)
Patrón común de todas las acciones del árbol.

flowchart LR
  subgraph US["Usuario"]
    A1["Marca piso, departamento o módulos"] --> A2["Pulsa la acción"]
    A4["Ajusta la vista previa y confirma"]
  end
  subgraph SY["Sistema"]
    B1["Expande la selección a descendientes"] --> B2["Filtra las líneas que aplican a la acción"]
    B2 --> B3["Arma la vista previa y avisa lo que dejó fuera"]
    B4["Crea documentos en borrador y asignaciones"]
    B5["Recalcula acumulados del árbol"]
  end
  A2 --> B1
  B3 --> A4
  A4 --> B4
  B4 --> B5

| Acción | Líneas que toma | Resultado |
| Asignar contrata | Contrata de la etapa y actividades elegidas | partner_id en las líneas; cantidades en la OC de servicio de la contrata en la obra |
| Asignar cuadrilla | Personal propio | Turnos por recurso y semana con la tarea del nodo |
| Registrar avance | Contrata o personal propio de la actividad elegida | Avances en Reportado por módulo o ambiente |
| Compra masiva | Material y servicio | Requerimiento de compra consolidado por producto |
| Requerimiento de obra | Material de instalación y acabado | Requerimiento por ambiente, departamento o piso |
| Orden de fabricación | Ambientes con tipología | OF por piso con el producto de la tipología; componentes de la BOM |
| Cambiar fechas | Todas las del nodo | Fechas de tareas y de necesidad desplazadas |

#### Compra masiva (F-03)

flowchart LR
  subgraph LG["Logística"]
    A1["Selecciona pisos y abre Compra masiva"] --> A2{"¿Modo?"}
    A2 -- "Con analítica" --> A3["A comprar = necesidad"]
    A2 -- "Stock general" --> A4["A comprar = necesidad menos libre"]
    A3 --> A5["Crea requerimiento de compra"]
    A4 --> A5
    A6["Cotiza y emite OC"]
  end
  subgraph AP["Aprobador"]
    B1["Aprueba el requerimiento"]
  end
  subgraph AL["Almacén central"]
    C1["Recibe"]
  end
  A5 --> B1
  B1 --> A6
  A6 --> C1

En el modo de stock general el material comprado para la obra 1 puede despacharse a la obra 2. Propuesta: al despachar a otra obra material de una compra masiva de stock general, se libera esa cantidad del comprado de la obra original y se muestra en el filtro «Comprado y desviado» C.

#### Requerimiento de obra con control de saldo (F-04)

flowchart LR
  subgraph PR["Asistente de proyectos"]
    A1["Selecciona ambientes y crea requerimiento"] --> A2["Solicita aprobación"]
    A5["Justifica el exceso"]
  end
  subgraph SY["Sistema"]
    B1{"¿Excede o fuera de plan?"}
    B2{"¿Política?"}
    B3["Bloquea"]
    B4["Revisión por exceso"]
    B5["Sigue tu flujo"]
  end
  subgraph AP["Jefatura de Proyectos"]
    C1["Aprueba el exceso"]
  end
  A2 --> B1
  B1 -- "No" --> B5
  B1 -- "Sí" --> B2
  B2 -- "Bloquear" --> B3
  B2 -- "Solo alerta" --> B5
  B2 -- "Aprobación" --> A5
  A5 --> B4
  B4 --> C1
  C1 --> B5


#### Orden de fabricación desde la BOM (F-05)

flowchart LR
  subgraph PL["Planificación de producción"]
    A1["Selecciona piso o ambientes"] --> A2["Orden de fabricación"]
  end
  subgraph SY["Sistema"]
    B1["OF por piso: producto de la tipología × ambientes"]
    B2["Componentes desde la BOM de la tipología"]
    B3{"¿Componentes exceden el saldo del plan?"}
    B4["Aplica la política del plan"]
  end
  subgraph PD["Producción y almacén"]
    C1["Confirma"] --> C2["Entrega planchas enteras, corte, armado, cierre"]
  end
  A2 --> B1
  B1 --> B2
  B2 --> C1
  C1 --> B3
  B3 -- "Sí" --> B4
  B3 -- "No" --> C2
  B4 --> C2

Los componentes salen de la BOM de la tipología, como hace Odoo V. El plan no los dicta: los controla. Al confirmar, la OF se compara contra el saldo de las líneas de producción y armado de los ambientes incluidos; al cerrar, sus consumos suben el consumido de esas líneas. La regla de plancha entera, el consumo en m² y el costeo por pieza siguen lo ya especificado.

#### Contrata: asignación, avance, liquidación y pago (F-06)

flowchart LR
  subgraph PR["Proyectos"]
    A1["Asigna contrata a la selección"] --> A2["Confirma la OC de servicio"]
  end
  subgraph CT["Contrata"]
    B1["Reporta unidades de driver con foto"]
    B3["Presenta la liquidación el jueves"]
  end
  subgraph SV["Supervisor de obra"]
    C1{"¿Valida el avance?"}
    C2["Valida la liquidación"]
  end
  subgraph JP["Jefatura de Proyectos"]
    D1["Aprueba"]
  end
  subgraph SY["Sistema"]
    E1["Jueves: liquidación en borrador con el periodo jueves a miércoles"]
    E2["Recibe en la OC y crea factura con vencimiento sábado"]
  end
  subgraph TS["Tesorería"]
    F1["Paga el sábado"]
  end
  A2 --> B1
  B1 --> C1
  C1 -- "No" --> B1
  C1 -- "Sí" --> E1
  E1 --> B3
  B3 --> C2
  C2 --> D1
  D1 --> E2
  E2 --> F1

| # | Cuándo | Actor | Pantalla | Acción | Efecto en el sistema |
| 1 | Antes de ejecutar | Proyectos | Árbol (P-02), Asignar contrata (P-05) | Selecciona y asigna | Contrata en las líneas; OC de servicio con el alcance |
| 2 | Diario | Contrata | Registrar avance (P-06) | Reporta unidades de driver por módulo o ambiente | Avances en Reportado |
| 3 | Diario | Supervisor | Avances por validar (P-07) | Valida o rechaza | Sube el acumulado; el % de avance se recalcula solo |
| 4 | Jueves, primera hora | Sistema | — | Acción programada | Liquidaciones en borrador del periodo jueves a miércoles |
| 5 | Jueves | Contrata y supervisor | Liquidación (P-08) | Presenta y valida | Estado Validada |
| 6 | Jueves o viernes | Jefatura de Proyectos | Liquidación (P-08) | Aprueba | Recepción en la OC y factura con vencimiento sábado |
| 7 | Sábado | Tesorería | Pagos | Paga el neto | Liquidación Pagada al conciliar |

#### Personal propio (F-07) y replanificación (F-08)
Personal propio: «Asignar cuadrilla» crea turnos con la tarea del nodo; el capataz registra las horas de la cuadrilla en la hoja de horas y, si la tarea tiene driver, reporta el avance como una contrata. El costo va por hoja de horas, no por liquidación. Como los obreros no tienen usuario, el capataz necesita el permiso de hoja de horas sobre otros empleados, igual que en la simulación de MOMEN del 09-oct N.
Replanificación: crea una versión nueva en borrador con motivo; mientras no se apruebe, la anterior sigue vigente. Al aprobarse, la anterior pasa a Reemplazado y sus asignaciones abiertas y avances no liquidados pasan a las líneas equivalentes de la nueva.

#### Pedir y asignar recursos desde el cronograma (F-09)

flowchart LR
  subgraph GP["Gestor del proyecto"]
    A1["Abre el cronograma de la obra"] --> A2["Marca pisos, ambientes o etapas"]
    A2 --> A3["Revisa el panel de recursos y la carga semanal"]
    A3 --> A4{"¿Qué necesita?"}
    A4 -- "Mover fechas" --> A5["Arrastra la barra de la etapa"]
    A4 -- "Recurso" --> A6["Pulsa la acción y confirma la vista previa"]
  end
  subgraph SY["Sistema"]
    B1["Recalcula fecha de necesidad de las líneas y el cronograma valorizado"]
    B2{"¿Hay requerimientos u OC con fecha anterior?"}
    B3["Avisa a Logística con actividad"]
    B4["Crea el documento en borrador con asignaciones y control de saldo"]
  end
  A5 --> B1
  B1 --> B2
  B2 -- "Sí" --> B3
  A6 --> B4


#### Producto y costo de la línea (F-10)

flowchart LR
  subgraph PL["Planificador (Oficina Técnica)"]
    A1["Elige el producto de la línea"] --> A2{"¿Existe?"}
    A2 -- "No" --> A3["Crear producto (W-11)"]
    A2 -- "Sí" --> A4["Abre precios de compra (P-16)"]
    A3 --> A4
    A4 --> A5["Elige la base y escribe el costo (W-12)"]
  end
  subgraph LG["Logística"]
    C1["Completa marca, proveedor y cuentas del producto nuevo"]
  end
  subgraph SY["Sistema"]
    B1["Producto activo, marcado con el plan"]
    B2["Costo, base y fecha en las líneas en borrador"]
    B3{"¿Quedan líneas sin costo?"}
    B4["El plan se puede enviar a aprobación"]
  end
  A3 --> B1
  B1 --> C1
  A5 --> B2
  B2 --> B3
  B3 -- "No" --> B4
  B3 -- "Sí" --> A1


#### Ruta del ingreso: entrega, valorización, factura y cobranza (F-11)

flowchart LR
  subgraph SY["Sistema"]
    S1["Día de liquidación: entrega semanal en borrador"]
    S2["Corte de valorización según la obra: valorización en borrador"]
    S3["Cronograma valorizado pasa a real"]
  end
  subgraph PR["Jefatura y Proyectos"]
    P1["Confirma la entrega semanal"]
    P2["Revisa y envía la valorización"]
    P4["Levanta observaciones"]
  end
  subgraph CL["Cliente"]
    C1{"¿Conforme?"}
  end
  subgraph AF["Administración y Finanzas"]
    F1["Registra la conformidad con su documento"]
    F2["Factura lo confirmado"]
    F3["Registra el cobro"]
    F4["Cobra el fondo de garantía al cierre"]
  end
  S1 --> P1
  P1 --> S2
  S2 --> P2
  P2 --> C1
  C1 -- "Observa" --> P4
  P4 --> P2
  C1 -- "Sí" --> F1
  F1 --> F2
  F2 --> F3
  F3 --> S3
  F3 --> F4

| # | Cuándo | Actor | Pantalla | Acción | Efecto en el sistema |
| 1 | Día de liquidación | Sistema | — | Acción programada | Entrega semanal en borrador con los avances validados de la semana |
| 2 | Mismo día | Jefatura de Proyectos | Entrega semanal (P-19) | Confirma | Ingreso y costo devengados de la semana |
| 3 | Corte | Proyectos | Preparar valorización (W-13) | Agrupa entregas confirmadas | Valorización en borrador con % por partida |
| 4 | Corte + días para presentar | Proyectos | Valorización (P-20) | Envía al cliente | Fecha de envío y PDF en el historial |
| 5 | Hasta la confirmación prevista | Cliente, Proyectos | Valorización (P-20) | Observa y levanta | Observaciones con fecha y autor |
| 6 | Conformidad | Proyectos o Finanzas | Confirmar valorización (W-14) | Registra fecha, nombre, cargo y documento | Valorización Confirmada |
| 7 | Confirmación + días para facturar | Administración y Finanzas | Valorización (P-20) | Crear factura | Factura desde la OV con lo confirmado |
| 8 | Vencimiento | Administración y Finanzas | Pagos | Concilia el cobro | Cobro real en el cronograma valorizado |

## Control de saldo
Todo documento que nace del plan o que imputa al proyecto se contrasta con el saldo de sus líneas. La regla la pide Vicente: siempre contrastar contra el presupuesto, llevar el saldo y vigilar que no se exceda V.
| Evento | Dónde se engancha | Contra qué se valida | Si excede |
| Requerimiento de obra a aprobación | Método del botón «Solicitar aprobación» de tu módulo, antes de crear revisiones | Saldo de las líneas de material de los niveles de la línea | Política del plan |
| OF confirmada | mrp.production.action_confirm | Saldo de producción y armado de los ambientes incluidos | Política del plan |
| Avance reportado | Asistente y create de construction.task.progress | Driver presupuestado menos acumulado | Bloquea por encima de la tolerancia |
| Liquidación aprobada | Aprobación de la liquidación | Cantidad ordenada en la OC menos recibida | Bloquea |
| Factura de la valorización | Botón «Crear factura» de la valorización | Monto confirmado menos facturado de cada partida | Bloquea |
| OC con analítica de la obra | purchase.order.button_confirm | Presupuesto analítico de la combinación | Política del plan |

## Avance por driver
La contrata reporta el número de unidades del driver que se le paga: módulos armados por tipo, metros lineales instalados de mueble bajo y alto, tapas de cajón colocadas. El porcentaje de avance no se registra: el sistema lo calcula comparando ese acumulado contra las unidades presupuestadas V.
Por actividad en un nivel: avance = min(1, driver acumulado validado ÷ driver presupuestado).
Por nivel con varias actividades (ambiente, departamento, piso, obra): Σ(acumulado × tarifa) ÷ Σ(presupuestado × tarifa), porque las unidades no se pueden sumar entre sí C.
Ejemplo real de tarifas y drivers: cocina del Dpto 504 con el mueble bajo instalado: 2.76 × 18.00 = 49.68 sobre 131.06 de instalación = 37.9 % X.
- Quién reporta y quién valida. Reporta la contrata, por su capataz o el supervisor que transcribe; valida el supervisor de obra de Allcenter. Solo lo validado suma.
- Estado del módulo. Cuando el acumulado de armado de un módulo llega al presupuestado, pasa a Producido; cuando llegan todas sus actividades de instalación, a Instalado C.
- Lo que no se toca. El campo nativo progress de horas sigue funcionando para quien lo use.

## Liquidación semanal
Las contratas se pagan cada sábado. Liquidan el jueves el avance de la semana que va del jueves anterior al miércoles de la semana corriente V. Ejemplo con la instalación del piso 05:
- Periodo. Jueves a miércoles, inclusive. Lo ejecutado el jueves 05/11 ya pertenece al periodo siguiente.
- Qué entra. Avances validados con fecha de ejecución dentro del periodo, más los validados de periodos anteriores que no entraron a ninguna liquidación (validados tarde) C. Los reportados sin validar al momento de liquidar pasan a la semana siguiente.
- Cómo se paga. Cada línea es driver de la semana × tarifa; la retención se aplica según la tarifa. Al aprobar, se recibe en la OC de servicio y se crea la factura con vencimiento el sábado.
- Días parametrizables. Inicio de semana, día de liquidación y día de pago son campos de la obra con valor por defecto en la compañía, por si cambian V. El cierre es el día anterior al inicio de semana.

## Productos y precios
Planificar los recursos de una obra es elegir sus productos y ponerles costo. El presupuesto que se aprueba sale de esos costos, así que el costo de cada línea lo escribe el planificador después de ver los precios de compra V.
- Elegir el producto. La generación desde tipologías trae los productos de la BOM. Para líneas agregadas a mano, el planificador busca en el maestro; si el producto no existe, lo crea desde la línea con W-11 (P-17) y queda activo en el acto V.
- Ver los precios. P-16 muestra las compras confirmadas de los últimos 6 meses con sus estadísticos: promedio ponderado y simple, mediana, mínimo, máximo, desviación, último precio, promedio por semana y por mes, media móvil de 4 semanas y de 3 meses, y el resumen por proveedor. Con muchas compras, el planificador mira los estadísticos; con pocas, la lista de compras.
- Escribir el costo. W-12 aplica el costo elegido a todas las líneas en borrador del plan con ese producto y guarda la base (ponderado 6 meses, ponderado 3 meses, media móvil, último precio o manual) y su fecha. Una línea sin costo bloquea la aprobación.
- Moneda. Todo se compara en soles. Las compras en dólares se convierten con el tipo de cambio de Odoo a la fecha de aprobación de la OC.
La melamina blanca 3101508 tuvo 27 compras entre el 10-abr y el 10-oct-2026: 24 a Novopan en dólares y 3 a otros proveedores en soles. En soles, el promedio ponderado es 122.39, la media móvil de 4 semanas 122.79 y el último precio 123.89. El maestro de MOMEN la tiene a 127.41 y el producto en Odoo a 35.91, que es el precio en dólares N X. Si el plan tomara el costo del producto, la melamina saldría a menos de un tercio de lo real.
El tapacanto 3106287 está a 1.69 por metro en la BOM del maestro y se compra a 0.99 a 1.02 X N. Antes de aprobar el plan hay que revisar si la diferencia es de unidad o de precio.

## Abastecimiento de la obra
La compra masiva para el proyecto carga el almacén antes de que las etapas pidan material. Se trabaja desde el tablero P-18, que cruza la necesidad semanal del plan con lo que ya hay y lo que ya está pedido.
- Necesidad. Cantidad de cada línea de material repartida por la semana de inicio de la etapa que la consume, según las fechas de las etapas del cronograma. Si se mueve una etapa en el Gantt, la necesidad se mueve con ella.
- Horizonte. El usuario elige cuántas semanas cubrir y qué etapas. El tablero calcula «a comprar» como necesidad del horizonte menos stock libre menos OC abiertas de la obra, redondeado a la unidad de compra.
- Compra. Desde las filas marcadas abre la compra masiva (W-02) en uno de sus dos modos, con analítica de la obra o como stock general V. El requerimiento de compra resultante sube el comprado de las líneas del plan y queda contrastado con el saldo.
- Alertas. Último precio mayor al costo del plan por encima del umbral, necesidad sin OC a menos de una semana y producto sin proveedor habitual C.
- Después. Lo que llega al almacén de la obra sale con el requerimiento de obra (P-11) del módulo de Cristóbal, y la fabricación con la OF desde la BOM. El tablero no reemplaza esos documentos.

## Ruta del ingreso
El ingreso de la obra sigue cuatro actos, cada uno con su fecha prevista por obra y su registro en Odoo V:
| Acto | Qué es | Documento | Cuándo |
| Entrega semanal | Entrega interna del avance de la semana. Devenga ingreso y costo | construction.weekly.delivery (P-19) | Día de liquidación, cada semana |
| Valorización | Segundo acto de revisión, con el cliente. Sin su confirmación no se factura | construction.valuation (P-20) | Corte según la frecuencia de la obra, más los días para presentar y para confirmar |
| Facturación | Factura de lo confirmado desde la OV de la obra | account.move con x_valuation_id | Confirmación más los días para facturar |
| Cobranza | Pago del cliente conciliado; el fondo de garantía se cobra al cierre | Pago conciliado | Factura más el plazo de cobro |
Avance de la partida = (contratas a tarifa + horas a costo + material consumido a costo del plan, acumulados) ÷ monto planificado de la partida V.
Ingreso devengado de la semana = precio de la partida × (avance al cierre − avance al inicio) V.
Neto a cobrar = confirmado − fondo de garantía − amortización del adelanto.
- Trazabilidad. Cada valorización guarda las entregas que la forman, las fechas previstas y reales, las observaciones del cliente, quién confirmó, su cargo y el documento de conformidad. La factura apunta a la valorización y la OV sabe qué valorizaciones la movieron.
- Configuración por obra. Frecuencia de valorización (cada n semanas o fechas fijas), días para presentar, para la confirmación del cliente y para facturar, plazo de cobro, adelanto, amortización y fondo de garantía (P-21). La compañía da los valores por defecto.
- Semana. Jueves a miércoles por defecto y configurable en la obra V. La misma semana rige entregas, liquidaciones, cronograma y estadísticas de precios.
Si el avance de la partida midiera solo contratas, la producción en planta devengaría costo sin ingreso: en el plan de MOMEN las tres primeras semanas darían S/ 47,984 de costo contra S/ 15,285 de ingreso. Con el material consumido dentro del avance dan S/ 47,984 contra S/ 44,744, y el margen de cada semana del plan queda en la misma proporción que el de la obra, −6.75 % X C. Decisión de Vicente del 10-oct V.

## Cronograma valorizado
El cronograma valorizado semanal de costo e ingreso por obra es el reporte P-22, construido sobre la vista construction.schedule.report: una fila por obra, semana y concepto (costo, entrega, valorización, facturación, cobranza), en escenario plan o real.
- Plan. Costo: cada línea del plan repartida en los días hábiles de su etapa. Ingreso: precio de cada partida × avance previsto de la partida, con material. Valorización, factura y cobro: el calendario de la obra (P-21).
- Real. Costo: avances validados a tarifa, horas registradas y consumos. Ingreso: entregas confirmadas. Luego valorizaciones confirmadas, facturas publicadas y pagos conciliados.
- Lectura. Curva S de costo e ingreso acumulados, margen acumulado y cobrado acumulado por semana. Se exporta a Excel y se ve en pivote.
S/ 170,764
Costo del plan
S/ 159,231
Precio adjudicado
−S/ 11,533
Margen al cierre
S/ 162,606
Mayor brecha costo − cobrado (02/12)
Cifras del plan de MOMEN con el calendario supuesto del ejemplo X C y los parámetros de ingreso de P-21 E. La brecha usa costo devengado, que no es lo pagado: las contratas se pagan cada sábado y los materiales según el plazo de cada proveedor.

## Caso MOMEN
Cifras leídas del libro Maestro_Planificacion_MOMEN_v03.xlsx el 10-oct X.
153
Departamentos en 20 pisos
1,263
Módulos
10
Tipologías
S/ 126,855
Material según BOM
S/ 43,910
Contratas
| Contratas por etapa | Proyección estándar (S/) | Valorizado real (S/) | Ejecución |
| Armado | 15,007.50 | 15,535.25 | 103.5 % |
| Instalación | 17,952.10 | 17,798.60 | 99.1 % |
| Entregas | 10,949.96 | 12,044.96 | 110.0 % |
| Total | 43,909.56 | 45,378.80 | 103.3 % |
Hoja PANEL_CONTROL del maestro: el mismo contraste que el árbol dará por nivel y contrata mientras la obra avanza.
PROYECCION_MATERIALES repite tornillos 4×50 (3105983, S/ 558.81) y 4×30 (3105097, S/ 281.50): suma S/ 127,694.85 cuando la BOM da S/ 126,854.54. El plan debe cuadrar con la BOM X.
20 de 249 filas de BOM sin etapa (melamina blanco RH y rejilla, en las 10 tipologías, S/ 10,709.20). 3 productos sin costo. Armado de cajones con tarifa y sin cantidades. Sin anchos ni códigos por módulo: para bajar la instalación al módulo hace falta leer el ETO X.
El único monto de contrato disponible es el adjudicado, S/ 159,231.23, de la carpeta MOMEN; no está cargado en New Allcenter ni en producción. Es S/ 11,532.87 menor que el costo del plan (S/ 170,764.10). Puede ser una pérdida real o un costo del maestro alto: la melamina blanca está a 127.41 en la BOM y se compra a 122.39 X N. Si el monto incluye IGV, la diferencia crece. La cotización tampoco cuadra: lista S/ 307,707.50 menos un «acuerdo comercial» de S/ 159,231.23 da S/ 148,476.28. Y sobre el adelanto, el correo de adjudicación habla de 30 % con carta fianza y el contrato dice «No aplica». Hay que confirmar los tres puntos antes de usar MOMEN para probar la ruta del ingreso.

## Relación con Paquetes de obra
El diseño «Paquetes de obra» del 02-oct-2026 resuelve el gesto de enviar muebles a producción, instalación o entrega. Con esta versión el árbol con selección en cascada cubre ese gesto: el paquete pasa a ser una acción combinada sobre la selección (OF, requerimiento y contrata en un solo paso). Los estados del módulo (x_unit_state) son los mismos de ese diseño. Se construye después del planificador y depende de él C.

## Plan por fases
Días estimados por ALTA Latam para dimensionar la conversación contigo, no una cotización tuya E. Las fases 1 a 7 construyen el plan y su ejecución; las 8 a 11 se agregaron en la versión 1.3 y pueden ir en paralelo a partir de la fase 3.
| Fase | Entrega | Pantallas | Días |
| 1 · Jerarquía y catálogo | Niveles en la tarea, tipologías por obra con módulos, actividades, tarifas, etapa en la BOM, generación del plan y de los módulos | P-01, P-04, P-12, P-14 | 5 |
| 2 · Árbol del plan | Acción de cliente OWL con carga por niveles, acumulación, selección en cascada, panel de recursos, filtros | P-02 | 6 |
| 3 · Línea base | Valorización, aprobación, presupuesto, resumen, versiones | P-03 | 3 |
| 4 · Asignaciones y compras | Modelo de asignación, compra masiva en dos modos, requerimiento de obra, OF desde BOM | P-10, P-11 | 5 |
| 5 · Contratas | Asignar contrata, OC de servicio por obra, avance por driver, validación | P-05 a P-07, P-09 | 4 |
| 6 · Liquidación semanal | Modelo, acción programada del jueves, aprobación, recepción, factura con vencimiento sábado | P-08 | 4 |
| 7 · Control y personal propio | Políticas, enganches, análisis, cuadrillas, cambiar fechas | P-13 | 4 |
| 8 · Cronograma | Herencia de al.gantt.data, filas de etapas por ambiente, selección múltiple, panel de recursos, carga semanal, arrastre con recálculo y avisos. Depende de los puntos de extensión que exponga Cristóbal | P-15 | 6 |
| 9 · Productos, precios y abastecimiento | Vista de precios con conversión de moneda y estadísticos, crear producto, aplicar costo, tablero de abastecimiento | P-16 a P-18 | 6 |
| 10 · Ruta del ingreso | Entrega semanal, valorización con confirmación y observaciones, factura desde la OV, calendario por obra | P-19 a P-21 | 6 |
| 11 · Cronograma valorizado e inicio | Vista SQL plan y real, curva S, pivote y exportación; pantalla de inicio con hitos y pendientes por grupo | P-22, P-01 | 5 |
| Total |  |  | 54 |

## Criterios de aceptación
Se prueban sobre MOMEN en la base limpia que estás preparando.
- Generar el plan de MOMEN crea 1,263 tareas de módulo bajo 153 ambientes, y la obra en el árbol suma S/ 126,854.54 de material y S/ 43,909.56 de contratas, con tolerancia de S/ 1.
- El piso 05 en el árbol muestra 66 módulos, 41.33 ML y S/ 8,944.44; el Dpto 501, 7 módulos y S/ 993.66.
- Marcar el piso 05 marca sus 8 departamentos, 8 ambientes y 66 módulos; desmarcar un módulo deja en parcial a su ambiente, departamento, piso y obra.
- Asignar a Leandro la instalación del piso 05 pone la contrata en 59 líneas y agrega a su OC de servicio 8 líneas por S/ 941.17.
- Reportar y validar 2.76 ML de mueble bajo en el Dpto 504 deja esa línea en 100 % y la instalación de la cocina en 37.9 %, sin que nadie escriba un porcentaje.
- El jueves 05/11/2026 la acción programada crea la liquidación de Leandro del periodo 29/10 a 04/11, con pago el sábado 07/11. Con el avance del ejemplo suma S/ 380.88 bruto y S/ 342.79 neto.
- Un avance ejecutado el 05/11 no entra a esa liquidación y aparece en la del 12/11.
- Aprobar la liquidación recibe en la OC las cantidades de la semana y crea la factura con vencimiento el sábado; no deja recibir más que lo ordenado.
- La OF del piso 05 se crea con el producto de cada tipología y los componentes de su BOM, y al confirmarse se contrasta con el saldo del plan.
- Un requerimiento que excede el saldo se comporta según cada una de las tres políticas.
- En el cronograma, marcar la instalación del piso 05 y pulsar «Asignar contrata» abre el mismo asistente de P-05 con 8 actividades y S/ 941.17.
- Mover una semana la barra de instalación del piso 05 corre siete días la fecha de necesidad de sus líneas y avisa de los requerimientos que quedan con fecha anterior.
- Los precios de 3101508 entre el 10-abr y el 10-oct-2026 dan 27 compras, ponderado S/ 122.39 y media móvil de 4 semanas S/ 122.79, convirtiendo cada compra en dólares al tipo de cambio de su fecha (tolerancia S/ 0.01).
- Un plan con una línea sin costo no se puede enviar a aprobación; aplicar el costo con W-12 guarda en la línea la base y su fecha.
- Un producto creado desde el plan queda activo, con código de su familia y marcado con el plan que lo creó.
- Con precio de partida S/ 159,231.23 y avance de 28.10 % a 42.94 %, contando el material consumido, la entrega de la semana 29/10–04/11 devenga S/ 23,627.65 de ingreso.
- Una valorización no pasa a Confirmada sin fecha, nombre, cargo y documento; confirmada, su factura lleva la cantidad entregada de la OV al % acumulado y no puede superar lo confirmado.
- Con el calendario de P-21, el cronograma valorizado muestra la valorización 2 confirmada en la semana 12/11–18/11, facturada en la 19/11–25/11 y cobrada en la 17/12–23/12, y el cobrado acumulado cierra en S/ 159,231.23 al sumar el fondo de garantía.
- El inicio de la aplicación muestra a un supervisor solo los avances por validar de sus obras, y al pulsar la fila abre esa lista filtrada.

## Decisiones

### Tomadas por Vicente
| Fecha | Decisión |
| 09-oct | Compra masiva en dos modos: con analítica de la obra o como stock general, a elegir en cada lanzamiento. |
| 10-oct | Planificar por la mínima unidad fabricada. Revisado: es el módulo. |
| 10-oct | Recursos acumulados visualmente por nivel; seleccionar un departamento selecciona sus muebles y un piso sus departamentos; las asignaciones y acciones se aplican a todo el grupo. |
| 10-oct | El pago a la contrata es siempre por su driver o tarifa; la contrata reporta ese número y el % de avance lo calcula el sistema. |
| 10-oct | Pago semanal los sábados; liquidación los jueves con el avance de jueves a miércoles. |
| 10-oct | Los componentes de la OF salen de la BOM de la tipología. |
| 10-oct | El planificador es una aplicación propia, construida sobre la aplicación Gantt. |
| 10-oct | El gestor del proyecto pide y asigna recursos desde el Gantt. |
| 10-oct | Cronograma valorizado semanal de costo e ingreso por obra. |
| 10-oct | Si el producto no existe, se crea desde el plan y queda activo en el acto. |
| 10-oct | El costo de cada línea lo escribe el planificador después de ver los precios de compra de los últimos 6 meses y sus estadísticos. |
| 10-oct | Pantalla de compra masiva para cargar el almacén de la obra. |
| 10-oct | Ruta del ingreso: entregas semanales que devengan ingreso y costo, valorización con confirmación del cliente trazable en Odoo, facturación y cobranza, con fechas configurables por obra. |
| 10-oct | Semana de jueves a miércoles, configurable. |
| 10-oct | Ingreso por avance de la partida: precio de la partida × % de avance valorizado de toda la partida. |
| 10-oct | El avance de la partida pondera también el material consumido. |

### Abiertas
| Decisión | Por qué importa | Propuesta ALTA |
| Una OC de servicio por contrata y obra | Una sola OC recibe todas las liquidaciones de la contrata en la obra; la alternativa es una OC por asignación | Una por contrata y obra C |
| Ponderación del avance agregado | Las unidades de driver no se suman entre actividades | Por valor (driver × tarifa) C |
| Quién presenta la liquidación | La contrata no tiene usuario interno hoy | El supervisor presenta en nombre de la contrata; más adelante, portal C |
| Avances validados tarde | Si se validan después del jueves, ¿esperan a la semana siguiente? | Entran a la siguiente liquidación como rezagados C |
| Feriados | Un jueves o sábado feriado mueve la liquidación o el pago | Se corre al día hábil anterior según el calendario de la compañía C |
| Anchos por módulo | Sin ancho, la instalación queda en el ambiente | Cargar el ETO de cada obra nueva con el skill de lectura C |
| Stock del modo con analítica | Reserva, ubicación propia o solo analítica | Solo analítica, sin reserva C |
| Planes analíticos del presupuesto | A qué dimensión corresponde cada x_planN_id | Confirmar en la base limpia N |
| Enganche en tu requerimiento | El control debe correr antes de crear las revisiones | Que expongas un método para heredar C |
| Puntos de extensión del Gantt | Sin ellos hay que parchear tu componente cada vez que cambia | Columnas adicionales, panel lateral, evento de selección múltiple y botones de barra C |
| Licencia de dhtmlxGantt | La vista de carga de recursos sería de la edición PRO | Verificar tu licencia; si no la incluye, tabla OWL propia C |
| Contrato de MOMEN | El adjudicado es menor que el costo del plan; IGV y adelanto sin confirmar | Confirmar con Proyectos antes de las pruebas del ingreso C |
| Fondo de garantía en la factura | Línea negativa, cuenta por cobrar aparte o dato informativo | Acordar con contabilidad C |
| Umbral de alerta de precio | Cuándo avisar que el último precio supera al del plan | 5 %, parámetro de la compañía C |
| Días no hábiles del ingreso | Presentación, factura o cobro previstos en feriado o fin de semana | Pasan al siguiente día hábil, para no adelantar ingresos en el cronograma C |

## Cambios de versión
| Versión | Fecha | Cambios |
| 1.4 | 10-oct-2026 | Todas las maquetas con la barra de la aplicación y su menú activo. Inicio de la aplicación con obras, próximo hito y pendientes por grupo (P-01). Sección de beneficios de usabilidad y automatización. El avance de la partida pondera también el material consumido: se recalculan entrega, valorización, calendario y cronograma valorizado. Fases a 54 días. |
| 1.3 | 10-oct-2026 | Aplicación propia «Planificación de obra» sobre el Gantt de Cristóbal, módulo al_construction_planner con menú propio. Cronograma con selección, panel de recursos, carga semanal y acciones (P-15). Crear producto desde el plan (P-17), precios de compra de 6 meses con estadísticos en soles (P-16) y costo escrito por el planificador con su base. Tablero de abastecimiento de la obra (P-18). Ruta del ingreso: entrega semanal, valorización con confirmación del cliente, factura y cobranza, con calendario por obra y semana configurable (P-19 a P-21). Cronograma valorizado semanal con curva S (P-22). Modelos de etapa del ambiente, entrega, valorización y dos reportes; asistentes W-11 a W-14; estados y procesos F-09 a F-11. Fases recalculadas a 52 días. |
| 1.2 | 10-oct-2026 | Unidad mínima: el módulo, con jerarquía obra › piso › departamento › ambiente › módulo y regla de nivel por driver. Árbol del plan con acumulación por nivel, selección en cascada y acciones sobre el grupo (nueva pantalla central y asistentes Asignar contrata, Asignar cuadrilla, Registrar avance, Cambiar fechas). Pago por driver con % automático; desaparece el pago proporcional. Liquidación semanal jueves a miércoles, liquidación el jueves y pago el sábado, con su modelo, estados y pantalla. OF desde la BOM de la tipología; tipologías por obra. Fases recalculadas a 31 días. |
| 1.1 | 10-oct-2026 | Diccionario de campos, entidades, 15 pantallas, estados y procesos. Corrección de cifras del maestro. |
| 1.0 | 09-oct-2026 | Primera versión. |