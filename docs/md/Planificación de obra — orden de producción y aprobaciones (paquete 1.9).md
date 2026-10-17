# Planificación de obra — orden de producción y aprobaciones (paquete 1.9)

Oct 17, 2026 · @Vicente

## Objetivo y alcance

Que la orden de fabricación del mueble lleve las cantidades reales que salen del sistema matriz, que el jefe de producción vea ahí el exceso frente a lo presupuestado y lo apruebe o lo derive según márgenes configurables, que los accesorios de armado y los materiales de instalación se pidan sobre lo proyectado con sus cambios aprobados, y que todas esas aprobaciones pasen por la aplicación Aprobaciones de Odoo.

Este paquete recoge las decisiones de Vicente del 17-oct-2026. Usa códigos M19 para no chocar con los M17 y M18 de los paquetes 1.7 y 1.8. Cada requerimiento termina con una línea «Efecto en Manufactura», porque lo que se decida aquí tiene que servir después para configurar estaciones de trabajo, maquinaria, rendimientos y el costeo de piezas sin rehacerlo.

Plazo y estimación: a definir con Cristóbal. No forma parte de la salida a producción del lunes 19-oct.

## Qué reemplaza de los paquetes anteriores

| Código anterior | Qué decía | Qué pasa ahora |
| --- | --- | --- |
| Metrado previo y su responsable (M17-20, paquete 1.7 parte 2) | La orden no se confirma sin metrado aprobado; el supervisor carga el metrado | Reemplazado por Ambiente medido (M19-06): el supervisor solo marca medido con fecha y archivo, sin cantidades ni aprobación |
| Cantidades reales y documento del sistema matriz (M17-21, 1.7 parte 2) | El supervisor u Optimización escribe a mano planchas, metros de canto y piezas | Reemplazado por la carga del despiece y la optimización (M19-01), que hace la asistente de optimización con importador |
| Receta pieza por pieza (M17-26, 1.7 parte 2) | Fuera de paquete, con el CSV del «Manual Flujo V2» | Entra en M19-01, pero con el formato real que exporta hoy el sistema matriz |
| Presupuestado frente a real (M17-22, 1.7 parte 2) | Comparación por material en la orden | Absorbido por M19-05, que la lleva también al planificador |
| Margen y aprobación (M17-23, 1.7 parte 2) | Margen único y aprobación con validación por niveles | Reemplazado por M19-04 y M19-07: márgenes por rol y tramo, aprobación en Aprobaciones |
| Materiales cerrados y cambio aprobado (M17-24, 1.7 parte 2) | Cambio de material aprobado por el jefe de proyectos | Reemplazado por M19-02 y M19-03: el cambio de material lo aprueba Oficina Técnica |
| Metrado como receta real (M17-15, paquete 1.8) | El supervisor carga la receta real del mueble | Se mantiene la receta real ligada al mueble, pero la carga Optimización con M19-01 |
| Versus y autorización en producción (M17-20, paquete 1.8) | Umbral único (10 % por defecto) sobre el costo del mueble y autorización de la jefatura de proyectos | Reemplazado por M19-04: margen del jefe de producción y tramos superiores configurables |
| Validación por niveles en plan, metrado, requerimiento y orden | Decisión del 14-oct-2026 | Se revierte: todo pasa a Aprobaciones (M19-07) |

Siguen vigentes sin cambio: Requerimiento de producción al jefe de producción (M17-18), Agrupación de la orden (M17-19), Usabilidad del flujo (M17-25) y Pedido al almacén en planchas enteras (M17-27), todos del paquete 1.7 parte 2; el Importador de la proyección de materiales (M17-18) y la Validación de códigos de producto (M17-19) del paquete 1.8; y la Selección de nivel y etapa del requerimiento de obra (RQ-01 a RQ-08), ya publicada en la 19.0.20.

Ojo con los códigos: M17-18, M17-19 y M17-20 significan cosas distintas en el paquete 1.7 parte 2 y en el 1.8. En este documento siempre van con el nombre y el paquete.

