import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..services import schema_cache

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # ------------------------------------------------------------------
    # Retention
    # ------------------------------------------------------------------
    mcp_session_retention_days = fields.Integer(
        string="Retención de Sesiones (días)",
        config_parameter="mcp_server.session_retention_days",
        default=7,
    )
    mcp_log_retention_days = fields.Integer(
        string="Retención de Registros (días)",
        config_parameter="mcp_server.log_retention_days",
        default=30,
    )

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------
    mcp_rate_limit_per_minute = fields.Integer(
        string="Límite de Tasa (solicitudes/min)",
        config_parameter="mcp_server.rate_limit_per_minute",
        default=60,
    )
    mcp_rate_limit_window_seconds = fields.Integer(
        string="Ventana de Límite de Tasa (segundos)",
        config_parameter="mcp_server.rate_limit_window_seconds",
        default=60,
    )
    mcp_enable_redis_rate_limit = fields.Boolean(
        string="Usar Redis para Límite de Tasa",
        config_parameter="mcp_server.enable_redis_rate_limit",
    )
    mcp_redis_url = fields.Char(
        string="URL de Redis",
        config_parameter="mcp_server.redis_url",
        help="URL de conexión de Redis, p. ej. redis://localhost:6379/0. "
             "Solo se usa cuando 'Usar Redis para Límite de Tasa' está activado.",
    )

    # ------------------------------------------------------------------
    # Schema cache (used by other agents — fields defined here so the
    # settings UI is unified in one place)
    # ------------------------------------------------------------------
    mcp_enable_schema_cache = fields.Boolean(
        string="Activar Caché de Esquema",
        config_parameter="mcp_server.enable_schema_cache",
        default=True,
    )
    mcp_schema_cache_ttl_seconds = fields.Integer(
        string="TTL de Caché de Esquema (segundos)",
        config_parameter="mcp_server.schema_cache_ttl_seconds",
        default=300,
    )

    # ------------------------------------------------------------------
    # Module generator
    # ------------------------------------------------------------------
    mcp_enable_module_generator = fields.Boolean(
        string="Activar Generador de Módulos",
        config_parameter="mcp_server.enable_module_generator",
        help="Cuando está activado, la herramienta MCP odoo_generate_module está disponible para tokens "
             "con alcance de administrador. Desactivado por defecto: actívelo solo en entornos de confianza.",
    )
    mcp_generated_modules_path = fields.Char(
        string="Ruta de Módulos Generados",
        config_parameter="mcp_server.generated_modules_path",
        help="Ruta absoluta del sistema de archivos donde la acción de instalación extrae los ZIP de los módulos generados. "
             "Debe ser una ruta de addons personalizada registrada en Odoo, con permisos de escritura para el proceso de Odoo, "
             "y NO debe estar dentro de los directorios community/ o enterprise/.",
    )

    # ------------------------------------------------------------------
    # Admin actions
    # ------------------------------------------------------------------

    def action_test_redis(self):
        """Ping the configured Redis server and return a client notification."""
        ICP = self.env["ir.config_parameter"].sudo()
        redis_enabled = ICP.get_param("mcp_server.enable_redis_rate_limit", "False")
        if redis_enabled.lower() not in ("1", "true", "yes"):
            raise UserError(_("El límite de tasa con Redis no está activado. Actívelo primero."))

        redis_url = ICP.get_param("mcp_server.redis_url", "") or ""
        if not redis_url:
            raise UserError(_("La URL de Redis no está configurada."))

        try:
            from ..services.rate_limiter import get_rate_limiter
            limiter = get_rate_limiter(self.env)

            # If the factory returned the in-memory fallback, Redis is unavailable
            from ..services.rate_limiter import rate_limiter as _mem
            if limiter is _mem:
                raise UserError(
                    _("No se pudo conectar a Redis en %s. Verifique la URL y que redis-py esté instalado.") % redis_url
                )

            from ..services.redis_rate_limiter import RedisRateLimiter
            if isinstance(limiter, RedisRateLimiter) and not limiter.ping():
                raise UserError(
                    _("El ping a Redis falló para %s. El servidor podría estar caído.") % redis_url
                )

        except UserError:
            raise
        except Exception as exc:
            _logger.exception("MCP Redis test failed")
            raise UserError(_("La prueba de conexión a Redis falló: %s") % exc) from exc

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Conexión a Redis Correcta"),
                "message": _("Conectado correctamente a Redis en %s.") % redis_url,
                "type": "success",
                "sticky": False,
            },
        }

    def action_clear_schema_cache(self):
        """Clear all MCP schema cache entries and report stats."""
        stats_before = schema_cache.get_stats()
        cleared = schema_cache.invalidate()
        _logger.info(
            "MCP schema cache manually cleared by uid=%s: %d entries removed",
            self.env.uid, cleared
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Caché de Esquema Limpiada"),
                "message": _(
                    "Se eliminaron %(count)d entradas de la caché. "
                    "Tasa de aciertos anterior: %(rate)s%%."
                ) % {"count": cleared, "rate": stats_before.get("hit_rate_pct", 0)},
                "type": "success",
                "sticky": False,
            },
        }
