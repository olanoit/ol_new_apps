# -*- coding: utf-8 -*-
{
    'name': 'Planificación de obra (AL)',
    'summary': 'Plan de recursos de la obra para cualquier rubro: niveles, etapas, '
               'tipos de recurso y recetas configurables, con perfiles de vertical y '
               'funciones que se activan por puentes.',
    'description': """
Planificación de obra
=====================
Aplicación «Planificación de obra», construida sobre el Gantt de proyectos de
la suite, para planificar módulo por módulo todo lo que la obra va a consumir.

Fase 1 (jerarquía y catálogo):

* Jerarquía de la obra en las tareas: piso › departamento › ambiente › módulo,
  con los ancestros de cada nivel calculados.
* Tipologías por obra con sus módulos, actividades por ambiente y lista de
  materiales con la etapa de consumo de cada componente.
* Actividades de contrata (driver de pago) y tarifas por obra y contrata con
  vigencia.
* Plan de recursos versionado y asistente «Generar plan» que crea las tareas de
  módulo y las líneas de armado, contrata y material desde las tipologías.

Fase 2 (árbol del plan, P-02):

* «Árbol de recursos»: obra › piso › departamento › ambiente › módulo cargado
  por niveles, con módulos, ML, material, contrata y total acumulados en el
  servidor.
* Selección en cascada con barra de resumen, panel de recursos acumulados de
  la selección y filtros por etapa, tipo de recurso, estado y contrata.

Fase 3 (línea base, P-03):

* Flujo del plan: borrador › en aprobación › aprobado › en ejecución ›
  cerrado, con reemplazado y cancelado. «Solicitar aprobación» se bloquea
  con líneas sin etapa, sin costo o contratas sin actividad (y las lista).
* Aprobación por niveles con base_tier_validation (reglas por monto).
* Al aprobar: presupuesto analítico con una línea por combinación de cuentas
  analíticas, montos congelados en las líneas y la versión anterior pasa a
  «Reemplazado» con su presupuesto revisado.
* «Nueva versión» (W-09): copia todo o solo saldos, con motivo obligatorio y
  la línea anterior enlazada.
* «Aplicar costo» (W-12): costo que escribe el planificador con su base
  (manual, último precio, ponderado de 3 o 6 meses) y la fecha de la base.
* Resumen por etapa (P-03), análisis en pivote y gráfico, cierre del plan.

Fase 4 (asignaciones y compras, P-10 y P-11):

* Asignaciones del plan: qué parte de cada documento (compra masiva,
  requerimiento de obra, OF, OC de servicio, turno) corresponde a cada línea;
  lo hecho se reparte por fecha de necesidad y su estado sigue al documento.
* Pedido, comprado, despachado, consumido, saldo, comprometido, real y estado
  de cada línea (excedida, completa, en compra, parcial, planificada).
* Compra masiva (W-02) como stock general (descuenta lo libre en el central y
  lo que ya viene en compras), redondeada a la unidad de compra; el costo cae
  a la obra al consumir.
* Requerimiento de obra (W-03) agrupado por ambiente, departamento o piso, con
  saldo del plan y control por línea; control de exceso al solicitar la
  aprobación según la política del plan (avisar, pedir aprobación, bloquear)
  y justificación con revisión adicional (W-10).
* Orden de fabricación (W-04) por piso o selección desde la BOM de la
  tipología, con control del saldo de producción y armado al confirmarla.
* Metrado del ambiente (v1.6): medida real en ML de mueble bajo y alto y en
  módulos frente a lo planificado, con la diferencia valorizada; con
  diferencia, la jefatura lo aprueba antes de lanzar la OF del ambiente.
* Las asignaciones abiertas pasan a la versión nueva al aprobarla y el plan no
  se cierra con documentos abiertos.

Fase 5 (contratas, P-05 a P-07 y P-09):

* «Asignar contrata» (W-05): actividades de la selección con su driver total,
  la tarifa vigente (obra y contrata › obra › contrata › base), monto y
  retención; pone la contrata en las líneas y suma el alcance a la OC de
  servicio abierta de la contrata en la obra (una por contrata y obra).
* Avance reportado (AVN) por driver con fotos obligatorias: reportado,
  validado o rechazado con motivo; «Registrar avance» (W-07) propone el saldo
  por módulo o ambiente y no acepta más que el saldo más la tolerancia.
* «Avances por validar» (P-07) agrupado por obra, contrata y semana de
  liquidación.
* Ejecutado, liquidado y avance de cada línea; avance valorizado de cada nivel
  en el árbol y en la tarea (pestaña «Recursos y avance», P-09); el módulo
  pasa a Producido o Instalado con su avance.
* Semana de la obra configurable (inicio, día de liquidación y de pago), con
  valores por defecto en la compañía.

Fase 6 (liquidación semanal, P-08):

* Liquidación (LIQ) por contrata, obra y semana: avances validados del periodo
  más los rezagados; driver × tarifa de la OC, retención según la tarifa,
  acumulado y avance informativos.
* Acción programada diaria que prepara las liquidaciones en el día de
  liquidación de cada obra (feriados: el día hábil anterior).
* Presentar, devolver con motivo, validar y aprobación por niveles (jefatura);
  al aprobar recibe en la OC de servicio y crea la factura con vencimiento el
  día de pago; pasa a Pagada con la factura pagada.
* El plan no se cierra con liquidaciones pendientes y los avances no
  liquidados pasan a la versión nueva.

Fase 7 (control y personal propio, P-13, W-06, W-08):

* Estado y montos de control de cada línea (comprometido, real, saldo, %
  ejecutado) guardados, filtrables y agrupables; se actualizan con cada
  documento del plan y con una acción programada horaria.
* Pestaña «Control» del plan y «Análisis de control» en pivote y gráfico por
  etapa, tipo de recurso, contrata o producto.
* La OC con analítica de la obra se contrasta al confirmarla con el
  presupuesto analítico de su combinación según la política del plan (W-10).
* «Asignar cuadrilla» (W-06): turnos por obrero y semana con la tarea y la
  línea; las horas de la hoja de horas son el ejecutado y el real (costo
  hora), los turnos sin horas el comprometido.
* «Cambiar fechas» (W-08): desplaza o fija la fecha de la selección por
  etapas, recalcula la fecha de necesidad y avisa a Logística.
* Revertir un avance validado baja el estado del módulo.

Fase 8 (cronograma con recursos, P-15):

* Etapas de cada ambiente (producción, armado, instalación, acabado) con sus
  fechas, creadas al generar el plan; contrata, cuadrilla, monto y avance
  salen de las líneas.
* «Cronograma»: el Gantt de proyectos de la suite con las etapas como filas
  hijas de cada ambiente y sus vínculos, casillas de selección en cascada,
  panel con los recursos de la selección, botones de los asistentes W-02 a
  W-08 y carga semanal por contrata y etapa debajo del diagrama.
* Arrastrar una etapa desplaza la fecha de necesidad de sus líneas y avisa a
  Logística de los requerimientos y OC desfasados; «Cambiar fechas» (W-08)
  también mueve las etapas.

Fase 9 (productos, precios y abastecimiento, P-16 a P-18):

* «Precios de compra del producto» (P-16): las compras confirmadas de una
  ventana editable (6 meses) en soles, cada una al tipo de cambio de Odoo de
  su fecha de aprobación; ponderado, promedio simple, mediana, mínimo, máximo,
  desviación, último precio, medias móviles de 4 semanas y 3 meses, resumen
  por semana, mes y proveedor y gráfico semanal con las compras atípicas.
  Abre «Aplicar costo» con la base elegida.
* «Aplicar costo» (W-12) suma la media móvil de 4 semanas a sus bases.
* «Crear producto desde el plan» (W-11, P-17): código de la familia más
  correlativo asignado al guardar, productos de nombre parecido antes de
  crear, producto activo marcado con el plan y asignado a la línea, y
  actividad a Logística para completarlo.
* «Abastecimiento de la obra» (P-18): necesidad por semana de la etapa que
  consume el material, stock libre de la obra y del central, OC abiertas con
  la analítica de la obra, cantidad a comprar en la unidad de compra, costo
  del plan, último precio con alerta y compra masiva (W-02) con los
  productos marcados.
* Alertas de abastecimiento: precio sobre el plan (umbral en Ajustes),
  necesidad sin OC a menos de una semana y producto sin proveedor habitual.

Fase 10 (ruta del ingreso, P-19 a P-21):

* «Calendario e ingresos» de la obra (P-21): orden de venta del contrato,
  valorización cada n semanas o en fechas fijas, días para presentar, para
  la confirmación del cliente y para facturar, plazo de cobro, adelanto y
  fondo de garantía, con valores por defecto en Ajustes y tabla de
  valorizaciones previstas corridas al siguiente día hábil.
* Entrega semanal (P-19): una por obra y semana, preparada por la acción
  programada del día de liquidación y confirmada por la Jefatura; avance
  valorizado de cada partida con el material consumido, ingreso devengado,
  costo y margen.
* Valorización con el cliente (P-20): W-13 con las entregas confirmadas,
  envío con PDF, observaciones del cliente, conformidad obligatoria (W-14),
  lo no confirmado por valorizar y factura desde la OV al % acumulado
  confirmado, sin superar lo confirmado.

Fase 11 (cronograma valorizado e inicio, P-22 y P-01):

* «Cronograma valorizado» (P-22): por obra y semana, costo, ingreso
  devengado, margen, valorización confirmada, facturado y cobrado, en plan
  (líneas repartidas en los días hábiles de su etapa, ingreso por el avance
  previsto de cada partida y el calendario de P-21) y real (ejecutado
  valorizado, entregas y valorizaciones confirmadas, facturas publicadas y
  cobros conciliados). Curva S, fondo de garantía al cierre, exportación a
  Excel, pivote y gráfico; la última semana absorbe el redondeo.
* «Inicio» (P-01), acción por defecto de la aplicación: obras con plan,
  planificado, saldo, avance, próximo hito y estado, y «Pendientes de hoy»
  según los grupos del usuario, cada uno con su lista filtrada. El supervisor
  ve los avances y liquidaciones de sus obras (responsable o supervisor de
  obra).
* Menú «Reportes» (P-22, control de saldo y precios de compra) y «Cobranza de
  la obra» en Ingresos.

Fase 12 (importar maestro y ETO, W-15):

* «Importar maestro y ETO»: un libro Excel con las hojas del maestro de
  planificación (catálogo de actividades, tipologías, plantilla de módulos,
  actividades por ambiente, BOM con etapa de consumo y árbol de la obra) o
  solo con el ETO (código y ancho real de cada módulo). Todas las hojas son
  opcionales.
* Vista previa sin escribir nada, con conteos por hoja y advertencias: BOM
  sin etapa (con su monto en la obra), productos que no existen o sin costo,
  productos repetidos en una BOM (se suman), actividades o tipologías
  desconocidas, ambientes del ETO que no existen y cantidades con más
  decimales que la precisión de la unidad.
* Importación idempotente: volver a importar no duplica; lo que trae el libro
  de una tipología queda exactamente así. Opción para crear los productos que
  no existen; la hoja de actividades la aplica un administrador.
* «Generar plan» usa el ancho real del módulo del ETO: la instalación y la
  limpieza por ML bajan al módulo con su ancho.
* Plantilla vacía y libros de ejemplo (maestro de una obra genérica de 3
  pisos y su ETO) para descargar desde el asistente; se generan con
  tools/generar_ejemplos_importacion.py.

Paquete de mejoras v1.5 (fases 12 a 21 de la especificación v1.5):

* Plantilla de niveles por obra (agrupadores, unidad, ambiente, mueble y
  módulo) con tipo de unidad; ritmo de programación y etapas encadenadas por
  días hábiles con fechas acumuladas.
* Tipologías con familia, variantes, otros nombres, muebles y variantes por
  unidad.
* Contratos de obra con hitos de cobro por unidad, documentos habilitantes y
  valorización por hitos.
* Producto de servicio por actividad, tramos de pago, reglas analíticas y
  presupuesto por obra › etapa › partida.
* Portal de la contrata (P-23 a P-25) con foto y ubicación.
* Adicionales y deductivos con regla de precio; dependencias de terceros que
  bloquean etapas (P-32).
* Pestaña «Planificación» en la obra con margen planificado, devengado y
  contable.
* Validaciones de datos en el importador y aviso de avances duplicados.
* Sedes, marcación y costo de personal: al_construction_attendance. Hoja de
  trabajo en Documentos: al_construction_planner_spreadsheet.

Paquete de configurabilidad v1.7 (fases 26 a 34):

* Catálogos de etapas y de tipos de recurso (con su comportamiento: material,
  servicio, equipo, contrata, personal propio o producción).
* Niveles libres: agrupadores, unidad de entrega, nivel con etapas, subnivel y
  nivel de detalle, con casillas de receta, metrado, valorización y avance.
* Recetas (plantillas de ejecución) con «Generar desde la receta» e
  importación de recetas y niveles por Excel o desde los Work Items.
* Control por cualquier nivel, línea base contra versión y desvío.
* Núcleo sin Compras, Ventas ni Fabricación: cada función es un puente
  (al_construction_planner_*) que se activa en Ajustes ‣ Funciones;
  al_construction_planner_suite los instala todos.
* Perfiles de vertical (Construcción por partidas, Mobiliario) que aplican
  plantilla, etapas, recursos, funciones, puentes y parámetros, y se exportan
  e importan en JSON. Al actualizar, una compañía que ya usaba el
  planificador queda con el perfil Mobiliario.

Paquete 1.8 (fases 35 a 46, docs/planificador/DISENO_v1.8.md):

* Etapas con sub etapas («1 Producción › 1.1 Producción de piezas»), con su
  numeración y el orden del árbol en el plan, el control, el cronograma
  (barras resumen) y el filtro de etapas en árbol. Mobiliario: 1.1
  Producción de piezas, 1.2 Armado, 2.1 Instalación, 2.2 Acabado y 2.3
  Limpieza.
* Funciones «Avance» y «Metrado» separadas; el perfil Construcción por
  partidas no muestra metrados y las columnas de nivel toman los nombres de
  la plantilla de la compañía (partida, actividad). Aplicar un perfil avisa
  qué menús y funciones cambian.
* Panel de recursos por tipo de recurso con subtotales y por etapa; matriz
  insumo-producto (elementos por insumos, agrupados por etapa y tipo) con
  exportación a Excel.
* Avance en formulario con fotos, evaluación del supervisor y validación en
  el historial; avance de la partida por su driver (48 de 120 m²: 40 %).
* Recetas vinculadas a los Work Items: las diferencias se marcan y se
  aplican en uno u otro sentido con vista previa, sin tocar planes aprobados.

Especificación: docs/planificador/ESPECIFICACION_v1.4.md,
docs/planificador/DISENO_v1.7.md y docs/planificador/DISENO_v1.8.md. Diseño técnico y
plan por fases: docs/planificador/DISENO_TECNICO.md.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-PROJECTS/Apps',
    # Ícono propio de la app, con el estilo de Odoo 19 (icon.svg 50×50).
    'icon': '/al_construction_planner/static/description/icon.png',
    'version': '48.20261016',
    # LGPL-3 y no OPL-1: depende de base_tier_validation (AGPL-3), como
    # al_construction_material_request.
    'license': 'LGPL-3',
    # Núcleo del paquete 1.7 (M17-07): solo Proyectos, el Gantt de la suite y
    # las aprobaciones por niveles (la línea base se aprueba). Cada función que
    # opera en otra aplicación vive en su puente (al_construction_planner_*).
    'depends': [
        'al_project_gantt_base',
        'al_project_gantt_backend',
        'base_tier_validation',
        'analytic',
        'product',
    ],
    'data': [
        'security/planner_groups.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/ir_sequence_data.xml',
        'data/construction_level_template_data.xml',
        'data/construction_stage_data.xml',
        'data/construction_vertical_profile_data.xml',
        'data/tier_definition_data.xml',
        'data/ir_cron_data.xml',
        'wizards/plan_replan_wizard_views.xml',
        'wizards/plan_reschedule_wizard_views.xml',
        'wizards/plan_progress_wizard_views.xml',
        'wizards/plan_supply_wizard_views.xml',
        'views/construction_labor_views.xml',
        'views/construction_level_template_views.xml',
        'views/construction_stage_views.xml',
        'views/construction_vertical_profile_views.xml',
        'views/construction_execution_template_views.xml',
        'views/construction_progress_views.xml',
        'views/construction_resource_plan_views.xml',
        'views/construction_allocation_views.xml',
        'views/construction_planner_home_views.xml',
        'views/project_views.xml',
        'views/res_config_settings_views.xml',
        'views/construction_plan_tree_views.xml',
        'views/construction_schedule_views.xml',
        'views/construction_analytic_rule_views.xml',
        'views/construction_dependency_views.xml',
        'views/construction_measurement_views.xml',
        'views/construction_exceed_views.xml',
        'views/menus.xml',
        'views/construction_board_views.xml',
        'views/construction_recipe_calc_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'al_construction_planner/static/src/stage_filter/*',
            'al_construction_planner/static/src/io_matrix/*',
            'al_construction_planner/static/src/plan_tree/*',
            'al_construction_planner/static/src/schedule/*',
            'al_construction_planner/static/src/home/*',
            'al_construction_planner/static/src/project_panel/*',
            ('remove', 'al_construction_planner/static/src/**/*.dark.scss'),
        ],
        # Modo oscuro: se compila con las variables oscuras de Odoo.
        'web.assets_web_dark': [
            'al_construction_planner/static/src/**/*.dark.scss',
        ],
        'web.assets_tests': [
            'al_construction_planner/static/tests/tours/*',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