Configuración aplicada el 16-oct-2026 en `newallcenter_dev_1` y `newallcenter_dev_2` que se mantiene hasta que M19-07 esté publicado: política de exceso de materiales en «Solo alerta» y nivel de validación «Exceso sobre el plan» desactivado. La vía temporal del jefe de producción por el requerimiento de obra (RQ-07) también se mantiene hasta que el flujo de la orden de fabricación esté listo.

## Flujo y responsables

| Paso | Quién | Dónde |
| --- | --- | --- |
| 1. Presupuesto y proyección de materiales | Oficina Técnica | Hoja de cálculo de Odoo y planificador (M18-22) |
| 2. Medición del ambiente | Supervisor de proyectos | Planificador: marca el ambiente como medido (M19-06) |
| 3. Diseño | Supervisor de proyectos | SketchUp, fuera de Odoo |
| 4. Despiece y optimización | Asistente de optimización | Sistema matriz, con Lepton o la seccionadora CNC, fuera de Odoo |
| 5. Carga a la orden de fabricación | Asistente de optimización | Importador de la orden (M19-01) |
| 6. Revisión y aprobación del exceso | Jefe de producción; por encima de su margen, jefatura de Proyectos, Oficina Técnica o quien designe Gerencia | Orden de fabricación y Aprobaciones (M19-04, M19-07) |
| 7. Pedido de accesorios de armado | Jefe de producción o quien él asigne | Orden de fabricación (M19-02) |
| 8. Fabricación | Planta | Orden de fabricación |
| 9. Pedido de materiales e insumos de instalación | Jefe de producción, supervisores o quien indique el jefe de proyectos | Requerimiento de obra (M19-03) |
| 10. Presupuestado frente a real | Todos los anteriores, según permisos | Orden de fabricación y planificador (M19-05) |

Supervisores y Proyectos no piden accesorios de armado.

## Requerimientos

### Carga del despiece y la optimización a la orden de fabricación (M19-01)

Fuente: correo de Yelitza León (optimizacion@allcenter.pe) del 16-oct-2026, 18:37, con los dos archivos de la OP 32019, Montecarmelo cocina piso 3.

Dato leído en esos archivos:

- Listado de despiece (.XLS): bloques por departamento y módulo, con cabecera del tipo «DPTO-0301:MA01(VISTOIZQ):1 (8 items)». Por pieza trae cantidad, largo y ancho en mm, descripción (1.PRNT, 3.SUPLE, 4.FONDO, 5.TECH, 6.R/M, 7.PUERTA…), código de color y espesor (BL18, GB18, SA18, BL3), tapacanto por lado (L1, L2, A1, A2, delgado o grueso), ranura (espesor, distancia, profundidad, lado) y perforaciones.
- Orden de producción en PDF (formato ALL-PR-F-01): 530 piezas y 44 módulos en tres departamentos (DPTO-0301 con 15, DPTO-0302 con 14, DPTO-0303 con 15); planchas por material con su número de piezas (por ejemplo, melamina Blanco RH Pelikano 7.2 planchas y 209 piezas; aglomerado 2500 × 1830, 1 plancha y 87 piezas); tapacanto en metros por código (BR18 542 m, SA18 105 m, PA18 86 m, GB18 de 1 mm 50 m, PA18 de 3 mm 82 m); y una página de piezas sin armar.
- Ninguno de los dos trae accesorios ni consumibles.

Requerimiento:

