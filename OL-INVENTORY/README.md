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
[al_l10n_pe_stock_transfer](al_l10n_pe_stock_transfer/) | 1.20261010 | OPL-1 | Guía de remisión para traslados entre establecimientos (motivo 04) y control de los bienes de terceros en inventario y en la guía.
[al_stock_base](al_stock_base/) | 1.20261008 | OPL-1 | Página «Logística PE» en las transferencias: un solo lugar para los datos peruanos (guía de remisión, PLE, obra…).
[ol_stock_kardex_pe](ol_stock_kardex_pe/) | 12.20261009 | OPL-1 | Registro de Inventario Permanente Valorizado (13.1) y en Unidades Físicas (12.1) — formato imprimible SUNAT y kardex interactivo
[//]: # (end addons)
