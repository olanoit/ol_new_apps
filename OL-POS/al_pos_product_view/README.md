# TPV - Catálogo de productos: filtro por etiqueta y vista lista (AL)

Documentación funcional: [Vista de productos](../../mkdocs/content/applications/sales/point_of_sale/product_view.md)

Módulo `al_pos_product_view` para Odoo 19. Unifica en un solo módulo dos
funcionalidades del catálogo de productos del TPV, originalmente entregadas
como los módulos `mblz_pos_filter_products_by_active_ingredient` y
`mblz_pos_product_switch_view` (misma lógica, renombrada y fusionada).

## 1. Filtro por etiqueta

- Fila de **chips** (uno por etiqueta usado por al menos un producto
  cargado) sobre la grilla de productos del TPV, debajo del selector de
  categorías. Selección múltiple con semántica **OR** y botón *Limpiar*.
- Convive con la búsqueda por texto, las categorías y el modo "Agrupar por
  categoría"; el filtrado se aplica **antes** del tope de 100 productos
  visibles.
- **Botón de recarga** (icono ↻): trae los cambios del backend (etiquetas
  nuevas, renombrados, recoloreados, eliminados y re-asignaciones a
  productos) sin salir de la sesión.
- Campo **"Mostrar en la barra de filtros del TPV"** (`show_in_pos_filter`)
  por etiqueta, con edición masiva en la lista, para acotar los
  chips visibles sin afectar la lógica de filtrado.
- Activación por caja: *Punto de Venta → Configuración → Ajustes* →
  **Filtrar productos por etiqueta** (activada por defecto).

## 2. Conmutador de vista cuadrícula/lista

- **Botón de cambio de vista** sobre el catálogo: alterna entre las tarjetas
  nativas (cuadrícula) y una **vista de lista compacta** con miniatura,
  nombre, SKU, código de barras, etiquetas, stock disponible
  (solo almacenables), cantidad en carrito y precio con impuestos según
  `iface_tax_included` (coincide con el precio de la línea del pedido).
- Botón de **información** en cada fila y en cada tarjeta de la cuadrícula,
  que abre el **ProductInfoPopup reorganizado**: banner superior con una
  tarjeta de stock por almacén, productos opcionales como grilla de tarjetas y panel
  "Información General" en dos columnas (datos descriptivos | monetarios).
- **Control segmentado «Cuadrícula | Lista»** en la barra del catálogo,
  junto al botón **Actualizar stock**.
- Bajo el precio de cada fila, el **desglose de la tarifa** (descuento o
  recargo sobre el precio de venta). Las plantillas de una sola variante se
  tarifican por su variante, así que las reglas por variante se aplican.
- La ficha del producto muestra **una tarjeta de inventario por almacén**
  (disponible, previsto y «Sin stock» en rojo), con la de la caja resaltada.
- **Vista por defecto configurable por TPV** (*Ajustes* → **Vista de productos
  por defecto**) y **preferencia persistente por cajero** (cascada: usuario →
  configuración del TPV → cuadrícula), editable también desde
  *Usuarios / Mis preferencias* (**Vista de productos del TPV**).

## 3. Stock y filtros del catálogo

- **Stock al día** de la caja (ubicación de origen de su tipo de operación,
  o su almacén) en las filas y en las **tarjetas de la cuadrícula** (badge
  verde o rojo, solo almacenables). Se pide al servidor
  (`product.template.get_pos_location_stock`) al buscar, al cambiar de
  categoría, de página o de vista y al añadir un producto; al cerrar un
  pedido se descuenta lo vendido en local.
- Desplegable **Filtros** en la barra del catálogo: disponibilidad de stock
  (todos, con stock, sin stock; `get_pos_in_stock_template_ids`) y
  **Limpiar filtros**. A su lado, una **faceta** por filtro aplicado (stock
  y etiquetas) que se quita con su aspa.
- Los filtros de stock y de etiquetas (`get_pos_tag_template_ids`) traen
  del servidor los productos que la caja no había cargado
  (`limited_product_count`), hasta el tope de 100 visibles.
- Mensaje «Ningún producto cumple los filtros seleccionados» en lugar del
  estado vacío nativo.
- Opción por caja **Limpiar la búsqueda al añadir** (`iface_clear_search_on_add`,
  activada por defecto): el buscador se vacía cuando el producto entra al
  pedido.

## Dependencias

- `point_of_sale`
- `stock` (la vista de lista muestra `qty_available`)
- Sin dependencias externas: las etiquetas son `product.tag` del core.

## Estructura interna

Los assets de cada funcionalidad viven en subdirectorios separados para
evitar colisiones de nombres:

- `static/src/tag_filter/…` — chips de filtro (patch de `PosStore`,
  selector, patch de `ProductScreen`).
- `static/src/switch_view/…` — conmutador, stock y filtros del catálogo
  (fila de lista, filtro `AlpvCatalogFilter`, patches de `PosStore`,
  `ProductScreen`, `ProductCard` y `ProductInfoPopup`, helpers de precio y
  de badge de stock).

Los modelos compartidos por ambas funcionalidades (`pos.config`,
`res.config.settings`) están fusionados en un archivo único cada uno.

## Tests

Tour end-to-end `al_pos_product_view_tour` (bundle `web.assets_tests`:
conmutador, stock en la fila y en la tarjeta, búsqueda que se limpia,
filtro de stock y su faceta) + test HttpCase en
`tests/test_al_pos_product_view.py`, y pruebas de los métodos del servidor
y de los ajustes en `tests/test_pos_data.py`:

```bash
odoo -d <db> -u al_pos_product_view --test-enable \
     --test-tags=/al_pos_product_view --stop-after-init
```
