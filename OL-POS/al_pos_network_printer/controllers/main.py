import base64
import hashlib
import logging
import socket
import threading
import time
from io import BytesIO

from odoo import http
from odoo.addons.queue_job.exception import RetryableJobError
from odoo.exceptions import UserError
from odoo.http import request

_logger = logging.getLogger(__name__)

# Import diferido a propósito (ver __manifest__.py `external_dependencies`):
# si `python-escpos` no está instalado en el servidor, el módulo igual se
# instala y el POS sigue funcionando con cualquier otra impresora (Epson,
# IoT). Solo falla, con un mensaje claro (`print_receipt` más abajo), al
# intentar imprimir efectivamente en una impresora `escpos_network`. El
# módulo del que se migró esta idea importaba `escpos` sin protección a
# nivel de módulo: si la librería faltaba, todo el módulo (y por lo tanto
# todos sus controladores) fallaba al cargar.
try:
    from escpos.printer import Network as EscposNetwork
except ImportError:
    EscposNetwork = None

try:
    from PIL import Image
except ImportError:
    Image = None

# Import diferido, mismo criterio que python-escpos: solo hace falta para
# print_pdf_bytes() (comprobantes en PDF que genere otro módulo) — nunca
# para el camino normal de imprimir el
# ticket, que ya llega como imagen (ver print_receipt más abajo).
try:
    import pymupdf as fitz  # `import fitz` es el nombre viejo, deprecado desde pymupdf 1.24
except ImportError:
    fitz = None

# Ancho de impresión objetivo, en píxeles, para páginas de PDF rasterizadas
# con print_pdf_bytes(). 576px es el estándar de facto para térmicas de
# 80mm ESC/POS (203dpi, 8 puntos/mm × 72mm de área imprimible real).
DEFAULT_PDF_PRINT_WIDTH_PX = 576

# Por encima de este tamaño se rechaza el payload antes de decodificar el
# base64, para que un caller sin autenticar no pueda forzar al servidor a
# reservar memoria arbitraria. Un ticket de 80mm codificado como JPEG de
# baja compresión no debería acercarse ni de lejos a este límite.
MAX_RECEIPT_IMAGE_BYTES = 5 * 1024 * 1024

# Intervalo entre bytes null de keep-alive, usado para detectar una
# impresora que se desconectó sin que hubiera ninguna impresión de por
# medio para notarlo.
KEEP_ALIVE_INTERVAL_SECONDS = 300


