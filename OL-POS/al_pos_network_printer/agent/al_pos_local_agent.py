#!/usr/bin/env python3
"""Agente local ESC/POS (Caminos A y B, ver ``README.md``).

Servidor HTTP mínimo (Camino A) + cliente websocket opcional (Camino B)
pensado para correr en la misma red local que la impresora (Raspberry Pi, la
propia caja del POS, cualquier máquina siempre encendida durante el horario
del local). No necesita Odoo instalado: es un proceso standalone
independiente del resto del repo.

- **Camino A** (``AL_AGENT_ALLOWED_PRINTERS`` + servidor HTTP, siempre
  activo): el navegador del cajero, que YA está físicamente en la red de la
  impresora, le habla directo acá para el ticket normal del POS, en vez de
  pasarle el ticket al backend de Odoo. Mismo contrato que ya expone
  ``al_pos_network_printer/controllers/main.py``
  (``POST .../print_receipt``, body ``{ip, port, img}`` en base64).
- **Camino B** (``AL_AGENT_ODOO_URL``/``AL_AGENT_ODOO_DB``/
  ``AL_AGENT_BUS_CHANNEL``, opcional — si faltan, este camino simplemente
  no arranca): hilo en segundo plano que se conecta saliente al
  ``/websocket`` de Odoo (mismo mecanismo que usa la IoT Box oficial, ver
  ``addons/iot_drivers/websocket_client.py`` del propio Odoo) y queda
  escuchando el canal privado de ``pos.config.escpos_agent_channel``. Sirve
  para los comprobantes en PDF que imprime el BACKEND (un job
  de ``queue_job``, sin navegador de por medio), así que no hay forma de que
  "le hable directo" al agente como en el Camino A; el backend publica el
  trabajo en el canal y este hilo lo recibe.

La lógica de impresión ESC/POS en sí (``_NetworkPrinterConnection``) es una
copia deliberada de la del controlador de Odoo — no se puede importar
directo porque este proceso corre sin Odoo instalado.

Uso (solo Camino A):
    AL_AGENT_ALLOWED_PRINTERS="192.168.0.252:9100" python al_pos_local_agent.py

Uso (Camino A + B):
    AL_AGENT_ALLOWED_PRINTERS="192.168.0.252:9100" \\
    AL_AGENT_ODOO_URL="https://mi-instancia.odoo.com" \\
    AL_AGENT_ODOO_DB="mi_base" \\
    AL_AGENT_BUS_CHANNEL="<pos.config.escpos_agent_channel>" \\
    python al_pos_local_agent.py

Uso (Camino A por HTTPS — obligatorio si Odoo está detrás de HTTPS, ej.
Odoo.sh, o cualquier navegador bloquearía la llamada por "Mixed Content"):
    AL_AGENT_ALLOWED_PRINTERS="192.168.0.252:9100" \\
    AL_AGENT_TLS_ENABLED=1 \\
    AL_AGENT_TLS_HOSTNAME="och-pc" \\
    python al_pos_local_agent.py

Ver README.md de esta carpeta para la lista completa de variables de entorno
y el ejemplo de unidad systemd.
"""
import base64
import hmac
import ipaddress
import json
import logging
import os
import socket
import ssl
import sys
import threading
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path

try:
    from escpos.printer import Network as EscposNetwork
except ImportError:
    EscposNetwork = None

try:
    from PIL import Image
except ImportError:
    Image = None

# Los 3 imports de abajo solo hacen falta para el Camino B (Fase 2) — igual
# que python-escpos para el A, se difieren para que el agente arranque
# igual (solo con el Camino A) si no están instalados, y recién fallar con
# un mensaje claro si de verdad se configuró AL_AGENT_BUS_CHANNEL sin
# tenerlos.
try:
    import requests
except ImportError:
    requests = None

try:
    import websocket
except ImportError:
    websocket = None

try:
    import pymupdf as fitz  # `import fitz` es el nombre viejo, deprecado desde pymupdf 1.24
except ImportError:
    fitz = None

# HTTPS del Camino A (opcional, ver AL_AGENT_TLS_ENABLED más abajo) —
# confirmado en vivo (2026-09-09, prueba en Odoo.sh): una
# instancia Odoo servida por HTTPS (Odoo.sh siempre lo es) bloquea, del lado
# del NAVEGADOR, cualquier `fetch()` hacia un agente en `http://` plano
# ("Mixed Content" — a diferencia de un certificado inválido, esto no tiene
# ningún botón de "continuar de todos modos", corta la petición antes de que
# salga). `ssl` (stdlib) solo sabe *usar* un certificado, no generarlo — para
# eso hace falta `cryptography`, deferred-import igual que los 3 de arriba.
try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
except ImportError:
    x509 = None

