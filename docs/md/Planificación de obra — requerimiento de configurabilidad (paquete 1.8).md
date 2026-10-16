# Planificación de obra — requerimiento de configurabilidad (paquete 1.8)

Oct 15, 2026 · @Vicente

## Objetivo, alcance y estado

Planificación de obra (AL), `al_construction_planner`, debe servir con el mismo código a dos verticales: constructoras que ejecutan obra por partidas y contratas de mobiliario que fabrican en planta propia e instalan en obra. Al aplicar el perfil de la vertical, el planificador queda configurado con su diseño de operación; después, cada parámetro se puede ajustar. Otras verticales se agregarán como perfiles cuando las definamos.

El documento está ordenado en tres partes: los requerimientos generales del aplicativo (parte A), los de la vertical Construcción por partidas (parte B) y los de la vertical Mobiliario (parte C). Lo publicado en las versiones 28 a 33 cierra la 1.7. Los requerimientos nuevos forman el paquete 1.8 (M18-01 a M18-22); los de la 1.7 que siguen sin publicar o se rehacen (M17-15 y M17-18 a M17-20) conservan su código y están en la parte C.

### Estado de la 1.7 publicada

Fuente: registro de cambios del repositorio, versiones 28 a 33 del 15-oct-2026, y la base `construccion_dev_1`, que tiene instalada la versión 19.0.33.20261013 y los modelos de perfil, etapa, tipo de recurso y plantilla de ejecución.

| Requerimiento | Estado | Observación |
| --- | --- | --- |
| Niveles de profundidad libre (M17-01) | Publicado, v28 | — |
| Etapas configurables (M17-02) | Publicado, v28 | Catálogo plano, sin sub etapas: ver etapas con sub etapas (M18-02) |
| Tipos de recurso configurables (M17-03) | Publicado, v28 | Incluye equipo |
| Receta independiente del mueble (M17-04) | Publicado, v28 | Plantillas de ejecución; importación desde Excel o Work Items |
| Perfiles de vertical (M17-05) | Publicado, v32 | Los menús no cambian con el perfil: ver menús por vertical (M18-01) |
| Funciones activables (M17-06) | Publicado, v31 | «Avance y metrados» es un solo interruptor |
| Núcleo con módulos puente (M17-07) | Publicado, v30 | En `construccion_dev_1` los puentes de fabricación y mobiliario están desinstalados |
| Operación nativa: compras, producción, contratas, cuadrillas (M17-08 a M17-11) | Publicado, v32 | La cuadrilla se arma por rol: ver cuadrillas y nómina (M18-06) |
| Clasificación de menús (M17-12) | Parcial, v32 | Los menús que operan otro documento son accesos directos; la tabla de clasificación no la verifiqué |
| Control por cualquier nivel (M17-13) | Publicado, v29 | — |
| Destino de la compra masiva (M17-14) | Publicado, v29 | — |
| Metrado (M17-15) | Publicado como «metrado por cantidad», v29 | No corresponde al concepto: se rehace en la parte C |
| Material extra y avance por portal en cualquier nivel (M17-16 y M17-17) | Publicado, v29 | — |
| Importador de la proyección, validación de códigos y versus en producción (M17-18 a M17-20) | Sin publicar | Detallados en la parte C |

&#91;embedded content: núcleo y puentes · 7 puentes, cada uno con su aplicación\]

La arquitectura de núcleo y puentes ya está publicada (v30). Una constructora sin fabricación deja fuera los puentes de producción y mobiliario.

## Planificar y controlar frente a operar

El planificador planifica y controla; cada operación se ejecuta en la aplicación de Odoo que le corresponde y vuelve al planificador como dato de control. La excepción es la asignación de cuadrillas propias, porque ninguna aplicación nativa arma cuadrillas con rendimiento y las asigna a una etapa.

| Función | Qué hace el planificador | Dónde se opera | Qué vuelve como control |
| --- | --- | --- | --- |
| Materiales | Explosiona la necesidad por partida o receta, con fecha tomada de la etapa, y lanza el requerimiento de compra masivo | Compras: proveedores, cotizaciones, precios y OC. Inventario: recepción y despacho | Pedido, comprado, despachado, consumido, saldo |
| Producción | Propone órdenes de fabricación por nivel y etapa | Fabricación | Producido y consumido contra lo planificado |
| Contratas | Asigna contrata, tarifa y alcance por actividad | Compras: OC de servicio. Contabilidad: factura y pago | Avance validado, valorización de contratas (liquidación), retenido |
| Cuadrillas propias | Arma la cuadrilla y la asigna a la etapa (se opera aquí) | Planificación, Asistencias y Nómina registran lo trabajado | Jornales y horas reales contra lo planificado |
| Valorización de proyecto | Programa valorizaciones e hitos de cobro | Ventas y Contabilidad: factura y cobro | Valorizado, facturado, cobrado |
| Cronograma | Programa niveles, etapas y sub etapas en el Gantt | — | Avance contra línea base |

La liquidación semanal de contratas no tiene aplicación nativa: se queda en el planificador como control, dentro del puente de contratas.

## Parte A — Requerimientos generales del aplicativo

### Menús y términos por vertical (M18-01)

Aplicar un perfil debe dejar los menús, botones y etiquetas de la vertical. Hoy no ocurre: en `construccion_dev_1` el perfil Construcción por partidas tiene activo «Avance y metrados», y el menú muestra Ejecución › Avance › Metrados y Generar metrados.

- El perfil define qué menús, botones del árbol y del cronograma, y asistentes se muestran. Aplicar el perfil los oculta o muestra sin desinstalar nada.
- El interruptor «Avance y metrados» se separa en dos: «Avance» (las dos verticales) y «Metrado» (solo Mobiliario).
- El metrado es un concepto de la vertical Mobiliario: medida del espacio, diseño y despiece del mueble (parte C). No aparece en la vertical de construcción.
- En construcción, el avance de cada partida o contrata se mide por el driver definido para ella o en su APU (parte B).
- Las etiquetas de la interfaz y de los reportes toman los nombres de la plantilla de niveles del perfil (por ejemplo, partida en construcción; mueble y módulo en mobiliario).
- Al aplicar un perfil a una compañía que ya tiene obras, el sistema avisa qué menús y funciones cambian antes de confirmar.

Criterio de aceptación: con el perfil Construcción por partidas no aparece ningún menú, botón ni etiqueta de metrado; con el perfil Mobiliario aparecen Metrados y Generar metrados.

### Etapas con sub etapas y filtro jerárquico (M18-02)

El catálogo de etapas publicado en la v28 es plano: cada etapa tiene orden, etapa anterior, tipo y duración, sin etapa padre. Las verticales necesitan etapas con sub etapas en una secuencia fija (la de Mobiliario está en la parte C).