class _NetworkPrinterConnection:
    """Conexión TCP persistente a una impresora ESC/POS de red.

    El socket se mantiene abierto entre impresiones (evita el costo de un
    nuevo handshake TCP por cada ticket) y solo se reconecta cuando hace
    falta: cuando el keep-alive detecta una caída, o cuando falla una
    impresión.

    Cada instancia tiene su propio lock. El controlador del que se migró
    esta idea usaba un único booleano a nivel de módulo como lock global
    para *todas* las impresoras del sistema: imprimir en la impresora de
    una caja bloqueaba a todas las demás cajas mientras tanto. Acá, imprimir
    en la impresora de la caja 1 no afecta a la caja 2.
    """

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.lock = threading.Lock()
        self._printer = None
        self._stop = threading.Event()
        self._connect()
        self._keep_alive_thread = threading.Thread(
            target=self._keep_alive_loop, daemon=True
        )
        self._keep_alive_thread.start()

    def _connect(self):
        self._printer = EscposNetwork(self.host, self.port, timeout=10)

    def _reconnect(self):
        try:
            self._printer.close()
        except Exception:
            pass
        self._connect()

    def stop(self):
        """Corta el keep-alive y cierra el socket — llamado por
        `release_connection()` cuando ningún `pos.config` en modo
        "backend" sigue apuntando a este destino (ver
        `models/pos_config.py::write`). Sin esto, esta conexión (y su
        hilo de keep-alive, que reconecta solo cada vez que falla) queda
        viva para siempre en el proceso de Odoo aunque el TPV haya
        cambiado a modo "agent" — confirmado en vivo (2026-09-09): el
        agente local recién configurado recibía "Connection reset by
        peer" al imprimir, porque este keep-alive viejo seguía
        reconectando contra la misma impresora física, y la mayoría de
        las térmicas ESC/POS solo aceptan una conexión TCP a la vez."""
        self._stop.set()
        with self.lock:
            try:
                self._printer.close()
            except Exception:
                pass

    def _keep_alive_loop(self):
        while not self._stop.wait(KEEP_ALIVE_INTERVAL_SECONDS):
            with self.lock:
                try:
                    self._printer._raw(b"\x00")
                except Exception:
                    _logger.info(
                        "Keep-alive failed for printer %s:%s, reconnecting...",
                        self.host, self.port,
                    )
                    self._reconnect()

    def _execute_with_retry(self, fn):
        """Corre `fn()` bajo el lock, reconectando una vez si falla por un
        error a nivel de socket — misma lógica de reintento que antes vivía
        duplicada dentro de `print_image` (single-shot: si la conexión
        fresca vuelve a fallar, se propaga tal cual, sin recursión sin
        freno). Factorizada para que `print_test_ticket` (botón "Probar
        impresora", ver `pos_config.action_test_escpos_printer`) reuse el
        mismo manejo de conexión sin volver a escribirlo.
        """
        with self.lock:
            try:
                fn()
            except (BrokenPipeError, socket.error, OSError):
                _logger.info(
                    "Lost connection to %s:%s, reconnecting and retrying...",
                    self.host, self.port,
                )
                self._reconnect()
                fn()

    def print_image(self, image):
        """Imprime `image` (un PIL.Image) — el ticket real siempre llega así,
        ya renderizado por el navegador (ver
        `PosNetworkPrinterController.print_receipt`)."""
        def _do():
            self._printer.image(image)
            self._printer.cut()
        self._execute_with_retry(_do)

    def print_test_ticket(self, lines):
        """Imprime un ticket de texto plano de prueba usando los comandos
        nativos de `python-escpos` (`.text()`/`.set()`) en vez de rasterizar
        una imagen — a diferencia del ticket real, acá no hay nada que ya
        venga renderizado desde el navegador (este método lo llama un botón
        de Ajustes, sin ninguna orden de por medio), así que no vale la pena
        meter PIL/fuentes para 6 líneas de texto."""
        def _do():
            p = self._printer
            p.set(align="center", bold=True, width=2, height=2)
            p.text("PRUEBA DE IMPRESION\n")
            p.set(align="center", bold=False, width=1, height=1)
            for line in lines:
                p.text(f"{line}\n")
            p.text("\n")
            p.cut()
        self._execute_with_retry(_do)

    def open_cashbox(self):
        with self.lock:
            self._printer.cashdraw(2)


# Registro de conexiones activas, una por IP:puerto. Solo se toca bajo
# `_connections_registry_lock`, para evitar crear dos conexiones a la misma
# impresora si dos requests llegan al mismo tiempo en workers/threads
# distintos del mismo proceso.
#
# Limitación conocida (documentada en el README): en un despliegue con
# varios *workers* de Odoo (procesos separados), cada worker mantiene su
# propio registro en memoria, y por lo tanto su propia conexión TCP hacia
# cada impresora. Es la misma limitación que tiene cualquier controlador
# HTTP con estado local al proceso; no afecta la corrección de la
# impresión, solo significa que puede haber más de una conexión TCP abierta
# hacia la misma impresora si el tráfico se reparte entre varios workers.
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


def release_connection(host, port):
    """Cierra y descarta la conexión persistente hacia `host:port`, si
    existe — ver `pos.config.write()` en `models/pos_config.py`: se llama
    apenas ningún TPV en modo "backend" sigue apuntando a este destino
    (cambió a modo "agent", o cambió de impresora). No-op si no había
    ninguna conexión abierta hacia ahí."""
    key = (host, port)
    with _connections_registry_lock:
        connection = _connections.pop(key, None)
    if connection is not None:
        connection.stop()


def _find_target_owner(env, ip, port):
    """Devuelve el registro (`pos.config` o `pos.printer`) cuya impresora
    ESC/POS matchea `ip:port`, o `None` si ninguno lo hace — factorizado de
    `is_allowed_target()` para que `_enqueue_escpos_retry()` pueda encolar
    el job de reintento sobre el mismo registro que ya validó el destino,
    sin repetir la búsqueda ni asumir cuál de los dos modelos matcheó.
    """
    env = env(su=True)
    port_str = str(port)
    # Solo PDVs con la impresora ESC/POS de red ACTIVA (toggle, ver
    # `pos.config._escpos_receipt_printer_active`): con el toggle apagado
    # ese destino deja de ser válido aunque la IP siga guardada.
    config = env["pos.config"].sudo().search([
        ("escpos_network_printer_enabled", "=", True),
        ("escpos_printer_ip", "=", ip),
        ("escpos_printer_port", "=", port_str),
    ], limit=1)
    if config:
        return config
    printer = env["pos.printer"].sudo().search([
        ("escpos_printer_ip", "=", ip),
        ("escpos_printer_port", "=", port_str),
    ], limit=1)
    return printer or None


