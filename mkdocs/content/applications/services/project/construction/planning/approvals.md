---
modulos: [al_construction_planner_approvals, al_construction_planner_approvals_mrp, al_construction_planner, al_construction_material_request, al_construction_planner_purchase]
---

# Aprobaciones del plan y del requerimiento

Con el puente **Planificación de obra: aprobaciones**, el plan de recursos y el
requerimiento de obra se aprueban en la aplicación **Aprobaciones** de Odoo en
lugar de la validación por niveles. Cada envío busca su camino en la **tabla
de rutas**: qué documento es, qué cambió frente al plan y cuánto. La solicitud
queda enlazada al documento, con sus líneas, y su resultado vuelve a él:
aprobada lo libera y rechazada lo devuelve a borrador con el motivo.

## Configuración

1. Instale **Planificación de obra: aprobaciones**
   (`al_construction_planner_approvals`). Instala **Aprobaciones**.
2. En **Planificación de obra ‣ Configuración ‣ Ajustes ‣ Aprobaciones**, elija
   **Aplicación Aprobaciones** como **Motor de aprobación**. Es por compañía:
   lo que ya se envió con la validación por niveles termina con ese flujo.
3. Asigne el grupo **Planificación de obra: oficina técnica** a quienes aprueban
   cambios de material y de cantidad.
4. Revise la tabla en **Planificación de obra ‣ Configuración ‣ Aprobaciones y
   Gantt ‣ Rutas de aprobación**. Al instalar se crean tres filas de partida:

| Documento | Tipo de cambio | Desde | Aprobadores | Regla |
|---|---|---:|---|---|
| Plan de recursos | Todo el documento | 0 | Jefatura de proyectos | Basta uno |
| Requerimiento de obra | Cambio de material | 0 | Oficina técnica | Basta uno |
| Requerimiento de obra | Cambio de cantidad | 0 | Oficina técnica y jefatura de proyectos | Basta uno |

## Conceptos

| Concepto | Qué es |
|---|---|
| Tramo | Una fila de la tabla de rutas: documento, tipo de cambio, base y **Desde** |
| Base | **Porcentaje**: el exceso sobre lo presupuestado (la línea con más exceso; en el plan, lo que sube frente a la versión que reemplaza). **Monto**: el exceso en soles (en el plan, su total) |
| Desde | El tramo aplica cuando el exceso supera este valor; con 0 aplica siempre |
| Escalera | Un exceso que supera varios tramos pasa por todos, del menor al mayor: el siguiente tramo recibe la solicitud cuando el anterior aprobó |
| Cambio de material | Un material que no está en el plan para ese nivel y etapa |
| Cambio de cantidad | Más de lo que queda en el plan, o repetir lo ya pedido de un nivel y sub etapa |
| Aprobadores | Usuarios o grupos. Un grupo vale por sus usuarios internos activos de la compañía, sin quien envía |
| Regla | **Basta uno**: el tramo queda aprobado con la primera aprobación. **Todos**: aprueba cada usuario de la lista y una persona de cada grupo |
| Seguidores | El jefe de proyectos de la obra (casilla), usuarios y grupos, por ejemplo Logística: siguen la solicitud y el documento |
| Tipo de aprobación | El tipo de Aprobaciones de la solicitud; al instalar se crea **Aprobación de obra** por compañía |

!!! note "Nota"
    Odoo no repite un usuario en una solicitud. Si la misma persona está en dos
    tramos, aprueba una vez y cuenta en los dos.

## Enviar

### Requerimiento de obra

1. Arme el requerimiento como siempre (ver [Requerimientos de
   materiales](../material_requests.md)) y haga clic en **Solicitar
   aprobación**.
2. Sin cambios frente al plan, pasa a **Aprobado** y Logística lo procesa.
3. Con cambios, pasa a **En aprobación** y se crea la solicitud con una línea
   por cambio: material, nivel, presupuestado (saldo del plan), pedido,
   diferencia, diferencia en % y en soles, y tipo de cambio. Arriba del
   requerimiento aparece **Pendiente de aprobación** con el tramo y quién
   aprueba.
4. Un cambio sin ruta que aplique detiene el envío con el aviso «tiene cambios
   sin ruta de aprobación».

Con Aprobaciones, la política «Solo alerta» de materiales ya no deja pasar
estos cambios: el exceso va a su ruta y queda en **Excesos autorizados** al
aprobarse. La política **Bloquear** sigue bloqueando.

### Plan de recursos

**Solicitar aprobación** crea la solicitud con los tramos del plan que
apliquen por su total o por lo que sube frente a la versión vigente. Sin
tramos, el plan se aprueba directamente.