logging.basicConfig(
    level=os.environ.get("AL_AGENT_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
_logger = logging.getLogger("al_pos_local_agent")

# Fuente de verdad única de la versión del agente (CLI y GUI, que la importa
# como `agent.AGENT_VERSION` — ver al_pos_local_agent_gui.py). Se expone
# también en `--version`, en `/health` y en el log de arranque, para poder
# confirmar en el terreno qué build quedó instalada en la PC de un local sin
# tener que comparar archivos a mano. `installer.iss` (`AppVersion`) y
# `AgenteEscpos_Setup_<version>.exe` se actualizan a mano en el mismo
# commit que este valor — Inno Setup no puede leer una constante de Python.
AGENT_VERSION = "1.0.0"

# Mismo límite que el controlador de Odoo (ver controllers/main.py) — evita
# que un caller sin autenticar fuerce al agente a reservar memoria arbitraria
# antes de siquiera decodificar el base64.
MAX_RECEIPT_IMAGE_BYTES = 5 * 1024 * 1024
KEEP_ALIVE_INTERVAL_SECONDS = 300

# Mismo valor que DEFAULT_PDF_PRINT_WIDTH_PX en controllers/main.py —
# estándar de facto para térmicas de 80mm ESC/POS (203dpi, 8 puntos/mm × 72mm
# de área imprimible real).
PDF_PRINT_WIDTH_PX = 576

# Cuánto esperar entre intentos de reconexión del websocket del Camino B si
# se cae (mismo valor que usa el `ws.run_forever(reconnect=10)` oficial).
BUS_RECONNECT_SECONDS = 10

# Nombres de archivo del certificado autofirmado del Camino A (HTTPS
# opcional, ver Config.tls_enabled). Persistidos junto al script (mismo
# criterio que `agent_gui_config.yaml`) para que el certificado NO cambie
# en cada reinicio — si cambiara, el cajero tendría que volver a aceptar la
# advertencia de seguridad del navegador cada vez, que es justo lo que se
# evita generándolo una sola vez y reutilizándolo.
TLS_CERT_FILENAME = "agent_cert.pem"
TLS_KEY_FILENAME = "agent_key.pem"
TLS_CERT_VALIDITY_DAYS = 3650  # 10 años — mismo horizonte que un cert autofirmado de IoT Box típico


def _parse_allowed_printers(raw):
    """``"192.168.0.252:9100,192.168.0.253:9100"`` -> ``{(ip, port), ...}``.

    Allow-list explícita, igual criterio que ``is_allowed_target()`` del
    lado del backend de Odoo: el agente nunca debe abrir un socket hacia un
    destino que no esté acá, sin importar qué IP:puerto le pida el caller —
    si no, cualquiera en la misma LAN que alcance el puerto HTTP del agente
    podría usarlo de proxy para mandar bytes arbitrarios a cualquier otra
    IP:puerto de esa red (SSRF)."""
    allowed = set()
    for entry in (raw or "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        if ":" not in entry:
            raise ValueError(f"Entrada inválida en AL_AGENT_ALLOWED_PRINTERS: {entry!r} (falta ':puerto')")
        host, _, port = entry.rpartition(":")
        try:
            allowed.add((host, int(port)))
        except ValueError as exc:
            raise ValueError(f"Puerto inválido en AL_AGENT_ALLOWED_PRINTERS: {entry!r}") from exc
    return allowed


class Config:
    """Configuración leída de variables de entorno al arrancar — sin
    dependencias externas de parseo, para mantener el agente sin más
    requisitos que python-escpos."""

    def __init__(self, env=os.environ):
        self.listen_host = env.get("AL_AGENT_LISTEN_HOST", "0.0.0.0")
        self.listen_port = int(env.get("AL_AGENT_LISTEN_PORT", "8765"))
        self.allowed_printers = _parse_allowed_printers(env.get("AL_AGENT_ALLOWED_PRINTERS", ""))
        # Token compartido opcional (header X-Agent-Token) — recomendado
        # (ver README.md): la LAN de un local
        # comercial no es necesariamente una red de confianza total (ej.
        # Wi-Fi de clientes en la misma red). Sin token, cualquier
        # dispositivo que alcance el puerto HTTP del agente podría mandarle
        # trabajos de impresión.
        self.token = env.get("AL_AGENT_TOKEN") or None
        self.cors_origin = env.get("AL_AGENT_CORS_ORIGIN", "*")

        # HTTPS del Camino A (opcional) — ver el comentario junto al import
        # de `cryptography`, arriba, para el porqué. Desactivado por
        # default: una instalación on-premise normal (Odoo servido por
        # HTTP) no lo necesita y seguir en HTTP ahí
        # evita el paso extra de aceptar un certificado. Activarlo cuando
        # Odoo esté detrás de HTTPS (Odoo.sh, o cualquier hosting con TLS).
        self.tls_enabled = (env.get("AL_AGENT_TLS_ENABLED") or "").strip().lower() in ("1", "true", "yes", "on")
        # Hostname/IP con el que el NAVEGADOR va a llamar al agente — tiene
        # que coincidir con el host de `pos.config.escpos_agent_url` (sin
        # el esquema ni el puerto) para que el certificado autofirmado
        # cubra ese nombre como Subject Alternative Name. Si no se
        # especifica, se usa el hostname de esta máquina — igual hace falta
        # revisar que sea el mismo valor que se va a escribir en Odoo.
        self.tls_hostname = env.get("AL_AGENT_TLS_HOSTNAME") or socket.gethostname()
        self.tls_cert_dir = Path(env.get("AL_AGENT_TLS_CERT_DIR") or Path(__file__).resolve().parent)

        if not self.allowed_printers:
            raise ValueError(
                "AL_AGENT_ALLOWED_PRINTERS no puede estar vacío — el agente "
                "se niega a arrancar sin una allow-list explícita de destinos "
                "(ver README.md)."
            )

        # Camino B (Fase 2) — opcional. Si falta cualquiera de los 3, este
        # camino no arranca y el agente sigue funcionando solo con el A
        # (comportamiento de la Fase 1, sin cambios).
        self.odoo_url = (env.get("AL_AGENT_ODOO_URL") or "").rstrip("/") or None
        self.odoo_db = env.get("AL_AGENT_ODOO_DB") or None
        self.bus_channel = env.get("AL_AGENT_BUS_CHANNEL") or None

        # ACK (Fase 3, endurecimiento) — best-effort, POST de vuelta a Odoo
        # avisando si un trabajo del Camino B se imprimió de verdad. Vacío
        # (string vacío, a propósito distinto de None) desactiva el ACK sin
        # desactivar el Camino B entero — útil contra un Odoo viejo que
        # todavía no tenga esta ruta. Vacío por defecto: la ruta la define el
        # módulo de Odoo que publica los trabajos del Camino B.
        self.ack_path = env.get("AL_AGENT_ACK_PATH", "") or None

    @property
    def bus_enabled(self):
        return bool(self.odoo_url and self.odoo_db and self.bus_channel)


# ---------------------------------------------------------------------------
# Lógica de impresión ESC/POS — copia deliberada de
# controllers/main.py::_NetworkPrinterConnection (ver docstring del módulo,
# arriba, para el porqué de la duplicación en vez de un import compartido).
# ---------------------------------------------------------------------------
class _NetworkPrinterConnection:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.lock = threading.Lock()
        self._printer = None
        self._connect()
        self._keep_alive_thread = threading.Thread(target=self._keep_alive_loop, daemon=True)
        self._keep_alive_thread.start()

    def _connect(self):
        self._printer = EscposNetwork(self.host, self.port, timeout=10)

    def _reconnect(self):
        try:
            self._printer.close()
        except Exception:
            pass
        self._connect()

    def _keep_alive_loop(self):
        while True:
            time.sleep(KEEP_ALIVE_INTERVAL_SECONDS)
            with self.lock:
                try:
                    self._printer._raw(b"\x00")
                except Exception:
                    _logger.info("Keep-alive failed for %s:%s, reconnecting...", self.host, self.port)
                    self._reconnect()

    def print_image(self, image):
        with self.lock:
            try:
                self._printer.image(image)
                self._printer.cut()
                return
            except (BrokenPipeError, socket.error, OSError):
                _logger.info("Lost connection to %s:%s, reconnecting and retrying...", self.host, self.port)
                self._reconnect()
                self._printer.image(image)
                self._printer.cut()

    def open_cashbox(self):
        with self.lock:
            self._printer.cashdraw(2)


_connections = {}
_connections_registry_lock = threading.Lock()


def _get_connection(host, port):
    key = (host, port)
    with _connections_registry_lock:
        connection = _connections.get(key)
        if connection is None:
            connection = _NetworkPrinterConnection(host, port)
            _connections[key] = connection
        return connection


def _pdf_bytes_to_images(pdf_bytes, target_width_px=PDF_PRINT_WIDTH_PX):
    """Copia deliberada de ``_pdf_bytes_to_images()`` en
    ``controllers/main.py`` — rasteriza cada página del PDF a un
    ``PIL.Image`` escalado a ``target_width_px`` de ancho (alto
    proporcional), listo para el mismo ``print_image()`` que ya usa el
    Camino A."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        images = []
        for page in doc:
            zoom = target_width_px / page.rect.width
            pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            images.append(Image.open(BytesIO(pixmap.tobytes("png"))))
        return images
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Camino B (Fase 2) — cliente websocket saliente hacia el bus de Odoo.
# ---------------------------------------------------------------------------
class BusListener(threading.Thread):
    """Hilo en segundo plano — mismo patrón que
    ``addons/iot_drivers/websocket_client.py::WebsocketClient`` del propio
    Odoo (ver ``README.md`` para el
    detalle completo, incluida la validación en vivo del mecanismo): consigue una cookie de sesión con un
    ``GET /web/login?db=...`` normal (paso obligatorio — conectarse al
    websocket sin esto da 404 "No database is selected", ni pasando
    ``?db=`` en la URL alcanza), abre el websocket con esa cookie, se
    suscribe al canal privado, y por cada mensaje ``print_pdf`` que llegue
    rasteriza el PDF e imprime con el mismo ``_NetworkPrinterConnection``
    del Camino A. Reconecta solo si se cae."""

    def __init__(self, config, stats_cb=None):
        super().__init__(daemon=True, name="al-bus-listener")
        self.config = config
        self.last_message_id = 0
        # `stats_cb(event, data)` es un hook opcional (ninguno de los 2
        # parámetros lo usa en modo CLI/systemd) — lo consume la GUI de
        # Windows (`al_pos_local_agent_gui.py`) para reflejar actividad en
        # pantalla sin que este módulo sepa nada de Tkinter.
        self.stats_cb = stats_cb
        self.connected = False
        self._stop = threading.Event()
        self._ws_app = None
        self._pong_count = 0

    def stop(self):
        """Corta el hilo desde afuera (usado por la GUI al presionar
        "Detener") — cierra el websocket activo si hay uno y hace que el
        loop de reconexión de `run()` no vuelva a intentar."""
        self._stop.set()
        if self._ws_app is not None:
            try:
                self._ws_app.close()
            except Exception:
                pass

    def _get_session_id(self):
        resp = requests.get(
            f"{self.config.odoo_url}/web/login",
            params={"db": self.config.odoo_db},
            allow_redirects=False, timeout=10,
        )
        if resp.status_code not in (200, 302):
            raise RuntimeError(f"No se pudo obtener session_id (status {resp.status_code})")
        return resp.cookies["session_id"]

    def _websocket_url(self):
        parsed = urllib.parse.urlsplit(self.config.odoo_url)
        scheme = parsed.scheme.replace("http", "ws", 1)
        return urllib.parse.urlunsplit((scheme, parsed.netloc, "websocket", "", ""))

    def _send_subscribe(self, ws):
        ws.send(json.dumps({
            "event_name": "subscribe",
            "data": {"channels": [self.config.bus_channel], "last": self.last_message_id},
        }))

    def _on_open(self, ws):
        _logger.info("Camino B: conectado, suscribiendo al canal del bus")
        self._send_subscribe(ws)
        self.connected = True
        self._pong_count = 0
        if self.stats_cb:
            self.stats_cb("bus_connected", {})

    def _on_pong(self, ws, message):
        # Confirmado en vivo (2026-09-09, prueba en Odoo.sh): el WebSocket en
        # sí puede seguir perfectamente vivo (ping/pong respondiendo) varios
        # minutos después de que el servidor deje de relayar mensajes de
        # este canal — `ImDispatch` (bus.py) mantiene su propia conexión
        # dedicada a Postgres con `LISTEN imbus`; si esa conexión se cae y
        # se reconecta (ej. el pooler de conexiones cerrando conexiones
        # idle), el mapa interno "canal -> websocket" se resetea, y una
        # suscripción hecha una sola vez al abrir la conexión (`_on_open`)
        # queda huérfana sin que el cliente se entere — no hay ningún
        # mensaje de error, la conexión de cara al agente sigue "sana".
        # Reproducido a mano: 2 mensajes de prueba (`bus.bus._sendone()`
        # directo) nunca llegaron tras ~5-6 min de conexión idle, pese a
        # pongs normales cada 20s durante todo ese tiempo.
        #
        # Fix: reenviar el "subscribe" en cada pong (aprovecha el mismo
        # ciclo de `ping_interval`, sin hilo ni temporizador aparte) — barato
        # (un JSON chico) y muy por debajo de la ventana de expiración
        # observada, así que la suscripción nunca llega a quedar huérfana el
        # tiempo suficiente para importar en la práctica.
        self._pong_count += 1
        if self._pong_count % 3 == 1:
            _logger.info("Camino B: pong recibido (#%d) — conexión viva", self._pong_count)
        self._send_subscribe(ws)

    def _on_message(self, ws, raw_message):
        for message in json.loads(raw_message):
            self.last_message_id = message["id"]
            payload = message["message"]["payload"]
            msg_type = message["message"]["type"]
            _logger.info("Camino B: mensaje id=%s tipo=%s recibido", message["id"], msg_type)
            if msg_type == "print_pdf":
                self._handle_print_pdf(payload)
            else:
                _logger.warning("Camino B: tipo de mensaje desconocido %r, ignorado", msg_type)

    def _handle_print_pdf(self, payload):
        order_id = payload.get("order_id")
        ip = payload.get("ip")
        port = payload.get("port")
        try:
            port = int(port)
        except (TypeError, ValueError):
            port = None
        if not ip or port is None or (ip, port) not in self.config.allowed_printers:
            _logger.warning(
                "Camino B: trabajo rechazado — %s:%s no está en AL_AGENT_ALLOWED_PRINTERS.",
                ip, port,
            )
            self._send_ack(order_id, False, f"{ip}:{port} no está en la allow-list del agente")
            if self.stats_cb:
                self.stats_cb("voucher_failed", {
                    "ip": ip, "port": port, "order_id": order_id,
                    "error": "IP:puerto no está en la allow-list del agente",
                })
            return
        if fitz is None or Image is None:
            _logger.error(
                "Camino B: falta instalar 'pymupdf' (o Pillow) en el agente — "
                "no se puede rasterizar el PDF. pip install -r requirements.txt."
            )
            self._send_ack(order_id, False, "Falta pymupdf/Pillow en el agente")
            if self.stats_cb:
                self.stats_cb("voucher_failed", {
                    "ip": ip, "port": port, "order_id": order_id,
                    "error": "Falta pymupdf/Pillow en el agente",
                })
            return
        try:
            pdf_bytes = base64.b64decode(payload.get("pdf_b64") or "")
            images = _pdf_bytes_to_images(pdf_bytes)
            connection = _get_connection(ip, port)
            for image in images:
                connection.print_image(image)
            _logger.info("Camino B: comprobante impreso en %s:%s (%d página/s)", ip, port, len(images))
            self._send_ack(order_id, True)
            if self.stats_cb:
                self.stats_cb("voucher_printed", {"ip": ip, "port": port, "order_id": order_id})
        except Exception as exc:
            _logger.exception("Camino B: error imprimiendo el comprobante en %s:%s", ip, port)
            self._send_ack(order_id, False, str(exc))
            if self.stats_cb:
                self.stats_cb("voucher_failed", {"ip": ip, "port": port, "order_id": order_id, "error": str(exc)})

    def _send_ack(self, order_id, success, error=None):
        """Fase 3 (endurecimiento) — POST best-effort de vuelta a Odoo
        confirmando si el trabajo se imprimió de verdad, a la ruta que
        declare el módulo que publicó el trabajo (``AL_AGENT_ACK_PATH``).
        Sin `order_id` (mensajes viejos de un Odoo sin este campo, o de
        otro tipo de trabajo) no hay a qué orden dejarle el ack, se omite
        sin más — nunca debe tumbar el manejo del mensaje en sí, es
        estrictamente informativo.

        Header ``X-Odoo-Database`` — confirmado en vivo (2026-09-08,
        instalación on-premise): un POST sin sesión/cookie de Odoo (como este,
        el agente nunca inició sesión de usuario) a una ruta normal
        (`type="http"`) da 404 "No database is selected" — ni pasando
        `?db=...` en la URL alcanza, mismo síntoma que ya se documentó
        para `/websocket` en la Fase 0, pero acá el propio mensaje de
        error de Odoo señala la salida: el header `X-Odoo-Database`.
        A diferencia del websocket (que sí necesita una cookie de sesión
        real, aunque sea anónima), acá alcanza con el header — no hace
        falta el paso de `/web/login` para este POST puntual."""
        if not order_id or not self.config.ack_path:
            return
        try:
            requests.post(
                f"{self.config.odoo_url}{self.config.ack_path}",
                headers={"X-Odoo-Database": self.config.odoo_db},
                json={"ack": {
                    "channel": self.config.bus_channel,
                    "order_id": order_id,
                    "success": success,
                    "error": error,
                }},
                timeout=10,
            )
        except Exception:
            _logger.exception("Camino B: no se pudo mandar el ACK a Odoo (orden %s)", order_id)

    def _on_error(self, ws, error):
        _logger.error("Camino B: error de websocket: %s", error)

    def _on_close(self, ws, code, msg):
        _logger.info("Camino B: websocket cerrado (code=%s)", code)
        self.connected = False
        if self.stats_cb:
            self.stats_cb("bus_disconnected", {})

    def run(self):
        while not self._stop.is_set():
            try:
                session_id = self._get_session_id()
                self._ws_app = websocket.WebSocketApp(
                    self._websocket_url(),
                    header={"Cookie": f"session_id={session_id}"},
                    on_open=self._on_open, on_message=self._on_message,
                    on_error=self._on_error, on_close=self._on_close,
                    on_pong=self._on_pong,
                )
                # `ping_timeout` (< ping_interval) es obligatorio para que
                # esto sirva de algo — confirmado en vivo (2026-09-09,
                # prueba en Odoo.sh): sin él, `websocket-client`
                # manda el ping cada `ping_interval` pero nunca exige el
                # pong de vuelta a tiempo, así que una conexión matada en
                # silencio por el NAT/router del local (sin FIN/RST, el caso
                # típico tras un rato inactivo) queda "conectada" para
                # siempre del lado del agente — el badge decía "conectado"
                # pero ya no llegaba nada — sin que nunca se dispare
                # `on_close`/la reconexión de más abajo.
                self._ws_app.run_forever(ping_interval=20, ping_timeout=10)
            except Exception:
                _logger.exception("Camino B: excepción inesperada en el loop del websocket")
            if self._stop.is_set():
                break
            _logger.info("Camino B: reintentando conexión en %ds...", BUS_RECONNECT_SECONDS)
            self._stop.wait(BUS_RECONNECT_SECONDS)


# ---------------------------------------------------------------------------
# HTTPS del Camino A (opcional) — certificado autofirmado, generado una sola
# vez y persistido (ver TLS_CERT_FILENAME/TLS_KEY_FILENAME arriba).
# ---------------------------------------------------------------------------
def _generate_self_signed_cert(cert_path, key_path, hostname):
    """Genera un par clave/certificado autofirmado y lo escribe en
    ``cert_path``/``key_path`` (PEM, clave sin cifrar — el agente la lee
    solo, sin pedir passphrase).

    Cubre ``hostname`` (el valor de ``AL_AGENT_TLS_HOSTNAME``, o el
    hostname de la máquina por default) más ``localhost``/``127.0.0.1`` como
    Subject Alternative Names, para que sirva tanto si el navegador llega
    por nombre como por IP local. Al ser autofirmado, el navegador va a
    mostrar una advertencia de todos modos la primera vez (no hay Autoridad
    Certificadora detrás) — eso es esperado, el cajero la acepta una sola
    vez visitando ``https://<host>:<puerto>/health`` antes de la primera
    venta; lo que este certificado sí resuelve es el bloqueo de "Mixed
    Content" (ver el comentario junto al import de `cryptography`), que a
    diferencia de un certificado inválido NO tiene ningún botón para
    continuar."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Agente local ESC/POS"),
    ])
    san_names = {hostname, "localhost"}
    general_names = [x509.DNSName(name) for name in san_names]
    general_names.append(x509.IPAddress(ipaddress.ip_address("127.0.0.1")))
    try:
        general_names.append(x509.IPAddress(ipaddress.ip_address(hostname)))
    except ValueError:
        pass  # hostname no es una IP literal — ya cubierto como DNSName arriba

    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=TLS_CERT_VALIDITY_DAYS))
        .add_extension(x509.SubjectAlternativeName(general_names), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))