def is_allowed_target(env, ip, port):
    """Solo permite imprimir en un IP:puerto ya configurado en algún
    `pos.config` o `pos.printer` activo.

    Misma función que usaba el controller (ver docstring de
    `PosNetworkPrinterController._is_allowed_target`, que ahora delega
    acá), separada a nivel de módulo para que `print_pdf_bytes()` también
    pueda validar el destino desde código Python que no corre dentro de un
    request HTTP (ej. un job de `queue_job`, que no tiene `request.env`).
    """
    return bool(_find_target_owner(env, ip, port))


def _pdf_bytes_to_images(pdf_bytes, target_width_px=DEFAULT_PDF_PRINT_WIDTH_PX):
    """Rasteriza cada página de `pdf_bytes` a un `PIL.Image` escalado para
    que el ancho quede en `target_width_px` (alto proporcional) — mismo
    contrato de entrada que ya espera `_NetworkPrinterConnection.print_image`
    para el ticket normal (ver `print_receipt`), así que una vez rasterizado
    reutiliza exactamente el mismo camino de impresión, sin duplicar nada
    del manejo de conexión/lock/ESC-POS.
    """
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


def print_pdf_bytes(env, ip, port, pdf_bytes, target_width_px=DEFAULT_PDF_PRINT_WIDTH_PX):
    """Imprime un PDF (todas sus páginas, en orden) en la impresora ESC/POS
    de red `ip:port`, rasterizándolo primero — pensado para documentos que
    no son el ticket del POS (ej. un comprobante en PDF que genere otro
    módulo), y por eso llamable directamente desde
    Python (no solo por HTTP): un job de `queue_job` no tiene un request
    activo del que sacar `request.env`, así que acá `env` se recibe
    explícito en vez de tomarlo de `request` como hace el controller.

    Devuelve `True` si imprimió, `False` si el destino no está en la
    allow-list o si falta `PyMuPDF` — nunca levanta, para que un llamador
    "best-effort" (una impresión automática) no tumbe el flujo que lo
    rodea por un comprobante que no se pudo imprimir.
    """
    if fitz is None:
        _logger.warning(
            "print_pdf_bytes: falta instalar 'pymupdf' en el servidor Odoo "
            "(pip install pymupdf) — no se puede imprimir el PDF en %s:%s.",
            ip, port,
        )
        return False
    if not is_allowed_target(env, ip, port):
        _logger.warning(
            "print_pdf_bytes: %s:%s no está configurado en ningún "
            "pos.config/pos.printer, no se imprime.", ip, port,
        )
        return False
    try:
        images = _pdf_bytes_to_images(pdf_bytes, target_width_px=target_width_px)
        connection = _get_connection(ip, port)
        for image in images:
            connection.print_image(image)
        return True
    except Exception:
        _logger.exception("Error imprimiendo PDF en la impresora ESC/POS %s:%s", ip, port)
        return False


def print_test_ticket(ip, port, lines):
    """Imprime un ticket de texto de prueba en `ip:port` — usado por
    `pos.config.action_test_escpos_printer()` (botón "Probar impresora",
    ver `views/pos_config_view.xml`), que solo aplica con
    `escpos_printer_mode == "backend"`: ahí el backend de Odoo SÍ tiene
    ruta de red directa a la impresora, así que puede abrir el socket él
    mismo, sin request HTTP de por medio (es un botón de formulario en
    Ajustes) — mismo criterio que `print_pdf_bytes`.

    A diferencia de `print_pdf_bytes` (best-effort, nunca lanza, pensado
    para no tumbar un flujo de venta), esto SÍ debe fallar visiblemente:
    es justo lo que el botón está probando — el llamador (el `action_`
    del botón) es el que traduce la excepción a un `UserError` legible.

    Tampoco valida contra la allow-list de `is_allowed_target`: a
    diferencia del controller HTTP público (pensado contra un request que
    cualquiera podría falsificar), quien puede apretar este botón ya tiene
    acceso de escritura a este mismo `pos.config` — no hay nada que
    proteger acá que ese acceso no permita ya.
    """
    if EscposNetwork is None:
        raise UserError(
            "Falta instalar la librería 'python-escpos' en el servidor "
            "Odoo (pip install python-escpos)."
        )
    _get_connection(ip, port).print_test_ticket(lines)


