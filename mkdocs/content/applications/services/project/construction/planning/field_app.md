---
modulos: [al_construction_portal, al_construction_portal_sale]
---

# Aplicación de obra en el celular

La aplicación de obra lleva el trabajo de campo al celular y a la tablet: el
capataz, la contrata y la oficina técnica registran avances, partes diarios,
asistencia, pedidos, recepciones y devoluciones **aunque la obra no tenga
señal**. Lo registrado se guarda en el equipo y se envía solo cuando vuelve la
conexión.

Se instala como aplicación desde el navegador (Android e iOS) en
`https://<su-odoo>/obra/app/`. No necesita la tienda de aplicaciones.

## Quién entra y cómo

Cada obra tiene la pestaña **Portal de obra** con las personas que pueden
usar la aplicación:

| Rol | Para quién | Qué ve |
|---|---|---|
| Capataz o maestro de obra | Personal propio en la obra | Avance de todas las partidas, parte diario, cuadrilla y tareo, requerimientos, recepción y devolución. |
| Contrata | Usuario de portal de la empresa de la contrata | Solo las partidas asignadas a su empresa y sus valorizaciones con el neto a su cuenta. |
| Oficina técnica | Asistente de la oficina técnica | Lo mismo que el capataz salvo el tareo de la cuadrilla. |
| Residente de obra | El residente, aunque sea un locador sin ficha de empleado | Todo lo del capataz y de la oficina técnica, más **Mi día** y las bandejas **Por validar** y **Por aprobar**. Solo con usuario y clave. |

Hay dos formas de ingresar, que se activan por obra:

- **Usuario y clave** de Odoo. La sesión dura los días de **Ajustes ‣
  Planificación de obra ‣ Portal de obra ‣ Sesión del portal** (90 por
  defecto).
- **QR de la obra y PIN**. El QR se imprime en el cartel de la obra; la
  persona lo escanea, elige su nombre y escribe su PIN de 4 dígitos. Tres PIN
  errados bloquean a la persona hasta que la oficina la desbloquee. **Nuevo
  código del QR** invalida el cartel anterior.

!!! important "El residente entra con usuario y clave"
    Quien entra con el QR y el PIN no tiene el rol Residente, aunque lo tenga
    en la obra: ve lo del capataz y la oficina técnica, pero no las bandejas.
    El residente valida y aprueba, y eso pide su usuario y clave.

!!! note "El PIN"
    El PIN lo asigna la oficina con el botón **PIN** de la persona. Odoo solo
    guarda su huella: nadie puede leerlo después.

## Pantallas

| Pantalla | Qué hace |
|---|---|
| Inicio | Elige la obra; muestra las partidas por validar, lo pendiente de enviar y las entregas por recibir. |
| Avance | Lista de partidas con lo planificado, lo validado y el saldo; buscador y filtros. |
| Registrar avance | Cantidad o porcentaje acumulado, **al menos una foto**, la ubicación del celular y, si es re-trabajo, su motivo. Entra **Por validar** con origen Portal. |
| Parte diario | Clima, personal propio y de contratas, restricciones (material, frente, clima), ocurrencias, fotos y la firma. Uno por persona, obra y día: lo envían el capataz, la contrata y la oficina técnica. |
| Cuadrilla y tareo | Asistencia de la cuadrilla con su hora de entrada y las horas de cada persona por partida. |
| Requerimientos | Tres catálogos: materiales de la partida (con su saldo), EPP y útiles de oficina, con kits armados. |
| Pedido | Revisa el carrito, la fecha requerida y la prioridad; crea el requerimiento de obra. |
| Recepción | Confirma lo recibido de cada entrega con la foto de la guía firmada; lo que falta queda como entrega pendiente. |
| Devolución | Devuelve al almacén lo que sobra (andamios, herramientas, material) o lo da de baja como merma. |
| Valorizaciones | La contrata ve sus valorizaciones, su detalle con deductivos, fondo de garantía y detracción, y el pago de la factura. |
| Por enviar | Cola de lo registrado sin señal; se envía sola al volver la conexión o con **Reintentar el envío ahora**. |

## El residente en la aplicación

El residente trabaja en la aplicación sin usuario interno. Su barra inferior
es **Inicio**, **Bandejas** (con el total pendiente), **Obra** y **Por
enviar**.

### Mi día

El inicio del residente muestra arriba cuántos avances hay **por validar**,
cuántos requerimientos **por aprobar** y cuántos partes del día **por
revisar**. Debajo, la agenda de hoy por urgencia:

1. pedidos urgentes que esperan su aprobación;
2. cortes de valorización de las contratas en los próximos 7 días, con sus
   avances por validar;
3. entregas por recibir hoy;
4. partidas que empiezan hoy según el cronograma.

Cada fila abre la pantalla donde se atiende.

### Por validar

Los avances **Reportados** de la obra, de capataces y contratas. Tres órdenes:
**Por corte** (primero los de la contrata cuyo corte de valorización está más
cerca), **Por partida** y **Con aviso**.

