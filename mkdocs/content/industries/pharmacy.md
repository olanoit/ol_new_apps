---
modulos: [al_industry_pharmacy]
---

# Farmacia y botica

Para farmacias, boticas y droguerías minoristas que venden en caja, compran
por lote y controlan vencimientos.

## Qué instala

- **Punto de venta** con [boleta y factura electrónica](../sales/point_of_sale/electronic_invoicing.md),
  [cliente por RUC o DNI](../sales/point_of_sale/customer_lookup.md),
  [cobro con Yape y Plin](../sales/point_of_sale/qr_payments.md), la
  [vista de productos](../sales/point_of_sale/product_view.md)
  y el [tema del TPV](../sales/point_of_sale/theme.md) (nombre, logo y colores
  propios en la caja).
- **Inventario** con lotes y fecha de vencimiento (Caducidad de productos de
  Odoo), su fecha en la guía y el kárdex valorizado SUNAT.
- **Compras** y **Ventas** con margen, y programas de **fidelización**.
- El **libro de reclamaciones** virtual.

## Qué deja configurado

- Lotes y vencimientos activos para todos los usuarios internos.
- Categorías **Medicamentos** (venta libre, con receta médica, controlados),
  dermocosmética, bebés y maternidad, nutrición y dispositivos médicos; las de
  medicamentos con estrategia de salida **FEFO** (primero vence, primero sale).
- Categorías de caja y etiquetas (requiere receta, cadena de frío, genérico,
  de marca, psicotrópico).

## Datos DIGEMID del producto

La pestaña **Farmacia** del producto guarda el **registro sanitario**, el
**principio activo** (DCI), la **concentración**, la **forma farmacéutica** y
la **condición de venta** (venta libre, con receta médica o receta especial).
En la lista de productos, los filtros **Venta libre**, **Con receta** y **Sin
registro sanitario** ayudan a revisar el catálogo antes de una inspección.

## Instalación

1. En **Aplicaciones**, filtre por la categoría **OL-INDUSTRIES** e instale
   **Industria: Farmacia y botica**.
2. La compañía activa recibe la actividad económica principal CIIU **4772**
   si todavía no tiene una. Para otra compañía, cámbiese a ella y use
   **Aplicar a la compañía activa** (ver [Industrias](index.md)).
