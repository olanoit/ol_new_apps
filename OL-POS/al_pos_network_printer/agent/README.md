# Agente local ESC/POS — Camino A (Fase 1) + Camino B (Fase 2)

Corre en la red del local (no en el servidor de Odoo). Pensado para cuando el servidor Odoo no
tiene ruta de red hacia la impresora (Odoo.sh, o cualquier hosting fuera de la LAN del local) — en
una instalación on-premise normal **no hace falta este agente en absoluto**, el módulo sigue
imprimiendo directo desde el backend.

Cubre 2 caminos independientes, cada uno con su propia forma de activarse:

- **Camino A** (ticket normal del POS) — servidor HTTP mínimo: el navegador del cajero, que ya
  está en la red de la impresora, le habla directo acá. Siempre activo (necesita
  `AL_AGENT_ALLOWED_PRINTERS`, obligatoria).
- **Camino B** (comprobantes en PDF que imprime el backend de Odoo, por ejemplo los que genere
  otro módulo, publicados por el bus) — cliente websocket saliente hacia el bus de Odoo: lo
  imprime el backend (un job, sin navegador de por medio), así que el agente necesita
  estar conectado de antemano para recibirlo. Opcional — solo se activa si están las 3 variables
  `AL_AGENT_ODOO_URL`/`AL_AGENT_ODOO_DB`/`AL_AGENT_BUS_CHANNEL`; si falta alguna, el agente
  arranca igual, solo con el Camino A.

Este directorio es standalone — no depende de Odoo ni se instala como módulo. Es un script Python.

**Estructura**: código (`al_pos_local_agent.py`, `al_pos_local_agent_gui.py`) y empaquetado
(`AgenteEscpos.spec` + `installer.iss` + `build_installer.bat` para la GUI;
`AgenteEscposServicio.spec` + `build_service_exe.bat` para el `.exe` sin GUI pensado para
NSSM, ver [`docs/GUIA_SERVICIO_WINDOWS.md`](docs/GUIA_SERVICIO_WINDOWS.md);
`al-pos-local-agent.service.example` para systemd) viven acá, en la raíz de `agent/` — moverlos
rompería los paths relativos que ya asumen PyInstaller/Inno Setup. Las guías largas y los análisis
puntuales están en [`docs/`](docs/). `agent_gui_config.yaml` (gitignored, la escribe la propia GUI
con secretos reales) tiene una plantilla sin secretos en
[`agent_gui_config.example.yaml`](agent_gui_config.example.yaml).

**Versión**: `AGENT_VERSION` en `al_pos_local_agent.py` es la fuente de verdad — se puede
consultar con `python al_pos_local_agent.py --version`, en el título de la GUI, o en la
respuesta de `GET /health` (campo `version`), sin tener que comparar archivos a mano para saber
qué build quedó instalada en la PC de un local.

**¿Instalando esto por primera vez en un local, sin experiencia previa con Python/Linux?** Ver
[`docs/GUIA_INSTALACION_TECNICO.md`](docs/GUIA_INSTALACION_TECNICO.md) (Raspberry Pi/Linux) o
[`docs/GUIA_INSTALACION_WINDOWS.md`](docs/GUIA_INSTALACION_WINDOWS.md) (PC Windows con la GUI) en
vez de este README — son la versión paso a paso pensada para alguien que nunca tocó una terminal
Linux ni instaló nada del proyecto antes. Este README es la referencia rápida para quien ya sabe el
terreno.

**¿El agente va a correr en una PC Windows del local sin sesión de usuario permanente (kiosco/caja),
y se necesita el mismo nivel de confiabilidad que systemd (arranca antes del login, se reinicia
solo si se cae)?** Ver [`docs/GUIA_SERVICIO_WINDOWS.md`](docs/GUIA_SERVICIO_WINDOWS.md) — instala
`al_pos_local_agent.py` (sin GUI) como Servicio de Windows real, vía NSSM.

**¿El agente va a correr en una PC Windows del local con un usuario fijo que la deja siempre con
sesión iniciada (no en un Raspberry Pi headless ni en un kiosco sin login)?** Ver
[`al_pos_local_agent_gui.py`](al_pos_local_agent_gui.py) — GUI de escritorio (Tkinter) que arranca/detiene el agente y muestra su actividad en
pantalla, en vez de correrlo por línea de comandos/systemd:

```bash
pip install -r requirements.txt -r requirements-gui.txt
python al_pos_local_agent_gui.py
```

