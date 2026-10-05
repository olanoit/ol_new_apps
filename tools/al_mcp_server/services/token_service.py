import hashlib
import json
import logging
from datetime import timedelta

from werkzeug.wrappers import Response

from odoo.fields import Datetime

_logger = logging.getLogger(__name__)

# Solo se escribe last_used en la base si ha pasado este tiempo desde la última actualización.
# Evita una transacción de escritura por petición cuando hay mucha carga.
_LAST_USED_THROTTLE_MINUTES = 5


def _hash_token(raw: str) -> str:
    """Hash SHA-256 de un token Bearer en claro — replica el hash de mcp_token.py."""
    return hashlib.sha256(raw.encode()).hexdigest()


def extract_bearer(request) -> str | None:
    """Extrae el token Bearer de la cabecera Authorization."""
    auth = request.httprequest.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return None


def validate_token(token: str, env) -> dict | None:
    """
    Valida un token Bearer. Calcula el hash del token en claro antes de buscarlo
    para que la base de datos nunca guarde ni compare tokens en claro.

    Devuelve un diccionario con:
        uid             – ID del usuario de Odoo
        client_name     – nombre visible del token
        token_id        – ID del registro mcp.token
        token_hash      – lo usa el limitador de peticiones; nunca se registra en el log
        rate_limit      – límite propio del usuario (0 = usar el valor global)
        scope           – 'read' | 'write' | 'admin'
        capture_payloads – bool, si se capturan argumentos y resultados en el registro de auditoría
        restrictions    – diccionario listo para env.context['mcp_restrictions']:
            {
                'allowed_models': conjunto de nombres de modelo (vacío = todos permitidos),
                'denied_models':  conjunto de nombres de modelo (vacío = ninguno denegado),
                'field_restrictions': dict {nombre_modelo: [campo, ...]} (vacío = todos permitidos),
            }

    Devuelve None si el token no es válido, ha caducado o fue revocado.

    last_used se limita: se escribe como mucho una vez cada 5 minutos para evitar
    una transacción de escritura en cada petición HTTP cuando hay mucha carga.
    """
    if not token:
        return None

    token_hash = _hash_token(token)
    rec = env["mcp.token"].sudo().search(
        [("token", "=", token_hash), ("state", "=", "active")],
        limit=1,
    )
    if not rec:
        return None

    now = Datetime.now()

    if rec.expires_at and now > rec.expires_at:
        rec.write({"state": "expired"})
        return None

    # Limitación: solo se actualiza last_used si nunca se fijó o si supera el umbral
    threshold = now - timedelta(minutes=_LAST_USED_THROTTLE_MINUTES)
    if not rec.last_used or rec.last_used < threshold:
        rec.write({"last_used": now})

    # Arma los conjuntos de restricciones de modelos — se cargan una sola vez aquí para que tool_executor no vuelva a consultar
    allowed_models = set(rec.allowed_model_ids.mapped("model")) if rec.allowed_model_ids else set()
    denied_models = set(rec.denied_model_ids.mapped("model")) if rec.denied_model_ids else set()

    field_restrictions = {}
    if rec.field_restrictions:
        try:
            parsed = json.loads(rec.field_restrictions)
            if isinstance(parsed, dict):
                field_restrictions = {k: v for k, v in parsed.items() if isinstance(v, list)}
        except (json.JSONDecodeError, TypeError):
            _logger.warning(
                "Token MCP %s: JSON no válido en field_restrictions — se ignora", rec.id
            )

    return {
        "uid": rec.user_id.id,
        "client_name": rec.name,
        "token_id": rec.id,
        "token_hash": token_hash,        # se pasa al limitador de peticiones — nunca se registra en el log
        "rate_limit": rec.user_id.mcp_rate_limit or 0,  # N5: 0 = usar el valor global
        "scope": rec.scope or "write",
        "capture_payloads": bool(rec.capture_payloads),
        "restrictions": {
            "allowed_models": allowed_models,
            "denied_models": denied_models,
            "field_restrictions": field_restrictions,
        },
    }


def unauthorized(base_url: str) -> Response:
    """
    Devuelve 401 con WWW-Authenticate apuntando al descubrimiento OAuth.
    Claude Code CLI inicia automáticamente el flujo OAuth al ver esta cabecera.
    """
    return Response(
        json.dumps({"error": "unauthorized", "error_description": "Se requiere un token Bearer válido."}),
        status=401,
        content_type="application/json",
        headers={
            "WWW-Authenticate": (
                f'Bearer realm="{base_url}", '
                f'resource_metadata="{base_url}/.well-known/oauth-protected-resource/mcp/sse"'
            )
        },
    )