def retry_print_receipt(env, ip, port, raw_image_b64):
    """Cuerpo del job de reintento en background (ver
    `_enqueue_escpos_retry()` y `pos.config`/`pos.printer`
    `._escpos_retry_print_receipt_job`, que solo delegan acá) — se encola
    cuando `PosNetworkPrinterController.print_receipt` falla tras su propio
    retry-once síncrono (`_execute_with_retry`), para que un corte de
    energía/red/papel momentáneo en la impresora no pierda el ticket solo
    porque el cajero no alcanzó a notar o reintentar el popup del core.

    Revalida `is_allowed_target` antes de imprimir: el job puede correr
    minutos después de encolado, y para entonces el destino pudo haberse
    reconfigurado o eliminado — mismo nivel de paranoia que ya exige el
    endpoint HTTP público, acá porque el `pos.config`/`pos.printer` sobre el
    que corre el job pudo cambiar de IP entre que se encoló y que corrió.

    No lanza (deja el job "hecho", no lo reintenta) si el payload es
    inválido o el destino ya no está configurado — ninguno de los dos
    casos se arregla solo con más reintentos. Si falla la impresión en sí,
    levanta `RetryableJobError` para que `queue_job` lo reintente según el
    `retry_pattern` de `data/queue_job_function_data.xml`.
    """
    if not is_allowed_target(env, ip, port):
        _logger.info(
            "Retry job: %s:%s ya no está configurado, se descarta el reintento.",
            ip, port,
        )
        return
    try:
        image = Image.open(BytesIO(base64.b64decode(raw_image_b64)))
    except Exception:
        _logger.exception(
            "Retry job: no se pudo decodificar la imagen del ticket para "
            "%s:%s, se descarta el reintento.", ip, port,
        )
        return
    try:
        _get_connection(ip, port).print_image(image)
    except Exception as exc:
        raise RetryableJobError(
            f"No se pudo reimprimir en {ip}:{port}: {exc}"
        ) from exc


def _escpos_retry_queue_enabled(owner):
    """`True` si el `pos.config` (recibo principal) o alguno de los
    `pos.config` que usan este `pos.printer` (impresora de preparación,
    ver `pos.printer.pos_config_ids` del core) tiene activo
    `escpos_retry_queue_enabled` — el opt-in de la cola de reintento (ver
    ese campo en `models/pos_config.py`, inactivo por defecto). Un
    `pos.printer` puede estar compartido entre varios PDV; alcanza con que
    uno solo lo tenga activo para encolar sus reintentos."""
    if owner._name == "pos.config":
        return owner.escpos_retry_queue_enabled
    return bool(owner.pos_config_ids.filtered("escpos_retry_queue_enabled"))


def _enqueue_escpos_retry(env, ip, port, raw_image_b64):
    """Encola `retry_print_receipt()` sobre el `pos.config`/`pos.printer`
    que matchea `ip:port` — llamado desde `print_receipt` cuando el intento
    síncrono falla. `identity_key` incluye un hash del contenido de la
    imagen para no duplicar el job si el cajero también aprieta "Reintentar"
    en el popup nativo del core mientras el job en cola sigue pendiente
    (mismo ticket, mismo destino -> mismo `identity_key` -> `queue_job` no
    crea uno nuevo).

    No-op (devuelve `False`) si `escpos_retry_queue_enabled` está apagado
    (default) — la cola es opt-in, ver el campo en `models/pos_config.py`.
    Devuelve `True` si efectivamente encoló, para que el caller (el
    endpoint HTTP) sepa si el `"queued"` que le contesta al navegador es
    cierto."""
    owner = _find_target_owner(env, ip, port)
    if owner is None:
        # No debería pasar: `print_receipt` ya validó el destino antes de
        # llegar acá. Defensivo por si el registro se borró en el instante
        # entre esa validación y este punto.
        return False
    if not _escpos_retry_queue_enabled(owner):
        return False
    content_hash = hashlib.sha256(raw_image_b64.encode()).hexdigest()[:16]
    owner.with_delay(
        max_retries=15,
        description=f"Reintento de impresión ESC/POS {ip}:{port}",
        identity_key=f"escpos_retry:{ip}:{port}:{content_hash}",
    )._escpos_retry_print_receipt_job(ip, port, raw_image_b64)
    return True


