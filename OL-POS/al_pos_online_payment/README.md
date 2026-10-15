# Pago en línea del TPV: ticket sin pagos duplicados (AL)

Documentación funcional: [Cobros con QR y pasarelas en el TPV](../../mkdocs/content/applications/sales/point_of_sale/qr_payments.md)

Módulo técnico `al_pos_online_payment`, con `auto_install` sobre
`pos_online_payment`. Corrige un defecto de Odoo 19 que se presenta con
cualquier pasarela.

## El defecto

1. Al cobrar en línea, el TPV crea una línea local del método de pago en
   línea. `pos_online_payment` la saca de `serializeForORM`, así que nunca
   llega al servidor.
2. La pasarela confirma el pago: `payment.transaction` crea el `pos.payment`
   real en la orden y la deja pagada.
3. `afterOrderValidation` → `sendOrderInPreparation` → `syncAllOrders` carga
   la orden del servidor con ese pago (`loadConnectedData`) y lo **suma** a la
   línea local, que nadie borra.

El ticket muestra el pago dos veces y `order.change` igual al importe.

## La corrección

`PosStore.postSyncAllOrders` (el gancho vacío de `syncAllOrders` con las
órdenes cargadas): si la orden está `paid` o `done` y ya tiene un pago en
línea sincronizado, se borran sus líneas de pago en línea sin sincronizar.
Los pagos de otros métodos no se tocan.

## Pruebas

Validado en `ol_pe_v19` (caja «DEMO TPV Pasarelas», Izipay de prueba) con un
script de Playwright que registra las líneas de pago del TPV en cada paso:
antes de la corrección quedaban la línea local y el pago 78; después, solo
el pago 80, y el ticket muestra un único «DEMO Pago en línea S/ 4,13». No
lleva prueba automática: reproducir el pago exige la pasarela o un tour con
pago simulado en el servidor.

## Licencia

OPL-1.