- Cada etapa puede tener una etapa padre. El perfil define el árbol completo y su orden, por ejemplo 1 Producción › 1.1 Producción de piezas.
- La numeración y el orden del árbol se respetan en todas las vistas: árbol de recursos, cronograma, panel de recursos, análisis de control y reportes impresos y en Excel.
- Las líneas del plan, las recetas y los documentos generados se asignan a la sub etapa; la etapa padre suma lo de sus sub etapas en cantidad, monto y avance.
- En el cronograma, la etapa padre es una barra resumen y sus sub etapas, barras hijas encadenadas en el orden del perfil.
- El filtro de etapas es un árbol con casillas: marcar una etapa marca sus sub etapas, desmarcar una sub etapa deja a la etapa en selección parcial, como hoy funciona la selección en cascada del árbol de recursos.

Criterio de aceptación: con el perfil Mobiliario, el filtro muestra Producción y bajo ella Producción de piezas y Armado; marcar Producción deja ambas marcadas y el cronograma y el panel muestran solo esas dos sub etapas.

### Panel de recursos del cronograma por tipo (M18-03)

Al seleccionar elementos del alcance en el cronograma, el panel derecho carga los recursos que requieren. Según la ficha del módulo, hoy los muestra por actividad, producto o rol, con su contrata; no los agrupa por tipo de recurso. No lo verifiqué en pantalla porque la base no tiene planes cargados.

- El panel agrupa los recursos de la selección por tipo, en el orden del catálogo del perfil: materiales, contratas, mano de obra propia, equipo, servicios y producción.
- Cada grupo muestra su subtotal en cantidad y en soles, y el panel su total.
- Dentro de cada grupo se puede subagrupar por etapa y sub etapa.
- El panel respeta el filtro de etapas: si hay sub etapas marcadas, solo suma esas.
- Lo mismo aplica al panel del árbol de recursos.

Criterio de aceptación: al marcar un piso, el panel muestra un bloque de materiales, uno de contratas y uno de mano de obra propia, cada uno con su subtotal, y los totales coinciden con el análisis del plan para ese piso.

### Recursos planificados como tabla insumo-producto (M18-04)

Cada línea del plan ya relaciona un elemento del alcance (nivel), una etapa, un tipo de recurso, un insumo (producto, actividad o rol) y su cantidad y monto. Con esos datos se puede mostrar el plan como matriz. Hoy existe el análisis del plan en pivote, agrupable por etapa y tipo de recurso, sin vista de matriz insumo-producto. La disposición de la matriz la definió Vicente el 16-oct-2026.

- Opción «Insumo-producto» en el plan, el árbol y el cronograma: filas = elementos del alcance en el nivel que el usuario elija (módulo, mueble, ambiente, departamento o piso en mobiliario; partida o subpartida en construcción); columnas = insumos; celdas = cantidad o monto, a elección.
- Las columnas se agrupan, con subtotales, por etapa › sub etapa y, dentro de ellas, por tipo de recurso, en un encabezado de varios niveles. Cada grupo se pliega y despliega.
- Totales por fila (costo de cada elemento) y por columna (insumo en toda la selección).
- Respeta la selección del árbol o del cronograma y el filtro de etapas.
- Se puede ver lo planificado, lo comprometido, lo real o el saldo, y exportar a Excel con la misma agrupación.

Criterio de aceptación: para un piso de mobiliario, la matriz con una fila por mueble muestra las planchas de melamina bajo Producción de piezas, los tornillos bajo Armado y la contrata de instalación bajo Instalación, y la suma de las filas coincide con el monto planificado del piso.

### Control de consumo sin repetición (M18-05)

Lo que existe hoy, verificado en la base y en la ficha del módulo:

- Cada plan tiene una política de exceso (solo alerta, aprobación adicional o bloquear) y una tolerancia en porcentaje.
- Se aplica al pedir la aprobación de un requerimiento de obra y al confirmar una orden de fabricación: si lo pedido supera el saldo del plan para ese nivel, actúa la política.
- Todo material marcado como extra pasa por la jefatura de proyectos, esté o no en el plan.
- «Asignar contrata» no reasigna líneas que ya tienen otra contrata.

Es decir, ya existe para materiales y producción, configurable por plan. Lo que falta:

- Política por defecto en el perfil y en la obra, que cada plan hereda y puede cambiar, en lugar de definirse plan por plan.
- Política por tipo de recurso: materiales, contratas (alcance adicional en la OC de servicio de la misma actividad y nivel), mano de obra propia (jornales sobre lo planificado) y producción.
- Control por nivel y sub etapa: si los recursos de una producción o una instalación ya se pidieron completos, un nuevo pedido para ese mismo nivel y sub etapa requiere la autorización de la jefatura de proyectos.
- Registro de cada exceso autorizado con quién, cuándo, motivo y cantidad, visible en el análisis de control.

Criterio de aceptación: con la política «aprobación adicional», un segundo requerimiento de melamina para un mueble cuya producción de piezas ya pidió el 100% queda esperando a la jefatura, y la autorización queda registrada.

### Cuadrillas, nómina, sedes y costo por jornal

Una empresa de cualquiera de las dos verticales puede pagar a su personal con la nómina de construcción civil o con la del régimen general. Lo que existe hoy, leído en `construccion_dev_1`:

| Tema | Situación actual |
| --- | --- |
| Régimen de nómina | La suite AL tiene estructuras para régimen general y construcción civil; la ficha del empleado guarda categoría de construcción civil y jornal básico |
| Unidad de tiempo en RR. HH. | Los tipos de entrada de trabajo de la nómina de Odoo ya redondean sin redondeo, a medio día o a día completo, y el contrato toma sus entradas de trabajo del horario, de las asistencias o de Planificación |
| Rol de la cuadrilla | Es el rol de Planificación de Odoo, el mismo registro que el monitor de asistencia de la nómina usa como «tipo de turno». No se relaciona con la categoría ni con el jornal |
| Planificación de la cuadrilla | El asistente trabaja en semanas y horas por semana; el costo real son horas por costo hora |
| Sedes de marcación | La obra tiene «Sedes de la obra»; una sede puede ser de obra o de planta y cada una tiene etapa por defecto. No encontré creación automática al crear la obra (no verificado en código) |
| Cierre de costo de personal | Mensual por sede: horas de marcación por costo hora |

#### Cuadrillas vinculadas a la nómina (M18-06)

- Funciona con la nómina de construcción civil y con la de régimen general.
- Cada rol de cuadrilla se vincula a una categoría de construcción civil (operario, oficial, peón) o a un puesto del régimen general, y toma de ahí el jornal o el costo de referencia.
- La cuadrilla planificada lleva su composición por categoría o puesto y cantidad, con rendimiento por actividad; al asignar personas se valida que su categoría o puesto coincida.
- El rol de la cuadrilla y el tipo de turno del monitor de asistencia siguen siendo el mismo registro.

