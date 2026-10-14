# Ventas

Lo que la suite agrega a las aplicaciones de ventas de Odoo: la **aprobación
de órdenes de venta**, el **punto de venta** (los comprobantes electrónicos
peruanos desde la caja, el cliente por RUC o DNI, el cobro con QR y
pasarelas, el vendedor de cada venta, la búsqueda de productos, las
impresoras térmicas de red y la marca de cada caja) y la **tienda en línea**
(boleta o factura y la consulta del RUC o DNI en el checkout).

## Ventas

| Página | Qué resuelve |
|---|---|
| [Aprobación de órdenes de venta](sales/sale_approval.md) | Ventas de productos marcados que solo se confirman con una solicitud aprobada |

## Punto de venta

| Página | Qué resuelve |
|---|---|
| [Comprobantes electrónicos en el TPV](point_of_sale/electronic_invoicing.md) | Boleta y factura electrónica con su serie y su diario, ticket con QR y emisión a SUNAT retenida |
| [Cliente por RUC o DNI](point_of_sale/customer_lookup.md) | Crear el cliente desde la búsqueda con los datos de SUNAT, sin duplicados |
| [Cobros con QR y pasarelas](point_of_sale/qr_payments.md) | QR de Yape o Plin del negocio y pago en línea con Culqi, Niubiz o Izipay desde la caja |
| [Vendedor por venta](point_of_sale/salesperson.md) | Vendedor de cada orden, distinto del cajero, y ventas por vendedor |
| [Vista de productos](point_of_sale/product_view.md) | Filtro por etiquetas, lista compacta con stock y precio, vista preferida por cajero |
| [Impresoras de red](point_of_sale/network_printers.md) | Térmicas ESC/POS genéricas por red, sin IoT Box, con agente local para Odoo en la nube |
| [Tema del TPV](point_of_sale/theme.md) | Nombre, logo y colores por caja, pago en el panel de la orden y modo oscuro |

## Tienda en línea

| Página | Qué resuelve |
|---|---|
| [Checkout peruano](ecommerce/peruvian_checkout.md) | Boleta o factura en el checkout y consulta del RUC o DNI que llena el nombre y la dirección |

Las boletas y facturas de la caja siguen el mismo circuito que las de
Contabilidad: vea [Facturación electrónica](../finance/fiscal_localizations/peru/electronic_invoicing.md)
en la localización peruana.

!!! info "Ver también"
    - [Punto de venta en Odoo 19](https://www.odoo.com/documentation/19.0/es/applications/sales/point_of_sale.html)