- La carga la hace la asistente de optimización. Proponemos un grupo «Optimización» con permiso para cargar en órdenes en borrador, sin ver montos (M18-10).
- Se extiende el importador «Importar despiece CNC» del costeador de piezas (`allcenter_mrp_costeo_pieza`) en lugar de crear otro. Hoy ese importador espera un XLSX plano (obra, mueble_terminado, modulo, id_pieza, material, largo_mm, ancho_mm, area_m2, tapacanto_codigo, tapacanto_ml, cantidad, según la especificación v1.4 del 20-set); el sistema matriz exporta bloques agrupados, así que tiene que leer ese formato tal como sale.
- Los tableros de la orden se toman de las planchas que da la optimización (PDF), no de la suma de áreas de las piezas. La diferencia entre las dos es merma y retazo, y sigue la especificación de merma y retazo. Si leer el PDF de forma automática no es viable, la asistente escribe el resumen de planchas y metros de canto en una tabla de la orden y adjunta el PDF.
- Tabla de equivalencias entre el código del sistema matriz y el producto del maestro de Odoo (BL18, GB18, SA18, BL3, PA18, BR18 y los que aparezcan), mantenida por Oficina Técnica. Un código sin equivalencia detiene la carga y lista la fila, igual que la Validación de códigos de producto (M17-19, paquete 1.8).
- Cada bloque se asigna al departamento y módulo del plan (DPTO-0301 con Dpto 301; MA01 con el módulo de la tipología). Lo que no casa se marca en la vista previa.
- Se guardan por pieza el canto por lado, las ranuras y las perforaciones, aunque hoy no se consuman.
- Se registra con qué se optimizó: Lepton (corte manual) o seccionadora CNC.
- Vista previa sin escribir, con advertencias. Cargar de nuevo reemplaza la carga anterior y deja el historial de versiones en la orden; los dos archivos quedan adjuntos.
- La orden sigue la Agrupación de la orden (M17-19, paquete 1.7 parte 2): la OP 32019 corresponde a una orden de obra + partida + piso.
- Al terminar la carga se crea la actividad «Pedir accesorios de armado» para el jefe de producción, con Logística y Proyectos como seguidores (M19-02).

Criterio de aceptación: cargar los dos archivos de la OP 32019 en una orden de Montecarmelo cocina piso 3 deja 44 módulos y 530 piezas, componentes de tablero iguales a las planchas del PDF y tapacanto en metros igual al PDF, por material.

Efecto en Manufactura: las filas de pieza son la entrada de la ruta corte, canteado, ranurado y perforado. El canto por lado da el trabajo de la canteadora y las ranuras y perforaciones dan las operaciones de ranuradora y perforadora, así que los rendimientos por estación se podrán calcular sobre estos datos. El registro de Lepton o seccionadora permite elegir la ruta de corte. Sigue abierta en Manufactura la identidad de la pieza (producto por pieza con referencia obra-id_pieza, como hace el costeador, o lote o serie del material genérico); por eso la carga guarda las piezas como tabla ligada a la orden y la comparación de este paquete se hace por material, departamento y módulo, que funciona con cualquiera de las dos opciones. Es coherente con el producto por módulo decidido el 16-oct (M18-15).

### Accesorios de armado (M19-02)

- Los pide el jefe de producción o quien él asigne, desde la orden de fabricación, con el botón «Pedir accesorios».
- La pantalla propone los accesorios de lo proyectado o presupuestado para los módulos de la orden (sub etapa 1.2 Armado), con su saldo por pedir.
- Si cambia el material o la cantidad frente a lo proyectado, la solicitud va a Oficina Técnica por Aprobaciones (M19-07), con el jefe de proyectos como seguidor para su trazabilidad. Sin cambios, va directo al almacén.
- Lo pedido se agrega como componente de la orden y sale del almacén con la preparación de componentes hacia la preproducción de la planta. Es nuestra propuesta.
- La orden puede confirmarse sin haber pedido accesorios. En ese caso el sistema avisa al jefe de proyectos y a Logística.

Criterio de aceptación: una orden cargada con M19-01 propone los accesorios de Armado de sus módulos; pedirlos tal cual llega al almacén sin aprobación; cambiar una bisagra por otra crea la solicitud a Oficina Técnica; confirmar la orden sin pedir accesorios deja el aviso al jefe de proyectos y a Logística.