#### Unidad de tiempo y costo por jornal (M18-07)

- Las cuadrillas se planifican y se miden en jornales. La unidad es configurable en el perfil y en la obra: hora, medio día o día completo.
- Se reutiliza el redondeo de los tipos de entrada de trabajo de la nómina de Odoo (sin redondeo, medio día, día) en lugar de desarrollar un mecanismo nuevo.
- Lo ejecutado son los jornales marcados en la sede de obra, al jornal de la categoría o al costo del puesto según la nómina.
- El análisis de control muestra jornales y soles planificados contra ejecutados por obra, etapa y sub etapa.

#### Sede de marcación de obra (M18-08)

- Cada proyecto tiene solo sedes de obra. Opción en Ajustes y en el perfil: crear la sede de obra al marcar el proyecto como obra.
- La sede se crea con el nombre y la cuenta analítica de la obra, y la ubicación, el radio y la hora límite por defecto de la compañía, editables después.
- Las sedes de planta (producción central) pertenecen a la compañía y no se vinculan a un proyecto. Su costo de personal es costo de fabricación y llega a las obras a través de las órdenes de fabricación.

Criterio de aceptación: al marcar un proyecto como obra se crea su sede; una cuadrilla de un operario, un oficial y dos peones planificada por 5 días en día completo muestra 20 jornales planificados; tras una semana de marcación, el control muestra jornales ejecutados y su costo contra lo planificado. Una sede de planta no aparece en ningún proyecto.

### Valorización de proyecto y de contratas por avance y por porcentaje arbitrario (M18-09)

En este documento «valorización de proyecto» es la que se presenta al cliente para cobrar, y «valorización de contratas» es la liquidación para pagar a las contratas.

- La valorización de proyecto sigue la regla de la vertical (por avance de partida en construcción, por hitos por unidad en mobiliario) y además admite un porcentaje de avance arbitrario.
- En la preparación, cada partida o unidad propone el porcentaje de su regla y admite escribir otro. Un porcentaje escrito a mano pide motivo y queda marcado como manual, con quién y cuándo.
- El porcentaje arbitrario aplica también a la valorización de contratas: en la liquidación, cada línea de contrata propone el porcentaje de su avance validado y admite escribir otro, con motivo, y queda marcado como manual. Si el porcentaje escrito supera el avance validado, lo aprueba la jefatura de proyectos (regla aprobada por Vicente el 16-oct-2026).
- Se mantienen los controles actuales: la factura no supera lo confirmado por el cliente y lo no confirmado pasa a la siguiente valorización.

Criterio de aceptación: una partida con 42% de avance calculado se valoriza al 50% escrito a mano, con motivo, y la valorización y su factura muestran 50% marcado como manual. Una contrata con 30% de avance validado se liquida al 35%, con motivo y aprobación, y la liquidación muestra 35% marcado como manual.

### Visibilidad de montos (M18-10)

La planificación tiene cantidades, montos y fechas. Hoy ninguno de los 21 campos de monto del plan, sus líneas y las tareas tiene restricción de grupo a nivel de campo; las restricciones en vistas no las verifiqué.

- Un grupo «Planificación de obra: ve montos» habilita costos, precios, presupuestos, comprometido, real, márgenes y valorizaciones.
- Quien no lo tiene ve cantidades, fechas, avance y estados en el árbol, el cronograma, los paneles, la matriz insumo-producto, los análisis y los reportes, sin columnas ni totales en soles.
- Los reportes impresos y las exportaciones a Excel siguen la misma regla.

Criterio de aceptación: un supervisor sin el grupo abre el cronograma y la matriz insumo-producto de una obra y no ve ningún importe; la jefatura sí los ve.

### Registro de avance en formulario con trazabilidad (M18-11)

Hoy el avance (AVN) ya tiene formulario, fotos y chatter, pero se registra desde un asistente emergente. Aplica a las dos verticales.

- El avance de contratas y de cuadrillas se registra en el formulario estándar de Odoo, con lista y formulario, además del asistente para carga rápida.
- El formulario muestra el chatter: notas de trazabilidad, fotos y documentos de sustento, evaluación del supervisor y propuestas, con autor y fecha.
- Las fotos y evidencias cargadas desde el portal de la contrata quedan en el chatter del mismo avance.
- La validación, el rechazo y su motivo quedan registrados en el chatter.

Criterio de aceptación: un avance cargado desde el portal con dos fotos se abre en formulario, muestra las fotos en el chatter, el supervisor agrega una nota de evaluación y lo valida, y todo queda con autor y fecha.

## Parte B — Vertical Construcción por partidas

Para constructoras que ejecutan obra por partidas. El perfil ya existe en la base (v32); esta tabla fija lo que debe dejar configurado.

| Elemento | Definición del perfil | En la base hoy |
| --- | --- | --- |
| Niveles | Disciplina › subpartida › partida › actividad | Plantilla «Construcción por partidas» |
| Etapas | Actividades de la partida desde el catálogo, con sub etapas cuando la partida las tenga (M18-02) | Trazo y replanteo, Ejecución, Acabados, Pruebas y entrega |
| Receta | APU por partida en dos fuentes sincronizadas: Work Items de Ventas y receta del planificador (M18-13) | Plantillas de ejecución, importables desde Work Items |
| Producción y mobiliario | Desactivados; Fabricación no se instala | Puentes desinstalados |
| Contratas | Activada; la contrata entra al APU como línea de mano de obra | Activada |
| Cuadrillas propias | Activada; nómina de construcción civil o de régimen general (M18-06); medida en jornales (M18-07) | Activada, por horas |
| Compra masiva | Activada; stock general | — |
| Avance | Por el driver de cada partida o contrata (M18-12); sin metrado | «Avance y metrados» activo |
| Analítica | Planes Proyecto, Disciplina, Subpartida y Partida | Disciplina, Subpartida, Partida |
| Valorización de proyecto (cobranza al cliente) | Valorización por % de avance de partida y por porcentaje arbitrario (M18-09) | — |
| Semana de contratas | Configurable por compañía y por obra: día de inicio, de liquidación y de pago | Ya configurable desde la v5; el perfil solo trae el valor por defecto |
| Grupos | Jefatura y asistente de proyectos | — |

### Avance por driver de la partida o del APU (M18-12)

- Cada partida tiene su driver y unidad, tomados de su APU o definidos en ella: m², ml, m³, und, kg o global.
- Cada contrata y cada actividad del APU puede tener su propio driver; si no lo tiene, usa el de la partida.
- El avance se registra en cantidad del driver, desde el planificador o el portal de la contrata, con fotos y evidencias, en el formulario con chatter (M18-11).
- El porcentaje de avance de la partida es la cantidad ejecutada entre la cantidad presupuestada de su driver; el de los niveles superiores se pondera por valor, como hoy.
- Sin pantallas ni campos de metrado en esta vertical (M18-01).

