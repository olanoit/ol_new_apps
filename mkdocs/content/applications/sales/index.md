# Ventas

Lo que la suite agrega a las aplicaciones de ventas de Odoo: la **aprobación
de órdenes de venta** y el **punto de venta** (los comprobantes electrónicos
peruanos desde la caja, el vendedor de cada venta, la búsqueda de productos,
las impresoras térmicas de red y la marca de cada caja).

## Ventas

| Página | Qué resuelve |
|---|---|
| [Aprobación de órdenes de venta](sales/sale_approval.md) | Ventas de productos marcados que solo se confirman con una solicitud aprobada |

## Punto de venta

| Página | Qué resuelve |
|---|---|
| [Comprobantes electrónicos en el TPV](point_of_sale/electronic_invoicing.md) | Boleta y factura electrónica con su serie y su diario, ticket con QR y emisión a SUNAT retenida |
| [Vendedor por venta](point_of_sale/salesperson.md) | Vendedor de cada orden, distinto del cajero, y ventas por vendedor |
| [Vista de productos](point_of_sale/product_view.md) | Filtro por etiquetas, lista compacta con stock y precio, vista preferida por cajero |
| [Impresoras de red](point_of_sale/network_printers.md) | Térmicas ESC/POS genéricas por red, sin IoT Box, con agente local para Odoo en la nube |
| [Tema del TPV](point_of_sale/theme.md) | Nombre, logo y colores por caja, pago en el panel de la orden y modo oscuro |

Las boletas y facturas de la caja siguen el mismo circuito que las de
Contabilidad: vea [Facturación electrónica](../finance/fiscal_localizations/peru/electronic_invoicing.md)
en la localización peruana.

!!! info "Ver también"
    - [Punto de venta en Odoo 19](https://www.odoo.com/documentation/19.0/es/applications/sales/point_of_sale.html)
