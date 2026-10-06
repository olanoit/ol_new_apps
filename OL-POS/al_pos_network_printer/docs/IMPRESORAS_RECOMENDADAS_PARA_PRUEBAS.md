# Impresoras recomendadas para probar `al_pos_network_printer`

Este módulo imprime en impresoras térmicas **ESC/POS genéricas de red** (puerto RAW/JetDirect,
por defecto **9100**). No sirve para impresoras solo-USB o solo-Bluetooth, y no hace falta para
impresoras Epson usadas de forma nativa (Odoo 19 ya las cubre con su propio protocolo ePOS-XML,
sin este módulo).

Único requisito al comprar: que la ficha del producto liste **Ethernet / LAN / RJ45** como una de
sus interfaces (casi todas traen también USB). El puerto RAW 9100 viene activado de fábrica en la
inmensa mayoría de estas impresoras "ESC/POS compatible" — es el estándar de facto del segmento
económico chino que domina Amazon UK en esta categoría.

Esta lista está armada sobre **Amazon UK (amazon.co.uk)**, con enlaces
verificados. Los precios son aproximados (Amazon los cambia todo el tiempo) — confirmar el precio
vigente en cada link antes de comprar.

## Para probar el caso real del módulo (impresora genérica, no Epson)

| # | Modelo | Interfaces | Precio aprox. | Enlace |
|---|--------|-----------|----------------|--------|
| 1 | **MUNBYN** 80mm Thermal Receipt Printer, USB + Ethernet, ESC/POS | USB, Ethernet | ~£50-£65 | [amazon.co.uk](https://www.amazon.co.uk/Thermal-MUNBYN-Ethernet-Restaurant-Business/dp/B07872SDT9) |
| 2 | **NETUM NT-806** 80mm POS Printer, USB + Ethernet LAN, ESC/POS | USB, Ethernet (LAN) | ~£55-£70 | [amazon.co.uk](https://www.amazon.co.uk/Thermal-Receipt-NETUM-Ethernet-NT-806W/dp/B07Y5B55PP) |
| 3 | **CISSIYOG** 80mm Thermal Receipt Printer, USB + Ethernet, ESC/POS | USB, Ethernet | ~£45-£60 | [amazon.co.uk](https://www.amazon.co.uk/Thermal-Receipt-Ethernet-Restaurant-Business/dp/B0CM6DHW7R) |
| 4 | **Rongta** POS Printer, USB + Serial + Ethernet, ESC/POS | USB, Serial, Ethernet | ~£55-£75 | [amazon.co.uk](https://www.amazon.co.uk/Rongta-Printer-Restaurant-Ethernet-Interface/dp/B019W8K2T4) |

Cualquiera de las 4 sirve para validar el flujo completo (recibo principal vía
`escpos_printer_ip` en `pos.config`, o impresora de preparación vía `pos.printer` con
`printer_type = escpos_network`). Recomiendo la **#1 (MUNBYN)** o la **#2 (NETUM)** como primera
compra — son las que más reseñas y disponibilidad tienen en amazon.co.uk ahora mismo.

Si querés dos impresoras para probar también el escenario **multi-impresora por categoría**
(recibo principal + comanda de cocina/barra), pedí dos de la lista de arriba — no hace falta que
sean del mismo modelo.

## Opcional: control cruzado con una Epson real

Las Epson TM-* con Ethernet aceptan impresión ESC/POS cruda por el puerto 9100 **además** de su
protocolo ePOS-XML propio. Sirven para comparar la calidad de impresión y confirmar que el módulo
no rompe nada si alguien las usa como `escpos_network` en vez de configurarlas de forma nativa.
Son bastante más caras — no son necesarias para probar el módulo, solo un extra.

| Modelo | Interfaces | Precio aprox. | Enlace |
|--------|-----------|----------------|--------|
| **Epson TM-T20III** (C31CH51012A0), USB + Ethernet, ESC/POS & ePOS | USB, Ethernet | ~£175-£195 | [amazon.co.uk](https://www.amazon.co.uk/EPSON-PRINT-TM-T20III-ETHERNET-ADAPTER/dp/B07YLS1RRQ) |
| **Epson TM-m30** (122A0), USB + Ethernet | USB, Ethernet | ~£220-£260 | [amazon.co.uk](https://amazon.co.uk/Epson-C31CE95122A0-TM-M30-122A0-ETHERNET/dp/B016DQ1X78) |

## Otra opción con Ethernet: Star Micronics TSP143 LAN

| Modelo | Interfaces | Precio aprox. | Enlace |
|--------|-----------|----------------|--------|
| **Star Micronics TSP143LAN** | Ethernet | ~£150-£190 | [amazon.co.uk](https://www.amazon.co.uk/Star-Micronics-TSP143-Cutter-Connection-Grey/dp/B006Z488AE) |

⚠️ **Nota importante sobre Star**: de fábrica, muchos modelos Star vienen configurados en
"Star Line Mode" (su propio set de comandos, no ESC/POS estándar). Hay que cambiarla a modo de
**emulación ESC/POS** desde la utilidad de configuración de Star (o el switch/dip correspondiente
según el modelo) antes de que funcione con `python-escpos` y por lo tanto con este módulo. No es
la primera opción recomendada por esto — mejor partir con MUNBYN/NETUM/CISSIYOG/Rongta, que ya
vienen en modo ESC/POS puro de fábrica.

## Al recibir la impresora

1. Asignarle una IP fija en la red (DHCP reservado en el router, o configuración manual desde el
   panel/botones de la impresora o su utilidad de configuración por USB — cada marca trae la suya).
2. Confirmar que el puerto RAW/JetDirect esté en **9100** (viene así de fábrica en el 100% de los
   casos vistos; casi nunca hay que tocarlo).
3. Probar la conexión de red antes de tocar Odoo:
   ```
   telnet <IP_impresora> 9100
   ```
   o, para mandarle texto de prueba desde la terminal sin pasar por Odoo:
   ```
   echo "Hola mundo" | nc <IP_impresora> 9100
   ```
4. Recién ahí cargar la IP y el puerto en Odoo (Ajustes > Punto de Venta > Dispositivos
   conectados, o Preparation Printers) — ver `README.md`, sección "Configuración".

Sin impresora física a mano todavía, `README.md` (sección "Verificación sin impresora física")
explica cómo simular una con `nc -l -p 9100` para probar el módulo mientras llega el hardware.
