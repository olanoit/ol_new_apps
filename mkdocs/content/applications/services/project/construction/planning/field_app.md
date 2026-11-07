---
modulos: [al_construction_portal]
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
| Parte diario | Clima, personal propio y de contratas, restricciones (material, frente, clima), ocurrencias, fotos y la firma del maestro de obra. Uno por obra y día. |
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
7. Ajuste los motivos en **Configuración ‣ Motivos del residente**: rechazo de
   un avance, corrección de su cantidad y rechazo de un requerimiento.
8. Marque en las **categorías de producto** el catálogo del portal en que
   aparecen (EPP o útiles) y arme los kits en **Configuración ‣ Kits del
   portal**.
