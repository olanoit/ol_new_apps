OL-INVENTORY
============

**Inventario.**

Para qué es esta carpeta
------------------------

Inventario y existencias: kárdex valorizado peruano (formatos 12.1 y 13.1) y reportes de stock.

Qué va aquí
-----------

- Reportes y procesos de inventario: kárdex, valorización, movimientos.
- Modelos de producto transversales que luego consumen otras áreas.

Qué no va aquí
--------------

- Guías de remisión impresas o electrónicas → `OL-INVOICING/`.
- Requerimientos de materiales de obra → `OL-PROJECTS/`.

Módulos disponibles
-------------------

Tabla generada desde los manifiestos con `python3 scripts/gen_addons_table.py`
(no editar a mano).

[//]: # (addons)
módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_l10n_pe_mrp_cost](al_l10n_pe_mrp_cost/) | 1.20261029 | OPL-1 | Costo hora desde la planilla, tareo por orden, cierre de costos del mes (ajuste de mano de obra y prorrateo de CIF) y costo por elemento.
[al_l10n_pe_stock_transfer](al_l10n_pe_stock_transfer/) | 5.20261027 | OPL-1 | Guía de remisión para todos los traslados de la empresa: entre establecimientos (04), compras que recoge (02, 07, 08), devoluciones (06) y exportación (09), y control de los bienes de terceros.
[al_mrp_piece_costing](al_mrp_piece_costing/) | 3.20261027 | OPL-1 | La orden de corte reparte su costo entre las piezas por área, material de origen y metros de tapacanto, e importa el despiece como productos-pieza.
[al_stock_base](al_stock_base/) | 7.20261027 | OPL-1 | Página «Logística PE» en las transferencias: un solo lugar para los datos peruanos (guía de remisión, PLE, obra…).
[ol_stock_kardex_pe](ol_stock_kardex_pe/) | 17.20261029 | OPL-1 | Registro de Inventario Permanente Valorizado (13.1) y en Unidades Físicas (12.1) — formato imprimible SUNAT y kardex interactivo
[//]: # (end addons)
