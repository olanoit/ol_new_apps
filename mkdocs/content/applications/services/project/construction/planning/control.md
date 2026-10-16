---
modulos: [al_construction_planner, al_construction_planner_crew, al_construction_attendance]
---

# Control y personal propio

Cada línea del plan guarda su estado y sus montos de control: comprometido,
real, saldo y porcentaje ejecutado. Con ellos la Jefatura y Finanzas ven por
etapa y por tipo de recurso cómo va la obra contra su presupuesto. Esta página
explica también cómo se planifican y se costean las cuadrillas de personal
propio, cómo se controla una orden de compra con la analítica de la obra y
cómo se mueven las fechas del plan.

![Pestaña Control del plan con lo planificado, comprometido, real y saldo](control/plan-control.png)

## Configuración

- **Personal propio**: las actividades en horas llevan su **rol**
  (**Planificación ‣ Configuración ‣ Roles**) y los empleados su **costo hora**
  (**Empleados ‣ Ajustes de RR. HH.**). El capataz necesita el permiso de hoja de
  horas sobre otros empleados para registrar las de la cuadrilla. Para medir
  las cuadrillas en jornales, vea [Cuadrillas en
  jornales](#cuadrillas-en-jornales).
- **OC con analítica**: el control usa el presupuesto analítico del plan
  vigente. Las OC de servicio de las contratas no se controlan aquí: las
  controlan **Asignar contrata** y la liquidación.
- **Obra de la planilla de construcción civil**: póngale la cuenta analítica
  del proyecto. El planificador y la planilla no dependen uno del otro y se
  encuentran por esa cuenta.

## Conceptos

| Concepto | Qué incluye |
|---|---|
| Comprometido | Lo pedido que aún no es real: requerimientos y compras sin consumir, OC de servicio sin recibir y turnos sin horas registradas |
| Real | Lo consumido al costo del plan, lo recibido en la OC de servicio y las horas registradas por el costo hora del empleado |
| Saldo | Planificado − comprometido − real |
| % ejecutado | Real ÷ planificado |

Los montos se actualizan con cada documento del plan. Lo que cambia con el
tiempo (turnos que terminan) lo recoge una acción programada cada hora, o el
botón **Actualizar control**.

## Revisar el control

- La pestaña **Control** del plan muestra, en el orden del árbol de etapas,
  cada etapa padre con la suma de sus sub etapas y, en cada sub etapa, sus
  tipos de recurso, con lo planificado, comprometido, real, saldo y %
  ejecutado.
- **Informes ‣ Plan ‣ Control de saldo** y **Análisis de control** abren las mismas
  líneas en pivote y gráfico para agrupar por etapa padre, etapa, contrata,
  producto, actividad, nivel o estado.
- **Informes ‣ Plan ‣ Excesos autorizados** (o el botón **Excesos** del plan)
  lista cada exceso, pedido repetido, pago repetido, re-trabajo y porcentaje
  manual autorizado, con quién, cuándo, motivo, cantidad y documento (ver
  [Control de consumo](supply.md#control-de-consumo)).
- El re-trabajo de las contratas no suma al ejecutado de la línea ni a su
  saldo: queda separado en **Excesos autorizados**.

## Asignar una cuadrilla

1. Seleccione en el árbol, el plan o el [cronograma](schedule.md) y haga clic en
   **Asignar cuadrilla**.
2. Elija el rol, los obreros, la semana de inicio, el número de semanas y las
   horas por semana. El asistente crea los turnos de **Planificación** por obrero
   y semana, con la tarea y la línea del plan, y le da el rol al empleado si no
   lo tenía.
3. Los obreros registran sus horas en la hoja de horas de la tarea o de sus
   módulos. Las horas son lo ejecutado y, por el costo hora de cada empleado, lo
   real. El costo del personal propio va por hoja de horas, no por liquidación.

![Asistente Asignar cuadrilla con los obreros, las semanas y las horas](control/assign-crew.png)

Ejemplo: la cocina del Dpto 501 tiene planificado personal propio de 16 h a
S/ 12.00 (S/ 192.00). Se asignan dos obreros (costo hora S/ 9.50), dos semanas
desde el jueves 29/10/2026 y 4 h por semana cada uno: 4 turnos y 16 h. Un
obrero registra 6 h en un módulo de esa cocina:

| Concepto | Cálculo | Monto |
|---|---|---|
| Ejecutado | 6 h registradas | 6 h de 16 (37.5 %) |
| Real | 6 h × S/ 9.50 | 57.00 |
| Comprometido | (8 − 6) h del obrero 1 + 8 h del obrero 2 = 10 h × S/ 9.50 | 95.00 |
| Saldo | 192.00 − 95.00 − 57.00 | 40.00 |

El real va al costo hora del empleado, no al costo del plan: el saldo muestra si
la cuadrilla sale más cara o más barata que lo planificado.

## Cuadrillas en jornales

Las cuadrillas propias se pueden planificar y medir en **jornales** en lugar de
horas, con el costo de referencia del puesto o de la categoría de
construcción civil.

### Configuración

1. En **Ajustes ‣ Planificación de obra ‣ Jornales de las cuadrillas**, elija la
   **Unidad de las cuadrillas** (**Hora**, **Medio día** o **Día completo**),
   el **Redondeo de los jornales** (al más cercano, hacia arriba o hacia
   abajo) y las **Horas por jornal** (8 por defecto). El redondeo es el de los
   tipos de entrada de trabajo de la nómina de Odoo. Cada obra puede cambiar
   la unidad en **Proyecto ‣ Ajustes** (**Unidad de las cuadrillas**).
2. En cada rol de **Planificación ‣ Configuración ‣ Roles**, grupo **Cuadrilla
   de obra**, indique de dónde sale su costo:
    - **Categoría de construcción civil** (operario, oficial, peón): el costo
      es su jornal básico en la tabla vigente;
    - **Puesto (régimen general)**: el costo es el **Costo por jornal** del
      puesto (**Empleados ‣ Configuración ‣ Puestos de trabajo**, grupo **Cuadrilla de
      obra**);
    - sin ninguno, el **Costo por jornal** escrito en el rol.

    La **Categoría de construcción civil** del rol la agrega
    **Sedes, marcación y costo de personal de obra**.

El rol de la cuadrilla es el mismo registro que el tipo de turno del monitor
de asistencia de la nómina.

### Planificar y medir

1. En **Asignar cuadrilla**, elija **Planificar en: Jornales (días)** y los
   **Días por semana** de cada persona. El asistente muestra los **Jornales**
   de la cuadrilla y crea los turnos con las horas de esos jornales.
2. Al asignar, cada persona debe tener el puesto o la categoría de su rol; si
   no, el asistente lo dice y no crea los turnos.
3. Los jornales ejecutados salen de la marcación en la sede de la obra: las
   horas de cada día entre las horas por jornal, redondeadas en la unidad de
   la obra, al jornal de la categoría de la persona, al costo por jornal de su
   puesto o a su costo hora. Cada día va a la línea del plan del turno de la
   persona (su etapa y sub etapa). Una acción programada diaria los rehace;
   también se actualizan al registrar o corregir una marcación.

**Informes ‣ Plan ‣ Jornales de las cuadrillas** compara en pivote los
jornales y los soles planificados contra los ejecutados por obra, etapa padre
y etapa.

Ejemplo: una cuadrilla de un operario, un oficial y dos peones planificada 5
días en **Día completo** suma 20 jornales planificados.

## Controlar una OC con la analítica de la obra

Al confirmar una orden de compra de material con la cuenta analítica de la obra,
se suma su monto al comprometido de la combinación analítica (OC confirmadas sin
facturar más lo imputado). Si pasa el presupuesto de esa combinación más la
tolerancia, decide la política de materiales del plan (ver [Control de
consumo](supply.md#control-de-consumo)):

- **Avisar**: se confirma y queda **Excede el plan**;
- **Pedir aprobación**: la justificación es obligatoria y confirma la jefatura
  del planificador (**Exceso aprobado**);
- **Bloquear**: no se confirma.

## Cambiar fechas

1. Seleccione en el árbol, el plan o el cronograma y haga clic en **Cambiar
   fechas**.
2. Elija las etapas y desplace un número de días o fije una fecha.
3. Las fechas de necesidad de las líneas se recalculan. Con todas las etapas,
   también se mueven las tareas en el Gantt. Los requerimientos de obra y las
   compras con fecha anterior a la nueva necesidad reciben la actividad «Fechas
   del plan cambiadas» para Logística.

![Asistente Cambiar fechas con las etapas y los días](control/change-dates.png)

Ejemplo: postergar 14 días solo la instalación del piso 05 desplaza 14 días la
fecha de necesidad de sus líneas sin mover las tareas, y el requerimiento de
obra del piso recibe la actividad para Logística.

## Casos especiales

| Situación | Qué pasa | Qué hacer |
|---|---|---|
| Comprometido y real en cero | Se llenan con las asignaciones y las horas | Generar los documentos desde el plan; **Actualizar control** |
| «Pasa el presupuesto analítico … bloquear» | La OC lleva la combinación sobre su presupuesto | Reducir la OC, cambiar la política o replanificar |
| «El exceso lo aprueba la jefatura de proyectos» | Política «pedir aprobación» en una OC | Que la jefatura de proyectos confirme el aviso |
| «Combinación fuera del presupuesto» | La OC usa una combinación sin línea en el presupuesto | Usar la combinación del plan o replanificar |
| «La selección no tiene líneas de personal propio del rol» | No hay líneas de personal propio o tienen otro rol | Revisar la selección y el rol |
| Las horas no suben el ejecutado | El empleado no tiene el rol o registró en otra tarea | Asignar la cuadrilla; registrar en la tarea del nivel o sus módulos |
| «Las fechas no cambian» | Cero días o la fecha nueva es la actual | Indicar los días o la fecha |

!!! info "Ver también"
    - [Línea base y versiones](baseline.md)
    - [Cronograma con recursos](schedule.md)
    - [Construcción civil en la planilla](../../../../hr/payroll/peru/construction.md)
