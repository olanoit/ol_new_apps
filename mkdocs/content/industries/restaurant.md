---
modulos: [al_industry_restaurant]
---

# Restaurante

Para restaurantes, cafeterías y pollerías que atienden en mesa, para llevar
y por delivery.

## Qué instala

- El **TPV de restaurante** de Odoo (salón, mesas, comandas, división de
  cuentas y propinas) con [boleta y factura electrónica](../sales/point_of_sale/electronic_invoicing.md),
  [cliente por RUC o DNI](../sales/point_of_sale/customer_lookup.md),
  [cobro con Yape y Plin](../sales/point_of_sale/qr_payments.md),
  [mozo por venta](../sales/point_of_sale/salesperson.md)
  y el [tema del TPV](../sales/point_of_sale/theme.md) (nombre, logo y colores
  propios en la caja).
- **Compras** de insumos con recepción en almacén.
- El **libro de reclamaciones**.

!!! tip "Comandas en impresoras de red"
    Instale también [Impresoras de red](../sales/point_of_sale/network_printers.md).
    No viene en el paquete porque necesita `queue_job` en `server_wide_modules`.

## Qué deja configurado

Categorías de caja (entradas, platos de fondo, menú del día, bebidas,
postres, para llevar), categorías de carta e insumos y etiquetas (picante,
vegetariano, sin gluten).

## Instalación

1. En **Aplicaciones**, filtre por la categoría **OL-INDUSTRIES** e instale
   **Industria: Restaurante**.
2. La compañía activa recibe la actividad económica principal CIIU **5610**
   si todavía no tiene una. Para otra compañía, cámbiese a ella y use
   **Aplicar a la compañía activa** (ver [Industrias](index.md)).
