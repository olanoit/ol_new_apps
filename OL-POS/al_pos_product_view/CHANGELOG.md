Historial de cambios — TPV - Catálogo de productos: filtro por etiquetas y vista lista (AL)
===========================================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_pos_product_view.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 9.20261027 — 13/11/2026

- Stock al día de la ubicación de la caja en las filas y también en las tarjetas de la cuadrícula (badge verde o rojo), con botón «Actualizar stock».
- Desplegable «Filtros» con la disponibilidad de stock (todos, con stock, sin stock) y facetas de los filtros aplicados, también de las etiquetas, que se quitan con un clic.
- El filtro por etiquetas y el de stock traen del servidor los productos que la caja aún no había cargado.
- Control segmentado «Cuadrícula | Lista» y mensaje propio cuando los filtros dejan el catálogo vacío.
- Bajo el precio de la lista, el descuento o recargo de la tarifa sobre el precio de venta; las reglas de tarifa por variante ya se aplican.
- Ficha del producto: una tarjeta de inventario por almacén, con el de la caja resaltado.
- Opción por caja «Limpiar la búsqueda al añadir» (activada por defecto).

## 8.20261027 — 27/10/2026

- Ícono nuevo: el isotipo de ALTA.

## 7.20261011 — 11/10/2026

- Modo oscuro del TPV: el botón de información de las tarjetas y la sombra de las filas de la lista se adaptan al tema oscuro.

## 6.20261009 — 09/10/2026

- Etiqueta más corta en la etiqueta de producto: «Filtro del TPV».

## 5.20261008 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).

## 4.20260925 — 27/09/2026

- En la ficha de producto del TPV, los precios y totales del pedido vuelven a ocultarse a los empleados con permisos mínimos (Empleados activo), como en el Odoo estándar.
- El stock de la vista de lista es el del almacén de la caja, no la suma de todos los almacenes.
- El botón de recarga de etiquetas es mucho más ligero: solo relee las etiquetas de los productos.
- Las etiquetas de ejemplo (Bebidas, Textil…) solo se crean en bases de demostración; las que ya existen se conservan.

## 24/09/2026

- El cajero ya puede guardar su vista preferida desde Mis preferencias: antes fallaba con «No tienes permiso para modificar registros Usuario».
- La ficha de producto del TPV vuelve a abrirse con Empleados instalado: los bloques nativos que el módulo reubica dejan un marcador en su sitio, porque otros módulos se anclan a ellos.

## 2.20260721 — 25/08/2026

- Licencia OPL-1 en toda la suite.

## 25/07/2026

- Migración a Odoo 19 y unificación en un solo módulo del filtro por etiquetas y del conmutador de vista, sobre las etiquetas de producto estándar.
