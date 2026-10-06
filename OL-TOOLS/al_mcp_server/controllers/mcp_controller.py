import json
import logging
import queue
import uuid

from werkzeug.wrappers import Response

from odoo import http
from odoo.fields import Datetime
from odoo.http import request
from odoo.tools import config as _odoo_config

from ..services import mcp_protocol
from ..services.rate_limiter import get_rate_limiter
from ..services.sse_manager import session_manager
from ..services.token_service import extract_bearer, validate_token, unauthorized

_logger = logging.getLogger(__name__)

_workers = int(_odoo_config.get("workers", 0) or 0)
if _workers > 1:
    _logger.warning(
        "Servidor MCP: se detectaron workers=%s. Las sesiones SSE se guardan en memoria en cada worker. "
        "Un POST /mcp/messages puede llegar a otro worker y devolver 404. "
        "Configure nginx con 'ip_hash' o sesiones persistentes (sticky sessions) para evitarlo.",
        _workers,
    )

_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, Mcp-Session-Id",
}

# N2: exigir HTTPS — active mcp_require_https = true en odoo.conf.
# Se omite automáticamente en modo desarrollo (workers=0 con la opción dev_mode).
_REQUIRE_HTTPS = str(_odoo_config.get("mcp_require_https", "false")).lower() in ("1", "true", "yes")


def _https_guard() -> Response | None:
    """Devuelve 400 si se exige HTTPS y la petición llegó por HTTP; None si todo está bien."""
    if not _REQUIRE_HTTPS:
        return None
    if _odoo_config.get("dev_mode"):
        return None
    # Con proxy_mode Odoo ya aplica X-Forwarded-Proto de forma segura; leer la
    # cabecera directamente permitiría falsearla.
    scheme = request.httprequest.scheme
    if scheme != "https":
        return _json_resp(
            {"error": "https_required",
             "error_description": "Este endpoint MCP requiere HTTPS."},
            400,
        )
    return None


def _ip_guard(user_info: dict, ip: str) -> Response | None:
    """Devuelve 403 si las reglas de IP del token bloquean la IP del cliente; None si todo está bien.

    Carga el registro mcp.token para llamar a is_ip_allowed(). La lectura es barata
    porque el registro ya está en la caché del ORM tras la búsqueda con sudo de validate_token.
    """
    token_id = user_info.get("token_id")
    if not token_id:
        return None
    blocked = _json_resp(
        {"error": "ip_blocked",
         "error_description": "Su dirección IP no está permitida para este token."},
        403,
    )
    try:
        # sudo: el token se acaba de validar con validate_token (sudo) y aquí
        # solo se leen sus listas de IP.
        token_sudo = request.env["mcp.token"].sudo().browse(token_id)
        if not token_sudo.exists():
            return blocked
        if not token_sudo.is_ip_allowed(ip):
            _logger.warning(
                "MCP: IP %r bloqueada por el token %s (cliente=%s)", ip, token_id, user_info.get("client_name")
            )
            return blocked
    except Exception:
        # Ante un error se deniega (fail-closed), nunca se deja pasar.
        _logger.exception("MCP: falló la comprobación de IP del token %s", token_id)
        return blocked
    return None