Criterio de aceptación: una partida de muro drywall de 120 m² con 48 m² ejecutados muestra 40% de avance; su contrata de emplacado, con driver propio en m², muestra su propio avance y su liquidación por esa cantidad.

### Receta sincronizada con los Work Items (M18-13)

- La receta de cada partida (APU) existe en dos lugares: los Work Items de Ventas, con los que se cotiza, y la plantilla de ejecución del planificador, con la que se planifica y controla.
- Hoy la importación desde Work Items es una copia única. Verificado en construccion\_dev\_1 el 16-oct-2026: la plantilla guarda solo el origen («Copiada de un Work Item») y una referencia en texto, sin vínculo al Work Item; el formulario de la plantilla no tiene botones; ninguna automatización ni acción programada de la base enlaza Work Items con el planificador, y el módulo no agrega campos a los Work Items. Confirmado también en el código publicado del planificador (repositorio olanoit/ol\_new\_apps, versión del 16-oct-2026): el único punto que lee los Work Items es el asistente de importación. Se requiere sincronización en los dos sentidos: un cambio en el Work Item o en la plantilla vinculada queda marcado como diferencia y se propone aplicarlo en la otra, con vista previa.
- La sincronización no cambia planes ya aprobados: el cambio llega a los planes nuevos o mediante una revisión del plan.
- El mecanismo (marcar la diferencia y proponerla con vista previa, sin tocar planes aprobados) lo aprobó Vicente el 16-oct-2026.

Criterio de aceptación: cambiar el rendimiento de una cuadrilla en un Work Item marca su plantilla vinculada como desactualizada; al aceptar la propuesta, la plantilla queda igual al Work Item y los planes aprobados no cambian.

## Parte C — Vertical Mobiliario

Para contratas de mobiliario que fabrican en planta propia e instalan en obra. El perfil ya existe en la base (v32) con las cuatro etapas antiguas; esta tabla fija lo que debe dejar configurado.

| Elemento | Definición del perfil | En la base hoy |
| --- | --- | --- |
| Niveles | Torre › piso › departamento › ambiente › mueble › módulo. En cocinas la tipología va en el ambiente y el mueble es bajo, alto, torre o isla; el módulo lleva tipo y método de unión (M18-17, M18-18) | Plantilla «Edificio» |
| Etapas | 1 Producción (1.1 Producción de piezas, 1.2 Armado) y 2 Instalación (2.1 Instalación, 2.2 Acabado, 2.3 Limpieza) (M18-14) | Producción, Armado, Instalación, Acabado y entrega, en lista plana |
| Receta | Tipología con módulos y metros lineales. El metrado (medida, diseño y despiece) define materiales, accesorios y consumibles, que forman la lista de materiales del mueble. La oficina técnica presupuesta en la hoja de cálculo de Odoo (M18-22) | Tipología y plantillas de ejecución |
| Producción | Activada | Puente de fabricación desinstalado en `construccion_dev_1` |
| Contratas | Activada; catálogo de actividades de mobiliario con listas de tarifas por familia y por obra (M18-19); líneas de contrata generadas desde las piezas (M18-20); control de pago repetido y re-trabajo (M18-21); portal de la contrata | Activada |
| Cuadrillas propias | Activada; nómina de construcción civil o de régimen general (M18-06); medida en jornales (M18-07) | Activada, por horas |
| Compra masiva | Activada; stock general | — |
| Metrado y avance | Metrado como receta real del mueble (M17-15); avance por driver de la contrata | «Metrado por cantidad» (v29) |
| Analítica | Obra › etapa › partida, como hoy | — |
| Valorización de proyecto (cobranza al cliente) | Valorización por hitos por unidad y por porcentaje arbitrario (M18-09) | — |
| Semana de contratas | Configurable por compañía y por obra (ya existe desde la v5); valor por defecto: inicio jueves, liquidación jueves, pago sábado | — |
| Grupos | Jefatura y asistente de proyectos | — |

### Secuencia de etapas de mobiliario (M18-14)

- El perfil carga las etapas con este orden y numeración, que se respeta en la interfaz y en los reportes:
  1. Producción: 1.1 Producción de piezas, 1.2 Armado.
  2. Instalación: 2.1 Instalación, 2.2 Acabado, 2.3 Limpieza.
- Cada sub etapa sigue a la anterior; Instalación empieza al terminar Armado, salvo que el planificador cambie la dependencia.
- Las líneas de material de la lista de materiales se asignan a su sub etapa de consumo; las actividades de contrata, a la sub etapa donde se ejecutan.
- La migración pasa Producción y Armado de hoy a 1.1 y 1.2, Instalación a 2.1 y Acabado y entrega a 2.2; Limpieza (2.3) se crea vacía. Los datos existentes no cambian de monto.

Criterio de aceptación: el cronograma, el panel de recursos, el análisis de control y la valorización impresa muestran las cinco sub etapas en ese orden y con esa numeración.

### Importador de la proyección de materiales (M17-18)

Fuente verificada el 15-oct-2026 en el Drive de Allcenter: 61 hojas de proyección de materiales de 16 proyectos y la de MOMEN, todas con despiece por pieza (cantidad, largo, ancho, tipo de pieza, color y consumo de cada material con su código). Se leyeron las pestañas, el resumen y las primeras 25 filas de una tipología por hoja.

Con la hoja de trabajo en Odoo (M18-22), este importador sirve solo para traer a la hoja las obras ya proyectadas en Excel. Las obras nuevas no pasan por Excel.

- Lee las hojas en su formato actual, con sus dos variantes:
  - Cocinas: una pestaña por tipología y un bloque «MODULO» por módulo.
  - Closet, baño, lavandería, ducto y estacionamiento: una pestaña con un bloque por tipología completa.
- Carga la receta planificada de cada módulo con sus piezas y consumos; la del mueble es la suma de sus módulos en cocinas y el bloque mismo en los demás rubros.
- Toma de la pestaña resumen («… POR PISO») qué tipología lleva cada departamento, y admite las agrupaciones que hoy existen: por departamento, por piso (ductos), por sótano (estacionamientos) y por tipología con cantidad.
- Asigna cada material a su sub etapa de consumo (M18-14).
- Vista previa sin escribir y con advertencias.
- Separa los módulos bajos de los altos y arma el mueble con su tipo (M18-17); propone el método de unión de cada módulo (M18-18).
- Detecta tarugos en columnas fuera del rango que suma el resumen (cajoneras de MOMEN y MIDGO, columna extra «TARUGOS»).
- Detecta la fila de etapas corrida una columna (COSMOS, Montecarmello, Hercelles: el tarugo cae en INSTALACION).
- Detecta totales de módulo con fórmula desplazada (MOMEN, COCINA - 04, fila 31: el durolac queda en m² × 1,1 en lugar de planchas).

