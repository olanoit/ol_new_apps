"""
Limitador de peticiones distribuido con Redis, basado en una ventana deslizante sobre sorted sets.

Ante cualquier error de Redis pasa de forma transparente al RateLimiter en memoria, para que
una caída de Redis nunca bloquee las peticiones MCP.

Algoritmo (por clave):
  1. ZADD  mcp:ratelimit:{key}  score=now  member=uuid
  2. ZREMRANGEBYSCORE  ...  0  (now - window_seconds)   -- descarta las entradas caducadas
  3. ZCARD  ...                                          -- cuenta las entradas activas
  4. EXPIRE ...  window_seconds                          -- la clave se limpia sola
  Los pasos 2-4 van en un pipeline por atomicidad (aquí no hace falta MULTI/EXEC
  porque ZADD es idempotente al repetirse; la atomicidad real exigiría un script Lua,
  pero el pipeline reduce la latencia a un solo viaje de ida y vuelta, suficiente para
  este caso — en el peor caso, con carrera, se cuenta 1 de más, aceptable para limitar peticiones).
"""

import logging
import time
import uuid

_logger = logging.getLogger(__name__)

# Importación diferida — redis-py es opcional
_redis_mod = None
_redis_import_failed = False


def _import_redis():
    global _redis_mod, _redis_import_failed
    if _redis_mod is not None:
        return _redis_mod
    if _redis_import_failed:
        return None
    try:
        import redis as _r
        _redis_mod = _r
        return _redis_mod
    except ImportError:
        _redis_import_failed = True
        _logger.warning(
            "Servidor MCP: el paquete redis-py no está instalado. "
            "Instálelo con: pip install redis  "
            "Se usa el limitador de peticiones en memoria."
        )
        return None


_KEY_PREFIX = "mcp:ratelimit:"


class RedisRateLimiter:
    """Limitador de peticiones distribuido con ventana deslizante sobre sorted sets de Redis.

    Su interfaz es idéntica a la de RateLimiter, así que puede sustituirlo
    directamente en el controlador.
    """

    def __init__(self, redis_url: str, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._redis_url = redis_url
        self._client = None
        self._fallback = None  # se fija en el primer fallo de conexión

        redis_mod = _import_redis()
        if redis_mod is None:
            self._init_fallback()
            return

        try:
            # decode_responses=False mantiene las puntuaciones como float y los miembros como bytes — es correcto
            self._client = redis_mod.from_url(
                redis_url,
                socket_connect_timeout=1,
                socket_timeout=1,
                decode_responses=True,
            )
            # Verifica la conexión de inmediato para fallar pronto al arrancar
            self._client.ping()
            _logger.info("Servidor MCP: limitador de peticiones con Redis conectado a %s", redis_url)
        except Exception as exc:
            _logger.warning(
                "Servidor MCP: no se puede conectar a Redis (%s). "
                "Se usa el limitador de peticiones en memoria.", exc
            )
            self._client = None
            self._init_fallback()

    def _init_fallback(self):
        from .rate_limiter import RateLimiter
        self._fallback = RateLimiter(
            max_requests=self.max_requests,
            window_seconds=self.window_seconds,
        )

    def check(self, key: str, max_override: int = 0) -> tuple[bool, int]:
        """Comprueba el límite de peticiones. Devuelve (permitido, restantes).

        Ante cualquier error de Redis, pasa al limitador en memoria.
        """
        if self._fallback is not None:
            return self._fallback.check(key, max_override=max_override)

        effective_max = max_override if max_override > 0 else self.max_requests
        redis_key = f"{_KEY_PREFIX}{key}"

        try:
            now = time.time()
            cutoff = now - self.window_seconds
            member = str(uuid.uuid4())

            pipe = self._client.pipeline(transaction=False)
            pipe.zadd(redis_key, {member: now})
            pipe.zremrangebyscore(redis_key, "-inf", cutoff)
            pipe.zcard(redis_key)
            pipe.expire(redis_key, self.window_seconds + 1)
            results = pipe.execute()

            count = results[2]  # resultado de ZCARD
            if count > effective_max:
                # Ya se superó el límite — se elimina el miembro recién añadido
                self._client.zrem(redis_key, member)
                return False, 0

            remaining = max(0, effective_max - count)
            return True, remaining

        except Exception as exc:
            _logger.warning(
                "Servidor MCP: falló la comprobación del límite en Redis (%s). "
                "Se activa el limitador en memoria.", exc
            )
            self._init_fallback()
            return self._fallback.check(key, max_override=max_override)

    def reconfigure(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        if self._fallback is not None:
            self._fallback.reconfigure(max_requests, window_seconds)

    def ping(self) -> bool:
        """Devuelve True si Redis responde. Lo usa el botón de comprobación de estado del administrador."""
        if self._client is None:
            return False
        try:
            self._client.ping()
            return True
        except Exception:
            return False
