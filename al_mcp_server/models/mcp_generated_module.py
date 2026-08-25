import base64
import io
import json
import logging
import os
import shutil
import zipfile

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class McpGeneratedModule(models.Model):
    _name = "mcp.generated.module"
    _description = "Módulo Generado MCP"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------

    name = fields.Char(
        string="Nombre para Mostrar",
        required=True,
        tracking=True,
    )
    technical_name = fields.Char(
        string="Nombre Técnico",
        required=True,
        index=True,
        help="Nombre Python/de carpeta del módulo (snake_case).",
    )
    summary = fields.Char(string="Resumen")
    description = fields.Text(string="Descripción")
    category = fields.Char(string="Categoría", default="Productivity")
    author = fields.Char(string="Autor", default="MCP Generator")
    version = fields.Char(string="Versión", default="19.0.1.0.0")
    license = fields.Selection(
        [("OPL-1", "OPL-1"), ("LGPL-3", "LGPL-3"), ("AGPL-3", "AGPL-3")],
        string="Licencia",
        default="LGPL-3",
    )
    depends = fields.Char(
        string="Dependencias",
        default="base",
        help="Lista separada por comas de nombres técnicos de módulos Odoo.",
    )
    spec = fields.Text(
        string="Especificación (JSON)",
        required=True,
        help="Especificación JSON completa usada para generar este módulo.",
    )
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("generated", "Generado"),
            ("installed", "Instalado"),
            ("failed", "Fallido"),
        ],
        default="draft",
        tracking=True,
        required=True,
    )
    attachment_id = fields.Many2one(
        "ir.attachment",
        string="Archivo ZIP",
        readonly=True,
        ondelete="set null",
    )
    generation_log = fields.Text(
        string="Registro de Generación",
        readonly=True,
        help="Advertencias y errores capturados durante la generación del ZIP.",
    )
    created_by = fields.Many2one(
        "res.users",
        string="Creado Por",
        default=lambda self: self.env.uid,
        readonly=True,
        ondelete="set null",
    )
    installed_at = fields.Datetime(
        string="Instalado El",
        readonly=True,
    )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    _technical_name_unique = models.Constraint(
        "UNIQUE(technical_name)",
        "Ya existe un módulo con este nombre técnico.",
    )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @api.model
    def validate_spec(self, spec_dict: dict) -> list:
        """Return list of validation error strings (empty = valid)."""
        from ..services import module_generator
        return module_generator.validate_spec(spec_dict)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_generate(self):
        """Validate spec, build ZIP, store as ir.attachment, set state=generated."""
        self.ensure_one()
        from ..services import module_generator

        try:
            spec_dict = json.loads(self.spec or "{}")
        except (json.JSONDecodeError, TypeError) as exc:
            self.write({
                "state": "failed",
                "generation_log": f"JSON no válido en el campo de especificación: {exc}",
            })
            raise UserError(_(
                "El campo de especificación contiene JSON no válido: %(error)s",
                error=str(exc),
            ))

        try:
            zip_bytes, warnings = module_generator.build_zip(spec_dict)
        except ValueError as exc:
            log_msg = str(exc)
            self.write({
                "state": "failed",
                "generation_log": log_msg,
            })
            raise UserError(_(
                "La generación del módulo falló:\n%(error)s",
                error=log_msg,
            ))
        except Exception as exc:
            log_msg = f"Error inesperado: {exc}"
            self.write({
                "state": "failed",
                "generation_log": log_msg,
            })
            _logger.exception("Unexpected error generating module %s", self.technical_name)
            raise UserError(_(
                "La generación del módulo falló con un error inesperado:\n%(error)s",
                error=str(exc),
            ))

        # Remove old attachment if any
        if self.attachment_id:
            self.attachment_id.sudo().unlink()

        zip_b64 = base64.b64encode(zip_bytes).decode()
        attachment = self.env["ir.attachment"].sudo().create({
            "name": f"{self.technical_name}.zip",
            "datas": zip_b64,
            "mimetype": "application/zip",
            "res_model": self._name,
            "res_id": self.id,
        })

        log_text = "\n".join(warnings) if warnings else "Sin advertencias."
        self.write({
            "state": "generated",
            "attachment_id": attachment.id,
            "generation_log": log_text,
        })
        self.message_post(
            body=_(
                "ZIP del módulo generado correctamente. "
                "%(warning_count)s advertencia(s). "
                "Adjunto: %(filename)s",
                warning_count=len(warnings),
                filename=attachment.name,
            )
        )
        return True

    def action_download(self):
        """Return ir.actions.act_url to download the generated ZIP."""
        self.ensure_one()
        if not self.attachment_id:
            raise UserError(_("No hay archivo ZIP disponible. Genere el módulo primero."))
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{self.attachment_id.id}?download=1",
            "target": "self",
        }

    def action_install(self):
        """Extract ZIP to configured addons path and install via Odoo module manager.

        Requires ir.config_parameter 'mcp_server.generated_modules_path' to be set.
        Path must exist, be writable, and must NOT be inside community/ or enterprise/.
        """
        self.ensure_one()
        if self.state != "generated":
            raise UserError(
                _("El módulo debe estar en estado 'Generado' antes de instalar. Estado actual: %(state)s",
                  state=self.state)
            )
        if not self.attachment_id:
            raise UserError(_("No se encontró archivo ZIP. Genere el módulo primero."))

        IrParam = self.env["ir.config_parameter"].sudo()
        base_path = IrParam.get_param("mcp_server.generated_modules_path", "").strip()
        if not base_path:
            raise UserError(_(
                "La ruta de módulos generados no está configurada. "
                "Vaya a Configuración > Servidor MCP y establezca primero 'Ruta de Módulos Generados'."
            ))

        base_path = os.path.abspath(base_path)
        self._validate_install_path(base_path)

        target_dir = os.path.join(base_path, self.technical_name)

        # Fetch ZIP bytes
        att = self.attachment_id.sudo()
        zip_bytes = base64.b64decode(att.datas)

        # Atomic: remove existing dir if present, extract fresh
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)

        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                zf.extractall(base_path)
        except Exception as exc:
            # Rollback: remove partially extracted directory
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
            raise UserError(_(
                "No se pudo extraer el archivo ZIP: %(error)s",
                error=str(exc),
            ))

        # Update module list
        try:
            self.env["ir.module.module"].sudo().update_list()
        except Exception as exc:
            shutil.rmtree(target_dir, ignore_errors=True)
            raise UserError(_(
                "No se pudo actualizar la lista de módulos tras la extracción: %(error)s",
                error=str(exc),
            ))

        # Find and install
        module_rec = self.env["ir.module.module"].sudo().search(
            [("name", "=", self.technical_name)], limit=1
        )
        if not module_rec:
            shutil.rmtree(target_dir, ignore_errors=True)
            raise UserError(_(
                "El módulo %(name)s no se encontró en la lista de módulos tras update_list. "
                "Verifique que la ruta de addons esté registrada en la configuración de Odoo.",
                name=self.technical_name,
            ))

        try:
            module_rec.button_immediate_install()
        except Exception as exc:
            raise UserError(_(
                "La instalación del módulo falló: %(error)s",
                error=str(exc),
            ))

        self.write({
            "state": "installed",
            "installed_at": fields.Datetime.now(),
        })
        self.message_post(
            body=_(
                "Módulo instalado correctamente en %(path)s.",
                path=target_dir,
            )
        )
        return True

    def action_reset_to_draft(self):
        """Reset to draft (only from generated or failed). Clears attachment."""
        for rec in self:
            if rec.state not in ("generated", "failed"):
                raise UserError(_(
                    "No se puede restablecer el módulo %(name)s: el estado actual es %(state)s.",
                    name=rec.name,
                    state=rec.state,
                ))
        attachments = self.mapped("attachment_id")
        self.write({
            "state": "draft",
            "attachment_id": False,
            "generation_log": False,
        })
        if attachments:
            attachments.sudo().unlink()
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_install_path(self, path: str) -> None:
        """Raise UserError if *path* is not safe for module extraction."""
        if not os.path.isdir(path):
            raise UserError(_(
                "La ruta de módulos generados %(path)s no existe o no es un directorio.",
                path=path,
            ))
        if not os.access(path, os.W_OK):
            raise UserError(_(
                "El proceso de Odoo no puede escribir en la ruta de módulos generados %(path)s.",
                path=path,
            ))

        # Refuse paths inside Odoo upstream directories
        _BLOCKED_SEGMENTS = ("community", "enterprise")
        norm = path.lower().replace("\\", "/")
        for seg in _BLOCKED_SEGMENTS:
            if f"/{seg}/" in norm or norm.endswith(f"/{seg}"):
                raise UserError(_(
                    "La ruta de instalación %(path)s parece estar dentro del directorio "
                    "%(seg)s de Odoo. Elija una ruta de addons personalizada en su lugar.",
                    path=path,
                    seg=seg,
                ))
