import json
import logging
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class McpJob(models.Model):
    _name = "mcp.job"
    _description = "Trabajo Asíncrono MCP"
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
            ("bulk_update", "Actualización Masiva"),
            ("bulk_create", "Creación Masiva"),
            ("bulk_unlink", "Eliminación Masiva"),
            ("export_csv", "Exportar CSV"),
            ("export_xlsx", "Exportar XLSX"),
            ("call_method", "Llamar Método"),
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
    total_records = fields.Integer(string="Registros Totales", default=0)
    processed_records = fields.Integer(string="Registros Procesados", default=0)
    payload = fields.Text(
        string="Carga Útil (JSON)",
        help="Argumentos de entrada del trabajo, incluidas las instantáneas de mcp_scope y mcp_restrictions.",
    )
    result = fields.Text(
        string="Resultado (JSON)",
        help="Salida o resumen del trabajo (PII ocultada).",
    )
    error_message = fields.Text(string="Mensaje de Error")
    started_at = fields.Datetime(string="Iniciado El", readonly=True)
    finished_at = fields.Datetime(string="Finalizado El", readonly=True)
    duration_ms = fields.Integer(
        string="Duración (ms)",
        compute="_compute_duration_ms",
        store=True,
    )
    attachment_id = fields.Many2one(
        "ir.attachment",
        string="Archivo de Exportación",
        ondelete="set null",
        readonly=True,
    )
    # Governance snapshots — populated at submit time
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
    # Compute
    # ------------------------------------------------------------------

    @api.depends("operation")
    def _compute_name(self):
        op_labels = dict(self._fields["operation"].selection)
        for rec in self:
            label = op_labels.get(rec.operation, rec.operation or "")
            job_id = rec._origin.id or rec.id
            rec.name = f"Trabajo #{job_id} — {label}" if job_id else f"Nuevo Trabajo — {label}"

    @api.depends("started_at", "finished_at")
    def _compute_duration_ms(self):
        for rec in self:
            if rec.started_at and rec.finished_at:
                delta = rec.finished_at - rec.started_at
                rec.duration_ms = int(delta.total_seconds() * 1000)
            else:
                rec.duration_ms = 0

    # ------------------------------------------------------------------
    # Public actions
    # ------------------------------------------------------------------

    def action_run(self):
        """Synchronously execute this job. Idempotent — refuses to run if state != pending."""
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
            _logger.exception("MCP job %s failed", self.id)
            self._set_failed(str(exc))

    def action_cancel(self):
        """Cancel a pending job."""
        self.ensure_one()
        if self.state != "pending":
            raise UserError(
                _("No se puede cancelar el trabajo %s: solo se pueden cancelar los trabajos pendientes.") % self.name
            )
        self.write({"state": "cancelled"})

    def action_retry(self):
        """Reset a failed job to pending so the cron picks it up again."""
        self.ensure_one()
        if self.state != "failed":
            raise UserError(
                _("No se puede reintentar el trabajo %s: solo se pueden reintentar los trabajos fallidos.") % self.name
            )
        self.write({"state": "pending", "error_message": False, "progress": 0})

    def action_open_attachment(self):
        """Return an act_url action to download the job's export attachment."""
        self.ensure_one()
        if not self.attachment_id:
            raise UserError(_("No hay adjunto disponible para este trabajo."))
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{self.attachment_id.id}?download=1",
            "target": "new",
        }

    # ------------------------------------------------------------------
    # Internal state transitions
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
    # Core execution dispatcher
    # ------------------------------------------------------------------

    def _execute(self) -> dict:
        """Dispatch to the appropriate runner. Restores governance context before executing."""
        self.ensure_one()

        # Parse payload
        try:
            payload = json.loads(self.payload or "{}")
        except (json.JSONDecodeError, TypeError):
            payload = {}

        args = payload.get("args") or {}

        # Restore scope + restrictions snapshots into env.context — security-critical
        ctx_updates = {
            "mcp_scope": self.mcp_scope or payload.get("mcp_scope") or "write",
        }
        raw_restrictions = self.mcp_restrictions or payload.get("mcp_restrictions_json")
        if raw_restrictions:
            try:
                ctx_updates["mcp_restrictions"] = json.loads(raw_restrictions)
            except (json.JSONDecodeError, TypeError):
                pass

        job_env = self.with_context(**ctx_updates).env

        from ..services import job_runner

        op = self.operation
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

        raise ValueError(f"Unknown operation type: {op!r}")

    # ------------------------------------------------------------------
    # Cron entry point
    # ------------------------------------------------------------------

    @api.model
    def _process_pending_jobs(self, limit: int = 10):
        """Pick up to *limit* pending jobs and execute each in isolation.

        Called by the ir.cron record. Partial failure in one job does not
        prevent remaining jobs from running.

        Note: SAVEPOINT is intentionally avoided — PGBouncer in transaction
        pooling mode does not support server-side SAVEPOINT commands.
        action_run() already handles its own exception isolation internally.
        """
        pending = self.search([("state", "=", "pending")], order="id asc", limit=limit)
        for job in pending:
            try:
                job.action_run()
            except Exception as exc:
                _logger.exception("MCP cron: job %s raised outside action_run", job.id)
                try:
                    job.sudo().write({"state": "failed", "error_message": str(exc)})
                except Exception:
                    _logger.exception("MCP cron: could not fail job %s", job.id)