Criterio de aceptación: importar «PROYECTO COCINAS EDIFICIO FLORECE II» y «PROYECTO CLOSET LAMBAYEQUE» deja la receta de cada módulo y mueble con los mismos totales por material que la hoja.

### Validación de códigos de producto (M17-19)

- En 9 proyectos de cocina y en todas las lavanderías y ductos revisados, el código de la pestaña de tipología no coincide con el del resumen (melamina blanco: 3101057 en la tipología, 3101508 en el resumen).
- La oficina técnica trabaja con el maestro de productos vigente de Odoo. Con la hoja de cálculo de Odoo (M18-22) el maestro está vivo en la hoja y la pestaña «codigos» del Excel deja de usarse.
- El importador cruza cada código con el catálogo de Odoo y marca toda columna sin código, con código inexistente o con nombre que no coincide. Sin resolver esas marcas, la receta no se guarda como planificada.
- Dato leído el 16-oct-2026: el tarugo aparece con tres códigos (6201028, 3105088 y 62011087), y hay códigos de módulo que no existen en el maestro (6201028, 3105049, 3105047, 3105586). El importador los marca como cualquier otro código sin resolver.

Criterio de aceptación: una hoja con un código inexistente en Odoo no se importa y lista la columna y el código.

### Metrado como receta real (M17-15)

Reemplaza el metrado del ambiente en metros lineales (M16-03) y el «metrado por cantidad» publicado en la v29.

- El supervisor mide el espacio; el diseño y el despiece que resultan se cargan como receta real del mueble: piezas y consumo de materiales, accesorios y consumibles, a mano o con el formato del importador (M17-18).
- La receta real queda ligada al mueble y a su receta planificada.

Criterio de aceptación: un mueble metrado muestra lado a lado su receta planificada y su receta real, material por material.

### Versus y autorización en producción (M17-20)

Reemplaza la aprobación del metrado (M16-04).

- La receta real viaja con la orden de fabricación del mueble y los componentes de la orden salen de ella.
- Producción ve, por mueble y por material, presupuestado frente a real, en cantidad y en soles, con suma hacia módulo, ambiente, piso y obra.
- Si el costo real del mueble en soles supera al presupuestado en más del umbral (10% por defecto, configurable en Ajustes), la orden espera la autorización de la jefatura de proyectos. Bajo el umbral, producción sigue sin esperar.
- Toda diferencia queda registrada para revisión, haya pedido autorización o no.

Criterio de aceptación: un mueble cuyo costo real en soles supera en 8% al presupuestado pasa a producción con la diferencia registrada; uno con 12% espera la autorización de la jefatura.

### Productos del proyecto (M18-15)

Lo que hay hoy, leído en la base y en la ficha: la orden de fabricación sale por piso con el producto de la tipología (campo «Producto» de la tipología) multiplicado por sus ambientes. Los módulos de la tipología no tienen producto propio; el módulo existe como tarea con su estado (planificado, en producción, producido, en obra, instalado, entregado). Las plantillas de ejecución tienen «Producto de la partida».

Esto deja un vacío: lo que sale de planta y llega a obra no es un producto del maestro, sino una cantidad del producto genérico de la tipología. Para trazar el envío y el stock en tránsito, el módulo necesita existir como producto.

Decidido por Vicente el 16-oct-2026: un producto por módulo.

- Al aprobar el plan, el sistema crea en el maestro un producto fabricado por cada módulo de cada tipología de la obra, con código de obra y tipología, y su lista de materiales tomada de la receta.
- La orden de fabricación produce esos productos; la receta real del metrado (M17-15) actualiza la lista de materiales del módulo correspondiente.
- El producto de cada módulo se identifica por tipología y posición en el mueble, no por el nombre del módulo, porque 62 nombres de módulo tienen recetas distintas dentro de la misma obra (M18-18). Lleva como atributos el tipo de módulo y el método de unión (M18-17, M18-18). Esta forma de identificarlo es nuestra propuesta.
- Cada unidad física se identifica con número de serie o lote por departamento, para saber qué módulo va a qué ambiente.
- Al cerrar la obra, los productos quedan archivados.

Criterio de aceptación: al aprobar el plan de un piso, existen en el maestro los productos de sus módulos con su lista de materiales, y la orden de fabricación los produce con serie por departamento.

### Trazabilidad de envíos de planta a obra (M18-16)

Hoy el requerimiento de obra genera transferencias de materiales del almacén central a la ubicación de la obra. No encontré un registro de envío de módulos producidos de planta a obra (no verificado en código).

- Cada envío de planta a obra es una transferencia de inventario de Odoo con los módulos producidos (M18-15), su departamento y ambiente de destino, y también los recursos sueltos que se envían.
- La guía de remisión electrónica sale de esa transferencia con la localización peruana instalada.
- Al recibir en obra, el módulo pasa a «en obra»; lo que no llega o llega dañado queda registrado con foto en el chatter.
- Reporte de envíos por obra, piso, departamento, fecha y estado: producido, en tránsito, en obra, instalado.

Criterio de aceptación: un envío de los módulos de un departamento genera su transferencia y su guía; al recibirlos, sus tareas pasan a «en obra» y el reporte los muestra como recibidos.

### Origen del conocimiento de las secciones M18-17 a M18-21

Análisis del Drive de Allcenter del 16-oct-2026. Se leyeron completos: 49 fichas de pago de contratas ALL-PR-F-03 (cocinas, baños, closets y cajones), los despieces de proyección de materiales de 28 obras y los listados de despiece de producción ALL-P-F-01 de 2024 y 2025. Lo marcado «Dato leído» se leyó en esos archivos; lo demás es propuesta.

### Modelo del mueble de mobiliario (M18-17)

- Uso de la plantilla de niveles «Edificio» (torre › piso › departamento › ambiente › mueble › módulo):
  - Cocinas: la tipología o modelo (por ejemplo, COCINA 04) se asigna al ambiente. El mueble es el tipo: mueble bajo, mueble alto, torre o isla. El módulo se nombra por su función y su ancho en mm (MOD LAVADERO 900, MOD ALTO CAMPANA 610).
  - Closet, baño, lavandería, ducto y estacionamiento: el bloque del despiece es el mueble completo.
- Dato leído: el despiece de cocinas separa los módulos bajos de los altos, y la instalación se paga por ml de mueble bajo y de mueble alto.
- Atributo «tipo de módulo»: estándar o especial. Los especiales son microondas, campana, alacena con puertas o repisero, torre de horno, refrigeradora, esquinero, cajonera, condimentero, botellero y zócalo.
- «Módulo tarugo» y «Módulo tornillo» no son módulos. Los registros de prueba de ZZMOMEN con esos nombres se reemplazan por los módulos reales del despiece.