def _ensure_tls_cert(cert_dir, hostname):
    """Devuelve ``(cert_path, key_path)`` — si ya existen ambos archivos en
    ``cert_dir``, los reutiliza tal cual (a propósito: regenerar el
    certificado en cada arranque invalidaría la excepción de seguridad que
    el navegador del cajero ya había aceptado, forzando a aceptarla de
    nuevo). Solo genera un par nuevo la primera vez, o si se borraron a
    mano (ej. para rotar el certificado)."""
    cert_dir.mkdir(parents=True, exist_ok=True)
    cert_path = cert_dir / TLS_CERT_FILENAME
    key_path = cert_dir / TLS_KEY_FILENAME
    if cert_path.exists() and key_path.exists():
        _logger.info("HTTPS: reutilizando certificado existente en %s", cert_path)
        return cert_path, key_path

    _logger.info("HTTPS: generando certificado autofirmado nuevo para %r en %s...", hostname, cert_dir)
    _generate_self_signed_cert(cert_path, key_path, hostname)
    _logger.info(
        "HTTPS: certificado generado (válido %d días) — para rotarlo, borrar "
        "%s y %s y reiniciar el agente.",
        TLS_CERT_VALIDITY_DAYS, cert_path.name, key_path.name,
    )
    return cert_path, key_path


