---
modulos: [al_l10n_pe_pos_loyalty]
---

# Tarjetas de regalo y monedero

Las tiendas venden tarjetas de regalo y recargan el monedero electrónico de sus
clientes. Para SUNAT, vender una tarjeta o recargar el monedero **no es una
venta de bienes**: no lleva IGV ni comprobante. El comprobante se emite cuando
el cliente la **canjea** por productos, por el precio completo y con todo su
IGV. Así lo explica el
[Informe SUNAT 097-2010](https://www.sunat.gob.pe/legislacion/oficios/2010/informe-oficios/i097-2010.pdf).

En Odoo estándar, la venta de la tarjeta sale en la boleta y el canje es un
descuento que rebaja el total y el IGV del comprobante. Con el módulo
**Tarjetas de regalo y monedero en el TPV** (`al_l10n_pe_pos_loyalty`) se
sigue el criterio de SUNAT:

- La tarjeta vendida o la recarga **no entra en la boleta ni en la factura**.
  Si la venta solo lleva tarjetas o recargas, sale con ticket, sin
  comprobante electrónico.
- El importe queda como **deuda con el cliente** en una cuenta de pasivo (496
  Ingresos diferidos, configurable), nunca como ingreso.
- Al canjear, el comprobante va por el **importe completo** con su IGV y el
  vale lo **paga**, como cualquier otra forma de pago.

Lo usan cajeros, supervisores de tienda y contabilidad.

## Configuración

1. El módulo se instala solo con
   [Comprobantes electrónicos en el TPV](electronic_invoicing.md) y los
   programas de fidelización del TPV.
2. Vaya a **Punto de venta ‣ Configuración ‣ Ajustes**, sección
   **Contabilidad**, bloque **Tarjetas de regalo y monedero**, y revise la
   **Cuenta**. Al instalar se propone la 496 del plan contable.
3. Cree los programas de **Tarjetas de regalo** o **Monedero electrónico** en
   **Punto de venta ‣ Productos ‣ Descuentos y programas de lealtad** y
   agréguelos a las cajas.

!!! warning "Importante"
    El producto con el que se vende la tarjeta o la recarga va **sin
    impuestos**. Al instalar, el módulo quita el impuesto inafecto de los
    productos de Odoo para tarjetas y recargas y el IGV del producto del canje.
    Revise los productos que cree usted.

## Vender una tarjeta de regalo

1. En la caja, agregue el producto de la tarjeta y cobre.
2. Si la venta solo lleva tarjetas o recargas, la caja la cambia a
   **Recibo**, aunque esté elegida la boleta: no pide cliente ni emite
   comprobante.
3. Si la venta lleva además productos, la boleta o factura va solo por los
   productos. El ticket muestra la tarjeta aparte, con la nota de que no forma
   parte del comprobante.

!!! example "Ejemplo: venta de una tarjeta"
    Rosa compra una tarjeta de regalo de S/ 50,00 y paga en efectivo. La venta
    sale con ticket y en el cierre de caja queda:

    | Cuenta | Descripción | Debe | Haber |
    |---|---|---|---|
    | 101 | Caja | 50,00 | |
    | 496 | Ingresos diferidos (tarjetas por canjear) | | 50,00 |
    | | **Totales** | **50,00** | **50,00** |

## Canjear la tarjeta

1. Registre la venta y aplique la tarjeta o el monedero como siempre (código
   de la tarjeta o botón **eWallet**).
2. Cobre la diferencia y elija la boleta o la factura.
3. El comprobante va por el precio completo. En el ticket, el canje aparece
   entre los pagos.

!!! example "Ejemplo: canje de S/ 20,00"
    Un ibuprofeno de S/ 50,00 + IGV 9,00 = 59,00. El cliente paga S/ 20,00 con
    su tarjeta y S/ 39,00 en efectivo. La boleta es de **S/ 59,00 con IGV de
    S/ 9,00**, no de S/ 39,00.

    | Cuenta | Descripción | Debe | Haber |
    |---|---|---|---|
    | 1212 | Boletas por cobrar | 59,00 | |
    | 70121 | Mercaderías – venta local | | 50,00 |
    | 40111 | IGV – cuenta propia | | 9,00 |
    | 101 | Caja (cobro en efectivo) | 39,00 | |
    | 1212 | Boletas por cobrar | | 39,00 |
    | 496 | Ingresos diferidos (canje de la tarjeta) | 20,00 | |
    | 1212 | Boletas por cobrar | | 20,00 |
    | | **Totales** | **118,00** | **118,00** |

    El canje es un asiento propio en el diario de la caja, conciliado con la
    boleta: la boleta queda pagada.

## Casos especiales

| Situación | Qué pasa |
|---|---|
| Venta solo de tarjetas con **Factura** elegida | Sale con ticket, sin comprobante |
| Facturar desde el backend una venta solo de tarjetas | Aviso: no lleva comprobante |
| Venta sin comprobante (**Recibo**) con canje | El cierre de caja baja la 496 por el canje, sin tocar el IGV |
| Redondeo de efectivo | Se redondea el comprobante, no lo cobrado en caja |
| Devolver una tarjeta o un canje | Odoo no lo permite desde la caja |
| Tarjeta vencida sin canje | El saldo sigue en la 496. Para Renta pasa a ingreso al vencer: el ajuste se hace a mano, con el contador |
| Vale «por» un producto determinado | Puede ser venta o anticipo gravado (Informe SUNAT 157-2015): no lo venda como tarjeta de regalo |

!!! note "Nota"
    El módulo trata las ventas del punto de venta. Las tarjetas que se venden o
    canjean en la tienda en línea o en pedidos de venta siguen el flujo de Odoo.

!!! info "Ver también"
    - [Informe SUNAT 097-2010](https://www.sunat.gob.pe/legislacion/oficios/2010/informe-oficios/i097-2010.pdf)
    - [Comprobantes electrónicos en el TPV](electronic_invoicing.md)
    - [Informe SUNAT 157-2015](https://www.sunat.gob.pe/legislacion/oficios/2015/informe-oficios/i157-2015.pdf)
    - [Punto de venta en Odoo 19](https://www.odoo.com/documentation/19.0/es/applications/sales/point_of_sale.html)