Criterio de aceptación: importar COCINA 04 de MOMEN deja el ambiente con la tipología, dos muebles (bajo y alto) y sus 9 módulos con nombre y tipo.

### Método de unión del módulo (M18-18)

- Dato leído: ningún archivo de Allcenter ni Odoo registra el método por módulo. Solo se deduce de los insumos del despiece:
  - solo tornillo: 20 a 25 tornillos 4x50;
  - mixto: 12 a 15 tornillos 4x50 y 12 tarugos;
  - solo tarugo: 20 a 28 tarugos;
  - minifix: se paga en los baños de ELEMENT y ROOF GARDEN, pero ningún despiece lo usa;
  - sin unión: zócalos y tapas de isla.
- Dato leído: closets, lavanderías, ductos y estacionamientos van siempre con tornillo y corner.
- Dato leído: 62 nombres de módulo tienen recetas distintas dentro de la misma obra. Por eso el método no se deduce del nombre.
- Atributo «método de unión» del módulo, con estos valores: tornillo, tarugo, mixto, minifix, sin unión.
- El importador (M17-18) lo propone con reglas configurables sobre los insumos de armado; no cuentan los tornillos de instalación (5x60 y el segundo grupo). El atributo es editable. El importador avisa cuando la receta no calza en ninguna regla.

Criterio de aceptación: un bloque con 12 tornillos 4x50 y 12 tarugos queda como mixto; uno con 25 tornillos queda como tornillo; un zócalo queda como sin unión.

### Catálogo de actividades de contrata de mobiliario (M18-19)

Las actividades son un catálogo propio, separado de los módulos. Cada actividad tiene unidad, sub etapa (M18-14) y tarifa por lista. Dato leído, tarifas base de la lista de cocinas:

| Clase | Actividad | Unidad | Tarifa S/ |
| --- | --- | --- | --- |
| Armado del casco, según el método (1.2) | Tornillo | und | 6 |
|  | Tarugo | und | 8 |
|  | Mixto (partida propia, decidido por Vicente el 16-oct-2026) | und | A definir con Allcenter |
| Armado en obra (2.1) | Minifix | und | 6,5 |
| Armado de módulo especial (1.2) | Microondas | und | 7 |
|  | Campana | und | 7 |
|  | Alacena con puertas (repisero: 7) | und | 12 |
|  | Torre de horno | und | 15 |
|  | Refrigeradora | und | 12 |
|  | Esquinero | und | 14 |
|  | Cajonera | und | 7 |
|  | Condimentero | und | 3 |
|  | Botellero | und | 7 |
|  | Zócalos | und | 3 |
| Complementarias (1.2) | Entarugado | und | 3 |
|  | Colocación de puertas | ml | 3 |
|  | Tapacanteo | und | 1 |
|  | Cortes especiales | und | 1 |
|  | Pegado de canto | und | 0,5 |
|  | Repisas fijas | und | 1,5 |
|  | Armado de cajón | und | 1 |
|  | Tapa de cajón | und | 1 |
|  | Correderas | und | 1,5 |

- Listas de tarifas por familia: cocina y baño en una; closet y cajones en otra, más baja (tornillo 5,5, tarugo 7, esquinero 12, tapacanteo y cortes 0,5). Las listas se versionan por obra, porque, dato leído, las tarifas se pactan por obra.
- El módulo estándar toma la actividad según su método; el especial, según su tipo.
- Dato leído: el entarugado se paga también en módulos sin tarugo. Por eso es una actividad aparte y no se deriva del método.

Criterio de aceptación: un módulo mixto genera una línea «Armado módulo mixto» y uno de tipo microondas genera «Armado microondas», cada uno en 1.2 con su tarifa de la lista de la obra.

### Receta de contrata generada desde las piezas (M18-20)

- Dato leído: hoy las cantidades de pago se digitan por departamento, no se derivan del modelo, y el mismo modelo varía entre departamentos.
- El plan genera las líneas de contrata de cada módulo desde su receta:
  - 1 und de la actividad de armado que corresponde (M18-19);
  - colocación de puertas = suma de anchos de las piezas PUERTA, en ml;
  - cajones, tapas y correderas = desde las piezas FRENTE y TAPA y desde la cajonera;
  - instalación = ml de mueble bajo y de mueble alto, como suma de los anchos de sus módulos.
- La regla de instalación queda por validar: contra las fichas de MOMEN la suma se acerca pero no es exacta.
- Si la receta real del metrado (M17-15) cambia las piezas PUERTA, FRENTE o TAPA, o el método de unión, las líneas de contrata del módulo se recalculan antes de liquidar, y la diferencia con lo planificado queda a la vista. Esta regla es nuestra propuesta.

Criterio de aceptación: el dpto 304 de MOMEN (COCINA 04) genera sus líneas de armado y de puertas, y su total se compara con lo pagado en la ficha ALL-PR-F-03 (filas 68 a 71).

### Pago repetido y re-trabajo de contratas (M18-21)

- Amplía el control de consumo sin repetición (M18-05) a las actividades de contrata: la misma actividad, módulo y dpto no se liquida dos veces sin autorización de la jefatura de proyectos.
- Dato leído: hay dptos valorizados igual en dos semanas, por contratistas distintos (MIDGO 602, 707 y 802; ROOF GARDEN 115).
- El re-trabajo va en una línea propia, con motivo tomado de una lista: cambio, faltante, mal armado. Dato leído: hoy se escribe «CAMBIO» o «FALTANTE» en las columnas de piso o dpto y se paga con las mismas partidas.

Criterio de aceptación: una segunda liquidación del armado del mismo módulo queda esperando autorización; un re-trabajo con motivo «mal armado» se liquida sin bloqueo y queda separado en el análisis de control.

### Hoja de trabajo de la oficina técnica en Odoo (M18-22)

Decidido por Vicente el 16-oct-2026: la oficina técnica de mobiliario arma todo el presupuesto y la carga de la obra en la hoja de cálculo de Odoo, y se prescinde del Excel. La hoja recibe datos crudos; el analista mide sobre el plano y registra. Aprobado el presupuesto por el cliente, la hoja carga el planificador.

### Piloto

Armado y probado el 16-oct-2026 en newallcenter\_dev\_1, sin cambios de código, sobre la hoja de trabajo que ya trae el planificador (al\_construction\_planner\_spreadsheet): obra ZZHOJA-97-26 PILOTO HOJA DE TRABAJO, documento «Maestro de planificación · ZZHOJA-97-26 PILOTO HOJA DE TRABAJO» (id 192) en Documentos. Datos de ejemplo: COCINA 04 de MOMEN, módulos 1 y 5. Los códigos de producto del ejemplo se reasignaron por aproximación a productos de esa base y no son los de Allcenter. El piloto es el modelo de la plantilla que se pide.

