# Configurar `al_pos_network_printer` en Odoo — guía paso a paso

Guía general (no atada a una marca de impresora en particular; para elegir una, ver
[`IMPRESORAS_RECOMENDADAS_PARA_PRUEBAS.md`](IMPRESORAS_RECOMENDADAS_PARA_PRUEBAS.md)) de cómo dejar el módulo
funcionando en un servidor Odoo 19 para que el POS pueda imprimir **directamente** (recibo
principal y/o comandas de cocina/barra) en una impresora térmica ESC/POS genérica conectada por
red, sin IoT Box.

> ⚠️ **Antes de empezar**: este módulo asume que el servidor Odoo tiene acceso de red directo a la
> impresora (misma LAN, o una ruta de red hacia ella) — es el propio backend de Odoo el que abre el
> socket TCP. Esto funciona en un servidor propio/on-premise (el caso de este proyecto) o en una VM
> en la misma red que el local. **En Odoo.sh no funciona tal cual** — ahí hace falta el agente
> local de [`../agent/README.md`](../agent/README.md), que corre en la red del local.

## Índice

1. [Prerrequisitos](#1-prerrequisitos)
2. [Paso 1 — Instalar las librerías Python en el servidor](#paso-1--instalar-las-librerías-python-en-el-servidor)
3. [Paso 2 — Instalar el módulo en Odoo](#paso-2--instalar-el-módulo-en-odoo)
4. [Paso 3 — Configurar el recibo principal del PDV](#paso-3--configurar-el-recibo-principal-del-pdv)
5. [Paso 4 — (Opcional) Configurar impresoras de preparación por categoría](#paso-4--opcional-configurar-impresoras-de-preparación-por-categoría)
6. [Paso 5 — Verificar la conexión sin tener la impresora a mano](#paso-5--verificar-la-conexión-sin-tener-la-impresora-a-mano)
7. [Paso 6 — Probar imprimiendo de verdad desde el POS](#paso-6--probar-imprimiendo-de-verdad-desde-el-pos)
8. [Solución de problemas](#8-solución-de-problemas)

## 1. Prerrequisitos

- Un servidor Odoo 19 con acceso a la misma red (o una red enrutada) que la impresora térmica.
- La impresora debe hablar **ESC/POS por el puerto RAW/JetDirect** (normalmente TCP 9100) — es el
  estándar de facto de casi cualquier térmica de recibos de 58/80mm con puerto Ethernet o Wi-Fi
  (Xprinter, Zjiang, Gainscha, MUNBYN, etc.). Impresoras **Epson** no necesitan este módulo — usan
  el campo nativo de Odoo (ver la nota al final del Paso 3).
- La impresora ya debe tener una **IP fija** (o reservada por DHCP) dentro de esa red — si la IP
  cambia sola, el módulo deja de encontrarla. Ver la sección «Al recibir la impresora» de
  [`IMPRESORAS_RECOMENDADAS_PARA_PRUEBAS.md`](IMPRESORAS_RECOMENDADAS_PARA_PRUEBAS.md#al-recibir-la-impresora)
  si hace falta.
- Acceso de administrador a Odoo (grupo `point_of_sale.group_pos_manager` como mínimo) y acceso de
  shell al servidor para instalar la librería Python (Paso 1).

## Paso 1 — Instalar las librerías Python en el servidor

El módulo se puede **instalar sin esto** — el POS sigue funcionando con Epson/IoT Box normalmente —
pero al intentar imprimir en una impresora `escpos_network` sin la librería, falla con un mensaje
claro pidiendo instalarla. Hace falta antes de probar nada.

En el mismo entorno/virtualenv donde corre `odoo-bin`:

```bash
pip install -r ol_new_apps/OL-POS/al_pos_network_printer/requirements.txt
```

(o el `requirements.txt` de la raíz del repositorio `ol_new_apps`, si se instalan las
dependencias de todos sus módulos a la vez)

o, directo:

```bash
pip install python-escpos pymupdf
```

| Paquete | Para qué se usa | ¿Obligatorio? |
|---|---|---|
| `python-escpos` | Convierte la imagen del ticket (JPEG) a comandos ESC/POS y abre el socket TCP hacia la impresora. | Sí — sin esto no imprime nada. |
| `pymupdf` | Rasteriza un PDF completo página por página para imprimirlo en la misma impresora (usado por `print_pdf_bytes()`, por ejemplo para los comprobantes en PDF que genere otro módulo). | Solo si algún otro módulo necesita imprimir PDFs por esta vía — el ticket normal del POS no la usa. |
| `Pillow` (PIL) | Manipula la imagen antes de enviarla. | Ya viene como dependencia transitiva de `python-escpos` (y normalmente ya está instalada, Odoo la necesita para otras cosas). |

No hace falta reiniciar Odoo todavía — eso es el Paso 2.

## Paso 2 — Instalar el módulo en Odoo

1. Confirmar que la carpeta `OL-POS/` del repositorio `ol_new_apps` está en el `addons_path` del
   servidor (`odoo.conf`/`cfg`, clave `addons_path`), y también `OL-THIRD-PARTY/`, donde está
   `queue_job` (OCA).
2. **Aplicaciones → Actualizar lista de aplicaciones** (con el modo desarrollador activo si hace
   falta) para que Odoo vea el módulo nuevo.
3. Buscar **«TPV - Impresora de red ESC/POS (AL)»** e instalarlo. Depende de `point_of_sale` y de
   `queue_job` (OCA, incluido en `OL-THIRD-PARTY/`) — no agrega ningún modelo nuevo pesado, solo
   2 campos en `pos.config`/`pos.printer` y 2 rutas HTTP. Para que los reintentos de impresión se
   ejecuten, el servidor debe arrancar con `--load=base,web,queue_job` (o `server_wide_modules`
   equivalente en el `.cfg`).
4. Si el servidor ya estaba corriendo, no hace falta reiniciarlo para que la instalación surta
   efecto (a diferencia de una actualización posterior de este mismo módulo si cambia código
   Python — ahí sí hace falta un restart completo del proceso, no solo `-u`).

## Paso 3 — Configurar el recibo principal del PDV

Esto es lo mínimo para que **"Imprimir recibo"** desde el POS salga por la impresora ESC/POS en vez
de abrir el diálogo de impresión del navegador.

**Ajustes → Punto de Venta → (seleccionar el punto de venta) → sección "Dispositivos conectados"**

1. Activar el toggle **"ePos Printer"** (`pos.config.other_devices`). Este campo es del *core* de
   Odoo — solo controla si esta sección de la pantalla se ve; hay que activarlo para que aparezcan
   los campos del Paso 3.2, aunque la impresora final NO sea Epson.
2. Con el toggle activo aparece una fila nueva agregada por este módulo, debajo del campo nativo de
   Epson:
   - **IP de impresora ESC/POS genérica (no Epson)** → la IP (o hostname) de la impresora, ej.
     `192.168.0.252`.
   - **Puerto** → `9100` por defecto (el estándar RAW/JetDirect — no cambiarlo salvo que la
     impresora use otro).
3. **Dejar vacío** el campo nativo de Odoo **"Epson Printer IP"** — no se pueden completar los dos
   a la vez. Si se intenta, Odoo tira un error de validación al guardar
   ("Configure solo una impresora de recibo principal...").
4. Guardar.
5. (Opcional, recomendado) En la misma pantalla, activar **"Imprimir automáticamente"**
   (`iface_print_auto`) si se quiere que el ticket salga solo al confirmar el pago, sin que el
   cajero tenga que apretar "Imprimir recibo" a mano.

Con esto ya alcanza para el caso más común: un solo recibo, una sola impresora.

> **¿Por qué no usar el campo Epson nativo de Odoo?** Ese campo solo sirve si la impresora es
> realmente una Epson (habla el protocolo propietario ePOS-XML, impresión directa
> navegador → impresora, sin pasar por el backend). Las impresoras ESC/POS genéricas (la inmensa
> mayoría de las térmicas económicas del comercio minorista) no hablan ese protocolo — de ahí este
> módulo, que agrega el tercer camino (`escpos_network`) pasando por el backend de Odoo. Ver
> [`README.md`](../README.md#arquitectura) para el diagrama completo.

## Paso 4 — (Opcional) Configurar impresoras de preparación por categoría

Solo hace falta si además de/en vez del recibo principal, se quiere que ciertas categorías de
producto (ej. "Bebidas" a la barra, "Comida" a cocina) impriman una comanda aparte en otra
impresora física.

**Punto de Venta → Configuración → Impresoras de preparación → Nuevo**

1. **Tipo de impresora**: elegir **"Usar una impresora ESC/POS genérica de red"**.
2. Completar **IP de la impresora ESC/POS** y **Puerto** (9100 por defecto).
3. En **Categorías de producto**, elegir las categorías que debe imprimir esta impresora
   específica.
4. Guardar la impresora, ir al PDV correspondiente (**Ajustes → Punto de Venta →** el PDV) y:
   - En **"Impresoras de comanda"** (`order_printer_ids`), agregar la impresora recién creada.
   - Activar **"Order Printer"** (`is_order_printer`) si no está activo — sin esto el PDV nunca
     envía nada a imprimir por esta vía, aunque la impresora esté bien configurada.

Se pueden configurar varias impresoras de preparación por PDV, cada una con sus propias categorías
— cada una es independiente de la del recibo principal (Paso 3) y entre sí (conexión TCP y lock
propios, ver [`README.md`](../README.md#arquitectura)).

## Paso 5 — Verificar la conexión sin tener la impresora a mano

Útil para separar "¿el problema es de red/config de Odoo?" de "¿el problema es la impresora
física?" antes de tener el hardware real conectado, o para probar en un ambiente de desarrollo.

En el servidor (o cualquier máquina en la misma red que Odoo pueda alcanzar), simular una impresora
con `nc`:

```bash
nc -l -p 9100 > /tmp/ticket_capturado.bin
```

Apuntar el campo de IP del Paso 3 (o 4) a la IP de esa máquina — `127.0.0.1` si es el mismo
servidor — y el puerto a `9100`. Al imprimir un recibo desde el POS, `ticket_capturado.bin` debería
empezar con los bytes `1d 76 30` (comando ESC/POS `GS v 0` — "imagen raster"), señal de que Odoo
armó y mandó el comando correctamente. Si ese archivo queda vacío o nunca se crea, el problema está
del lado de Odoo (revisar la [tabla de la sección 8](#8-solución-de-problemas)), no de la impresora.

## Paso 6 — Probar imprimiendo de verdad desde el POS

1. Abrir una sesión de POS en el punto de venta configurado.
2. Agregar un producto cualquiera, cobrar.
3. En la pantalla de recibo, apretar **"Imprimir recibo"** (o esperar el auto-print si se activó
   `iface_print_auto` en el Paso 3.5).
4. Debería salir un ticket físico impreso — sin ningún diálogo de impresión del navegador de por
   medio.

Si en cambio se abre el diálogo de impresión del navegador (`window.print()`), Odoo no está usando
la impresora de red configurada — ver la fila correspondiente en la tabla de abajo.

## 8. Solución de problemas

| Síntoma | Causa probable | Qué revisar |
|---|---|---|
| Se abre el diálogo de impresión del navegador en vez de imprimir físico | El POS no detectó ninguna impresora configurada, o `escpos_printer_ip` quedó vacío | Revisar Paso 3 completo — en particular, si se guardó Ajustes desde otra pestaña sin ese campo relleno, puede haberse pisado el valor. Recargar la pestaña del POS después de guardar. |
| Error "Falta instalar 'python-escpos'" o similar al imprimir | La librería no está instalada en el entorno donde corre `odoo-bin` | Repetir el Paso 1 — verificar que sea el mismo virtualenv/entorno que usa el proceso real de Odoo (`pip show python-escpos` desde ahí). |
| RPC/timeout al imprimir, o error de conexión | La impresora está apagada, la IP cambió, o el servidor Odoo no tiene ruta de red hasta ella | Verificar con `ping <IP>` y `nc -zv <IP> 9100` desde el propio servidor Odoo (no desde la máquina del cajero — es el backend el que necesita la ruta). |
| El PDV rechaza guardar con "Configure solo una impresora de recibo principal..." | Quedaron completos a la vez el campo Epson nativo y el ESC/POS de este módulo | Vaciar uno de los dos — no pueden coexistir para el recibo principal (Paso 3.3). |
| Las comandas de cocina/barra no salen, pero el recibo principal sí | Falta activar "Order Printer" en el PDV, o la impresora de comanda no tiene categorías asignadas | Revisar Paso 4.4 completo. |
| Todo configurado bien pero nunca imprime nada, ni error visible | El servidor Odoo corre en Odoo.sh o en un hosting sin ruta de red hacia la impresora | Este módulo necesita que el backend de Odoo tenga acceso directo a la LAN de la impresora; si no lo tiene, usar el agente local de [`../agent/README.md`](../agent/README.md). |