# ---------------------------------------------------------------------------
# Servidor HTTP
# ---------------------------------------------------------------------------
class AgentRequestHandler(BaseHTTPRequestHandler):
    config: Config = None  # seteado por create_server() antes de arrancar el server
    # Hook opcional `stats_cb(event, data)` — mismo propósito que el de
    # BusListener, ver su docstring de __init__. None en modo CLI/systemd.
    stats_cb = None

    server_version = "AlPosLocalAgent/0.1"

    def log_message(self, fmt, *args):
        _logger.info("%s - %s", self.address_string(), fmt % args)

    # -- helpers ------------------------------------------------------
    def _allow_origin_header(self):
        """Valor a mandar en `Access-Control-Allow-Origin`.

        Con `AL_AGENT_CORS_ORIGIN` en su default (`*`), NO se manda el
        string literal `"*"` — se refleja el header `Origin` real de la
        request (o `*` igual si no vino Origin, ej. un curl de prueba).
        Confirmado en vivo (2026-09-15, prueba en Odoo.sh,
        Private/Local Network Access de Chrome): un `*` literal sigue
        bloqueando el fetch() incluso con `Access-Control-Allow-Private-
        Network: true` ya presente y el permiso de red local ya concedido
        (`navigator.permissions.query({name:'local-network-access'})` →
        `granted`) — mismo criterio que ya exige el spec para
        `credentials: 'include'` (no se puede combinar con un wildcard
        literal), y Private Network Access aplica la misma restricción
        para la respuesta "elevada" que autoriza cruzar a una red privada.
        Semánticamente sigue siendo "cualquier origen" — simplemente se
        lo manda por su nombre real en vez del comodín. Con
        `AL_AGENT_CORS_ORIGIN` configurado a un valor específico
        (no `*`), se manda ese valor tal cual, sin reflejar nada."""
        if self.config.cors_origin != "*":
            return self.config.cors_origin
        return self.headers.get("Origin") or "*"

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", self._allow_origin_header())
        # Al reflejar el Origin (arriba) la respuesta ya no es la misma
        # para cualquier origen — sin este header, un cache/proxy
        # intermedio podría servirle a un origen distinto la respuesta
        # calculada para otro. Este servidor no cachea nada él mismo, es
        # higiene para lo que pueda haber delante (ver README).
        self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _check_token(self):
        if not self.config.token:
            return True
        # `hmac.compare_digest` en vez de `==`: comparación en tiempo
        # constante, para que la duración de la respuesta no filtre cuántos
        # caracteres del token adivinó un atacante en la LAN (timing attack
        # clásico contra comparación de secretos byte a byte).
        received = self.headers.get("X-Agent-Token") or ""
        return hmac.compare_digest(received, self.config.token)

    def _resolve_target(self, body):
        ip = body.get("ip")
        port = body.get("port")
        if not ip or not port:
            return None, None
        try:
            port = int(port)
        except (TypeError, ValueError):
            return None, None
        if (ip, port) not in self.config.allowed_printers:
            _logger.warning("Rejected print request: %s:%s is not in AL_AGENT_ALLOWED_PRINTERS.", ip, port)
            return None, None
        return ip, port

    # -- CORS preflight -------------------------------------------------
    def do_OPTIONS(self):
        origin = self.headers.get("Origin") or "(sin header Origin)"
        pna_requested = self.headers.get("Access-Control-Request-Private-Network")
        _logger.info(
            "Preflight OPTIONS %s — Origin=%s, Access-Control-Request-Private-Network=%s",
            self.path, origin, pna_requested,
        )
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", self._allow_origin_header())
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Agent-Token")
        # Private Network Access (Chrome ~130+, enforcement gradual desde
        # 2026): cuando el POS corre en un origen público (Odoo.sh,
        # *.odoo.com) y el destino es de red privada (LAN, como este
        # agente), Chrome exige este header en la respuesta del preflight
        # ANTES de dejar pasar el fetch() real — sin importar que
        # `Access-Control-Allow-Origin` ya diga "*". Confirmado en vivo
        # (2026-09-15): sin esto, el navegador corta la conexión después
        # del preflight con "Failed to fetch", aunque el agente esté sano y
        # el certificado ya aceptado — el síntoma es indistinguible de
        # "agente apagado" del lado de la excepción de fetch(), solo se ve
        # en la pestaña Network (204 en el preflight, sin request real
        # después). Se manda siempre, no solo cuando el navegador la pide
        # (`Access-Control-Request-Private-Network`): no tiene efecto en
        # clientes que no la entienden.
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Content-Length", "0")
        self.end_headers()

    # -- rutas ------------------------------------------------------
    def do_GET(self):
        # Log explícito de Origin en cada GET real (no solo en el
        # preflight OPTIONS) — mismo motivo que el log de do_OPTIONS: es
        # la única forma de confirmar del lado del servidor si una
        # request de verdad llegó a procesarse (y con qué Origin) o si el
        # navegador la cortó antes, sin depender de lo que las DevTools
        # remotas del cajero puedan mostrar.
        _logger.info("GET %s — Origin=%s", self.path, self.headers.get("Origin") or "(sin header Origin)")
        if self.path == "/health":
            self._send_json(200, {
                "status": "ok",
                "version": AGENT_VERSION,
                "escpos_available": EscposNetwork is not None,
                "allowed_printers": sorted(f"{h}:{p}" for h, p in self.config.allowed_printers),
            })
            return
        self._send_json(404, {"result": False, "errorCode": "NOT_FOUND"})

    def do_POST(self):
        _logger.info("POST %s — Origin=%s", self.path, self.headers.get("Origin") or "(sin header Origin)")
        if self.path not in ("/print", "/open_cashbox"):
            self._send_json(404, {"result": False, "errorCode": "NOT_FOUND"})
            return

        if not self._check_token():
            self._send_json(401, {"result": False, "errorCode": "UNAUTHORIZED"})
            return

        if EscposNetwork is None:
            self._send_json(200, {"result": False, "errorCode": "ESCPOS_NOT_INSTALLED"})
            return

        try:
            body = self._read_json_body()
        except (ValueError, UnicodeDecodeError):
            self._send_json(400, {"result": False, "errorCode": "INVALID_BODY"})
            return

        ip, port = self._resolve_target(body)
        if ip is None:
            self._send_json(200, {"result": False, "errorCode": "PRINTER_NOT_CONFIGURED"})
            return

        if self.path == "/open_cashbox":
            self._handle_open_cashbox(ip, port)
            return
        self._handle_print(ip, port, body)

    def _handle_print(self, ip, port, body):
        raw_image = body.get("img") or ""
        if len(raw_image) > MAX_RECEIPT_IMAGE_BYTES:
            self._send_json(200, {"result": False, "errorCode": "IMAGE_TOO_LARGE"})
            return
        try:
            image = Image.open(BytesIO(base64.b64decode(raw_image)))
        except Exception:
            _logger.exception("Could not decode the receipt image payload.")
            self._send_json(200, {"result": False, "errorCode": "INVALID_IMAGE"})
            return
        try:
            _get_connection(ip, port).print_image(image)
        except Exception as exc:
            _logger.exception("Error printing on ESC/POS printer %s:%s", ip, port)
            if self.stats_cb:
                self.stats_cb("ticket_failed", {"ip": ip, "port": port, "error": str(exc)})
            self._send_json(200, {"result": False, "errorCode": "PRINTER_NOT_REACHABLE", "canRetry": True})
            return
        if self.stats_cb:
            self.stats_cb("ticket_printed", {"ip": ip, "port": port})
        self._send_json(200, {"result": True})

    def _handle_open_cashbox(self, ip, port):
        try:
            _get_connection(ip, port).open_cashbox()
        except Exception as exc:
            _logger.exception("Error opening the cash drawer via %s:%s", ip, port)
            if self.stats_cb:
                self.stats_cb("cashbox_failed", {"ip": ip, "port": port, "error": str(exc)})
            self._send_json(200, {"result": False, "errorCode": "PRINTER_NOT_REACHABLE"})
            return
        if self.stats_cb:
            self.stats_cb("cashbox_opened", {"ip": ip, "port": port})
        self._send_json(200, {"result": True})