Efecto en Manufactura: al quedar como componentes ligados a la operación de Armado, el consumo se podrá registrar por orden de trabajo cuando se configure la estación de armado, y el costo de accesorios entra al costo del módulo.

### Materiales e insumos de instalación (M19-03)

Se apoya en el requerimiento de obra con selección de nivel y etapa (RQ-01 a RQ-08).

- Los piden el jefe de producción, los supervisores o quien indique el jefe de proyectos (grupo «Solicitante»).
- Se pide sobre lo proyectado o presupuestado con «Traer materiales del plan» en las sub etapas de Instalación.
- Cambio de material, o material que no está en el plan: lo aprueba Oficina Técnica.
- Cambio de cantidad frente al saldo: lo aprueba Oficina Técnica o la jefatura de Proyectos; basta uno de los dos.
- Los aprobadores se pueden cambiar en la tabla de rutas (M19-07), para el caso en que Gerencia designe a otra persona.
- Sin cambios, el requerimiento va directo al almacén, como se decidió el 16-oct.
- Cuando esto esté publicado, la política «Solo alerta» de materiales deja de aplicar a estos cambios.

Criterio de aceptación: un requerimiento traído del plan sin cambios pasa al almacén; uno con más cantidad que el saldo crea una solicitud que puede aprobar Oficina Técnica o la jefatura de Proyectos; uno con un material fuera del plan solo lo puede aprobar Oficina Técnica.

Efecto en Manufactura: ninguno directo, porque la instalación no pasa por orden de fabricación. Comparte con la orden la tabla de rutas de aprobación (M19-07).

### Exceso en la orden de fabricación y aprobación del jefe de producción (M19-04)

- La orden muestra, por material, presupuestado, real cargado (M19-01 y M19-02), diferencia en cantidad, en % y en soles, y el total de la orden.
- Si el exceso está dentro del margen que el jefe de producción puede aprobar, ve el botón «Aprobar exceso» en la misma orden; queda registrado quién, cuándo y el motivo.
- Si supera ese margen, el botón es «Solicitar aprobación» y crea la solicitud en Aprobaciones dirigida a la jefatura de Proyectos, a Oficina Técnica o a quien designe Gerencia, según la tabla de rutas.
- Mientras haya un exceso pendiente de aprobación, la orden no pasa a «En progreso». Es nuestra propuesta; ver decisiones abiertas.
- Toda diferencia queda registrada aunque no haya necesitado aprobación. Lo que sale por debajo de lo presupuestado se registra sin aprobación.
- Configurable en Ajustes y en la tabla de rutas:
  - porcentaje que puede aprobar cada rol;
  - tramos sucesivos con su aprobador (los porcentajes los define Allcenter; no hay cifras en este documento);
  - base del porcentaje: costo total de la orden en soles, como se decidió el 16-oct para M17-20 del paquete 1.8, o por material;
  - reglas distintas para cambio de material y para cambio de cantidad.

Criterio de aceptación: con un primer tramo configurado para el jefe de producción, una orden cuyo exceso cae dentro del tramo muestra «Aprobar exceso» y, al aprobarla, puede iniciar; una que lo supera crea la solicitud al aprobador del tramo siguiente y no inicia hasta que se apruebe.

Efecto en Manufactura: el estado del exceso vive en la orden (el campo `construction_exceed_state` ya existe en `mrp.production`), así que cuando haya órdenes de trabajo el bloqueo se aplica al inicio de la primera operación. El exceso de tableros incluye merma; cuando el costeo de piezas esté en marcha, ese exceso se podrá separar en pieza, merma y retazo.

### Presupuestado frente a real en la orden y en el planificador (M19-05)

- En la orden: pestaña con presupuestado, requerido (lo cargado del sistema matriz más los accesorios pedidos) y consumido (al cerrar la orden), por material, en cantidad y en soles. Las tres columnas son nuestra propuesta.
- En el planificador: los mismos datos sumados de módulo a mueble, ambiente, piso y obra, y por etapa.
- Los montos solo los ven las personas autorizadas (M18-10).

