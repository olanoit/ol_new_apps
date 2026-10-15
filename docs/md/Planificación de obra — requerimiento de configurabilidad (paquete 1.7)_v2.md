# Planificación de obra — requerimiento de configurabilidad (paquete 1.7)

Oct 15, 2026 · @Vicente

## Objetivo y alcance

Pedimos que Planificación de obra (AL), `al_construction_planner`, se configure por rubro en lugar de estar construido para mobiliario. Con el mismo módulo deben poder trabajar Allcenter, constructoras como CREVAL o Montegrande, contratas de partidas eléctricas y empresas de tuberías para minería.

El requerimiento parte de la versión 27 (paquete 1.6 completo, M16-01 a M16-11) y se numera como paquete 1.7 (M17-xx), siguiendo la convención del repositorio. La numeración es una propuesta; ajústala si te conviene otra.

Alcance:

- Perfiles de vertical que configuran el planificador completo al elegirlos, empezando por construcción y mobiliario, sobre una estructura de niveles y etapas definida por configuración.
- Funciones activables desde Ajustes, con un núcleo que solo depende de Proyectos.
- Separación entre lo que el planificador planifica y controla y lo que se opera en la aplicación nativa de Odoo.
- Generalización de cuatro mejoras del paquete 1.6 hoy redactadas en términos de mueble.

Fuera de alcance: cargar datos de clientes, migrar las bases de CREVAL o Montegrande y cambiar la localización contable.

## Rubros que debe soportar

Los cuatro rubros difieren en profundidad del árbol, en etapas y en si fabrican. La configuración tiene que cubrir esas tres diferencias sin código por cliente.

| Rubro | Ejemplo | Niveles del árbol | Etapas | Fabrica |
| --- | --- | --- | --- | --- |
| Contrata de mobiliario | Allcenter | Torre › piso › departamento › ambiente › mueble › módulo | Producción, armado, instalación, acabado y entrega | Sí |
| Constructora por partidas | CREVAL, Montegrande | Disciplina › subpartida › partida | Actividades de la partida (por ejemplo trazo, emplacado, masillado) | No |
| Contrata eléctrica | Por definir | Zona o tablero › sistema › partida | Canalización, cableado, conexionado, pruebas | No |
| Tuberías para minería | Por definir | Área › línea › spool | Habilitación, prefabricación en taller, traslado, montaje, prueba hidrostática | Sí |

La fila de Allcenter describe lo que el módulo ya hace. La de constructora recoge lo decidido para CREVAL y Montegrande. Las filas de contrata eléctrica y tuberías son ejemplos nuestros para probar la configuración; los niveles y etapas reales se validarán con cada cliente.

## Planificar y controlar frente a operar

El planificador planifica y controla; cada operación se ejecuta en la aplicación de Odoo que le corresponde y vuelve al planificador como dato de control. La única excepción es la asignación de cuadrillas propias, porque ninguna aplicación nativa arma cuadrillas con rendimiento y las asigna a una etapa.

| Función | Qué hace el planificador | Dónde se opera | Qué vuelve como control |
| --- | --- | --- | --- |
| Materiales | Explosiona la necesidad por partida o receta, con fecha tomada de la etapa, y lanza el requerimiento de compra masivo | Compras: proveedores, cotizaciones, precios y OC. Inventario: recepción y despacho | Pedido, comprado, despachado, consumido, saldo |
| Producción | Propone órdenes de fabricación por nivel y etapa | Fabricación | Producido y consumido contra lo planificado |
| Contratas | Asigna contrata, tarifa y alcance por actividad | Compras: OC de servicio. Contabilidad: factura y pago | Avance validado, liquidado, retenido |
| Cuadrillas propias | Arma la cuadrilla y la asigna a la etapa (excepción: se opera aquí) | Hojas de horas y Asistencias registran lo trabajado | Horas reales contra horas del plan |
| Ingresos | Programa valorizaciones e hitos de cobro | Ventas y Contabilidad: factura y cobro | Valorizado, facturado, cobrado |
| Cronograma | Programa niveles y etapas en el Gantt | — | Avance contra línea base |