class PosNetworkPrinterController(http.Controller):
    """Puente HTTP -> socket ESC/POS para impresoras de red sin IoT Box.

    Reemplaza la ruta `/cr_print_receipt` (`auth='none', cors='*'`, sin
    validar el destino) del módulo del que se migró esta idea. Acá el
    destino se restringe con una allow-list (ver `_is_allowed_target`) y no
    se habilita CORS: la llamada la hace el propio POS de Odoo vía `rpc()`,
    así que nunca necesita servir a un origen distinto del propio servidor
    de Odoo.
    """

    def _is_allowed_target(self, ip, port):
        """Solo permite imprimir en un IP:puerto ya configurado en algún
        `pos.config` o `pos.printer` activo.

        Sin esto, cualquiera capaz de invocar esta ruta podría usar el
        servidor Odoo como proxy para abrir conexiones TCP arbitrarias hacia
        la red interna (SSRF) y escribirles bytes arbitrarios. Con esto, la
        superficie queda acotada a exactamente lo que un administrador ya
        configuró explícitamente — el mismo nivel de confianza que Odoo ya
        le da a la IP de una impresora Epson o a una IoT Box.

        Delega en `is_allowed_target()` (nivel de módulo) — ver su docstring
        para por qué está separada.
        """
        return is_allowed_target(request.env, ip, port)

    def _resolve_target(self, receipt):
        ip = receipt.get("ip")
        port = receipt.get("port")
        if not ip or not port:
            return None, None
        try:
            port = int(port)
        except (TypeError, ValueError):
            return None, None
        if not self._is_allowed_target(ip, port):
            _logger.warning(
                "Rejected print request: %s:%s is not configured on any "
                "pos.config/pos.printer.", ip, port,
            )
            return None, None
        return ip, port

    @http.route("/al_pos_network_printer/print_receipt", type="jsonrpc", auth="public")
    def print_receipt(self, receipt):
        if EscposNetwork is None:
            raise UserError(
                "No se puede imprimir: falta instalar la librería "
                "'python-escpos' en el servidor Odoo (pip install python-escpos)."
            )

        ip, port = self._resolve_target(receipt)
        if ip is None:
            return {"result": False, "errorCode": "PRINTER_NOT_CONFIGURED"}

        raw_image = receipt.get("img") or ""
        if len(raw_image) > MAX_RECEIPT_IMAGE_BYTES:
            return {"result": False, "errorCode": "IMAGE_TOO_LARGE"}

        try:
            image = Image.open(BytesIO(base64.b64decode(raw_image)))
        except Exception:
            _logger.exception("Could not decode the receipt image payload.")
            return {"result": False, "errorCode": "INVALID_IMAGE"}

        try:
            _get_connection(ip, port).print_image(image)
        except Exception:
            _logger.exception("Error printing on ESC/POS printer %s:%s", ip, port)
            queued = _enqueue_escpos_retry(request.env, ip, port, raw_image)
            return {
                "result": False,
                "errorCode": "PRINTER_NOT_REACHABLE",
                "canRetry": True,
                "queued": queued,
            }

        return {"result": True}

    @http.route("/al_pos_network_printer/open_cashbox", type="jsonrpc", auth="public")
    def open_cashbox(self, receipt):
        # Misma validación que print_receipt: solo abre el cajón de una
        # impresora que ya esté configurada como tal en la base de datos.
        if EscposNetwork is None:
            return {"result": False, "errorCode": "ESCPOS_NOT_INSTALLED"}

        ip, port = self._resolve_target(receipt)
        if ip is None:
            return {"result": False, "errorCode": "PRINTER_NOT_CONFIGURED"}

        try:
            _get_connection(ip, port).open_cashbox()
        except Exception:
            _logger.exception("Error opening the cash drawer via %s:%s", ip, port)
            return {"result": False, "errorCode": "PRINTER_NOT_REACHABLE"}

        return {"result": True}
