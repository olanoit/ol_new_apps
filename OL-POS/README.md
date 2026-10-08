OL-POS
======

**Punto de venta.**

Para qué es esta carpeta
------------------------

Módulos que extienden el TPV de Odoo 19: boletas y facturas electrónicas desde la caja, vendedor por venta, catálogo con filtro por etiquetas y vista de lista, y tema con marca blanca.

Qué va aquí
-----------

- Extensiones del frontend del TPV (componentes OWL, parches de `pos_store` y pantallas).
- Comprobantes electrónicos emitidos desde el TPV y su recibo.
- Diseño y marca del TPV, y flujos de venta en caja.

Qué no va aquí
--------------

- Catálogo de productos que no sea exclusivo del TPV → `OL-INVENTORY/`.
- Reportes impresos de facturas emitidas desde el backend → `OL-INVOICING/`.

Módulos disponibles
-------------------

Tabla generada desde los manifiestos con `python3 scripts/gen_addons_table.py`
(no editar a mano).

[//]: # (addons)
módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_l10n_pe_edi_pos](al_l10n_pe_edi_pos/) | 12.20261008 | OPL-1 | Boleta/Factura electrónica desde el punto de venta: selector de tipo de documento, diario por tipo y ticket con formato CPE SUNAT.
[al_pos_network_printer](al_pos_network_printer/) | 3.20261008 | OPL-1 | Imprime tickets y comandas del TPV en impresoras térmicas ESC/POS genéricas conectadas por red, sin IoT Box.
[al_pos_product_view](al_pos_product_view/) | 5.20261008 | OPL-1 | Chips de filtro por etiqueta de producto sobre el catálogo del TPV y conmutador cuadrícula/lista con filas compactas, popup de información enriquecido y preferencia por cajero.
[al_pos_theme](al_pos_theme/) | 2.20261008 | OPL-1 | Rediseño integral y marca blanca del TPV: tokens de diseño, logo, colores y nombre configurables por caja, sin rastros de Odoo.
[al_pos_vendedor](al_pos_vendedor/) | 3.20261008 | OPL-1 | Vendedor por orden en el TPV: selector en la pantalla de pago, vendedor predeterminado por sesión, vendedor en el ticket y en el análisis de ventas.
[//]: # (end addons)
