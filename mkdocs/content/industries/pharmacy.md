---
modulos: [al_industry_pharmacy]
---

# Farmacia y botica

Para farmacias, boticas y droguerías minoristas que venden en caja, compran por
lote, controlan vencimientos y cumplen con DIGEMID.

## Qué instala

- La suite de farmacia completa (ver [Farmacia y botica](../applications/health/pharmacy.md)):
    - maestro farmacéutico con principio activo, registro sanitario,
      condición de venta, equivalentes y presentaciones (caja, blíster, unidad);
    - buenas prácticas de almacenamiento: recepción, lotes y vencimientos,
      temperatura, alertas sanitarias, actas de baja y bonificaciones;
    - receta y dispensación en la caja, con alternativas genéricas y control
      del químico farmacéutico;
    - estupefacientes y psicotrópicos: receta especial, libros y balance
      trimestral;
    - DIGEMID: Observatorio de precios, 30 % de genéricos, precios por DCI,
      reacciones adversas e IGV exonerado.
- **Punto de venta** con [boleta y factura electrónica](../applications/sales/point_of_sale/electronic_invoicing.md),
  [cliente por RUC o DNI](../applications/sales/point_of_sale/customer_lookup.md),
  [cobro con Yape y Plin](../applications/sales/point_of_sale/qr_payments.md),
  [vista de productos](../applications/sales/point_of_sale/product_view.md)
  y el [tema del TPV](../applications/sales/point_of_sale/theme.md).
- **Compras** y **Ventas** con margen, **fidelización**, kárdex valorizado SUNAT
  y el **libro de reclamaciones** virtual.

## Qué deja configurado

- Lotes y vencimientos activos para todos los usuarios internos.
- Categorías **Medicamentos** (venta libre, con receta médica, controlados),
  dermocosmética, bebés y maternidad, nutrición y dispositivos médicos; las de
  medicamentos con salida **FEFO** (primero vence, primero sale).
- Categorías de caja y etiquetas.
- Con datos de demostración: una botica con 14 medicamentos de marcas y
  laboratorios inventados (genéricos y de marca, con receta, controlados,
  insulina en cadena de frío), sus presentaciones, el listado de genéricos
  esenciales, dos médicos y los puntos de control de temperatura.

## Instalación

1. En **Aplicaciones**, filtre por la categoría **OL-INDUSTRIES** e instale
   **Industria: Farmacia y botica**.
2. La compañía activa recibe la actividad económica principal CIIU **4772**
   si todavía no tiene una. Para otra compañía, cámbiese a ella y use
   **Aplicar a la compañía activa** (ver [Industrias](index.md)).
3. Siga la [configuración de la suite](../applications/health/pharmacy.md):
   roles, químicos farmacéuticos, director técnico y ajustes.
