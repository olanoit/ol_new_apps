"""
Limitador de peticiones con ventana deslizante — sin dependencias externas.

Configuración (en odoo.conf):
    mcp_rate_limit = 60          # total de peticiones por ventana entre todos los workers
    mcp_rate_window = 60         # tamaño de la ventana en segundos

Con varios workers de Odoo, el límite se reparte automáticamente entre ellos para que
la tasa efectiva total de todos los workers se mantenga cerca de mcp_rate_limit.

Ejemplo (odoo.conf, workers=4, mcp_rate_limit=120):
    cada worker permite 30 pet./60 s → total ≈ 120 pet./60 s

Los contenedores (buckets) se limpian solos al caducar para evitar fugas de memoria.

get_rate_limiter(env) devuelve un limitador respaldado por Redis si está configurado y
disponible; si no, devuelve la instancia única en memoria del módulo.
"""

import logging
import threading
import time
from collections import deque

from odoo.tools import config as _odoo_config

_logger = logging.getLogger(__name__)

_DEFAULT_MAX = 60
_DEFAULT_WINDOW = 60  # segundos


def _resolve_limits() -> tuple[int, int]:
    """Calcula el límite por worker a partir de odoo.conf, ajustado al número de workers."""
    total_max = int(_odoo_config.get("mcp_rate_limit", _DEFAULT_MAX) or _DEFAULT_MAX)
    window = int(_odoo_config.get("mcp_rate_window", _DEFAULT_WINDOW) or _DEFAULT_WINDOW)
    workers = int(_odoo_config.get("workers", 0) or 0)

    # Se divide entre el número de workers para que el límite efectivo total sea correcto.
    # Proceso único (workers=0): no hace falta ajustar.
    per_worker = max(10, total_max // max(1, workers)) if workers > 1 else total_max
    return per_worker, window


class RateLimiter:

    def __init__(self, max_requests: int | None = None, window_seconds: int | None = None):
        if max_requests is None or window_seconds is None:
            _max, _win = _resolve_limits()
            max_requests = max_requests if max_requests is not None else _max
            window_seconds = window_seconds if window_seconds is not None else _win

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._buckets: dict[str, deque] = {}
        self._last_cleanup = time.monotonic()

    def check(self, key: str, max_override: int = 0) -> tuple[bool, int]:
        """Comprueba si `key` está dentro del límite. Devuelve (permitido, restantes).

        max_override: límite por usuario (> 0 sustituye al valor global, 0 = usar el global).
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds
        effective_max = max_override if max_override > 0 else self.max_requests

        with self._lock:
            self._maybe_cleanup(now)
            bucket = self._buckets.setdefault(key, deque())

            while bucket and bucket[0] < cutoff:
                bucket.popleft()

            if len(bucket) >= effective_max:
                return False, 0

            bucket.append(now)
            return True, effective_max - len(bucket)

    def reconfigure(self, max_requests: int, window_seconds: int) -> None:
        """Actualiza los límites en tiempo de ejecución (p. ej. desde ir.config_parameter)."""
        with self._lock:
            self.max_requests = max_requests
            self.window_seconds = window_seconds
            self._buckets.clear()

    def _maybe_cleanup(self, now: float) -> None:
        """Elimina cada 5 minutos los contenedores totalmente caducados para evitar fugas de memoria."""
        if now - self._last_cleanup < 300:
            return
        cutoff = now - self.window_seconds
        dead = [k for k, b in self._buckets.items() if not b or b[-1] < cutoff]
        for k in dead:
            del self._buckets[k]
        self._last_cleanup = now


# Instancia única del módulo — compartida por todas las peticiones de este worker.
# Los límites se leen de odoo.conf al arrancar y se ajustan solos al número de workers.
rate_limiter = RateLimiter()

# ------------------------------------------------------------------ #
# Caché de limitadores con Redis: indexada por redis_url para que     #
# reconfigurar sea barato (solo se reconecta si cambia la URL).       #
# ------------------------------------------------------------------ #
_redis_limiter_cache: dict[str, object] = {}
_redis_cache_lock = threading.Lock()


def get_rate_limiter(env=None):
    """Devuelve el limitador de peticiones activo para esta petición.

    Si se pasa env y la limitación con Redis está activada en ir.config_parameter,
    devuelve una instancia de RedisRateLimiter (compartida, una por redis_url y worker).
    Ante cualquier error de configuración o si falta redis-py, devuelve la instancia en memoria.

    La instancia de Redis se guarda en caché a nivel de módulo para no reconectar en cada petición.
    """
    if env is None:
        return rate_limiter

    try:
        ICP = env["ir.config_parameter"].sudo()
        redis_enabled = ICP.get_param("mcp_server.enable_redis_rate_limit", "False")
        if redis_enabled.lower() not in ("1", "true", "yes"):
            return rate_limiter

        redis_url = ICP.get_param("mcp_server.redis_url", "") or ""
        if not redis_url:
            _logger.warning(
                "Servidor MCP: la limitación con Redis está activada pero mcp_server.redis_url no está definido. "
                "Se usa el limitador en memoria."
            )
            return rate_limiter

        max_req = int(ICP.get_param("mcp_server.rate_limit_per_minute", _DEFAULT_MAX) or _DEFAULT_MAX)
        window = int(ICP.get_param("mcp_server.rate_limit_window_seconds", _DEFAULT_WINDOW) or _DEFAULT_WINDOW)

        with _redis_cache_lock:
            cached = _redis_limiter_cache.get(redis_url)
            if cached is not None:
                # Actualiza los límites por si se cambiaron en los ajustes
                cached.reconfigure(max_req, window)
                return cached

            from .redis_rate_limiter import RedisRateLimiter
            limiter = RedisRateLimiter(redis_url, max_req, window)
            _redis_limiter_cache[redis_url] = limiter
            return limiter

    except Exception:
        _logger.exception(
            "Servidor MCP: error al obtener el limitador desde la configuración. Se usa el limitador en memoria."
        )
        return rate_limiter