La liquidación semanal de contratas tampoco tiene aplicación nativa. Se queda en el planificador como función de control, dentro del puente de contratas.

## Situación actual

El modelo de datos está fijado al mueble en cuatro puntos, y Ajustes no tiene ningún interruptor de funciones. Datos leídos el 15-oct-2026 de la base `construccion_dev_1` (IONOS) con el módulo en la versión 19.0.27.20261013, sobre las definiciones de campos que instala el módulo.

| Punto | Lo que hay hoy | Dato verificado |
| --- | --- | --- |
| Etapas | Lista cerrada: producción, armado, instalación, acabado y entrega | 13 campos de selección con esa lista, en 13 modelos |
| Niveles | Funciones fijas en la plantilla (agrupador, unidad, ambiente, mueble, módulo) y vínculos con nombre fijo en las tareas | 19 campos que apuntan a la tarea de piso, departamento, mueble o módulo, en 9 modelos |
| Tipos de recurso | Material, servicio, contrata, personal propio, producción. No existe equipo | 5 campos de selección con esa lista |
| Receta | Tipología con familia (cocina, closet, baño, lavandería, ducto, área común, especial, otro), módulos con ancho en mm y metros lineales; materiales en una lista de materiales de Fabricación | Campos de `construction.typology` y `construction.typology.module` |
| Ajustes | Parámetros de adelanto, fondo de garantía, días de pago y liquidación, frecuencia de valorización y cuentas | 21 parámetros, ninguno de tipo activar o desactivar |
| Dependencias | Obligatorias, entre ellas Proyecto–Fabricación, Requerimiento de compra, Presupuestos, Planificación, Ventas y Aprobaciones por niveles | 13 módulos en el manifiesto |

Consecuencia práctica: instalar el planificador en una constructora sin fabricación arrastra Fabricación. En `construccion_dev_1` la instalación del 14-oct-2026 sumó 19 módulos, entre ellos Fabricación, órdenes de trabajo y Calidad.

## Estructura configurable — prioridad 1

Es el bloque que habilita todo lo demás: mientras niveles, etapas y recursos sean listas fijas, apagar menús no cambia el modelo.

### Niveles de profundidad libre (M17-01)

- La plantilla de niveles admite n niveles, con nombre libre y orden.
- Cada nivel declara su comportamiento con casillas: lleva etapas, lleva receta de recursos, se mide con metrado, se valoriza o factura, recibe avance, es unidad de entrega.
- Los 19 vínculos con nombre fijo (piso, departamento, mueble, módulo) se reemplazan por el nivel superior y la ruta completa almacenada, para conservar la acumulación de montos sin recorrer el árbol.
- Árbol de recursos, cronograma, importador y asistentes leen la plantilla y no asumen nombres.

Criterio de aceptación: una obra con la plantilla disciplina › subpartida › partida › actividad genera su árbol, acumula montos en cada nivel y se ve completa en el árbol y en el cronograma.

### Etapas configurables (M17-02)

- Las etapas pasan a ser un catálogo propio, asociado a la plantilla de la obra.
- Cada etapa tiene nombre, orden, etapa anterior por defecto, nivel del que cuelga y tipo: fabricación, ejecución en campo o control.
- Los 13 campos que hoy usan la lista cerrada apuntan al catálogo.
- El tipo de etapa decide qué asistentes aplican: una etapa de fabricación habilita la orden de fabricación; una de campo, la asignación de contrata o cuadrilla.

Criterio de aceptación: una partida de drywall programa trazo, emplacado y masillado encadenadas, y un spool programa prefabricación en taller seguida de montaje.

### Tipos de recurso configurables (M17-03)