Decisiones de diseño tomadas por Vicente en el piloto:

- Datos crudos. Las únicas columnas calculadas por fila son el código del producto, los m² de la pieza y el costo de la línea de materiales.
- Los resúmenes son tablas dinámicas sobre la propia hoja, no sumas por fórmula.
- El costo se calcula por fila en BOM, con el costo vivo del maestro.
- Los materiales se eligen en dos pasos: Categoría (último nivel de la categoría del maestro, por ejemplo «1011 TABLEROS», sin «Deliveries» ni «Expenses») y después Producto, cuya lista muestra solo los de esa categoría con código y nombre completo (por ejemplo «\[10110011003\] Tablero melamínico 18 mm Duratex (2150 × 2440 mm, Blanco, RH)»). Se puede escribir para buscar. Los productos nuevos aparecen en la lista de su categoría.
- La carga al planificador se hace con el botón «Enviar al planificador» de la hoja, una vez aprobado el presupuesto.

### Estructura de la hoja

| Pestaña | Qué registra el analista | Lo lee hoy el planificador | Pide el paquete 1.8 |
| --- | --- | --- | --- |
| LEEME | Instrucciones | — | — |
| RESUMEN | Cuatro tablas dinámicas: ambientes por tipología, costo por módulo y sub etapa, despiece por tablero, materiales por tipología | — | — |
| OBRA | Datos y condiciones de la obra | No | Sí |
| ARBOL | Piso, departamento, ambiente, tipología y tipo de unidad | Sí | — |
| TIPOLOGIAS | Código, nombre, familia, otros nombres y tipología base | Sí | — |
| MUEBLES | Muebles de cada tipología | Sí | — |
| MODULOS | Código (el del ETO), nombre, mueble, tipo, ancho, grupo ML, actividad de armado, tipo de módulo y método de unión | Sí, salvo tipo de módulo y método | Tipo de módulo y método (M18-17, M18-18) |
| PIEZAS | Despiece: cantidad, largo, ancho, tipo de pieza, color, categoría, producto, cantos; código y m² calculados | No | Sí (M18-20) |
| BOM | Materiales por módulo: categoría, producto, cantidad, unidad, etapa y sub etapa; código y costo calculados | Sí, sumados por tipología | Por módulo y por sub etapa (M18-15, M18-14) |
| PRODUCTOS NUEVOS | Código provisional, nombre, unidad, categoría y costo estimado | No | Sí |
| ACTIVIDADES | Actividades de contrata con su cantidad | Sí, por tipología | Por módulo (M18-20) |
| VARIANTES | Color, excluir o metrado distinto por departamento | Sí | — |
| TARIFAS | Tarifa de la obra, contratista, retención y vigencia | No | Sí (M18-19) |
| CONTRATOS, HITOS y VENTA | Contratos del CXC, hitos de cobro y precio por tipología | No | Sí |
| MO PROPIA | Rol, categoría, sub etapa, jornal y rendimiento | No | Sí |
| REFERENCIAS | Listas vivas de Odoo: actividades, maestro de productos (código, nombre completo, unidad, costo y categoría) y categorías | — | — |
| \_LISTAS (oculta) | Lista de productos filtrada para cada fila de PIEZAS y BOM | — | — |

### Resultados del piloto

Medidos el 16-oct-2026 en newallcenter\_dev\_1:

- Vista previa de «Enviar al planificador», sin importar: 1 tipología, 2 muebles, 2 módulos, 5 actividades, 1 ambiente y 33 de las 36 filas de BOM. Las otras 3 son los dos productos nuevos, que se crean si se marca «Crear los productos que no existen». El importador sumó los materiales por tipología.
- La hoja piloto queda lista en unos 7 s. Cambiar una categoría actualiza la lista de productos en 0,04 s y editar una medida, en 0,02 s.
- Prueba de volumen con 100 módulos, 1 800 filas de materiales, 1 200 piezas y 500 departamentos (versión anterior, sin listas dependientes): abre en 6,5 s y cada edición tarda 0,84 s con el costo por fila.
- La hoja envía valores ya calculados, porque el botón la lee en el navegador. En el servidor la hoja se guarda como JSON con las fórmulas, una foto periódica y las revisiones; el servidor no calcula fórmulas.
- En las tablas dinámicas aparece un grupo «(Sin definir)» por las filas vacías del rango.

### Desarrollo pedido

- Plantilla de mobiliario: que «Hoja de trabajo» de la obra cree la hoja con la estructura del piloto (pestañas, encabezados, listas desplegables, listas dependientes, columnas calculadas y tablas dinámicas) en lugar de las nueve pestañas en blanco de hoy.
- REFERENCIAS con el maestro de productos completo (hoy la lista llega a 300 filas), incluido el nombre completo y la categoría, y la lista de categorías por último nivel.
- Que el envío lea también OBRA, CONTRATOS, HITOS, VENTA, TARIFAS, MO PROPIA, PIEZAS y PRODUCTOS NUEVOS y las columnas marcadas «(1.8)», con la lista de materiales por módulo y las sub etapas.
- Productos nuevos: tomar nombre, unidad, categoría y costo de PRODUCTOS NUEVOS (hoy el importador toma el nombre de la columna Producto de BOM, que en la hoja trae el código entre corchetes); asignar el código con la regla del maestro, mostrar los parecidos con la lógica de P-17 y reemplazar el código provisional.
- Listas dependientes para al menos 300 filas por pestaña, ampliables por obra.
- Que las tablas dinámicas no muestren el grupo «(Sin definir)» de las filas vacías.
- Que el botón avise si el presupuesto de la obra no está aprobado. Este control es nuestra propuesta.
- Solo para la vertical Mobiliario. En construcción la receta sigue en los Work Items y en el planificador (M18-13).

Criterio de aceptación: la COCINA 04 de MOMEN armada solo en la hoja, con un material que no existe en el maestro, se envía al planificador y deja la obra con su árbol, la tipología, sus muebles y 9 módulos con código, tipo y método de unión, la lista de materiales de cada módulo, las actividades y tarifas de la obra, el contrato con sus hitos y el producto nuevo creado con su código. Un segundo envío no duplica nada.

## Migración y compatibilidad con las bases existentes

La v33 ya migra las bases existentes al perfil Mobiliario sin cambiar su plantilla, parámetros ni funciones. Los requerimientos nuevos deben mantener esa regla.