Criterio de aceptación: la orden de la OP 32019 y el piso 3 de Montecarmelo en el planificador muestran el mismo presupuestado y el mismo requerido por material.

Efecto en Manufactura: la columna consumido sale del consumo de componentes de la orden; con estaciones y rendimientos se sumará el costo de operación, y con el costeo de piezas el costo por pieza.

### Ambiente medido (M19-06)

- El supervisor marca el ambiente como medido con fecha de medición y un archivo adjunto (plano, foto o exportación de SketchUp). No escribe cantidades y no hay aprobación.
- La asistente de optimización ve la lista de ambientes medidos pendientes de cargar a una orden.
- Al cargar una orden con ambientes sin marcar como medidos, el sistema avisa. Es nuestra propuesta.
- En la vertical de mobiliario reemplaza al «Metrado del nivel» con cantidad medida y su validación. En construcción por partidas se mantiene el metrado por driver; ver decisiones abiertas.

Criterio de aceptación: el supervisor marca Cocina de Dpto 301 como medido con fecha y archivo; el ambiente aparece en la lista de pendientes de Optimización y desaparece al cargar su orden.

Efecto en Manufactura: la fecha de medición es el punto de partida del plazo de planta (de medición a orden cargada, de orden a producido), que servirá para planificar capacidad cuando estén configuradas las estaciones.

### Aprobaciones en la aplicación Aprobaciones (M19-07)

Decisión del 17-oct-2026: todas las aprobaciones del planificador, del requerimiento de obra y de la orden de fabricación van a la aplicación Aprobaciones de Odoo. Se deja la validación por niveles.

Cubre: aprobación del plan de recursos, cambios de material y de cantidad del requerimiento de obra (M19-03), cambios de accesorios (M19-02) y exceso de la orden por encima del margen del jefe de producción (M19-04). La aprobación del metrado desaparece con M19-06.

Lo que trae lo nativo, leído en `newallcenter_dev_1` el 17-oct-2026: tipos de aprobación con aprobadores como usuarios, mínimo de aprobaciones y orden de aprobadores, campos opcionales de monto, producto y cantidad, y solicitudes con líneas de producto. No enlaza la solicitud con el documento que la origina, no tiene condiciones por monto o porcentaje y no acepta grupos como aprobadores. Ya hay un antecedente en la base: el tipo «Aprobación de orden de venta» con una automatización.

Mejoras necesarias para que cumpla:

1. Documento de origen en la solicitud (plan, requerimiento u orden) y botón inteligente en los dos sentidos.
2. Creación automática de la solicitud desde el documento, con sus líneas: material, presupuestado, pedido, diferencia, %, monto en soles y tipo de cambio (material o cantidad).
3. Tabla de rutas configurable: tipo de documento, tipo de cambio y tramo de porcentaje o monto, con el tipo de aprobación y los aprobadores de cada fila.
4. Aprobadores por grupo o puesto (jefatura de Proyectos, Oficina Técnica, Gerencia), además de usuarios, con la opción «basta uno» o «todos».
5. Aprobar o rechazar también desde el documento de origen.
6. El resultado vuelve al documento: aprobar libera (el requerimiento pasa al almacén, la orden puede iniciar) y rechazar lo devuelve a borrador con el motivo.
7. Seguidores y avisos según la ruta, por ejemplo jefe de proyectos y Logística.

Migración: los niveles de validación de plan, metrado, requerimiento y orden quedan desactivados al publicar. Las revisiones que estén pendientes en ese momento terminan con el flujo anterior. Es nuestra propuesta.

Criterio de aceptación: un requerimiento de obra con un material fuera del plan crea una solicitud en Aprobaciones con el requerimiento enlazado y sus líneas; Oficina Técnica la aprueba desde el requerimiento y este pasa al almacén.

Efecto en Manufactura: la misma tabla de rutas servirá para futuras aprobaciones de fabricación (re-trabajo, merma por encima del estándar) sin desarrollo nuevo.

