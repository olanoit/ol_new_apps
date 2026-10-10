# TPV - Impresora de red ESC/POS (AL)

Guía funcional: [GUIA_FUNCIONAL.md](GUIA_FUNCIONAL.md)

Módulo técnico `al_pos_network_printer`. 
Impresión de tickets y comandas del **Punto de Venta de Odoo 19** en impresoras térmicas
**ESC/POS genéricas conectadas por red** (Xprinter, Zjiang, Gainscha y similares), sin necesidad
de una IoT Box.

---

## Índice

1. [¿Por qué este módulo? Odoo 19 nativo vs este módulo](#por-qué-este-módulo-odoo-19-nativo-vs-este-módulo)
2. [Arquitectura](#arquitectura)
3. [Instalación](#instalación)
4. [Configuración](#configuración)
5. [Seguridad](#seguridad)
6. [Limitaciones conocidas](#limitaciones-conocidas)
7. [Procedencia y licencia](#procedencia-y-licencia)
8. [Documentación adicional](#documentación-adicional)

---

## ¿Por qué este módulo? Odoo 19 nativo vs este módulo

Desde Odoo 19, el POS ya trae impresión de red **sin IoT Box** de forma nativa — pero solo para
impresoras **Epson**, usando el protocolo propietario ePOS-XML (impresión directa
navegador → impresora, vía `EpsonPrinter`). Las impresoras térmicas genéricas ESC/POS (las más
comunes y económicas en el comercio minorista: Xprinter, Zjiang, Gainscha, etc.) no hablan ese protocolo,
y el navegador no puede abrir un socket TCP crudo — así que sin este módulo, la única forma de
usarlas sin Epson es con una IoT Box.

| | Recibo principal | Impresoras de preparación (cocina/barra) |
|---|---|---|
| **Odoo 19 nativo** | Solo Epson (`pos.config.epson_printer_ip`, ePOS-XML) | Solo IoT Box o Epson (`pos.printer`, tipos `iot` / `epson_epos`) |
| **Este módulo agrega** | ESC/POS genérica de red (`escpos_printer_ip`) | ESC/POS genérica de red (`pos.printer`, tipo nuevo `escpos_network`) |

El módulo **no reemplaza ni duplica** nada de lo nativo: agrega un tercer tipo de conexión,
`escpos_network`, tanto para el recibo principal como para las impresoras de preparación por
categoría, dejando intactos los caminos Epson e IoT existentes.

## Arquitectura

El navegador no puede abrir un socket TCP crudo (por eso Epson resolvió esto con HTTP/ePOS-XML).
Para una impresora ESC/POS genérica, la única forma de hablarle por red es que **algo con acceso a
sockets** abra la conexión — acá ese "algo" es el propio backend de Odoo:

```
POS (navegador)                Backend de Odoo                    Impresora ESC/POS
──────────────                ─────────────────                   ─────────────────
render del ticket
  -> canvas -> JPEG
  (BasePrinter, core)
        │
        │ rpc() POST JSON
        ▼
  /al_pos_network_printer/print_receipt
        │                     1. valida IP:puerto contra
        │                        pos.config / pos.printer
        │                        (allow-list, ver Seguridad)
        │                     2. decodifica el JPEG
        │                     3. abre/reutiliza conexión TCP
        │                        persistente (una por impresora)
        │                                      │
        │                                      │ comandos ESC/POS
        │                                      │ (GS v 0 = raster image)
        │                                      ▼
        │                                 puerto 9100 (RAW/JetDirect)
        ◄──────────── {result: true/false} ────┘
```

- **Frontend**: `EscposNetworkPrinter` (`static/src/app/utils/printer/escpos_network_printer.js`)
  extiende el mismo `BasePrinter` que usan `EpsonPrinter` y `HWPrinter` en el core — la generación
  del JPEG del ticket (`canvas` → `toDataURL`) la sigue haciendo el core, este módulo solo cambia
  el transporte.
- **Backend**: `PosNetworkPrinterController` (`controllers/main.py`) recibe el JPEG en base64,
  valida el destino, y usa [`python-escpos`](https://python-escpos.readthedocs.io/) para convertir
  la imagen en comandos ESC/POS y enviarlos por un socket TCP mantenido vivo (keep-alive) hacia la
  impresora.
- Cada impresora tiene su propia conexión y su propio lock — imprimir en la impresora de una caja
  no bloquea a las demás.
- **Reintento en background (opt-in, apagado por defecto — solo modo "Backend de Odoo")**: con
  "Reintentar impresión fallida en segundo plano" activado (Ajustes/ficha del PDV,
  `pos.config.escpos_retry_queue_enabled`), si la impresión falla tras el retry-once síncrono de
  arriba (impresora apagada, sin papel, red caída un momento), se encola un job de
  [`queue_job`](https://github.com/OCA/queue) que reintenta solo — con espaciado creciente, hasta
  ~20 minutos — hasta que la impresora vuelva a responder, sin depender de que el cajero note o
  reintente el popup de impresión del core. Apagado (el default): un fallo se comporta exactamente
  igual que antes de que existiera esta pieza. Ver [Limitaciones conocidas](#limitaciones-conocidas)
  para el alcance exacto (no cubre el modo "Agente local").

## Instalación

1. **Librerías Python** en el servidor Odoo (mismo entorno donde corre `odoo-bin`):
   ```
   pip install -r OL-POS/al_pos_network_printer/requirements.txt
   ```
   En los servidores que montan el repositorio en `shared-addons`, el `requirements.txt` de la
   raíz de `ol_new_apps` ya las incluye y se instalan al arrancar el contenedor. Sin ellas el
   módulo se instala igual; solo falla al imprimir en una impresora `escpos_network`, con un
   error claro.
2. **`queue_job`** (OCA, incluido en `OL-THIRD-PARTY/`): Odoo lo instala solo como dependencia.
   Para que los reintentos en segundo plano se ejecuten, el servidor debe cargarlo como módulo
   global: `--load=base,web,queue_job` (o `server_wide_modules` en el `.conf`). Opcionalmente, en
   la sección `[queue_job]` del `.conf`, el canal propio de este módulo:
   `channels = root:2,root.escpos_print:2`.
3. Instalar **«TPV - Impresora de red ESC/POS (AL)»** desde Aplicaciones (categoría `OL-POS`).

Guía paso a paso más detallada (con tabla de solución de problemas): ver
[`docs/CONFIGURACION_ODOO_PASO_A_PASO.md`](docs/CONFIGURACION_ODOO_PASO_A_PASO.md).

## Configuración

### Recibo principal (uno por punto de venta)

**Ajustes → Punto de Venta → (seleccionar el PDV) → Dispositivos conectados → ePos Printer**

1. Activar "ePos Printer" (`other_devices`).
2. Completar **«IP ESC/POS»** con la IP de la impresora y el puerto
   (9100 por defecto).
3. Dejar vacío el campo de IP Epson de Odoo — no se pueden configurar ambos a la vez (hay una
   validación que lo impide, ver [Seguridad](#seguridad)).
4. Botón **"Probar impresora"** (visible con método de impresión "Backend de Odoo" e IP
   completada): imprime un ticket de texto real (sin depender del navegador ni de una venta) para
   confirmar que el backend puede alcanzar la impresora — ver
   [Verificación sin impresora física](#verificación-sin-impresora-física) para probarlo sin
   impresora a mano. En método "Agente local" este botón no aplica (el backend no tiene ruta de red
   hacia la impresora en ese modo); ahí usar "Probar agente", más abajo en la misma sección.
5. **"Imprimir automáticamente al pagar"** (`escpos_auto_print`): al marcar y guardar, el ticket
   sale solo apenas se confirma el pago, sin pantalla de recibo intermedia (activa
   `iface_print_auto` + `iface_print_skip_screen` del core juntos). Al desmarcar y guardar, vuelve
   el proceso normal (pantalla de recibo, impresión manual). Aplica igual sin importar el método de
   impresión (backend/agente) o el tipo de impresora (ESC/POS de red, Epson, IoT Box).

### Impresoras de preparación (cocina/barra, opcional — una o más por categoría de producto)

**Punto de Venta → Configuración → Preparation Printers → Nuevo**

1. **Printer Type**: elegir "Use a generic ESC/POS network printer".
2. Completar la IP y el puerto de la impresora.
3. Seleccionar las categorías de producto que debe imprimir esa impresora.
4. Asociar la impresora al PDV correspondiente (campo "Order Printers" en la configuración del
   PDV) y activar "Order Printer" (`is_order_printer`) en ese PDV.

### Verificación sin impresora física

Para probar el camino completo (Odoo → red → impresora) sin tener una impresora a mano, se puede
simular una con `nc`:
```
nc -l -p 9100 > /tmp/ticket_capturado.bin
```
y apuntar el campo de IP a `127.0.0.1` / puerto `9100`. Al imprimir desde el POS, `ticket_capturado.bin`
debería empezar con los bytes `1d 76 30` (comando ESC/POS `GS v 0`, imagen raster).

El botón **"Probar impresora"** de la ficha del PDV sirve para lo mismo sin necesitar el POS
abierto ni hacer una venta: imprime un ticket de texto de prueba directo desde el backend contra la
IP/puerto configurados. Con el `nc` de arriba escuchando, `ticket_capturado.bin` va a contener el
texto plano (comandos ESC/POS de texto, no una imagen rasterizada — a diferencia del ticket real).

## Seguridad

El endpoint HTTP (`/al_pos_network_printer/print_receipt`) es necesariamente público
(`auth='public'`, igual que `/hw_proxy/*` del core) porque el POS puede correr en modo kiosco sin
una sesión de backend completa. Para que eso no se convierta en un proxy SSRF abierto (cualquiera
podría, si no, usar el servidor Odoo para abrir conexiones TCP a cualquier IP/puerto de la red
interna), la ruta valida que el IP:puerto recibido **coincida exactamente con una impresora ya
configurada** en `pos.config` o `pos.printer` — cualquier otro destino se rechaza con
`PRINTER_NOT_CONFIGURED` antes de intentar ninguna conexión. Este es el mismo nivel de confianza
que Odoo ya le da a la IP de una impresora Epson o de una IoT Box: solo lo que un administrador
configuró explícitamente.

Además:
- El payload de imagen tiene un límite de tamaño (5 MB) antes de decodificar el base64.
- No se habilita CORS (`cors`) en la ruta: la llama el propio POS de Odoo, nunca otro origen.

## Limitaciones conocidas

- **Solo impresoras genéricas ESC/POS de red (puerto RAW/JetDirect, típicamente 9100).** Para
  impresoras Epson use el campo nativo de Odoo (ePOS-XML); para impresoras USB/serial se necesita
  una IoT Box.
- **Requiere la misma red local que el servidor Odoo** (o una ruta de red hacia ella), igual que
  una IoT Box — la impresión la hace el backend de Odoo, no el navegador del cajero. En la práctica
  esto significa un servidor Odoo propio/on-premise en la misma red que el local — **en Odoo.sh no
  funciona** (el hosting de Odoo no tiene ni puede tener ruta de red hacia la impresora del
  cliente). Para esos casos está el **agente local** (modo «Agente local», ver
  [`agent/README.md`](agent/README.md)).
- **Despliegues con varios *workers* de Odoo**: cada worker (proceso) mantiene su propio registro
  de conexiones en memoria. No afecta la corrección de la impresión, pero puede haber más de una
  conexión TCP abierta hacia la misma impresora si el tráfico se reparte entre varios workers.
- **La cola de reintento en background (ver [Arquitectura](#arquitectura)) solo aplica en modo
  "Backend de Odoo".** En modo "Agente local" (Camino A) el navegador del cajero le habla directo al
  agente standalone, sin pasar por el backend de Odoo — el backend nunca se entera de un fallo ahí,
  así que no hay nada que encolar. En ese modo el único mecanismo de recuperación sigue siendo el
  popup de reintento manual del core. `open_cashbox` tampoco se encola en ningún modo: abrir el
  cajón solo tiene sentido en el momento del pago, no "más tarde".

## Procedencia y licencia

Adaptación a la suite AL del módulo `mblz_pos_network_printer` de Mobilize: nombre técnico,
rutas, agente y textos sin la marca de origen, y sin la integración con su módulo de
bonificaciones (el «Camino B» del agente queda como canal genérico para los comprobantes en PDF
que imprima el backend). Licencia **OPL-1**, como el resto de módulos propios de la suite (ver
`LICENSE`). Depende de `queue_job` (OCA, LGPL-3), incluido en `OL-THIRD-PARTY/`.

El historial de versiones está en [`CHANGELOG.md`](CHANGELOG.md).

## Documentación adicional

- [`docs/CONFIGURACION_ODOO_PASO_A_PASO.md`](docs/CONFIGURACION_ODOO_PASO_A_PASO.md) — configuración
  en Odoo paso a paso, con tabla de solución de problemas.
- [`docs/IMPRESORAS_RECOMENDADAS_PARA_PRUEBAS.md`](docs/IMPRESORAS_RECOMENDADAS_PARA_PRUEBAS.md) —
  impresoras térmicas ESC/POS de red probadas o recomendadas.
- [`agent/README.md`](agent/README.md) — agente local (Caminos A y B), variables de entorno y
  problemas conocidos.
- [`agent/docs/GUIA_INSTALACION_WINDOWS.md`](agent/docs/GUIA_INSTALACION_WINDOWS.md),
  [`agent/docs/GUIA_SERVICIO_WINDOWS.md`](agent/docs/GUIA_SERVICIO_WINDOWS.md) y
  [`agent/docs/GUIA_INSTALACION_TECNICO.md`](agent/docs/GUIA_INSTALACION_TECNICO.md) — instalación
  del agente en Windows (con interfaz o como servicio) y en Linux.
- [`agent/docs/GUIA_CLOUDFLARE_TUNNEL.md`](agent/docs/GUIA_CLOUDFLARE_TUNNEL.md) — publicar el agente
  con HTTPS mediante un túnel de Cloudflare.