class McpController(http.Controller):

    # ------------------------------------------------------------------
    # OPTIONS — verificación previa CORS de todos los endpoints MCP
    # ------------------------------------------------------------------

    @http.route(["/mcp", "/mcp/sse", "/mcp/messages"], type="http", auth="public",
                methods=["OPTIONS"], csrf=False)
    def mcp_cors(self, **_kwargs):
        return Response("", status=200, headers=_CORS_HEADERS)

    # ------------------------------------------------------------------
    # POST /mcp  – transporte Streamable HTTP (especificación MCP 2025-03-26)
    # Transporte recomendado para Claude CLI, la extensión de VSCode y todos
    # los clientes MCP modernos. Sin estado: no necesita sesión SSE.
    # ------------------------------------------------------------------

    @http.route("/mcp", type="http", auth="public", methods=["POST"], csrf=False)
    def mcp_http(self, **_kwargs):
        return self._handle_streamable_http()

    # ------------------------------------------------------------------
    # POST /mcp/sse  – transporte Streamable HTTP (alias de la URL antigua)
    # ------------------------------------------------------------------

    @http.route("/mcp/sse", type="http", auth="public", methods=["POST"], csrf=False)
    def mcp_streamable(self, **_kwargs):
        return self._handle_streamable_http()

    def _handle_streamable_http(self):
        """JSON-RPC sin estado sobre HTTP POST. Busca o crea una sesión HTTP de auditoría
        persistente por token para registrar message_count y las llamadas a herramientas."""
        guard = _https_guard()
        if guard:
            return guard

        token = extract_bearer(request)
        if not token:
            return unauthorized(_base_url())

        try:
            user_info = validate_token(token, request.env)
        except Exception:
            _logger.exception("MCP HTTP: falló la validación del token")
            return unauthorized(_base_url())

        if not user_info:
            return unauthorized(_base_url())

        ip = request.httprequest.remote_addr
        ip_block = _ip_guard(user_info, ip)
        if ip_block:
            return ip_block

        allowed, _remaining = get_rate_limiter(request.env).check(
            user_info["token_hash"], max_override=user_info.get("rate_limit", 0)
        )
        if not allowed:
            return _json_resp({"error": "rate_limit_exceeded", "retry_after": 60}, 429)

        try:
            body = json.loads(request.httprequest.data or b"{}")
        except json.JSONDecodeError:
            return _json_resp(
                {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Error de análisis"}},
                400,
            )

        uid = user_info["uid"]
        token_id = user_info["token_id"]
        scope = user_info.get("scope", "write")
        restrictions = user_info.get("restrictions")
        capture_payloads = user_info.get("capture_payloads", False)

        # Busca o crea un registro persistente de sesión HTTP para este token
        session_db_id = _get_or_create_http_session(
            request.env, uid, token_id, ip
        )

        _logger.debug(
            "MCP HTTP: uid=%s scope=%s method=%s session_db=%s",
            uid,
            scope,
            body.get("method") if isinstance(body, dict) else "batch",
            session_db_id,
        )

        try:
            env = request.env(user=uid)
            if isinstance(body, list):
                responses = [
                    mcp_protocol.process_message(
                        env, msg,
                        session_db_id=session_db_id,
                        transport="http",
                        scope=scope,
                        restrictions=restrictions,
                        capture_payloads=capture_payloads,
                    )
                    for msg in body
                ]
                responses = [r for r in responses if r is not None]
                _update_http_session(request.env, session_db_id, len(body))
                if not responses:
                    return Response("", status=202, headers=_CORS_HEADERS)
                return _json_resp(responses)
            else:
                response = mcp_protocol.process_message(
                    env, body,
                    session_db_id=session_db_id,
                    transport="http",
                    scope=scope,
                    restrictions=restrictions,
                    capture_payloads=capture_payloads,
                )
                _update_http_session(request.env, session_db_id, 1)
                if response is None:
                    return Response("", status=202, headers=_CORS_HEADERS)
                return _json_resp(response)
        except Exception:
            _logger.exception("MCP HTTP: error de procesamiento uid=%s", uid)
            msg_id = body.get("id") if isinstance(body, dict) else None
            return _json_resp(
                {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32603, "message": "Error interno"}},
                500,
            )

    # ------------------------------------------------------------------
    # GET /mcp/sse  – transporte SSE antiguo (especificación MCP anterior a 2025-03-26)
    # ------------------------------------------------------------------

    @http.route("/mcp/sse", type="http", auth="public", methods=["GET"], csrf=False)
    def mcp_sse(self, **_kwargs):
        guard = _https_guard()
        if guard:
            return guard

        token = extract_bearer(request)
        if not token:
            return unauthorized(_base_url())

        try:
            user_info = validate_token(token, request.env)
        except Exception:
            _logger.exception("MCP SSE: falló la validación del token")
            return unauthorized(_base_url())

        if not user_info:
            return unauthorized(_base_url())

        ip = request.httprequest.remote_addr
        ip_block = _ip_guard(user_info, ip)
        if ip_block:
            return ip_block

        allowed, _remaining = get_rate_limiter(request.env).check(
            user_info["token_hash"], max_override=user_info.get("rate_limit", 0)
        )
        if not allowed:
            return _json_resp({"error": "rate_limit_exceeded", "retry_after": 60}, 429)

        uid = user_info["uid"]
        token_id = user_info["token_id"]
        scope = user_info.get("scope", "write")
        restrictions = user_info.get("restrictions")
        capture_payloads = user_info.get("capture_payloads", False)

        db = request.db
        mcp_session = session_manager.create(uid, db, ip)
        session_id = mcp_session.session_id

        # Guarda el contexto de gobierno en la sesión en memoria para que el manejador
        # POST (mcp_messages) recupere scope/restricciones sin volver a validar el token.
        mcp_session.scope = scope
        mcp_session.restrictions = restrictions
        mcp_session.capture_payloads = capture_payloads
        mcp_session.token_id = token_id

        _logger.info(
            "MCP SSE: nueva conexión uid=%s scope=%s sesión=%s ip=%s",
            uid, scope, session_id, ip,
        )

        # Registro de auditoría — commit antes de empezar el streaming para dejar limpio el cursor
        try:
            rec = request.env["mcp.session"].sudo().create({
                "session_id": session_id,
                "user_id": uid,
                "token_id": token_id,
                "ip_address": ip,
                "transport": "sse",
                "state": "active",
            })
            request.env.cr.commit()
            mcp_session.db_id = rec.id
        except Exception:
            _logger.warning("No se pudo crear el registro de auditoría mcp.session")

        messages_url = f"{_base_url()}/mcp/messages?session_id={session_id}"

        def _generate():
            try:
                yield f"event: endpoint\ndata: {messages_url}\n\n"
                while True:
                    try:
                        data = mcp_session.get(timeout=15)
                        if data is None:
                            break
                        yield f"event: message\ndata: {json.dumps(data, default=str)}\n\n"
                    except queue.Empty:
                        yield ": ping\n\n"
            except Exception:
                _logger.exception("MCP SSE: error del generador, sesión=%s", session_id)
            finally:
                _logger.info("MCP SSE: sesión %s cerrada", session_id)
                session_manager.remove(session_id)

        return Response(
            _generate(),
            content_type="text/event-stream; charset=utf-8",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
                **_CORS_HEADERS,
            },
        )

    # ------------------------------------------------------------------
    # POST /mcp/messages  – canal de mensajes del transporte SSE antiguo
    # ------------------------------------------------------------------

    @http.route("/mcp/messages", type="http", auth="public", methods=["POST"], csrf=False)
    def mcp_messages(self, session_id=None, **_kwargs):
        mcp_session = session_manager.get(session_id)
        if not mcp_session:
            _logger.warning("Mensajes MCP: sesión no encontrada: %s", session_id)
            return _json_resp({"error": "Sesión no encontrada o caducada"}, 404)

        # El session_id no sustituye al token: si se revocó, caducó o la IP ya
        # no está permitida, la sesión SSE se cierra.
        if not _session_token_still_valid(mcp_session, request.httprequest.remote_addr):
            session_manager.remove(session_id)
            mcp_session.close()
            return unauthorized(_base_url())

        allowed, _remaining = get_rate_limiter(request.env).check(f"session:{session_id}")
        if not allowed:
            return _json_resp({"error": "rate_limit_exceeded", "retry_after": 60}, 429)

        try:
            body = json.loads(request.httprequest.data or b"{}")
        except json.JSONDecodeError:
            return _json_resp({"error": "JSON no válido"}, 400)
        if not isinstance(body, dict):
            return _json_resp({"error": "Se esperaba un objeto JSON-RPC"}, 400)

        _logger.debug("Mensaje MCP: sesión=%s método=%s", session_id, body.get("method"))

        # Recupera el contexto de gobierno guardado durante el handshake SSE
        scope = getattr(mcp_session, "scope", "write")
        restrictions = getattr(mcp_session, "restrictions", None)
        capture_payloads = getattr(mcp_session, "capture_payloads", False)

        try:
            env = request.env(user=mcp_session.uid)
            response = mcp_protocol.process_message(
                env, body,
                session_db_id=mcp_session.db_id,
                transport="sse",
                scope=scope,
                restrictions=restrictions,
                capture_payloads=capture_payloads,
            )
            if response is not None:
                mcp_session.put(response)
        except Exception:
            _logger.exception("Error al procesar el mensaje MCP, sesión=%s", session_id)
            mcp_session.put({
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "error": {"code": -32603, "message": "Error interno"},
            })

        # Actualiza el registro de auditoría en la base de datos (no crítico)
        try:
            env = request.env(user=mcp_session.uid)
            audit = env["mcp.session"].sudo().browse(mcp_session.db_id)
            if audit.exists():
                audit.write({
                    "message_count": mcp_session.message_count,
                    "last_activity": Datetime.now(),
                })
                env.cr.commit()
        except Exception:
            _logger.debug("Falló la actualización de auditoría de mcp.session, sesión=%s", session_id)

        return Response("", status=202, headers=_CORS_HEADERS)


