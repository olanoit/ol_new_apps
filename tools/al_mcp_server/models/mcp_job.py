import json
import logging
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


class McpJob(models.Model):
    _name = "mcp.job"
    _description = "Trabajo asíncrono MCP"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"
    _rec_name = "name"

    name = fields.Char(
        string="Nombre",
        compute="_compute_name",
        store=True,
    )
    operation = fields.Selection(
        [
            ("bulk_update", "Actualización masiva"),
            ("bulk_create", "Creación masiva"),
            ("bulk_unlink", "Eliminación masiva"),
            ("export_csv", "Exportar CSV"),
            ("export_xlsx", "Exportar XLSX"),
            ("call_method", "Llamar método"),
            ("custom", "Personalizado"),
        ],
        string="Operación",
        required=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Usuario",
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        ondelete="restrict",
        index=True,
    )
    token_id = fields.Many2one(
        "mcp.token",
        string="Token",
        readonly=True,
        ondelete="set null",
    )
    session_id = fields.Many2one(
        "mcp.session",
        string="Sesión",
        readonly=True,
        ondelete="set null",
    )
    state = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("running", "En ejecución"),
            ("done", "Hecho"),
            ("failed", "Fallido"),
            ("cancelled", "Cancelado"),
        ],
        string="Estado",
        default="pending",
        required=True,
        tracking=True,
        index=True,
    )
    progress = fields.Integer(
        string="Progreso (%)",
        default=0,
    )
    total_records = fields.Integer(string="Registros totales", default=0)
    processed_records = fields.Integer(string="Registros procesados", default=0)
    payload = fields.Text(
        string="Carga útil (JSON)",
        help="Argumentos de entrada del trabajo, incluidas las instantáneas de mcp_scope y mcp_restrictions.",
    )
    result = fields.Text(
        string="Resultado (JSON)",
        help="Salida o resumen del trabajo (PII ocultada).",
    )
    error_message = fields.Text(string="Mensaje de error")
    started_at = fields.Datetime(string="Iniciado el", readonly=True)
    finished_at = fields.Datetime(string="Finalizado el", readonly=True)
    duration_ms = fields.Integer(
        string="Duración (ms)",
        compute="_compute_duration_ms",
        store=True,
    )
    attachment_id = fields.Many2one(
        "ir.attachment",
        string="Archivo de exportación",
        ondelete="set null",
        readonly=True,
    )
    # Instantáneas de gobierno: se rellenan al enviar el trabajo
    mcp_scope = fields.Char(
        string="Alcance MCP",
        readonly=True,
        help="Instantánea del alcance del token en el momento del envío del trabajo.",
    )
    mcp_restrictions = fields.Text(
        string="Restricciones MCP (JSON)",
        readonly=True,
        help="Instantánea de las restricciones del token en el momento del envío del trabajo.",
    )

    # ------------------------------------------------------------------
    # Cálculos
    # ------------------------------------------------------------------

    @api.depends("operation")
    def _compute_name(self):
        op_labels = dict(self._fields["operation"].selection)
        for rec in self:
            label = op_labels.get(rec.operation, rec.operation or "")
            job_id = rec._origin.id or rec.id
            rec.name = f"Trabajo #{job_id} — {label}" if job_id else f"Nuevo trabajo — {label}"

    @api.depends("started_at", "finished_at")
    def _compute_duration_ms(self):
        for rec in self:
            if rec.started_at and rec.finished_at:
                delta = rec.finished_at - rec.started_at
                rec.duration_ms = int(delta.total_seconds() * 1000)
            else:
                rec.duration_ms = 0

    # ------------------------------------------------------------------
    # Sobrescrituras del ORM
    # ------------------------------------------------------------------

    # Qué se ejecuta, con qué usuario y con qué alcance: lo fija el servidor al
    # enviar el trabajo; el dueño no puede cambiarlo (la regla solo mira el
    # registro antes del write).
    _PROTECTED_FIELDS = frozenset({
        "user_id", "operation", "payload", "mcp_scope", "mcp_restrictions",
        "token_id", "session_id",
    })

    def write(self, vals):
        if not self.env.su and not self.env.user.has_group("base.group_system"):
            protected = set(vals) & self._PROTECTED_FIELDS
            if protected:
                raise AccessError(_(
                    "Solo un administrador puede modificar estos campos del trabajo: %(fields)s",
                    fields=", ".join(sorted(protected)),
                ))
        return super().write(vals)

    # ------------------------------------------------------------------
    # Acciones públicas
    # ------------------------------------------------------------------

    def action_run(self):
        """Ejecuta este trabajo de forma síncrona. Idempotente: no se ejecuta si state != pending."""
        self.ensure_one()
        if self.state != "pending":
            raise UserError(
                _("No se puede ejecutar el trabajo %s: el estado actual es '%s' (debe ser 'pending').") % (
                    self.name, self.state
                )
            )
        self._set_running()
        try:
            result = self._execute()
            self._set_done(result)
        except Exception as exc:
            _logger.exception("El trabajo MCP %s falló", self.id)
            self._set_failed(str(exc))

    def action_cancel(self):
        """Cancela un trabajo pendiente."""
        self.ensure_one()
        if self.state != "pending":
            raise UserError(
                _("No se puede cancelar el trabajo %s: solo se pueden cancelar los trabajos pendientes.") % self.name
            )
        self.write({"state": "cancelled"})

    def action_retry(self):
        """Devuelve un trabajo fallido a pendiente para que el cron lo vuelva a tomar."""
        self.ensure_one()
        if self.state != "failed":
            raise UserError(
                _("No se puede reintentar el trabajo %s: solo se pueden reintentar los trabajos fallidos.") % self.name
            )
        self.write({"state": "pending", "error_message": False, "progress": 0})

    def action_open_attachment(self):
        """Devuelve una acción act_url para descargar el adjunto de exportación del trabajo."""
        self.ensure_one()
        if not self.attachment_id:
            raise UserError(_("No hay adjunto disponible para este trabajo."))
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{self.attachment_id.id}?download=1",
            "target": "new",
        }

    # ------------------------------------------------------------------
    # Transiciones internas de estado
    # ------------------------------------------------------------------

    def _set_running(self):
        self.write({
            "state": "running",
            "started_at": fields.Datetime.now(),
            "progress": 0,
        })

    def _set_done(self, result: dict):
        from ..services.redaction import redact
        from ..services.json_utils import odoo_json_default
        try:
            safe_result = json.dumps(redact(result), ensure_ascii=False, default=odoo_json_default)
        except Exception:
            safe_result = str(result)
        self.write({
            "state": "done",
            "finished_at": fields.Datetime.now(),
            "progress": 100,
            "result": safe_result,
            "error_message": False,
        })

    def _set_failed(self, error_message: str):
        self.write({
            "state": "failed",
            "finished_at": fields.Datetime.now(),
            "error_message": error_message,
        })

    # ------------------------------------------------------------------
    # Despachador principal de ejecución
    # ------------------------------------------------------------------

    def _execute(self) -> dict:
        """Delega en el ejecutor adecuado. Restaura el contexto de gobierno antes de ejecutar."""
        self.ensure_one()

        # Interpreta la carga útil
        try:
            payload = json.loads(self.payload or "{}")
        except (json.JSONDecodeError, TypeError):
            payload = {}

        args = payload.get("args") or {}

        # Restaura en env.context las instantáneas de alcance y restricciones (crítico para la seguridad)
        ctx_updates = {
            "mcp_scope": self.mcp_scope or payload.get("mcp_scope") or "write",
        }
        raw_restrictions = self.mcp_restrictions or payload.get("mcp_restrictions_json")
        if raw_restrictions:
            try:
                ctx_updates["mcp_restrictions"] = json.loads(raw_restrictions)
            except (json.JSONDecodeError, TypeError):
                pass

        # El cron corre como su propio usuario (normalmente superusuario): el
        # trabajo debe ejecutarse SIEMPRE con los permisos de quien lo envió.
        if not self.user_id or not self.user_id.active:
            raise UserError(_("El usuario que envió el trabajo no existe o está inactivo."))
        job_env = self.with_user(self.user_id).with_context(**ctx_updates).env

        from ..services import job_runner, tool_executor

        op = self.operation
        # Mismo alcance y restricciones del token que la herramienta síncrona.
        tool_executor.enforce_job_operation(job_env, op, args)
        if op == "bulk_update":
            return job_runner.run_bulk_update(job_env, args, self)
        if op == "bulk_create":
            return job_runner.run_bulk_create(job_env, args, self)
        if op == "bulk_unlink":
            return job_runner.run_bulk_unlink(job_env, args, self)
        if op == "export_csv":
            return job_runner.run_export_csv(job_env, args, self)
        if op == "export_xlsx":
            return job_runner.run_export_xlsx(job_env, args, self)
        if op in ("call_method", "custom"):
            return job_runner.run_custom(job_env, args, self)

        raise ValueError(f"Tipo de operación desconocido: {op!r}")

    # ------------------------------------------------------------------
    # Punto de entrada del cron
    # ------------------------------------------------------------------

    @api.model
    def _process_pending_jobs(self, limit: int = 10):
        """Toma hasta *limit* trabajos pendientes y ejecuta cada uno de forma aislada.

        Lo invoca el registro ir.cron. El fallo de un trabajo no impide que se
        ejecuten los demás.

        Nota: se evita SAVEPOINT a propósito, porque PGBouncer en modo de pool
        por transacción no admite comandos SAVEPOINT en el servidor.
        action_run() ya aísla internamente sus propias excepciones.
        """
        pending = self.search([("state", "=", "pending")], order="id asc", limit=limit)
        for job in pending:
            try:
                job.action_run()
            except Exception as exc:
                _logger.exception("Cron MCP: el trabajo %s lanzó una excepción fuera de action_run", job.id)
                try:
                    job.sudo().write({"state": "failed", "error_message": str(exc)})
                except Exception:
                    _logger.exception("Cron MCP: no se pudo marcar como fallido el trabajo %s", job.id)
