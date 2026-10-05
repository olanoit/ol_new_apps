import json
import logging
import time

from . import tool_executor
from . import resource_service
from .tool_executor import odoo_json_default
from .redaction import redact

_logger = logging.getLogger(__name__)

MCP_PROTOCOL_VERSION = "2025-03-26"
SERVER_INFO = {"name": "Odoo MCP Server", "version": "11.0.0"}

_PAYLOAD_MAX_CHARS = 4000


def process_message(env, msg: dict, session_db_id: int | None = None,
                    transport: str = "http",
                    scope: str = "write",
                    restrictions: dict | None = None,
                    capture_payloads: bool = False) -> dict | None:
    """
    Procesa un mensaje MCP JSON-RPC 2.0 y devuelve el diccionario de respuesta,
    o None para las notificaciones que no requieren respuesta.

    session_db_id:    ID en base de datos del registro mcp.session (para registrar las llamadas a herramientas).
    transport:        'sse' o 'http' — se guarda en mcp.session.log.
    scope:            alcance del token — 'read' | 'write' | 'admin'.
                      Se inyecta en env.context['mcp_scope'] para que tool_executor
                      lo aplique sin otra consulta a la base de datos.
    restrictions:     diccionario con 'allowed_models', 'denied_models' y
                      'field_restrictions' — se carga una vez al validar el token.
                      Se inyecta en env.context['mcp_restrictions'].
    capture_payloads: si es True, los argumentos y resultados de las herramientas se
                      guardan en el registro de auditoría (tras ocultar datos personales y truncar).
    """
    if not isinstance(msg, dict):
        return _err(None, -32600, "Solicitud no válida")

    method = msg.get("method")
    msg_id = msg.get("id")
    params = msg.get("params") or {}

    # Inyecta el contexto de gobierno para que todas las llamadas posteriores (tool_executor, etc.)
    # lo lean sin arrastrar parámetros adicionales por toda la pila de llamadas.
    ctx_updates = {"mcp_scope": scope}
    if restrictions:
        ctx_updates["mcp_restrictions"] = restrictions
    env = env.with_context(**ctx_updates)

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------
    if method == "initialize":
        return _ok(
            msg_id,
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {},
                    "resources": {"subscribe": False, "listChanged": False},
                },
                "serverInfo": SERVER_INFO,
            },
        )

    if method in ("notifications/initialized", "notifications/cancelled"):
        return None

    if method == "ping":
        return _ok(msg_id, {})

    # ------------------------------------------------------------------
    # Herramientas
    # ------------------------------------------------------------------
    if method == "tools/list":
        from ..models.mcp_tool_registry import get_tool_definitions
        return _ok(msg_id, {"tools": get_tool_definitions()})

    if method == "tools/call":
        return _handle_tool_call(
            env, msg_id, params, session_db_id, transport, capture_payloads
        )

    # ------------------------------------------------------------------
    # Recursos
    # ------------------------------------------------------------------
    if method == "resources/list":
        return _ok(msg_id, {"resources": resource_service.RESOURCES})

    if method == "resources/templates/list":
        return _ok(msg_id, {"resourceTemplates": resource_service.RESOURCE_TEMPLATES})

    if method == "resources/read":
        return _handle_resource_read(env, msg_id, params)

    # ------------------------------------------------------------------
    # Prompts (no implementados — se devuelve una lista vacía por compatibilidad con los clientes)
    # ------------------------------------------------------------------
    if method == "prompts/list":
        return _ok(msg_id, {"prompts": []})

    if method == "prompts/get":
        return _err(msg_id, -32602, "No hay prompts definidos en este servidor.")

    # ------------------------------------------------------------------
    # Desconocido
    # ------------------------------------------------------------------
    if msg_id is not None:
        return _err(msg_id, -32601, f"Método no encontrado: {method}")

    return None


# ---------------------------------------------------------------------------
# Manejador de llamadas a herramientas
# ---------------------------------------------------------------------------

