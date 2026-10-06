# -*- coding: utf-8 -*-
{
    'name': 'TPV - Impresora de red ESC/POS (AL)',
    'summary': 'Imprime tickets y comandas del TPV en impresoras térmicas ESC/POS '
               'genéricas conectadas por red, sin IoT Box.',
    'description': """
Impresora de red ESC/POS para el TPV
====================================
Adaptación a la suite AL de la impresora de red del TPV de Mobilize
(``mblz_pos_network_printer``).

* **Tercer tipo de conexión** ``escpos_network``, junto a Epson e IoT, para el
  recibo principal y para las impresoras de preparación por categoría
  (Xprinter, Zjiang, Gainscha, MUNBYN y otras térmicas ESC/POS de red).
* **Dos formas de imprimir**: desde el servidor de Odoo (on-premise) o con un
  **agente local** en la tienda cuando el servidor no llega a la impresora
  (Odoo.sh u otra nube). El agente, para Windows o Linux, va en ``agent/``.
* **Reintento en segundo plano** con ``queue_job`` si la impresora no
  responde, para no perder el ticket; se abandona a los ~20 minutos.
* **Seguridad**: la ruta de impresión solo acepta IP y puerto configurados en
  una caja o impresora activa (sin uso como proxy), con token para el agente.
    """,
    'author': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'maintainer': 'CRISTÓBAL OCH <olanoit@gmail.com>',
    'website': 'https://www.altabpo.com',
    'category': 'OL-POS/Apps',
    'version': '1.20261006',
    'license': 'OPL-1',
    # Odoo 19 ya imprime por red sin IoT Box, pero solo en Epson (ePOS-XML:
    # ``pos.config.epson_printer_ip`` y ``printer_type = 'epson_epos'``). Este
    # módulo agrega ``escpos_network`` para las térmicas ESC/POS genéricas.
    #
    # ``queue_job`` (OCA, en OL-THIRD-PARTY/): cuando el servidor no alcanza la
    # impresora (modo «backend», ver ``pos.config.escpos_printer_mode``), se
    # encola un trabajo que reintenta solo hasta que vuelva a responder, en
    # vez de perder el ticket si el cajero ignora el aviso del TPV (ver
    # ``controllers/main.py::retry_print_receipt``). Para que los trabajos se
    # ejecuten, el servidor debe cargar ``queue_job`` como módulo global
    # (``--load=base,web,queue_job``).
    "depends": ["point_of_sale", "queue_job"],
    "external_dependencies": {
        # Import diferido en controllers/main.py: el módulo se instala y el
        # POS sigue funcionando igual sin esta librería; solo falla al
        # intentar imprimir efectivamente en una impresora `escpos_network`
        # (ver PosNetworkPrinterController). `pymupdf` es más diferido
        # todavía: solo hace falta para `print_pdf_bytes()` (imprimir un PDF
        # completo que genere otro módulo) — el ticket
        # normal del POS no la necesita en absoluto.
        "python": ["python-escpos", "pymupdf"],
    },
    "data": [
        "data/queue_job_channel_data.xml",
        "data/queue_job_function_data.xml",
        "views/pos_printer_views.xml",
        "views/pos_config_view.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "al_pos_network_printer/static/src/app/utils/printer/escpos_network_printer.js",
            "al_pos_network_printer/static/src/app/components/agent_authorization_dialog/agent_authorization_dialog.js",
            "al_pos_network_printer/static/src/app/components/agent_authorization_dialog/agent_authorization_dialog.xml",
            "al_pos_network_printer/static/src/overrides/services/pos_store.js",
        ],
        # Botón "Probar agente" (widget de vista) en Ajustes/la ficha del
        # PDV — corre en el cliente web de backend, no en el POS, mismo
        # bundle que usa el core para `point_of_sale_test_epos` (ver
        # point_of_sale/__manifest__.py).
        "web.assets_backend": [
            "al_pos_network_printer/static/src/backend/test_escpos_agent/*",
        ],
    },
    "installable": True,
    "application": False,
}
