# TPV - Catálogo de productos: filtro por etiqueta y vista lista (AL)

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
- **Botón de recarga** (icono ↻): trae los cambios del backend (principios
  nuevos, renombrados, recoloreados, eliminados y re-asignaciones a
  productos) sin salir de la sesión.
- Campo **"Mostrar en la barra de filtros del POS"** (`show_in_pos_filter`)
  por etiqueta, con edición masiva en la lista, para acotar los
  chips visibles sin afectar la lógica de filtrado.
- Activación por caja: *Punto de Venta → Configuración → Ajustes* →
  **Filter products by active ingredient** (activada por defecto).

## 2. Conmutador de vista cuadrícula/lista

- **Botón de cambio de vista** sobre el catálogo: alterna entre las tarjetas
  nativas (cuadrícula) y una **vista de lista compacta** con miniatura,
  nombre, SKU, código de barras, etiquetas, stock disponible
  (solo almacenables), cantidad en carrito y precio con impuestos según
  `iface_tax_included` (coincide con el precio de la línea del pedido).
- Botón de **información** en cada fila y en cada tarjeta de la cuadrícula,
  que abre el **ProductInfoPopup reorganizado**: banner superior con stock
  por bodega (chips), productos opcionales como grilla de tarjetas y panel
  "Información General" en dos columnas (datos descriptivos | monetarios).
- **Vista por defecto configurable por TPV** (*Ajustes* → **Default product
  view**) y **preferencia persistente por cajero** (cascada: usuario →
  configuración del TPV → cuadrícula), editable también desde
  *Usuarios / Mis preferencias* (**POS Product View**).

## Dependencias

- `point_of_sale`
- `stock` (la vista de lista muestra `qty_available`)
- `product.tag (core)` (puente externo: carga el modelo
  `product.active.ingredient` y el m2m `active_ingredient_ids` al cliente
  TPV; arrastra `mblz_product_active_ingredient`)

## Estructura interna

Los assets de cada funcionalidad viven en subdirectorios separados para
evitar colisiones de nombres:

- `static/src/ingredient_filter/…` — chips de filtro (patch de `PosStore`,
  selector, patch de `ProductScreen`).
- `static/src/switch_view/…` — conmutador (fila de lista, patches de
  `ProductScreen`, `ProductCard` y `ProductInfoPopup`, helper de precio).

Los modelos compartidos por ambas funcionalidades (`pos.config`,
`res.config.settings`) están fusionados en un archivo único cada uno.

## Tests

Tour end-to-end `al_pos_product_view_tour` (bundle `web.assets_tests`) +
test HttpCase en `tests/test_al_pos_product_view.py`:

```bash
odoo -d <db> -u al_pos_product_view --test-enable \
     --test-tags=/al_pos_product_view --stop-after-init
```
