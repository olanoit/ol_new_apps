"""
Caché de esquemas en el propio proceso del servidor MCP.

Guarda valores ya calculados (esquemas de modelos, catálogo, resultados de fields_get)
para que las peticiones repetidas de la IA dentro de la ventana TTL no consulten el ORM.

Diseño:
- Diccionario a nivel de módulo protegido por un threading.RLock.
- Expulsión LRU al llegar a MAX_ENTRIES mediante un deque de claves en orden de inserción.
- Contadores de aciertos y fallos para la observabilidad.
- Vaciado completo de la caché al modificar ir.model / ir.model.fields (ver ir_model_invalidate.py).
"""

import logging
import threading
import time
from collections import deque

_logger = logging.getLogger(__name__)

_MAX_ENTRIES = 1000

_lock = threading.RLock()
# {cache_key: (timestamp_float, value)}
_store: dict[str, tuple[float, object]] = {}
# Claves en orden de inserción — se usan para la expulsión LRU (la de la izquierda es la más antigua)
_order: deque[str] = deque()

# Contadores de aciertos y fallos (aproximados con concurrencia — suficiente para operación)
_hits = 0
_misses = 0


# ---------------------------------------------------------------------------
# Utilidades de configuración (se leen de env en cada llamada — es barato y evita configuración obsoleta)
# ---------------------------------------------------------------------------

def _cache_enabled(env) -> bool:
    ICP = env["ir.config_parameter"].sudo()
    return ICP.get_param("mcp_server.enable_schema_cache", "True").lower() in ("1", "true", "yes")


def _cache_ttl(env) -> int:
    ICP = env["ir.config_parameter"].sudo()
    try:
        return int(ICP.get_param("mcp_server.schema_cache_ttl_seconds", 300) or 300)
    except (ValueError, TypeError):
        return 300


def scoped_key(env, key: str) -> str:
    """Prefija la clave con base de datos, usuario e idioma.

    fields_get y las acciones dependen de los grupos del usuario y del idioma;
    compartir la entrada entre usuarios (o entre bases del mismo proceso)
    filtraría metadatos que el usuario no puede ver.
    """
    return f"{env.cr.dbname}:{env.uid}:{env.lang or ''}:{key}"


# ---------------------------------------------------------------------------
# Operaciones principales
# ---------------------------------------------------------------------------

def get_or_compute(key: str, ttl_seconds: int, compute_fn):
    """Devuelve el valor en caché si existe y está vigente; si no, llama a compute_fn() y lo guarda.

    No depende de env a propósito — quien llama comprueba _cache_enabled() antes.
    """
    global _hits, _misses

    with _lock:
        entry = _store.get(key)
        if entry is not None:
            ts, value = entry
            if time.monotonic() - ts <= ttl_seconds:
                _hits += 1
                return value
            # Caducado — se quita del almacén y del deque de orden
            del _store[key]
            try:
                _order.remove(key)
            except ValueError:
                pass

    # Se calcula fuera del bloqueo para no retenerlo durante un trabajo del ORM que puede ser lento
    _misses += 1
    value = compute_fn()

    with _lock:
        _evict_if_needed()
        _store[key] = (time.monotonic(), value)
        _order.append(key)

    return value


def invalidate(prefix: str | None = None) -> int:
    """Vacía entradas de la caché.

    Si se indica prefix, solo se eliminan las entradas cuya clave empieza por ese prefijo.
    Devuelve el número de entradas eliminadas.
    """
    with _lock:
        if prefix is None:
            count = len(_store)
            _store.clear()
            _order.clear()
            return count

        to_delete = [k for k in _store if k.startswith(prefix)]
        for k in to_delete:
            del _store[k]
            try:
                _order.remove(k)
            except ValueError:
                pass
        return len(to_delete)


def get_stats() -> dict:
    """Devuelve las estadísticas actuales de la caché para la interfaz de administración."""
    with _lock:
        total = len(_store)
        hits = _hits
        misses = _misses

    total_reqs = hits + misses
    hit_rate = round(hits / total_reqs * 100, 1) if total_reqs > 0 else 0.0
    return {
        "entries": total,
        "hits": hits,
        "misses": misses,
        "hit_rate_pct": hit_rate,
        "max_entries": _MAX_ENTRIES,
    }


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------

def _evict_if_needed() -> None:
    """Elimina la entrada más antigua cuando el almacén está lleno. Se llama con _lock adquirido."""
    while len(_store) >= _MAX_ENTRIES and _order:
        oldest = _order.popleft()
        _store.pop(oldest, None)
