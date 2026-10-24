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
| Oficina técnica | Residente o asistente | Lo mismo que el capataz salvo el tareo de la cuadrilla. |

Hay dos formas de ingresar, que se activan por obra:

- **Usuario y clave** de Odoo. La sesión dura los días de **Ajustes ‣
  Planificación de obra ‣ Portal de obra ‣ Sesión del portal** (90 por
  defecto).
- **QR de la obra y PIN**. El QR se imprime en el cartel de la obra; la
  persona lo escanea, elige su nombre y escribe su PIN de 4 dígitos. Tres PIN
  errados bloquean a la persona hasta que la oficina la desbloquee. **Nuevo
  código del QR** invalida el cartel anterior.

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
5. Marque en las **categorías de producto** el catálogo del portal en que
   aparecen (EPP o útiles) y arme los kits en **Configuración ‣ Kits del
   portal**.