def _handle_tool_call(env, msg_id, params: dict,
                      session_db_id: int | None, transport: str,
                      capture_payloads: bool) -> dict:
    tool_name = params.get("name")
    tool_input = params.get("arguments") or {}
    t0 = time.monotonic()
    try:
        # Savepoint: si la herramienta falla, se deshacen sus escrituras parciales
        # (el controlador hace commit al final de la petición) y el cursor sigue
        # usable para registrar el error.
        with env.cr.savepoint():
            result = tool_executor.execute_tool(env, tool_name, tool_input)
        duration_ms = int((time.monotonic() - t0) * 1000)
        req_payload, res_payload = _build_payloads(capture_payloads, tool_input, result)
        _log_tool_call(env, session_db_id, transport, tool_name, tool_input,
                       result, duration_ms, is_error=False,
                       request_payload=req_payload, response_payload=res_payload)
        text = json.dumps(result, default=odoo_json_default, ensure_ascii=False, indent=2)
        return _ok(
            msg_id,
            {"content": [{"type": "text", "text": text}], "isError": False},
        )
    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        req_payload, _ = _build_payloads(capture_payloads, tool_input, None)
        _log_tool_call(env, session_db_id, transport, tool_name, tool_input,
                       {}, duration_ms, is_error=True, error_message=str(exc),
                       request_payload=req_payload, response_payload=None)
        _logger.exception("Error en la herramienta MCP %r", tool_name)
        return _ok(
            msg_id,
            {"content": [{"type": "text", "text": str(exc)}], "isError": True},
        )


def _build_payloads(capture: bool, args: dict, result) -> tuple[str | None, str | None]:
    """Devuelve (request_payload_str, response_payload_str) si capture=True; si no, (None, None)."""
    if not capture:
        return None, None
    try:
        redacted_args = redact(args)
        req = json.dumps(redacted_args, default=odoo_json_default, ensure_ascii=False)
        req = req[:_PAYLOAD_MAX_CHARS]
    except Exception:
        req = None

    res = None
    if result is not None:
        try:
            redacted_result = redact(result)
            res = json.dumps(redacted_result, default=odoo_json_default, ensure_ascii=False)
            res = res[:_PAYLOAD_MAX_CHARS]
        except Exception:
            res = None

    return req, res


def _log_tool_call(env, session_db_id, transport, tool_name, tool_input,
                   result, duration_ms, is_error=False, error_message="",
                   request_payload=None, response_payload=None):
    """Crea el registro mcp.session.log. No es crítico: si falla, se ignora en silencio."""
    try:
        odoo_model = tool_input.get("model") or ""
        record_count = 0
        if not is_error and isinstance(result, dict):
            record_count = (
                result.get("total")
                or result.get("count")
                or result.get("updated")
                or result.get("deleted")
                or (1 if "id" in result else 0)
            )

        vals = {
            "session_id": session_db_id or False,
            "user_id": env.uid,
            "tool_name": tool_name or "",
            "odoo_model": odoo_model or False,
            "record_count": record_count or 0,
            "duration_ms": duration_ms,
            "is_error": is_error,
            "error_message": (error_message[:255] if error_message else False),
            "transport": transport,
        }
        if request_payload is not None:
            vals["request_payload"] = request_payload
        if response_payload is not None:
            vals["response_payload"] = response_payload

        env["mcp.session.log"].sudo().create(vals)
    except Exception:
        _logger.debug("No se pudo crear mcp.session.log", exc_info=True)


# ---------------------------------------------------------------------------
# Manejador de lectura de recursos
# ---------------------------------------------------------------------------

def _handle_resource_read(env, msg_id, params: dict) -> dict:
    uri = params.get("uri", "")
    try:
        content = resource_service.read_resource(uri, env)
        return _ok(
            msg_id,
            {
                "contents": [
                    {"uri": uri, "mimeType": "application/json", "text": content}
                ]
            },
        )
    except Exception as exc:
        _logger.exception("Error al leer el recurso MCP: %s", uri)
        return _err(msg_id, -32002, str(exc))


# ---------------------------------------------------------------------------
# Utilidades JSON-RPC
# ---------------------------------------------------------------------------

def _ok(msg_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _err(msg_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}