- Catálogo de tipos de recurso con su forma de abastecimiento: compra, almacén, fabricación, contrata o cuadrilla propia.
- Se agrega equipo, hoy inexistente.
- Planificación, control y análisis agrupan por este catálogo.

Criterio de aceptación: una receta con material, mano de obra de contrata, cuadrilla propia y equipo genera líneas de plan de los cuatro tipos y el control las separa.

### Receta independiente del mueble (M17-04)

- La tipología se generaliza a una plantilla de ejecución: líneas de recurso con cantidad por unidad del nivel, rendimiento, cuadrilla y etapa.
- Los campos de mueble (familia cocina o closet, ancho en mm, metros lineales, tipo de módulo) pasan a una extensión del rubro mobiliario.
- La receta se carga de tres formas: escrita en el planificador, importada desde Excel o tomada de los Work Items de Ventas (paquete Construction de Odoo), que es donde hoy está el APU en `construccion_dev_1`.

Criterio de aceptación: la partida «Muro drywall RF» (ARQ-03.02.01) genera su plan desde su Work Item, con material, mano de obra y equipo, sin crear una tipología de mueble.

### Perfiles de vertical (M17-05)

Al elegir la vertical, el planificador queda configurado completo con el diseño de operación que ya funciona en ella. Después cada parámetro se puede ajustar.

- Un perfil de vertical es un registro de datos, no código. Reúne niveles, etapas, tipos de recurso, interruptores activos, parámetros de Ajustes, grupos y reglas de aprobación, planes analíticos y valores por defecto de la obra.
- Se elige en Ajustes como perfil de la compañía y se puede cambiar en cada obra al crearla.
- Aplicarlo instala los puentes que el perfil activa y crea lo que falta, sin borrar lo existente. Se puede volver a aplicar.
- Aplicado el perfil, todo sigue editable, y el perfil muestra qué parámetros se apartan de su definición.
- Arranca con dos perfiles que reproducen el diseño de operación actual: Construcción por partidas (CREVAL, Montegrande) y Mobiliario (Allcenter).
- Los perfiles nuevos se cargan sin desarrollo: se exporta un perfil configurado en una base y se importa en otra. Contrata eléctrica y tuberías entrarán así cuando las definamos.

| Elemento | Construcción por partidas | Mobiliario |
| --- | --- | --- |
| Niveles | Disciplina › subpartida › partida › actividad | Torre › piso › departamento › ambiente › mueble › módulo |
| Etapas | Actividades de la partida, desde el catálogo | Producción, armado, instalación, acabado y entrega |
| Receta | APU por partida; fuente por decidir (Work Items o receta propia) | Tipología con módulos, metros lineales y lista de materiales |
| Producción | Desactivada; Fabricación no se instala | Activada |
| Contratas | Activada; la contrata entra al APU como línea de mano de obra | Activada; destajo por driver y portal de la contrata |
| Cuadrillas propias | Activada | Activada |
| Compra masiva | Activada; destino por decidir (stock general u obra) | Activada; stock general |
| Metrado y avance | Por partida, en su unidad (m², und, ml) | ML de mueble bajo y alto, y módulos |
| Analítica | Planes Proyecto, Disciplina, Subpartida y Partida | Obra › etapa › partida, como hoy |
| Ingresos | Valorización por avance de partida, por confirmar | Valorización por hitos por unidad |
| Semana de contratas | Por definir con CREVAL y Montegrande | Inicio jueves, liquidación jueves, pago sábado |
| Grupos | Jefatura y asistente de proyectos | Jefatura y asistente de proyectos |

La columna de mobiliario sale de la configuración actual del módulo (ficha y registro de cambios). La de construcción sale de lo decidido para CREVAL y Montegrande; lo marcado por decidir o por confirmar está en Decisiones abiertas.