- La secuencia de etapas de mobiliario (M18-14) convierte las cuatro etapas actuales a las sub etapas nuevas sin cambiar montos.
- Los metrados registrados con la lógica de metros lineales o de cantidad quedan como histórico de solo lectura.
- Los planes aprobados, sus presupuestos analíticos, asignaciones, avances, liquidaciones y valorizaciones conservan montos y vínculos.

Criterios de aceptación:

1. Los 19 criterios de `docs/planificador/ACEPTACION.md` siguen con el mismo resultado que hoy.
2. Las pruebas del paquete 1.6 y de las versiones 28 a 33 pasan sin cambios en sus cifras.
3. Una base existente actualizada muestra los mismos montos de plan, comprometido y real por obra que antes de actualizar.

## Casos de prueba por vertical

| Vertical | Obra de prueba | Qué comprueba |
| --- | --- | --- |
| Mobiliario | Demo del piso 05 actual, más una obra importada desde «PROYECTO COCINAS EDIFICIO FLORECE II», y la COCINA 04 de MOMEN (dpto 304) contra su ficha de pago ALL-PR-F-03 | Sub etapas en orden, importador, validación de códigos, metrado como receta real, versus con umbral del 10%, panel por tipo, matriz insumo-producto, control de consumo, modelo del mueble, método de unión, actividades y tarifas de contrata, receta de contrata desde las piezas, pago repetido y re-trabajo |
| Construcción por partidas | 2 disciplinas, 4 subpartidas y 8 partidas con APU ya cargados en `construccion_dev_1` (drywall, pintura, luminarias, tomacorrientes) | Menús sin metrado, avance por driver, receta desde Work Items, cuadrilla por jornal con sede creada sola, valorización por porcentaje arbitrario, Fabricación sin instalar |

Las cantidades y montos de la obra de construcción son datos de demostración y se marcan así.

## Decisiones

Tomadas por Vicente el 15 y 16-oct-2026:

- El umbral de autorización en producción se mide sobre el costo total del mueble en soles (M17-20).
- La plantilla de la oficina técnica trabaja con el maestro de productos vigente (M17-19).
- La compra masiva de la vertical de construcción va a stock general.
- La valorización de proyecto y la de contratas admiten un porcentaje arbitrario, en las dos verticales (M18-09).
- Etapas de mobiliario: Producción (producción de piezas, armado) e Instalación (instalación, acabado, limpieza) (M18-14).
- Cualquiera de las dos verticales puede usar la nómina de construcción civil o la de régimen general (M18-06).
- Las cuadrillas se miden en jornales y la unidad de tiempo (hora, medio día, día completo) es configurable, reutilizando lo que ya trae la nómina de Odoo (M18-07).
- Las sedes de marcación de un proyecto son solo de obra; las de planta no se atribuyen a un proyecto (M18-08).
- La semana de contratas es configurable en las dos verticales.
- Los montos solo los ven las personas autorizadas (M18-10).
- El avance se registra en formulario estándar con chatter (M18-11).
- Productos del proyecto: un producto por módulo, creado en el maestro al aprobar el plan (M18-15).
- El costo de personal de las sedes de planta llega a las obras a través de las órdenes de fabricación (M18-08).
- La receta de construcción vive en los Work Items de Ventas y en el planificador, sincronizadas (M18-13).
- Se prescinde del Excel: con el maestro vivo en la hoja de Odoo, la exportación de la pestaña «codigos» ya no se usa (M17-19, M18-22).
- Matriz insumo-producto: filas = elementos del alcance; columnas = insumos agrupados por etapa y sub etapa (M18-04).
- Los requerimientos nuevos forman el paquete 1.8; los pendientes de la 1.7 conservan su código M17.
- El armado de módulos mixtos es una partida propia de contrata (M18-19).
- La oficina técnica de mobiliario arma todo el presupuesto y la carga de la obra en la hoja de cálculo de Odoo, y el envío al planificador crea directamente los productos nuevos (M18-22).
- En construcción por partidas no se usa la hoja de cálculo: la receta sigue en los Work Items y en el planificador, sincronizados (M18-13).
- Hoja de trabajo de mobiliario: datos crudos, resúmenes con tablas dinámicas, costo por fila en BOM, materiales por categoría (último nivel) y producto, y carga con el botón de la hoja al aprobarse el presupuesto (M18-22).

Abiertas:

- Tarifa del armado de módulo mixto: a definir con Allcenter (M18-19).
- Regla de ml de instalación: validar contra las fichas de MOMEN, donde la suma de anchos se acerca pero no es exacta (M18-20).

## Fuentes

- Base `construccion_dev_1`, [construccion-dev.altalatam.com](https://construccion-dev.altalatam.com/odoo), módulo en la versión 19.0.33.20261013, leída el 16-oct-2026.
- [Registro de cambios del planificador](https://github.com/olanoit/ol_new_apps/blob/19.0/OL-PROJECTS/al_construction_planner/CHANGELOG.md), versiones 28 a 33.
- [Ficha del planificador](https://raw.githubusercontent.com/olanoit/ol_new_apps/19.0/docs/fichas/al_construction_planner.yml)
- [Criterios de aceptación](https://raw.githubusercontent.com/olanoit/ol_new_apps/19.0/docs/planificador/ACEPTACION.md)
- Hojas de proyección de materiales de Allcenter, por ejemplo [PROYECTO COCINAS EDIFICIO FLORECE II](https://docs.google.com/spreadsheets/d/1qOuWSBbRaSg2dwyH-Rmm6NyQbLg5F_9QSlAbGOFCatc/edit), [PROYECTO CLOSET LAMBAYEQUE](https://docs.google.com/spreadsheets/d/1rVv9E3PB4x2KBdPG-uRPxvmihPG8I1TyLNkjiMkakRk/edit) y [PROYECTO MOMEN\_ COCINAS](https://docs.google.com/spreadsheets/d/1j_XekRnUwodsDQ6iDxkhbDKfCVM0-cfZnD6Xj3GSEYw/edit), leídas el 15-oct-2026.
- Drive de Allcenter, leído el 16-oct-2026: fichas «Armado de muebles de cocinas/BAÑO/CAJONES \_ Edificio …» e «Instalación …» (ALL-PR-F-03) de 32 obras; carpetas «PROYECCION DE MATERIALES» de 28 obras; «PROYECTO MOMEN\_ COCINAS»; «ALL-P-F-01 Listado de despieces de producción» 2024 y 2025.
- Libro Allcenter\_Maestro\_Carga\_Obra\_v1.0.xlsx de la oficina técnica, revisado el 16-oct-2026.
- Código publicado del planificador, repositorio olanoit/ol\_new\_apps, versión del 16-oct-2026: importador del maestro, hoja de trabajo y creación de productos.
- Piloto de la hoja de trabajo en newallcenter\_dev\_1, documento 192 de la obra ZZHOJA-97-26, armado y medido el 16-oct-2026.
