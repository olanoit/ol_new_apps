---
modulos: [al_sale_approval]
---

# Aprobación de órdenes de venta

Algunas ventas deben aprobarse antes de confirmarse (por ejemplo, un contrato
de muebles para una obra). Con **Aprobación de órdenes de venta**
(`al_sale_approval`), las órdenes con productos marcados no se confirman sin
una solicitud aprobada en la app **Aprobaciones**.

## Configuración

1. Instale **Aprobación de órdenes de venta** (`al_sale_approval`); instala
   **Aprobaciones** (Odoo Enterprise).
2. En **Aprobaciones ‣ Configuración ‣ Categorías de aprobación**, cree la
   categoría (p. ej. «Aprobación de orden de venta») con sus aprobadores y la
   **referencia** obligatoria.
3. En **Ajustes ‣ Ventas ‣ Aprobación de órdenes de venta**, elija esa
   categoría.
4. En el producto, pestaña **Información general**, active **Requiere
   aprobación de venta**.

## Pedir y dar la aprobación

1. En la cotización, el campo **Aprobación** dice *Por solicitar*.
   **Solicitar aprobación** crea la solicitud de la categoría con la orden
   como referencia, el cliente y el monto, y la abre: envíela con **Enviar**.
2. La orden pasa a *En aprobación*; el botón **Aprobaciones** lleva a sus
   solicitudes.
3. Cuando el aprobador la aprueba, la orden queda *Aprobada* y **Confirmar**
   deja pasar la venta. Si la rechaza, queda *Rechazada* y se puede volver a
   solicitar.

## Casos especiales

| Situación | Qué pasa | Qué hacer |
|---|---|---|
| «La orden … necesita una solicitud aprobada» | La orden tiene un producto que requiere aprobación y no está aprobada | **Solicitar aprobación** y esperar al aprobador |
| «Elija la categoría de aprobación de ventas» | Falta la categoría en Ajustes | Elegirla en **Ajustes ‣ Ventas** |
| Órdenes cargadas de otro sistema | Ya estaban aprobadas fuera de Odoo | Gerencia de ventas marca **Sin aprobación (carga histórica)** |
| Solicitudes anteriores al módulo | No están enlazadas a la orden | Valen si su referencia es el número de la orden |

!!! info "Ver también"
    - [Aprobaciones en Odoo 19](https://www.odoo.com/documentation/19.0/es/applications/productivity/approvals.html)