def _session_token_still_valid(mcp_session, ip: str) -> bool:
    """Revalida el token que abrió la sesión SSE (estado, caducidad e IP)."""
    token_id = getattr(mcp_session, "token_id", None)
    if not token_id:
        return False
    # sudo: lectura del token de la sesión, sin exponer nada al cliente.
    token_sudo = request.env["mcp.token"].sudo().browse(token_id)
    if not token_sudo.exists() or token_sudo.state != "active":
        return False
    if token_sudo.expires_at and Datetime.now() > token_sudo.expires_at:
        return False
    try:
        return token_sudo.is_ip_allowed(ip)
    except Exception:
        _logger.exception("MCP: falló la comprobación de IP del token %s", token_id)
        return False


# ---------------------------------------------------------------------------
# Utilidades de sesión HTTP
# ---------------------------------------------------------------------------

def _get_or_create_http_session(env, uid: int, token_id: int, ip: str) -> int | None:
    """Devuelve el ID en base de datos de mcp.session para un token del transporte HTTP.

    Primero consulta la caché en memoria (O(1), sin acceso a la base en peticiones repetidas).
    Solo busca y crea en la base en la primera petición de cada token en cada worker.
    """
    # Camino rápido: acierto en la caché en memoria
    cached = session_manager.get_http_session_db_id(token_id)
    if cached:
        return cached

    # Camino lento: búsqueda o creación en la base (solo una vez por token y worker)
    try:
        env_sudo = env["mcp.session"].sudo()
        existing = env_sudo.search(
            [("token_id", "=", token_id), ("transport", "=", "http"), ("state", "=", "active")],
            limit=1,
        )
        if existing:
            session_manager.set_http_session_db_id(token_id, existing.id)
            return existing.id

        rec = env_sudo.create({
            "session_id": str(uuid.uuid4()),
            "user_id": uid,
            "token_id": token_id,
            "ip_address": ip,
            "transport": "http",
            "state": "active",
        })
        env.cr.commit()
        session_manager.set_http_session_db_id(token_id, rec.id)
        return rec.id
    except Exception:
        _logger.debug("No se pudo buscar ni crear el registro de sesión HTTP")
        return None


def _update_http_session(env, session_db_id: int | None, message_delta: int) -> None:
    """Incrementa message_count y actualiza last_activity de una sesión HTTP."""
    if not session_db_id:
        return
    try:
        env.cr.execute(
            "UPDATE mcp_session SET message_count = message_count + %s, "
            "last_activity = NOW() AT TIME ZONE 'UTC' WHERE id = %s",
            (message_delta, session_db_id),
        )
        env.cr.commit()
    except Exception:
        _logger.debug("No se pudieron actualizar las estadísticas de la sesión HTTP db_id=%s", session_db_id)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _base_url() -> str:
    req = request.httprequest
    proto = req.environ.get("HTTP_X_FORWARDED_PROTO") or req.scheme
    return f"{proto}://{req.host}"


def _json_resp(data, status: int = 200) -> Response:
    return Response(
        json.dumps(data, ensure_ascii=False),
        content_type="application/json",
        status=status,
        headers={"Access-Control-Allow-Origin": "*"},
    )
