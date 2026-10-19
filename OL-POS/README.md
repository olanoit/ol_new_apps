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
[al_l10n_pe_edi_pos](al_l10n_pe_edi_pos/) | 16.20261019 | OPL-1 | Boleta/Factura electrónica desde el punto de venta: selector de tipo de documento, diario por tipo y ticket con formato CPE SUNAT.
[al_l10n_pe_pos_loyalty](al_l10n_pe_pos_loyalty/) | 1.20261019 | OPL-1 | La venta de tarjetas de regalo y recargas del monedero no lleva comprobante y su canje es una forma de pago: la boleta o factura sale con el IGV completo.
[al_pos_network_printer](al_pos_network_printer/) | 4.20261009 | OPL-1 | Imprime tickets y comandas del TPV en impresoras térmicas ESC/POS genéricas conectadas por red, sin IoT Box.
[al_pos_online_payment](al_pos_online_payment/) | 1.20261016 | OPL-1 | Corrige el TPV de Odoo 19 que, tras un cobro en línea, muestra el pago dos veces y un cambio igual al importe pagado.
[al_pos_payment_gateway](al_pos_payment_gateway/) | 6.20261018 | OPL-1 | Cada pasarela (Izipay, Niubiz, Culqi…) como método de pago propio del TPV: el cliente paga con el QR en su teléfono y las devoluciones vuelven a su tarjeta.
[al_pos_pe_partner_lookup](al_pos_pe_partner_lookup/) | 2.20261014 | OPL-1 | En la lista de clientes del TPV, un RUC o DNI que no está registrado se crea en un clic con los datos de SUNAT/RENIEC y queda elegido para la venta.
[al_pos_pe_wallet_qr](al_pos_pe_wallet_qr/) | 1.20261014 | OPL-1 | El QR de cobro de Yape, Plin u otra billetera como método de pago QR del TPV: se muestra en la caja y en la pantalla del cliente, y el cajero confirma el pago.
[al_pos_product_view](al_pos_product_view/) | 7.20261011 | OPL-1 | Chips de filtro por etiqueta de producto sobre el catálogo del TPV y conmutador cuadrícula/lista con filas compactas, popup de información enriquecido y preferencia por cajero.
[al_pos_theme](al_pos_theme/) | 3.20261018 | OPL-1 | Rediseño integral y marca blanca del TPV: tokens de diseño, logo, colores y nombre configurables por caja, sin rastros de Odoo.
[al_pos_vendedor](al_pos_vendedor/) | 4.20261011 | OPL-1 | Vendedor por orden en el TPV: selector en la pantalla de pago, vendedor predeterminado por sesión, vendedor en el ticket y en el análisis de ventas.
[//]: # (end addons)