def create_server(config, stats_cb=None):
    """Construye (sin arrancar) el `ThreadingHTTPServer` del Camino A y,
    si corresponde, el `BusListener` del Camino B — factorizado de `main()`
    para que tanto el modo CLI/systemd como la GUI de Windows
    (`al_pos_local_agent_gui.py`) compartan exactamente la misma lógica de
    arranque; la GUI necesita levantar/bajar el agente en caliente varias
    veces dentro del mismo proceso, algo que `main()` (pensado para un solo
    arranque de vida completa del proceso) no ofrece.

    Devuelve ``(server, bus_listener)`` — ``bus_listener`` es ``None`` si el
    Camino B no está configurado o le faltan dependencias; el llamador es
    responsable de arrancarlo (``bus_listener.start()``) después de arrancar
    el server."""
    bus_listener = None
    if config.bus_enabled:
        missing = [
            name for name, mod in (("requests", requests), ("websocket-client", websocket), ("pymupdf", fitz))
            if mod is None
        ]
        if missing:
            _logger.error(
                "Camino B configurado (AL_AGENT_ODOO_URL/DB/BUS_CHANNEL) pero "
                "falta(n) instalar: %s. El agente arranca igual, solo con el "
                "Camino A, hasta que se instalen (pip install -r requirements.txt).",
                ", ".join(missing),
            )
        else:
            bus_listener = BusListener(config, stats_cb=stats_cb)
    else:
        _logger.info(
            "Camino B inactivo (falta AL_AGENT_ODOO_URL/AL_AGENT_ODOO_DB/"
            "AL_AGENT_BUS_CHANNEL) — el agente solo atiende el Camino A."
        )

    AgentRequestHandler.config = config
    AgentRequestHandler.stats_cb = stats_cb
    server = ThreadingHTTPServer((config.listen_host, config.listen_port), AgentRequestHandler)

    # HTTPS del Camino A (opcional) — ver Config.tls_enabled y el comentario
    # junto al import de `cryptography`. `server.tls_enabled` queda expuesto
    # para que `main()`/la GUI sepan qué esquema mostrar en el log sin
    # recalcular nada.
    server.tls_enabled = False
    if config.tls_enabled:
        if x509 is None:
            _logger.error(
                "AL_AGENT_TLS_ENABLED activado pero falta instalar 'cryptography' "
                "— el agente arranca igual, solo por HTTP plano (pip install -r "
                "requirements.txt)."
            )
        else:
            cert_path, key_path = _ensure_tls_cert(config.tls_cert_dir, config.tls_hostname)
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
            server.socket = ssl_context.wrap_socket(server.socket, server_side=True)
            server.tls_enabled = True

    return server, bus_listener