Criterio de aceptación: en una base nueva, elegir Construcción por partidas deja listo el planificador para la obra de prueba de constructora, sin pasos manuales y sin Fabricación. Elegir Mobiliario reproduce la demo del piso 05 con las cifras del criterio 2: 66 módulos, 41.33 ML y S/ 8,944.44. Un perfil exportado de una base e importado en otra deja la misma configuración.

## Alcance activable — prioridad 2

Cada empresa activa solo lo que usa, y lo que no activa no se instala.

### Interruptores en Ajustes (M17-06)

- Siempre activos: Proyectos, planificación (árbol, plan de recursos, línea base) y cronograma.
- Activables: control, producción, contratas, compras y abastecimiento, requerimientos de obra, cuadrillas propias, presupuesto analítico, avance y metrados, valorización e ingresos, rubro mobiliario.
- Cada interruptor muestra u oculta sus menús, campos, botones del árbol y asistentes.
- Se implementan como los campos `module_*` de los Ajustes de Odoo: activar instala el puente correspondiente.

Criterio de aceptación: con solo control y contratas activos, el menú no muestra órdenes de fabricación, compra masiva ni valorizaciones, y Fabricación no está instalada.

### Núcleo con módulos puente (M17-07)

El manifiesto del núcleo depende solo de Proyectos, el Gantt AL y Aprobaciones por niveles (la línea base se aprueba). El resto pasa a puentes. Los nombres técnicos son una propuesta.

| Puente (propuesto) | Depende de | Contiene hoy |
| --- | --- | --- |
| Producción | Proyecto–Fabricación | Orden de fabricación desde el plan, etapa de consumo en la lista de materiales, estado producido |
| Compras y abastecimiento | Requerimiento de compra, requerimientos de obra | Compra masiva, abastecimiento de la obra, precios de compra, crear producto, material extra |
| Contratas | Compras, portal | Asignar contrata, tarifas, avance por driver, liquidación semanal, descuento a la contrata, portal de la contrata |
| Cuadrillas propias | Planificación, Hojas de horas | Asignar cuadrilla, turnos, horas como real |
| Presupuesto y control | Presupuestos | Presupuesto analítico al aprobar, control de OC contra presupuesto, análisis de control |
| Valorización e ingresos | Ventas, Proyecto–Ventas | Calendario e ingresos, entrega semanal, valorización, hitos de cobro, cronograma valorizado |
| Rubro mobiliario | Producción | Tipología de mueble, metros lineales, módulos con ancho, importación del ETO |

&#91;embedded content: núcleo y puentes · 7 puentes, cada uno con su aplicación\]

Una constructora sin fabricación activa compras, contratas, cuadrillas, presupuesto y valorización, y deja fuera producción y mobiliario.

Criterio de aceptación: el núcleo instala en una base sin Fabricación, sin Ventas y sin Requerimiento de compra, y genera y aprueba un plan.

## Operación en la aplicación nativa — prioridad 2

El planificador genera el documento de partida y lee el resultado; la gestión del documento ocurre en su aplicación.

### Compras (M17-08)

- Explosión de materiales por partida o receta, con fecha de necesidad tomada de la etapa y saldo por pedir.
- La compra masiva genera el requerimiento de compra agrupado por partida, receta, etapa o fecha, a elección del usuario.
- Compras asigna proveedor, pide cotizaciones, compara y fija precios sobre ese requerimiento. El planificador no crea OC de material.
- El planificador lee comprometido, comprado y recibido por línea, como hoy hace con las asignaciones.

Criterio de aceptación: una compra masiva de dos partidas llega a Compras como requerimiento, se cotiza a tres proveedores desde Compras y el comprado vuelve a las líneas del plan.

### Producción (M17-09)

- El planificador propone órdenes de fabricación por nivel y etapa de tipo fabricación; Fabricación las ejecuta.
- El asistente actual de orden de fabricación desde el plan pasa al puente de producción.

Criterio de aceptación: una obra de tuberías propone las órdenes de los spools de un área y el consumo de Fabricación vuelve a sus líneas.

### Contratas (M17-10)