## Decisiones tomadas

Por Vicente el 17-oct-2026:

- El supervisor diseña en SketchUp y la asistente de optimización opera el sistema matriz, ejecuta las optimizaciones y carga a la orden.
- El supervisor solo marca el ambiente como medido, con fecha y archivo.
- La comparación presupuestado frente a real va en la orden y en el planificador.
- Los accesorios de armado los pide el jefe de producción o quien él asigne, según lo planificado; supervisores y Proyectos no los piden. Los cambios los aprueba Oficina Técnica, con trazabilidad al jefe de proyectos.
- La orden se puede confirmar sin accesorios pedidos, con aviso al jefe de proyectos y a Logística. El aviso de accesorios pendientes va al jefe de producción con trazabilidad a Logística y Proyectos.
- Los materiales e insumos de instalación los piden el jefe de producción, los supervisores o quien indique el jefe de proyectos, sobre lo proyectado o presupuestado. El cambio de material lo aprueba Oficina Técnica; el de cantidad, Oficina Técnica o la jefatura de Proyectos.
- El jefe de producción aprueba en la orden el exceso dentro de su porcentaje; por encima, la orden le facilita pedir la aprobación a la jefatura de Proyectos, a Oficina Técnica o a quien designe Gerencia. Debe ser muy configurable.
- El margen lo define Allcenter.
- Todas las aprobaciones van a la aplicación Aprobaciones; lo que lo nativo no cubra se resuelve con mejoras sobre esa aplicación.

## Decisiones abiertas

- [ ] Porcentajes y tramos de aprobación: los define Allcenter.
- [ ] Tabla de equivalencias de los códigos del sistema matriz con el maestro de productos de Odoo: Oficina Técnica y Optimización.
- [ ] Base del porcentaje: costo total de la orden en soles (decisión del 16-oct) o por material. Proponemos mantener la del 16-oct como valor por defecto.
- [ ] Si el margen del jefe de producción también cubre el exceso de cantidad de accesorios o si esos cambios van siempre a Oficina Técnica.
- [ ] Qué bloquea un exceso pendiente: el inicio de la orden (nuestra propuesta) o su confirmación.
- [ ] Metrado en construcción por partidas: se mantiene el metrado por driver o también pasa a «medido».
- [ ] Lectura del PDF de optimización: automática o resumen escrito por la asistente con el PDF adjunto.
- [ ] Plazo y estimación: Cristóbal.
- [ ] Guía de remisión del despacho a obra (hallazgo H-32 del caso de prueba): fuera de este paquete; se revisa con Ximena.

## Fuentes

- Correo de Yelitza León (optimizacion@allcenter.pe) del 16-oct-2026, 18:37: listado de despiece (.XLS) y orden de producción (PDF, ALL-PR-F-01) de la OP 32019, Montecarmelo cocina piso 3.
- Base `newallcenter_dev_1`, [newallcenter-dev1.altalatam.com](https://newallcenter-dev1.altalatam.com), leída el 16 y el 17-oct-2026: Requerimiento de materiales de obra 19.0.20.20261016, Planificación de obra 19.0.42.20261016, puente de fabricación 19.0.3, aplicación Aprobaciones y tipo «Aprobación de orden de venta».
- Paquetes anteriores: «Planificación de obra — orden de producción (paquete 1.7 parte 2)» del 15-oct, «Planificación de obra — requerimiento de configurabilidad (paquete 1.8)» del 16-oct y «Requerimiento de obra — selección de nivel y etapa» del 16-oct.
- Especificación del costeo de piezas CNC v1.4 (20-set-2026), flujo de manufactura (23-set-2026) y especificación de merma y retazo, en el proyecto Allcenter.
- Decisiones de Vicente del 16 y 17-oct-2026.
- Las cifras de la OP 32019 son dato leído. Las marcadas «nuestra propuesta» no están decididas.
