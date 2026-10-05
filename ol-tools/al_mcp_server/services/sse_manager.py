import queue
import threading
import uuid
from datetime import datetime


class McpServerSession:
    """Representa una conexión activa de un cliente MCP con su cola de mensajes SSE."""

    def __init__(self, uid: int, db: str, ip: str | None = None):
        self.session_id: str = str(uuid.uuid4())
        self.uid: int = uid
        self.db: str = db
        self.ip: str | None = ip
        self.message_count: int = 0
        self.last_activity: datetime = datetime.utcnow()
        self._queue: queue.Queue = queue.Queue()
        self.db_id: int | None = None  # ID del registro mcp.session en la base; se fija tras crear la auditoría
        self.token_id: int | None = None  # mcp.token que abrió la sesión (se revalida por mensaje)

    def put(self, data: dict) -> None:
        self.message_count += 1
        self.last_activity = datetime.utcnow()
        self._queue.put(data)

    def get(self, timeout: int = 25):
        return self._queue.get(timeout=timeout)

    def close(self) -> None:
        self._queue.put(None)


class SseSessionManager:
    """Registro seguro entre hilos de las sesiones MCP SSE activas y caché de IDs de sesión HTTP.

    Las sesiones HTTP no tienen estado — cada POST /mcp es independiente — pero se mantiene
    un registro mcp.session persistente por token para auditoría y registro. Para evitar una
    búsqueda adicional en la base en cada petición, la correspondencia token_id → session_db_id
    se guarda en memoria (por worker, lo cual basta para la auditoría).
    """

    def __init__(self):
        self._sessions: dict[str, McpServerSession] = {}
        # Caché de sesiones HTTP: token_id (int) → mcp.session.id (int)
        self._http_cache: dict[int, int] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Registro de sesiones SSE
    # ------------------------------------------------------------------

    def create(self, uid: int, db: str, ip: str | None = None) -> McpServerSession:
        session = McpServerSession(uid, db, ip)
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> McpServerSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def remove(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def active_count(self) -> int:
        with self._lock:
            return len(self._sessions)

    # ------------------------------------------------------------------
    # Caché de IDs en base de datos de las sesiones HTTP
    # ------------------------------------------------------------------

    def get_http_session_db_id(self, token_id: int) -> int | None:
        """Devuelve el ID de mcp.session en caché para este token, o None si no está en caché."""
        with self._lock:
            return self._http_cache.get(token_id)

    def set_http_session_db_id(self, token_id: int, session_db_id: int) -> None:
        """Guarda en caché el ID de mcp.session de este token."""
        with self._lock:
            self._http_cache[token_id] = session_db_id

    def invalidate_http_session(self, token_id: int) -> None:
        """Quita un token de la caché de sesiones HTTP (p. ej. al revocar el token)."""
        with self._lock:
            self._http_cache.pop(token_id, None)


# Instancia única del módulo, compartida por todas las peticiones de este worker
session_manager = SseSessionManager()
