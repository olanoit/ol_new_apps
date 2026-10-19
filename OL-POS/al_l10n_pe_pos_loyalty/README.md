# Perú - Tarjetas de regalo y monedero en el TPV (AL)

Documentación funcional: [Tarjetas de regalo y monedero](../../mkdocs/content/applications/sales/point_of_sale/gift_cards.md)

Módulo puente con `auto_install` sobre `al_l10n_pe_edi_pos` y `pos_loyalty`.
Aplica el Informe SUNAT 097-2010 a los programas de pago de Odoo
(`gift_card` y `ewallet`). Verificación de la norma en
`docs/farmacia/VERIFICACIONES.md`, sección 5.

## Qué cambia

- **Líneas de vale** (`pos.order.line._l10n_pe_pos_voucher_lines`): la venta
  de un producto que dispara un programa de pago (o los productos de Odoo
  `loyalty.gift_card_product_50` y `loyalty.ewallet_product_50`) y las
  líneas de recompensa de esos programas. Solo en compañías peruanas.
- **Comprobante**: con el contexto `invoicing`, las líneas de vale no pasan a
  la factura (`_prepare_tax_base_line_values`, el mismo patrón que
  `pos_settle_due`). Una orden solo de vales no se factura: al sincronizar
  pasa a `recibo` y desde el backend da `UserError`.
- **Pago con el vale** (`_reconcile_invoice_payments`): asiento en el diario
  del TPV entre la cuenta del vale y la cuenta por cobrar del cliente, por el
  importe con signo de las líneas de vale, conciliado con el comprobante y
  los pagos.
- **Redondeo de efectivo** (`_create_invoice`): Odoo iguala el comprobante a
  lo cobrado; se le resta el importe del vale para que redondee solo el
  comprobante.
- **Cierre de caja**: las líneas de vale van sin impuestos a la cuenta de la
  compañía (`l10n_pe_pos_voucher_account_id`, 496 por defecto) y su apunte no
  lleva `tax_ids` (`pos.session._get_sale_key`). El producto de descuento que
  crea `loyalty` trae el impuesto de venta por defecto y el TPV lo usa con el
  precio incluido: sin esto, el canje rebajaba el IGV.
- **Instalación** (`res.company._l10n_pe_pos_setup_vouchers`): propone la
  cuenta y quita el impuesto inafecto (9998) que ponía `al_l10n_pe_edi_pos`
  hasta la versión 15 y los impuestos peruanos de los productos de canje.
- **TPV**: `PosOrderline.isPeVoucherLine`; la validación del pago pasa a
  recibo una orden solo de vales; el ticket CPE quita los vales de las
  líneas, suma el canje a los pagos y anota la tarjeta vendida
  (`peReceiptLines`, `peExtraPayments`, `peNotes` de `al_l10n_pe_edi_pos`).

## Pruebas

`tests/test_pos_vouchers.py`: 6 pruebas de cierre de caja y facturación
(canje con IGV completo, tarjeta vendida con productos, venta solo de
tarjetas, sesión sin comprobante con canje gravado, redondeo de efectivo) y 2
tours (venta solo de tarjeta como recibo y ticket CPE de una venta mixta).

## Licencia

OPL-1.