- Asignar contrata, tarifa y alcance por actividad es planificación.
- La OC de servicio se confirma y gestiona en Compras; la factura y el pago, en Contabilidad.
- Avance por driver y liquidación semanal se mantienen en el puente de contratas, como control.

Criterio de aceptación: la OC de servicio que nace de «Asignar contrata» se confirma en Compras y la liquidación aprobada recibe sobre ella.

### Cuadrillas propias (M17-11)

- La cuadrilla se arma y asigna en el planificador: composición por rol, rendimiento de la actividad y etapa.
- Los turnos se publican en Planificación de Odoo; lo trabajado se registra en Hojas de horas y Asistencias.
- El módulo ya extiende los turnos de Planificación en «Asignar cuadrilla»; se pide revisar que el flujo cumpla esta división.

Criterio de aceptación: una cuadrilla de un operario, un oficial y un peón asignada a una partida aparece como turnos en Planificación y sus horas suben el real de la línea.

### Clasificación de cada menú (M17-12)

Cada menú y asistente se clasifica como planificar, controlar u operar. Los de operar se trasladan a su aplicación, se convierten en acceso directo a ella o se justifican como control.

Por su nombre, hoy operan dentro del planificador: OC de servicio, requerimientos de compra, órdenes de fabricación, contratos de obra, liquidaciones semanales, valorizaciones, cobranza y entregas semanales. Esta lista es nuestra lectura de los nombres de menú y se debe validar contra el código.

Criterio de aceptación: tabla de clasificación entregada con el paquete y menús reubicados según ella.

## Control por cualquier nivel (M17-13) — prioridad 3

El control ya existe en la línea del plan (presupuesto, comprometido, real, saldo, % ejecutado) y debe poder leerse en cualquier nivel de la plantilla.

- Planificado, comprometido, real y avance acumulados por nivel, por etapa y por tipo de recurso.
- Comparación contra la línea base aprobada y entre versiones del plan.
- El análisis de control agrupa por los niveles de la plantilla de la obra, no por piso, departamento o ambiente.

Criterio de aceptación: en una constructora, el análisis de control muestra el desvío por disciplina, por subpartida y por partida, contra la versión aprobada.

## Generalización del paquete 1.6

El paquete 1.6 está completo en la versión 27, y cuatro de sus mejoras están escritas en términos de mueble. Las otras siete se mantienen como están y pasan a sus puentes.

| Mejora del paquete 1.6 | Cambio pedido | Requerimiento |
| --- | --- | --- |
| Compra masiva siempre a stock general (M16-02) | Destino configurable por plantilla o por obra: stock general o directo a la obra con su analítica. Mobiliario conserva stock general por defecto | Destino de la compra masiva (M17-14) |
| Metrado del ambiente en ML de mueble bajo, ML de mueble alto y módulos (M16-03) | El metrado se registra en la unidad del nivel que la plantilla marca como medible (m², und, ml, kg), con la diferencia contra lo planificado en cantidad y en soles | Metrado en la unidad del nivel (M17-15) |
| Pedido de material extra desde el portal, eligiendo piso o ambiente (M16-06) | El capataz elige cualquier nivel de la plantilla | Material extra en cualquier nivel (M17-16) |
| Avance de armado por el portal, módulo por módulo (M16-11) | El avance se reporta en el nivel de medición que defina la plantilla, para cualquier etapa de campo | Avance por portal en el nivel de medición (M17-17) |

Se mantienen sin cambio y se reubican: compra masiva consolidada (M16-01), aprobación del metrado (M16-04, la espera de la orden de fabricación va al puente de producción), material extra con aprobación de la jefatura (M16-05 y M16-07), descuento a la contrata (M16-08), y los grupos jefatura de proyectos (M16-09) y asistente de proyectos (M16-10).

## Migración y compatibilidad con Allcenter

Allcenter no puede perder nada al pasar al modelo configurable; la actualización convierte sus datos sin intervención manual.

