# Cobro con pasarelas en el TPV: un método por pasarela y devoluciones (AL)

Documentación funcional: [Cobros con QR y pasarelas en el TPV](../../mkdocs/content/applications/sales/point_of_sale/qr_payments.md)

Módulo técnico `al_pos_payment_gateway`, sobre el pago en línea nativo del TPV
(`pos_online_payment`) y `al_pos_online_payment`.

## Un método por pasarela

- `pos.config._check_online_payment_methods` reemplaza la regla nativa de un
  solo método en línea por caja: puede haber varios, pero cada pasarela va en
  uno solo.
- Antes de mostrar el QR, el TPV llama a `pos.order.al_set_online_payment_method`
  con el método de la línea que se cobra; `online_payment_method_id` (que usa la
  página `/pos/pay`) devuelve ese método, así el cliente ve solo sus pasarelas.
- Al confirmarse la transacción, `_process_pos_online_payment` corre con la
  pasarela en el contexto (`al_pos_online_provider_id`) y el pago se registra
  con el método que la tiene, aunque el cajero haya cambiado de método.
- Botón **Cobrar en el TPV** en la pasarela: crea (o abre) su método.

## Devolver a la tarjeta

1. En una orden de devolución, una línea negativa de un método en línea se
   devuelve al validar, después de las comprobaciones del TPV:
   `pos.order.al_refund_online_payment` busca el cobro de las órdenes devueltas
   con ese método y llama a `payment.transaction._refund`. Con la devolución
   confirmada, crea su pago contable (`_post_process`) y devuelve la referencia.
2. La línea queda «hecha» con esa referencia en `transaction_id` (si la
   validación se repite, no se devuelve dos veces) y se envía al servidor
   (`pos_online_payment` no envía las líneas en línea locales).
3. `pos.payment.create` enlaza el pago contable de la devolución por la
   referencia (`online_account_payment_id`): sin él, Odoo no acepta un pago en
   línea. El cierre de caja lo concilia como cualquier cobro en línea.

Si la pasarela no confirma, el TPV muestra el motivo y la transacción queda
registrada (no se revierte: la pasarela puede confirmarla después).

Los parches del TPV van en `point_of_sale.assets_prod`, después de los de
`pos_online_payment`, que define `processOnlinePaymentsDataFromServer` sin
`super`.

## Pruebas

`tests/test_pos_payment_gateway.py` (8, `post_install`), sobre el entorno de
las pruebas de `pos_online_payment` con una segunda pasarela:

- dos métodos en línea en la caja y la misma pasarela en dos rechazada;
- el QR de la segunda pasarela solo admite esa pasarela y el pago queda con su
  método; un pago llega al método de su pasarela;
- devolución total con su pago contable, orden de devolución pagada y caja
  cerrada; no más de lo cobrado; sin devolución confirmada no hay pago
  negativo en línea;
- recorridos del TPV: elegir la segunda pasarela antes del QR y devolver una
  venta cobrada en línea hasta el ticket.

## Licencia

OPL-1.
