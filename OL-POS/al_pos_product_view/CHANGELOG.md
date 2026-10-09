Historial de cambios — TPV - Catálogo de productos: filtro por etiquetas y vista lista (AL)
===========================================================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_pos_product_view.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

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
