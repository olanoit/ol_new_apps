# PE - Cobro con QR de Yape y Plin en el TPV (AL)

Documentación funcional: [Cobros con QR y pasarelas en el TPV](../../mkdocs/content/applications/sales/point_of_sale/qr_payments.md)

Módulo técnico `al_pos_pe_wallet_qr`. Agrega el formato de QR **«QR de
billetera (Yape, Plin)»** al cobro por QR nativo del TPV de Odoo 19
(`payment_method_type = 'qr_code'`).

## Cómo funciona

- `res.partner.bank.l10n_pe_wallet_qr_image`: la imagen del QR de cobro de la
  billetera, en la cuenta donde abona.
- `_get_available_qr_methods` añade `l10n_pe_wallet`.
- `_get_qr_code_base64` y `_get_qr_code_url` devuelven la imagen: el QR de
  Yape o Plin es fijo y no lleva el importe.
- `_get_error_messages_for_qr` exige la imagen y los soles.
- El TPV usa sus propios flujos: `pos.payment.method.get_qr_code`, el diálogo
  `QRPopup`, la pantalla del cliente y `default_qr` para trabajar sin
  conexión.
- Si la compañía muestra QR en las facturas, el método también está
  disponible ahí.

## Límite

Yape y Plin no publican una API para comercios que confirme el pago, así que
el cajero confirma al ver la notificación. Para un cobro confirmado
automáticamente se usa el pago en línea nativo (`pos_online_payment`) con
Culqi, Niubiz o Izipay; está documentado en la misma página.

## Pruebas

- `tests/`: método disponible, imagen en el TPV y como QR sin conexión,
  cuenta sin imagen y solo soles.
- Validado en `ol_pe_v19` con la caja «DEMO TPV Yape»
  (`docs/tpv_pe/preparar_demo_qr.py`).

## Licencia

OPL-1.