def main():
    # Antes de `Config()` a propósito: `--version` tiene que funcionar sin
    # ninguna variable de entorno configurada (ej. para verificar qué build
    # quedó instalada en una PC recién llegada, antes de tocar nada más).
    if "--version" in sys.argv[1:] or "-v" in sys.argv[1:]:
        print(f"al-pos-local-agent {AGENT_VERSION}")
        sys.exit(0)

    try:
        config = Config()
    except ValueError as exc:
        _logger.error(str(exc))
        sys.exit(1)

    if EscposNetwork is None:
        _logger.warning(
            "python-escpos no está instalado — el agente arranca igual (para "
            "que /health responda), pero /print y /open_cashbox van a fallar "
            "con ESCPOS_NOT_INSTALLED hasta que se instale (pip install -r "
            "requirements.txt)."
        )

    server, bus_listener = create_server(config)
    if bus_listener is not None:
        bus_listener.start()
        _logger.info("Camino B activo — conectando a %s (db=%s)", config.odoo_url, config.odoo_db)

    scheme = "https" if server.tls_enabled else "http"
    _logger.info(
        "Agente v%s escuchando en %s://%s:%s — impresoras permitidas: %s",
        AGENT_VERSION, scheme, config.listen_host, config.listen_port,
        ", ".join(f"{h}:{p}" for h, p in sorted(config.allowed_printers)),
    )
    if server.tls_enabled:
        _logger.info(
            "HTTPS activo con certificado autofirmado — la primera vez, abrir "
            "https://%s:%s/health en el navegador del cajero y aceptar la "
            "advertencia de seguridad antes de la primera venta.",
            config.tls_hostname, config.listen_port,
        )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if bus_listener is not None:
            bus_listener.stop()


if __name__ == "__main__":
    main()