Reutiliza `al_pos_local_agent.py` tal cual (mismo archivo, misma carpeta) — no duplica nada de
la lógica de impresión/bus, solo la administra vía `agent.create_server()`. La única dependencia
extra sobre `requirements.txt` es `PyYAML` (`requirements-gui.txt`), para persistir la
configuración entre sesiones en `agent_gui_config.yaml` (se crea solo al guardar Configuración,
no se versiona).

Empaquetado como `.exe` con [`AgenteEscpos.spec`](AgenteEscpos.spec) (PyInstaller)
+ [`installer.iss`](installer.iss) (Inno Setup); correr
[`build_installer.bat`](build_installer.bat) en Windows arma ambos pasos de una. Para instalar y
configurar la GUI paso a paso, ver
[`docs/GUIA_INSTALACION_WINDOWS.md`](docs/GUIA_INSTALACION_WINDOWS.md).

**¿Odoo está detrás de HTTPS (Odoo.sh, o cualquier hosting con TLS) y el certificado autofirmado
del agente da problemas** (advertencia de seguridad en cada navegador nuevo, Private Network
Access, CORS — ver [Problemas conocidos](#problemas-conocidos) más abajo)**?** Ver
[`docs/GUIA_CLOUDFLARE_TUNNEL.md`](docs/GUIA_CLOUDFLARE_TUNNEL.md) — expone el agente con un dominio público
y un certificado real (gratis, vía Cloudflare Tunnel), que evita esos 3 problemas de raíz en vez
de ir resolviéndolos uno por uno.

## Instalación

```bash
cd agent
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Configuración (variables de entorno)

| Variable | Obligatoria | Default | Qué hace |
|---|---|---|---|
| `AL_AGENT_ALLOWED_PRINTERS` | **Sí** | — (el agente no arranca sin esto) | Lista de `ip:puerto` separados por coma que el agente tiene permitido usar — ej. `192.168.0.252:9100`. Cualquier pedido de impresión hacia otro destino se rechaza. |
| `AL_AGENT_TOKEN` | No, pero recomendado | (sin token) | Si se define, todo `POST /print`/`/open_cashbox` debe traer el header `X-Agent-Token` con este mismo valor. Generar uno largo y único por local — ej. `python3 -c "import secrets; print(secrets.token_hex(32))"`. |
| `AL_AGENT_LISTEN_HOST` | No | `0.0.0.0` | Interfaz donde escucha el servidor HTTP. |
| `AL_AGENT_LISTEN_PORT` | No | `8765` | Puerto HTTP del agente (no confundir con el 9100 de la impresora). |
| `AL_AGENT_CORS_ORIGIN` | No | `*` | Valor del header `Access-Control-Allow-Origin` — el navegador hace la llamada desde el origen de Odoo.sh, que es distinto al del agente, así que hace falta CORS. Se puede acotar al dominio real de la instancia Odoo en vez de `*`. |
| `AL_AGENT_LOG_LEVEL` | No | `INFO` | Nivel de log estándar de Python (`DEBUG`, `WARNING`, ...). |
| `AL_AGENT_ODOO_URL` | No (las 3 juntas activan el Camino B) | — | URL base de la instancia Odoo, ej. `https://mi-instancia.odoo.com`. |
| `AL_AGENT_ODOO_DB` | No | — | Nombre de la base de datos (el mismo que se le pasa a `/web/login?db=...`). |
| `AL_AGENT_BUS_CHANNEL` | No | — | Valor de `pos.config.escpos_agent_channel` (Ajustes → Punto de Venta → el PDV — se genera solo, copiarlo de ahí). Es un secreto: tratarlo como una contraseña. |
| `AL_AGENT_ACK_PATH` | No | (vacío: ACK desactivado) | Ruta del ACK del Camino B (ver más abajo). La define el módulo de Odoo que publique los trabajos; si queda vacía, el agente imprime igual pero no confirma nada. |
| `AL_AGENT_TLS_ENABLED` | No, pero **obligatoria si Odoo está detrás de HTTPS** (Odoo.sh, o cualquier hosting con TLS) | `0`/desactivado | `1`/`true` sirve el Camino A por HTTPS con un certificado autofirmado, generado una sola vez y persistido junto al script (`agent_cert.pem`/`agent_key.pem`, ver más abajo). Sin esto, el navegador bloquea la llamada del POS al agente con "Mixed Content" en cuanto Odoo se sirve por HTTPS — a diferencia de un certificado inválido, ese bloqueo no tiene ningún botón de "continuar de todos modos". Requiere `cryptography` (ver `requirements.txt`); si falta, el agente arranca igual, solo por HTTP, con un WARNING. |
| `AL_AGENT_TLS_HOSTNAME` | No | hostname de la máquina | Hostname/IP con el que el navegador va a llamar al agente — tiene que ser el mismo host (sin esquema ni puerto) que se va a escribir en `pos.config.escpos_agent_url`. Se usa como Subject Alternative Name del certificado (además de `localhost`/`127.0.0.1`, siempre incluidos). |
| `AL_AGENT_TLS_CERT_DIR` | No | misma carpeta que el script | Dónde persistir `agent_cert.pem`/`agent_key.pem`. Para rotar el certificado, borrar esos 2 archivos y reiniciar el agente — se regenera solo. |

## Arrancar

Solo Camino A:

```bash
AL_AGENT_ALLOWED_PRINTERS="192.168.0.252:9100" \
AL_AGENT_TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(32))')" \
.venv/bin/python al_pos_local_agent.py
```

Solo Camino A, por HTTPS (Odoo detrás de HTTPS — Odoo.sh, o cualquier hosting con TLS):

```bash
AL_AGENT_ALLOWED_PRINTERS="192.168.0.252:9100" \
AL_AGENT_TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(32))')" \
AL_AGENT_TLS_ENABLED=1 \
AL_AGENT_TLS_HOSTNAME="och-pc" \
.venv/bin/python al_pos_local_agent.py
```

Después, en Odoo (`pos.config.escpos_agent_url`) usar `https://och-pc:8765` (mismo host que
`AL_AGENT_TLS_HOSTNAME`) — y en el navegador del cajero, visitar
`https://och-pc:8765/health` una sola vez y aceptar la advertencia de seguridad del certificado
autofirmado, antes de la primera venta.

Camino A + Camino B (comprobantes en PDF publicados por el bus):

```bash
AL_AGENT_ALLOWED_PRINTERS="192.168.0.252:9100" \
AL_AGENT_TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(32))')" \
AL_AGENT_ODOO_URL="https://mi-instancia.odoo.com" \
AL_AGENT_ODOO_DB="mi_base" \
AL_AGENT_BUS_CHANNEL="<pos.config.escpos_agent_channel>" \
.venv/bin/python al_pos_local_agent.py
```

Verificar que está vivo:

```bash
curl http://localhost:8765/health
# {"status": "ok", "escpos_available": true, "allowed_printers": ["192.168.0.252:9100"]}
```

El log al arrancar dice si el Camino B quedó activo o no (y por qué, si no) — buscar la línea
`Camino B activo` o `Camino B inactivo`.

## Endpoints

### Camino A (HTTP)

Mismo contrato que ya usa `al_pos_network_printer/controllers/main.py` del lado del backend de
Odoo (ver [`README.md`](../README.md#arquitectura) del módulo) — cambia el destino de la llamada,
no el formato:

- `POST /print` — body `{"ip": "...", "port": 9100, "img": "<base64 JPEG>"}` → `{"result": true}` o
  `{"result": false, "errorCode": "..."}`.
- `POST /open_cashbox` — body `{"ip": "...", "port": 9100}` → mismo shape de respuesta.
- `GET /health` — sin autenticación, para monitoreo/diagnóstico.

### Camino B (bus/websocket)

No expone ningún endpoint propio — es un cliente, no un servidor. Se conecta saliente a
`wss://<AL_AGENT_ODOO_URL>/websocket`, se suscribe al canal `AL_AGENT_BUS_CHANNEL`, y espera
mensajes `{"type": "print_pdf", "payload": {"ip", "port", "pdf_b64", "order_id"}}` — publicados del
lado de Odoo por el módulo que genere el comprobante. Reconecta solo
si se cae (10s entre intentos — probado en vivo: retoma solo tras reiniciar Odoo por completo, con
varios reintentos "connection refused" mientras estuvo caído).

**ACK (Fase 3)**: si `AL_AGENT_ACK_PATH` tiene valor (por defecto está vacío, es decir,
desactivado), después de cada trabajo el agente manda un `POST` best-effort a esa ruta confirmando
si imprimió de verdad o no; qué hace Odoo con esa confirmación (por ejemplo, dejar un mensaje en el
chatter de la orden) lo decide el módulo que definió la ruta. Detalle no obvio,
confirmado en vivo: ese `POST` va con el header `X-Odoo-Database: <AL_AGENT_ODOO_DB>` — sin él,
Odoo devuelve 404 "No database is selected" (el agente nunca tiene sesión de usuario, y a
diferencia del `/web/login` que sí acepta `?db=` en la URL, esta ruta normal no).

## Correr como servicio (Linux, systemd)

1. Copiar esta carpeta (o solo `al_pos_local_agent.py` + el venv) a, por ejemplo,
   `/opt/al-pos-local-agent/` en la máquina que va a quedar siempre encendida.
2. Copiar [`al-pos-local-agent.service.example`](al-pos-local-agent.service.example) a
   `/etc/systemd/system/al-pos-local-agent.service`, completar las variables de entorno con los
   valores reales del local (IP de la impresora, token generado).
3. `systemctl daemon-reload && systemctl enable --now al-pos-local-agent`

## Probar sin la impresora física a mano

Mismo truco que ya documenta el módulo principal
([`CONFIGURACION_ODOO_PASO_A_PASO.md`](../docs/CONFIGURACION_ODOO_PASO_A_PASO.md#paso-5--verificar-la-conexión-sin-tener-la-impresora-a-mano)):

```bash
nc -l -p 9100 > /tmp/ticket_capturado.bin
```

y apuntar `AL_AGENT_ALLOWED_PRINTERS` a esa IP/puerto (`127.0.0.1:9100` si es la misma máquina).

## Problemas conocidos

**El navegador tira "Mixed Content... This request has been blocked" al imprimir, y el agente no
recibe nada (ni un `OPTIONS`/`POST` en su log)** — confirmado en una prueba en Odoo.sh (2026-09-09): pasa cuando Odoo se sirve por HTTPS (Odoo.sh siempre lo es) y
`pos.config.escpos_agent_url` apunta a `http://` plano. El navegador corta la petición ANTES de que
salga — a diferencia de un certificado inválido, acá no hay ningún botón de "continuar de todos
modos". No pasaba en una instalación on-premise por HTTP porque ahí no hay
mezcla de esquemas. Fix: activar `AL_AGENT_TLS_ENABLED=1` (ver arriba) y cambiar
`escpos_agent_url` a `https://...` con el mismo host que `AL_AGENT_TLS_HOSTNAME`.

**Con HTTPS ya activo y el certificado ya aceptado (navegar a `/health` directo funciona), el POS
sigue mostrando el diálogo de autorización y el `fetch()` sigue tirando `TypeError: Failed to
fetch`** — confirmado en una prueba en Odoo.sh (2026-09-15): es **Private Network
Access (PNA)** de Chrome (~v130+, enforcement gradual), no un problema de certificado. Cuando una
página de un origen público (`*.odoo.com`, `*.dev.odoo.com`) hace `fetch()` hacia un destino de red
privada (una IP/hostname de LAN, como este agente), Chrome exige que el preflight `OPTIONS`
devuelva el header `Access-Control-Allow-Private-Network: true` — sin importar que
`Access-Control-Allow-Origin` ya sea `*` y todo lo demás esté bien. Sin ese header, el navegador
corta la conexión **después** del preflight (que sí devuelve 204), así que el síntoma es
indistinguible de "el agente está apagado" del lado del `fetch()` — solo se nota mirando la pestaña
Network del navegador (aparece el `OPTIONS` con 204, pero nunca el `GET`/`POST` real después).
Corregido: el `do_OPTIONS` del agente manda ese header siempre. Si un agente instalado antes no lo
hace, actualizar `al_pos_local_agent.py` y reiniciar el agente (o la GUI) para que tome el cambio.

**Con el header PNA ya puesto, el `fetch()` desde el POS sigue fallando igual (incluso en
`mode: 'no-cors'`, que normalmente ignora casi todo lo relacionado a CORS)** — confirmado en la misma
prueba en Odoo.sh (2026-09-15): con `AL_AGENT_CORS_ORIGIN` en su default (`*`), el agente mandaba el
string literal `"*"` en `Access-Control-Allow-Origin`. Ese comodín no es compatible con el permiso
elevado que Private/Local Network Access le da a este origen — mismo motivo por el que un `*`
literal tampoco es compatible con `credentials: 'include'` en fetch estándar. Por eso,
con `AL_AGENT_CORS_ORIGIN=*` (el default) el agente **refleja el header `Origin` real de cada
request** en vez de mandar el comodín textual — sigue siendo "cualquier origen" en la práctica,
solo cambia cómo se lo comunica. Si `AL_AGENT_CORS_ORIGIN` está seteado a un valor específico, se
sigue mandando tal cual, sin reflejar nada.

Esta versión también agrega logging explícito del `Origin` recibido en cada `OPTIONS`/`GET`/`POST`
(`journalctl`/log de la GUI) — si después de actualizar sigue sin autorizar, revisar ese log
primero: si la request ni siquiera aparece ahí, el bloqueo es del lado del navegador (no hay nada
que el agente pueda hacer distinto); si aparece pero con error, el log dice cuál.
