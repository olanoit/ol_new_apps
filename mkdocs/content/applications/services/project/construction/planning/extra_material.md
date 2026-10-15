---
modulos: [al_construction_planner, al_construction_material_request]
---

# Material extra y descuento a la contrata

El material que no estaba previsto (una plancha rota al cortar, un error de
medida, un cambio del cliente) se pide como **material extra**: un
requerimiento de obra marcado como extra, con su motivo, que siempre revisa la
Jefatura de Proyectos, esté o no dentro del plan. Al aprobarlo, la Jefatura
decide si se descuenta a la contrata responsable; el descuento entra en la
siguiente liquidación semanal de esa contrata en la obra.

## Conceptos

| Término | Significado |
|---|---|
| Material extra | Requerimiento de obra con **Material extra** marcado. Necesita un **Motivo del extra**: **Merma**, **Error de medida**, **Cambio del cliente** o **Reposición** |
| Revisión de la jefatura | Regla de aprobación «Material extra: jefatura de proyectos», que aplica a todo extra, además de las reglas del requerimiento |
| Descuento a la contrata | Monto que se resta de la siguiente liquidación de la contrata en la obra. Por defecto, el valor estimado del requerimiento |

## Configuración

En **Ajustes ‣ Planificación de obra ‣ Contratas**, elija la cuenta de
**Descuento de material extra**. Sin esa cuenta, una liquidación con
descuentos no se puede aprobar.

## Pedir material extra

Desde el backend:

1. Cree el requerimiento de obra como siempre, con el piso o ambiente donde se
   usa.
2. Marque **Material extra** y elija el **Motivo del extra**. Sin motivo, el
   requerimiento no se envía.
3. Haga clic en **Solicitar aprobación**.

Desde el portal, el capataz de la contrata:

1. Entra a **Mi cuenta ‣ Mis obras** y hace clic en **Pedir material extra**.
2. Elige la obra (si trabaja en varias), el piso o ambiente, el material del
   plan vigente, la cantidad y el motivo; opcionalmente escribe el detalle y
   adjunta una foto.
3. Hace clic en **Enviar pedido**.

El pedido del portal queda en **Borrador**, sin reservar material del almacén,
con la foto adjunta y una actividad para el responsable de la obra (o, si la
obra no tiene, para la Jefatura de Proyectos). El residente lo revisa y lo
envía a aprobación. El capataz solo ve los pisos y ambientes donde trabaja su
empresa y los materiales del plan de esa obra.

## Aprobar y descontar

1. La Jefatura abre el extra desde **Necesita mi revisión**.
2. Si el extra es responsabilidad de una contrata, en el grupo **Descuento a
   la contrata** marca **Descontar a la contrata**, elige la **Contrata a
   descontar** y, si hace falta, corrige el **Monto a descontar**.
3. Haga clic en **Validar**.

Solo la Jefatura de Proyectos cambia el descuento, y no se puede cambiar
después de entrar en una liquidación.

## El descuento en la liquidación

Al preparar o actualizar la liquidación semanal de una contrata, el
planificador toma los extras aprobados con descuento a esa contrata en esa
obra que aún no se descontaron. La liquidación los muestra en la pestaña
**Descuentos** y calcula:

**Neto = bruto − retención − descuentos**

Al aprobarla, la factura de proveedor lleva una línea negativa por cada extra,
a la cuenta de descuento. Si la liquidación se anula, sus descuentos quedan
libres para la siguiente.

Ejemplo: la liquidación del 05/11/2026 de la contrata Leandro tiene un bruto de
S/ 380.88 y una retención de S/ 38.09. Con un extra de S/ 50.00 por merma
descontado a Leandro, el neto baja de S/ 342.79 a S/ 292.79.

## Casos especiales

| Situación | Qué pasa | Qué hacer |
|---|---|---|
| «Indique el motivo del material extra» | El extra no tiene motivo | Elegir el motivo |
| «El descuento a la contrata lo decide la jefatura de proyectos» | Otro usuario intenta marcar o cambiar el descuento | Pedirlo a la Jefatura |
| «El extra ya se descontó en una liquidación» | El descuento ya entró en una liquidación | Anular esa liquidación, si aún no está aprobada |
| «Configure la cuenta del descuento de material a contratas» | Falta la cuenta en Ajustes | Configurarla y aprobar de nuevo |
| El descuento no aparece en la liquidación | El extra no está aprobado, es de otra obra o de otra contrata | Revisar el estado, la obra y la contrata del extra |
| El capataz no ve **Pedir material extra** | Su empresa no tiene actividades asignadas en ninguna obra | Asignar la contrata en el plan |

!!! info "Ver también"
    - [Requerimientos de materiales](../material_requests.md)
    - [Contratas y liquidación semanal](contractors.md)
    - [Portal de obra, sedes y marcación](site_portal.md)