Cada avance muestra quién lo reportó, la cantidad, las fotos (se amplían al
tocarlas), la última foto validada de la partida y la distancia a la obra. Los
avisos son:

- supera el saldo del plan;
- espera la aprobación de la jefatura por exceso (no se puede validar hasta
  que la jefatura lo apruebe en el escritorio);
- foto sin ubicación GPS o tomada fuera del radio de la obra;
- fecha en una semana cuya valorización ya se presentó.

Acciones:

- **Validar**. Se puede corregir la cantidad **a la baja** con **−** y **+**;
  entonces se elige el motivo de la corrección.
- **Rechazar**, con un motivo de la lista y un comentario opcional.
- **Re-trabajo**, con su motivo. Se valida con 0 a liquidar, la misma regla
  del escritorio.
- **Validar seleccionados**: los avances **sin aviso** tienen casilla y se
  validan juntos. Los que tienen aviso van de uno en uno.

Quien reportó el avance recibe el aviso en su portal. En Odoo, el avance
queda con el residente como **Validado por**.

### Por aprobar

Los requerimientos **En aprobación** de la obra en los que el residente es
revisor del nivel actual. Por línea se ve lo pedido, el saldo del plan y el
exceso; **Lo pedido** y **El saldo** fijan la cantidad de un toque, y **−** y
**+** dan otra menor. **Aprobar** y **Rechazar** quedan fijos abajo.

Si la regla tiene otro nivel después del residente (por ejemplo, la
jefatura por encima de un monto), el requerimiento sigue a ese nivel. Con la
aplicación Aprobaciones, rechazar devuelve el requerimiento a borrador con el
motivo, igual que en el escritorio.

En la tablet, las dos bandejas muestran la lista a la izquierda y el detalle
a la derecha.

### Partes del día y «Cerrar el día»

El contador **partes por revisar** de Mi día abre los partes que el capataz,
la contrata y la oficina técnica enviaron hoy, con la hora, y la lista de
quienes aún no enviaron su parte. En la tablet, el parte elegido se ve al
lado.

Debajo está el **parte diario de obra**: cuántos partes llegaron, cuántos
faltan, los avances validados y por validar del día y la asistencia propia.
El residente escribe su comentario y toca **Cerrar el día y enviar al
cliente**. Odoo:

1. arma el parte diario de obra con el personal de todos los partes, los
   avances validados del día, las restricciones, las ocurrencias, las fotos
   y el comentario;
2. lo envía en PDF al **Contacto del cliente en obra** de la obra. Si la obra
   no tiene contacto, el PDF queda en el historial de la obra;
3. deja los partes del día en **Revisado por el residente**. Un parte
   revisado ya no se cambia desde el portal.

### Registrar a un toque

Mi día tiene accesos directos para lo que registra el residente:

| Acceso | Qué crea en Odoo |
|---|---|
| **Cambio del cliente** | Un cambio de obra en **Borrador**, pedido por el cliente: descripción (con el dictado del teclado), adicional o deductivo, partidas afectadas o partida nueva, metrado estimado, fotos, nombre y cargo de quien lo pidió y **su firma con el dedo**. Al llegar a Odoo, el contacto del cliente recibe la constancia en PDF. No lleva montos: lo valoriza y lo aprueba el coordinador en el escritorio. Necesita el módulo `al_construction_portal_sale`, que se instala solo con el puente de Ventas del planificador. |
| **Deductivo** | Un deductivo de la contrata en **Pendiente**, con foto obligatoria: la orden, la partida, el motivo, y el monto o la cantidad (al precio de la partida en la orden). La contrata lo ve en su pantalla Valorizaciones y entra en su siguiente valorización. |
| **Pedir cuadrilla o contrata** | Una actividad en cada partida pedida, para el jefe de la obra, con la fecha en que se necesita y las personas por rol (cuadrilla) o el metrado (contrata). La asignación sigue en el escritorio. En **Mis solicitudes** el residente ve cada una como **Pedida**, **Asignada** (la partida ya tiene contrata en el plan o cuadrilla en esa fecha) o **Cancelada** (la actividad se cerró sin asignar). |

Todos entran a **Por enviar** si no hay señal.

### La obra: Resumen, Semana, Tareas y Gantt

La pestaña **Obra** de la barra inferior muestra cómo va la obra, sin poder
cambiar nada. Sin señal, muestra los datos de la última sincronización, con
la hora en el encabezado.

