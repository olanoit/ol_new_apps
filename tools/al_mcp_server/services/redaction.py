"""
Utilidad para ocultar datos sensibles al capturar contenido en el registro de auditoría MCP.

Recorre en profundidad diccionarios y listas y sustituye el valor de cualquier
clave que coincida con un conjunto configurable de nombres sensibles por la cadena
literal "[OCULTO]". Las claves se comparan sin distinguir mayúsculas de minúsculas.

Solo usa la biblioteca estándar — sin dependencia de Odoo, así que es fácil de probar.

Example:
    >>> from services.redaction import redact
    >>> redact({"username": "alice", "password": "s3cr3t"})
    {'username': 'alice', 'password': '[OCULTO]'}
    >>> redact([{"api_key": "abc", "data": [{"token": "xyz"}]}])
    [{'api_key': '[OCULTO]', 'data': [{'token': '[OCULTO]'}]}]
"""

_DEFAULT_SENSITIVE_KEYS = frozenset({
    "password", "passwd", "pwd",
    "secret",
    "token",
    "api_key", "apikey",
    "authorization",
    "x-api-key",
    "ssn",
    "credit_card",
    "cvv",
})

_REDACTED = "[OCULTO]"


def redact(obj, sensitive_keys=None):
    """
    Recorre en profundidad *obj* (dict/list/primitivo) y sustituye los valores sensibles.

    Args:
        obj: cualquier valor serializable a JSON (dict, list, str, int, etc.).
        sensitive_keys: iterable opcional de nombres de clave en minúsculas que se ocultan.
                        Por defecto, el conjunto de claves sensibles incorporado.

    Returns:
        Un objeto nuevo con la misma estructura pero con los valores sensibles sustituidos.
        Los escalares que no son dict ni list se devuelven sin cambios.
    """
    if sensitive_keys is None:
        keys = _DEFAULT_SENSITIVE_KEYS
    else:
        keys = frozenset(k.lower() for k in sensitive_keys)

    return _traverse(obj, keys)


def _traverse(obj, keys):
    if isinstance(obj, dict):
        return {
            k: (_REDACTED if k.lower() in keys else _traverse(v, keys))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_traverse(item, keys) for item in obj]
    return obj