### Orden de fabricación

Con el puente **Planificación de obra: aprobaciones en fabricación**
(`al_construction_planner_approvals_mrp`, se instala solo), la orden que sale
del plan compara al confirmarse, por material, lo **presupuestado** en el
plan (sus ambientes, etapas de fabricación) con lo **requerido** en sus
componentes. La pestaña **Presupuestado frente a real** muestra la diferencia
en cantidad, en % y en soles, con el total; **Actualizar comparación** la
rehace si se cambian los componentes. Toda diferencia queda registrada; lo que
sale por debajo no pide aprobación.

Configure en **Ajustes ‣ Planificación de obra ‣ Aprobaciones ‣ Exceso en la
orden de fabricación**:

| Ajuste | Qué hace |
|---|---|
| Margen del jefe de producción (%) | Exceso que aprueba en la misma orden; con 0, todo va a Aprobaciones |
| Base del margen | **Costo total de la orden**: el exceso neto en soles sobre lo presupuestado de la orden. **Por material**: el material con más exceso |
| El margen cubre cambios de material | Sin la marca, un material que no está en el plan va siempre a Aprobaciones |

Asigne el grupo **Planificación de obra: jefe de producción** y agregue en la
tabla de rutas los tramos del documento **Orden de fabricación** (por ejemplo,
jefatura de proyectos desde 0 y Gerencia desde 15 %).

1. Con exceso, la orden muestra **Excede lo presupuestado** y no empieza: no
   registra producción, no marca consumos ni inicia órdenes de trabajo.
2. Dentro del margen, el jefe de producción ve **Aprobar exceso**: escribe el
   motivo y queda quién y cuándo, con cada exceso en **Excesos autorizados**.
3. Por encima del margen (o si no es el jefe de producción), **Solicitar
   aprobación** crea la solicitud en Aprobaciones con los tramos que apliquen.
   Al aprobarse, la orden puede empezar; si se rechaza, sigue pendiente con el
   motivo en su historial: corrija los componentes y actualice la comparación o
   vuelva a solicitar.

Con este puente, la autorización de la receta real (umbral del metrado) ya no
detiene la confirmación de la orden.

## Aprobar o rechazar

Desde el documento: quien tiene la aprobación pendiente del tramo actual ve
**Aprobar** y **Rechazar** en el requerimiento o el plan. **Rechazar** pide el
motivo; el documento vuelve a **Borrador** y el motivo queda en su historial.

Desde **Aprobaciones**: la solicitud tiene el botón **Documento** para abrir el
plan o el requerimiento; la actividad de aprobación llega a cada aprobador del
tramo actual. Los tramos siguientes quedan **En espera**.

Al aprobarse el último tramo, el requerimiento pasa a **Aprobado** (Logística
lo procesa) y el plan, a **Aprobado** con sus montos congelados.

!!! tip "Consejo"
    **Volver a borrador** en el documento cancela su solicitud abierta. Al
    enviarlo de nuevo se crea otra, con los cambios de ese momento.

## Ejemplo

Requerimiento de la cocina del Dpto 501 con 2 bisagras más que el saldo y una
silicona que no está en el plan, con estas filas para el requerimiento:

| Tramo | Tipo de cambio | Base | Desde | Aprobadores |
|---|---|---|---:|---|
| 1 | Cambio de cantidad | Porcentaje | 0 | Oficina técnica o jefatura (basta uno) |
| 2 | Cambio de cantidad | Porcentaje | 50 | Gerencia |
| 1 | Cambio de material | Porcentaje | 0 | Oficina técnica |

Las bisagras son un cambio de cantidad por debajo del 50 %: solo su tramo 1.
La silicona es un cambio de material: Oficina Técnica. La solicitud lleva los
dos tramos; Oficina Técnica está en ambos, así que con su aprobación el
requerimiento queda aprobado (la jefatura, sola, cubre solo el de cantidad).
Si las bisagras se triplican, entra el tramo de Gerencia, que aprueba al
final.

## Casos especiales

| Situación | Qué pasa |
|---|---|
| Documento enviado con la validación por niveles antes del cambio de motor | Termina con sus revisiones por niveles |
| Se cancela la solicitud en Aprobaciones | El documento vuelve a borrador |
| Un tramo sin aprobadores (grupo vacío o solo quien envía) | No se envía: corrija la ruta |
| Obra sin plan vigente | El requerimiento no tiene con qué compararse y va directo al almacén |

!!! info "Ver también"
    - [Requerimientos de materiales](../material_requests.md)
    - [Asignaciones y compras](supply.md)
    - [Línea base y versiones](baseline.md)