| Vista | Qué muestra |
|---|---|
| **Resumen** | El avance físico real validado (el mismo número del tablero de obra del escritorio) frente al **programado a hoy**; las partidas atrasadas, los avances por validar, los pedidos abiertos y el personal de hoy (asistencia propia y personal de contrata de los partes). La **curva de avance** por semanas (programado y real, con su tabla) y el **avance por especialidad**. Los montos del plan solo aparecen si **Ajustes ‣ Portal de obra ‣ Montos en la pestaña Obra** está activo. |
| **Semana** | Las partidas que inician y las que terminan en la semana de la obra, y las que inician la semana siguiente. Avisa de las que inician sin contrata ni cuadrilla y de las que terminan con menos avance que **Ajustes ‣ Portal de obra ‣ Partida en riesgo** (70 % por defecto). |
| **Tareas** | Las partidas en cuatro columnas: **Por iniciar**, **En curso**, **Por terminar esta semana** y **Terminadas**, con filtros **Personal propio**, **Por contrata** y **Atrasadas**. La columna la calcula Odoo con las fechas del plan y el avance validado: no se arrastra. Tocar una partida abre el registro de su avance. |
| **Gantt** | Una barra por partida con el avance validado como relleno, las atrasadas en rojo, los hitos de la obra y la línea de hoy. Zoom de **semana** y de **mes**; abre con hoy a la vista. |

!!! note "De dónde salen las fechas"
    Las fechas de cada partida son las de las etapas de su ambiente en el
    plan vigente, las mismas del Cronograma del planificador; sin etapas, la
    fecha de necesidad de la línea. El **programado a una fecha** reparte el
    monto de cada línea del plan entre los días hábiles de la obra (los días
    con horario en el calendario de la compañía, sin feriados) de su etapa.

### Validar y aprobar sin señal

Validar, rechazar y aprobar también entran a **Por enviar**. Cada decisión
guarda lo que vio el residente: el avance reportado con su cantidad, o el
nivel de aprobación del requerimiento. Al recibirla, Odoo la vuelve a
comprobar. Si el registro cambió (ya validado, rechazado, con otra cantidad o
en otro nivel), no la aplica y **Por enviar** la muestra como rechazada, con
el motivo.

!!! example
    El residente valida sin señal un avance de 24 m². Antes de que vuelva la
    señal, la oficina lo rechaza en el escritorio. Al volver la conexión, la
    validación aparece rechazada con el motivo «El avance … ya fue
    rechazado» y el avance sigue rechazado.

## Sin señal

Cada registro lleva un identificador propio. Si el celular lo envía dos veces
(por ejemplo, porque la señal se cortó a mitad del envío), Odoo lo registra
una sola vez.

Las fotos se comprimen en el celular al lado mayor de **Ajustes ‣ Portal de
obra ‣ Fotos** (1600 px por defecto) antes de guardarse.

!!! tip "Fecha del avance"
    El avance no puede tener fecha futura ni más antigua que los días de
    **Ajustes ‣ Portal de obra ‣ Fecha del avance** (3 por defecto).

## Qué crea en Odoo

| En la aplicación | En Odoo |
|---|---|
| Registrar avance | Avance de la tarea **Por validar**, con fotos y ubicación. |
| Parte diario | **Ejecución ‣ Partes diarios**, con el avance del día ya resumido. |
| Cuadrilla y tareo | Marcación en la sede de la obra y **Ejecución ‣ Tareo de cuadrillas**. El jornal de cada persona se reparte entre las partidas en la proporción de sus horas. |
| Requerimientos | Requerimiento de obra (materiales de la partida) o requerimiento interno (EPP y útiles, con el área de gastos generales de la obra). |
| Recepción | Valida la entrega al almacén de la obra; lo que falta queda como entrega pendiente. |
| Devolución | Transferencia interna al almacén de origen o desecho. |

## Configuración

1. En la obra, pestaña **Portal de obra**, active el ingreso con usuario y
   clave o con QR.
2. Agregue a las personas con su rol. La contrata necesita su empresa.
3. Asigne el PIN si usa el QR.
4. Para los requerimientos internos elija el **área de gastos generales** de
   la obra.
5. Para el residente: agréguelo con el rol **Residente de obra** y marque
   **Aprobador por defecto de la obra** (uno por obra). No necesita ficha de
   empleado.
6. Para que los requerimientos lleguen al residente, elija una de estas
   formas (o las dos):
    - en **Ajustes ‣ Requerimientos de obra ‣ Requerimiento de obra sin regla
      de aprobación**, la opción **Pasar al residente de la obra (portal)**:
      lo que no tiene otra regla pasa al residente y, si la obra no tiene
      residente, al jefe de la obra;
    - en las reglas de aprobación de los requerimientos, el revisor por campo
      **Residente de la obra**. Con varios niveles, la regla de **secuencia
      más alta** revisa primero.
7. Elija el **Contacto del cliente en obra** en la pestaña Portal de obra:
   recibe el parte diario de obra y las constancias de los cambios.
8. Ajuste los motivos en **Configuración ‣ Motivos del residente**: rechazo de
   un avance, corrección de su cantidad y rechazo de un requerimiento.
9. Marque en las **categorías de producto** el catálogo del portal en que
   aparecen (EPP o útiles) y arme los kits en **Configuración ‣ Kits del
   portal**.