- Script de actualización que aplica el perfil Mobiliario y mapea los datos existentes: funciones de nivel a niveles de la plantilla, las 4 etapas al catálogo, los 5 tipos de recurso al catálogo y las tipologías a plantillas de ejecución con su extensión de mobiliario.
- Los planes aprobados, sus presupuestos analíticos, asignaciones, avances, liquidaciones y valorizaciones conservan sus montos y vínculos.
- Al actualizar, una base con el módulo instalado activa los interruptores de lo que ya usa, para que nada desaparezca del menú.

Criterios de aceptación:

1. Los 19 criterios de `docs/planificador/ACEPTACION.md` siguen con el mismo resultado que hoy: 13 en verde, 5 adaptados al demo y 1 pendiente del maestro de MOMEN.
2. Las pruebas del paquete 1.6 (M16-01 a M16-11) pasan sin cambios en sus cifras.
3. La base de Allcenter actualizada muestra los mismos montos de plan, comprometido y real por obra que antes de actualizar.

## Casos de prueba por rubro

Una obra de prueba por rubro, cada una con su perfil de vertical, recorriendo plan, aprobación, abastecimiento, avance y control.

| Rubro | Obra de prueba | Interruptores activos | Qué comprueba |
| --- | --- | --- | --- |
| Mobiliario | Demo del piso 05 actual | Todos | Que nada cambia: cifras de los criterios de aceptación y del paquete 1.6 |
| Constructora por partidas | 2 disciplinas, 4 subpartidas y 8 partidas con APU ya cargados en `construccion_dev_1` (drywall, pintura, luminarias, tomacorrientes) | Control, contratas, compras, cuadrillas, presupuesto, valorización | Niveles sin mueble, etapas por partida, receta desde Work Items, compra masiva a Compras, Fabricación sin instalar |
| Contrata eléctrica | Un tablero con dos sistemas y cuatro partidas | Control, contratas, compras | Instalación mínima sin producción ni ingresos por hitos |
| Tuberías para minería | Un área con dos líneas y seis spools | Producción, compras, contratas, control | Etapa de fabricación seguida de etapas de campo en el mismo cronograma |

Las obras de contrata eléctrica y tuberías son inventadas para la prueba; sus metrados y montos se marcan como datos de demostración.

## Decisiones abiertas

- [ ] Fuente de la receta para constructoras: Work Items de Ventas, receta propia del planificador o ambas con sincronización (receta independiente del mueble, M17-04).
- [ ] Destino por defecto de la compra masiva en el perfil Construcción por partidas: stock general u obra (destino de la compra masiva, M17-14).
- [ ] Semana de contratas y forma de valorizar del perfil Construcción por partidas, a validar con CREVAL y Montegrande (perfiles de vertical, M17-05).
- [ ] Orden de entrega: proponemos estructura configurable y perfiles primero, luego núcleo con puentes, luego operación nativa y control. Cristóbal confirma si conviene otro orden por dependencias técnicas.
- [ ] Numeración M17-xx y nombres técnicos de los puentes.

## Fuentes

- Base `construccion_dev_1`, [construccion-dev.altalatam.com](https://construccion-dev.altalatam.com/odoo), módulo en la versión 19.0.27.20261013, leída el 15-oct-2026.
- [Historial de commits de olanoit/ol\_new\_apps](https://github.com/olanoit/ol_new_apps/commits/19.0)
- [Registro de cambios del planificador](https://raw.githubusercontent.com/olanoit/ol_new_apps/19.0/OL-PROJECTS/al_construction_planner/CHANGELOG.md)
- [Ficha del planificador](https://raw.githubusercontent.com/olanoit/ol_new_apps/19.0/docs/fichas/al_construction_planner.yml)
- [Criterios de aceptación](https://raw.githubusercontent.com/olanoit/ol_new_apps/19.0/docs/planificador/ACEPTACION.md)
