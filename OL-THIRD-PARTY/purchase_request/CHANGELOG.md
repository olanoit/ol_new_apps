Historial de cambios — Purchase Request
=======================================

Módulo de ForgeFlow y la Odoo Community Association (OCA), copiado del
repositorio OCA/purchase-workflow (rama 19.0). El historial de sus autores está
en `readme/`; aquí se registran las incorporaciones a este repositorio y las
correcciones propias, marcadas en el código con «OL».

## 20.0.1.0.3 — 02/11/2026

- Corrección propia: al agregar una línea de solicitud a una orden de compra existente, la cantidad se suma después de enlazar la línea de solicitud con la línea de compra; antes se omitía la propia línea y la cantidad quedaba corta. Los tests de OCA se ajustan a esa cantidad.

## 19.0.1.0.2 — 12/10/2026

- Incorporado como dependencia de `al_construction_material_request` y `al_construction_planner` (requerimiento de compra de la obra).
