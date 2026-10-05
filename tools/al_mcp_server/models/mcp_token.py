import hashlib
import ipaddress
import json
import logging
import secrets
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

TOKEN_TTL_DAYS = 30
REFRESH_TOKEN_TTL_DAYS = 90

# Campos de credencial y gobierno: solo el administrador (o el servidor con
# sudo) puede modificarlos. El dueño del token solo puede renombrarlo o revocarlo.
_PROTECTED_FIELDS = frozenset({
    "token", "refresh_token", "user_id", "token_type", "state",
    "expires_at", "refresh_token_expires_at", "last_used",
    "scope", "ip_allowlist", "ip_denylist",
    "allowed_model_ids", "denied_model_ids", "field_restrictions",
    "capture_payloads",
})

# Campos de gobierno que deben sobrevivir a la rotación del token de refresco.
_GOVERNANCE_FIELDS = (
    "scope", "ip_allowlist", "ip_denylist", "field_restrictions", "capture_payloads",
)


def _hash_token(raw: str) -> str:
    """Hash SHA-256 de un token en claro: en la base de datos solo se guarda el hash."""
    return hashlib.sha256(raw.encode()).hexdigest()


class McpToken(models.Model):
    _name = "mcp.token"
    _description = "Token bearer MCP"
    _inherit = ["mail.thread", "mail.activity.mixin"]        # N3: chatter + pista de auditoría
    _order = "create_date desc"
    _rec_name = "name"

    name = fields.Char(string="Cliente", default="Cliente MCP")
    token = fields.Char(string="Hash del token (SHA-256)", readonly=True, index=True, copy=False)
    user_id = fields.Many2one("res.users", string="Usuario", required=True, ondelete="cascade", readonly=True)
    token_type = fields.Selection(
        [("oauth", "OAuth 2.0"), ("pat", "Token de acceso personal")],
        string="Tipo", default="oauth", readonly=True,
    )
    state = fields.Selection(
        [("active", "Activo"), ("revoked", "Revocado"), ("expired", "Caducado")],
        string="Estado", default="active", readonly=True,
        tracking=True,                  # N3: registra los cambios de estado en el chatter
    )
    expires_at = fields.Datetime(string="Caduca el", readonly=True)
    last_used = fields.Datetime(string="Último uso", readonly=True)

    # N1: campos del token de refresco (solo OAuth; el PAT no tiene token de refresco)
    refresh_token = fields.Char(
        string="Hash del token de refresco", readonly=True, index=True, copy=False,
    )
    refresh_token_expires_at = fields.Datetime(string="Caducidad del refresco", readonly=True)

    # ------------------------------------------------------------------
    # Funcionalidad 1: alcance por token
    # ------------------------------------------------------------------
    scope = fields.Selection(
        [("read", "Solo lectura"), ("write", "Lectura y escritura"), ("admin", "Acceso completo")],
        string="Alcance",
        default="write",
        required=True,
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Funcionalidad 2: lista de IP permitidas / denegadas
    # ------------------------------------------------------------------
    ip_allowlist = fields.Text(
        string="Lista de IP permitidas",
        help="Un rango CIDR o dirección IP por línea. Deje en blanco para permitir todas las IP. "
             "Admite IPv4, IPv6 y notación CIDR (p. ej. 192.168.1.0/24). "
             "Las líneas que comienzan con # se tratan como comentarios.",
    )
    ip_denylist = fields.Text(
        string="Lista de IP denegadas",
        help="Un rango CIDR o dirección IP por línea. Deje en blanco para no denegar ninguna. "
             "La lista de denegados se evalúa antes que la lista de permitidos. "
             "Las líneas que comienzan con # se tratan como comentarios.",
    )

    # ------------------------------------------------------------------
    # Funcionalidad 3: restricciones de modelos y campos
    # ------------------------------------------------------------------
    allowed_model_ids = fields.Many2many(
        "ir.model",
        "mcp_token_allowed_model_rel",
        "token_id",
        "model_id",
        string="Modelos permitidos",
        help="Restringe este token a modelos específicos de Odoo. "
             "Deje vacío para permitir el acceso a todos los modelos.",
        tracking=True,
    )
    denied_model_ids = fields.Many2many(
        "ir.model",
        "mcp_token_denied_model_rel",
        "token_id",
        "model_id",
        string="Modelos denegados",
        help="Bloquea este token para modelos específicos de Odoo. "
             "La lista de denegados se evalúa antes que la lista de permitidos.",
        tracking=True,
    )
    field_restrictions = fields.Text(
        string="Restricciones de campos (JSON)",
        help='Objeto JSON que asigna nombres de modelos a listas de campos permitidos. Ejemplo:\n'
             '{"sale.order": ["name", "partner_id", "amount_total"],\n'
             ' "res.partner": ["name", "email"]}\n\n'
             'Omitir un modelo significa que se permiten todos sus campos. '
             'Se aplica tanto a la lectura (descarta silenciosamente los campos no permitidos) '
             'como a la escritura (genera error si se escribe un campo no permitido).',
    )

    # ------------------------------------------------------------------
    # Funcionalidad 4: captura opcional de cargas útiles
    # ------------------------------------------------------------------
    capture_payloads = fields.Boolean(
        string="Capturar cargas útiles",
        default=False,
        help="Cuando está activado, los argumentos y respuestas de las llamadas a herramientas se almacenan en el registro de auditoría "
             "(tras ocultar PII). Desactivado por defecto por rendimiento.",
        tracking=True,
    )

    can_edit_governance = fields.Boolean(
        compute="_compute_can_edit_governance",
        string="Puede editar el gobierno",
        help="Técnico: el usuario actual puede editar el alcance y las restricciones.",
    )

    def _compute_can_edit_governance(self):
        is_admin = self.env.user.has_group("base.group_system")
        for rec in self:
            rec.can_edit_governance = is_admin

    # ------------------------------------------------------------------
    # ORM overrides — protección de credenciales y gobierno
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        # Los tokens solo se emiten desde issue()/refresh() (con sudo) o por un
        # administrador: un usuario no puede fabricar su propio hash ni alcance.
        if not self.env.su and not self.env.user.has_group("base.group_system"):
            raise AccessError(self.env._("Los tokens MCP solo se pueden emitir mediante OAuth o el botón de PAT."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and not self.env.user.has_group("base.group_system"):
            protected = set(vals) & _PROTECTED_FIELDS
            # El dueño sí puede revocar su propio token.
            if protected == {"state"} and vals.get("state") == "revoked":
                protected = set()
            if protected:
                raise AccessError(self.env._(
                    "Solo un administrador puede modificar estos campos del token MCP: %(fields)s",
                    fields=", ".join(sorted(protected)),
                ))
            # El seguimiento del chatter lee los modelos permitidos/denegados
            # (ir.model), que en 19.0 un usuario interno no puede leer. Tras
            # validar los campos y el permiso de escritura (reglas incluidas:
            # solo sus tokens), se escribe como superusuario. sudo() conserva
            # el usuario, así que el autor del cambio en el chatter es el dueño.
            self.check_access("write")
            tokens_sudo = self.sudo()
            return super(McpToken, tokens_sudo).write(vals)
        return super().write(vals)

    # ------------------------------------------------------------------
    # Emisión de tokens
    # ------------------------------------------------------------------

    @api.model
    def issue(self, uid: int, client_name: str = "Cliente MCP",
              token_type: str = "oauth") -> str:
        """Emite un token de acceso nuevo. Devuelve el token en claro (se muestra una vez y no se guarda).
        Para flujos OAuth con token de refresco, use issue_oauth()."""
        raw, _ = self._issue_pair(uid, client_name, token_type)
        return raw

    @api.model
    def issue_oauth(self, uid: int, client_name: str = "Cliente MCP") -> tuple[str, str]:
        """Emite el par de tokens de acceso y de refresco para flujos OAuth.
        Devuelve (raw_access_token, raw_refresh_token)."""
        return self._issue_pair(uid, client_name, "oauth")

    @api.model
    def _issue_pair(self, uid: int, client_name: str,
                    token_type: str) -> tuple[str, str | None]:
        """Interno: crea el registro mcp.token y devuelve (raw_access, raw_refresh|None)."""
        raw_access = secrets.token_urlsafe(32)
        now = fields.Datetime.now()
        vals = {
            "name": client_name,
            "token": _hash_token(raw_access),
            "user_id": uid,
            "token_type": token_type,
            "expires_at": now + timedelta(days=TOKEN_TTL_DAYS),
        }
        raw_refresh = None
        if token_type == "oauth":
            raw_refresh = secrets.token_urlsafe(32)
            vals["refresh_token"] = _hash_token(raw_refresh)
            vals["refresh_token_expires_at"] = now + timedelta(days=REFRESH_TOKEN_TTL_DAYS)

        # sudo: la emisión la invoca el flujo OAuth (usuario público) o el botón
        # de PAT; el propio usuario no tiene permiso de crear tokens (ver create()).
        token_sudo = self.with_user(uid).sudo().create(vals)
        token_sudo.message_post(body=f"Token bearer MCP emitido; cliente: {client_name}")
        return raw_access, raw_refresh

    @api.model
    def refresh(self, raw_refresh_token: str) -> tuple[str, str] | None:
        """Canjea un token de refresco por un nuevo par de tokens de acceso y refresco (rotación).
        El token anterior caduca. Devuelve (new_access, new_refresh) o None si no es válido."""
        token_hash = _hash_token(raw_refresh_token)
        rec = self.search(
            [("refresh_token", "=", token_hash), ("state", "=", "active")],
            limit=1,
        )
        if not rec:
            return None

        now = fields.Datetime.now()
        if rec.refresh_token_expires_at and now > rec.refresh_token_expires_at:
            rec.write({"state": "expired"})
            return None

        # Emite los tokens de reemplazo conservando alcance y restricciones del token
        # original (si no, un token restringido se "ampliaría" al refrescarse).
        new_raw_access = secrets.token_urlsafe(32)
        new_raw_refresh = secrets.token_urlsafe(32)
        vals = {field: rec[field] for field in _GOVERNANCE_FIELDS}
        vals.update({
            "name": rec.name,
            "token": _hash_token(new_raw_access),
            "refresh_token": _hash_token(new_raw_refresh),
            "user_id": rec.user_id.id,
            "token_type": rec.token_type,
            "expires_at": now + timedelta(days=TOKEN_TTL_DAYS),
            "refresh_token_expires_at": now + timedelta(days=REFRESH_TOKEN_TTL_DAYS),
            "allowed_model_ids": [(6, 0, rec.allowed_model_ids.ids)],
            "denied_model_ids": [(6, 0, rec.denied_model_ids.ids)],
        })
        self.create(vals)
        # Caduca el token usado (rotación: impide su reutilización)
        rec.write({"state": "expired"})
        return new_raw_access, new_raw_refresh

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def action_revoke(self):
        self.write({"state": "revoked"})

    def action_generate_pat(self):
        """Emite un PAT para el usuario actual y abre el asistente de visualización única."""
        raw = self.issue(
            self.env.uid,
            client_name=f"PAT — {self.env.user.name}",
            token_type="pat",
        )
        token_rec = self.search(
            [("user_id", "=", self.env.uid), ("token_type", "=", "pat")],
            order="create_date desc",
            limit=1,
        )
        wizard = self.env["mcp.pat.wizard"].create({
            "token_id": token_rec.id,
            "raw_token": raw,
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "mcp.pat.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
            "name": "Token de acceso personal: guárdelo ahora",
        }

    # ------------------------------------------------------------------
    # Utilidades de gobierno (llamadas desde token_service / tool_executor)
    # ------------------------------------------------------------------

    def is_ip_allowed(self, ip: str) -> bool:
        """Devuelve True si las reglas de IP de este token permiten *ip*.

        Orden de evaluación: primero la lista de denegadas y luego la de permitidas.
        - Si la IP está en la lista de denegadas → False
        - Si la lista de permitidas no está vacía y la IP NO está en ella → False
        - En otro caso → True
        """
        self.ensure_one()
        try:
            client = ipaddress.ip_address(ip)
        except ValueError:
            # IP no interpretable: se deniega por seguridad
            _logger.warning("Token MCP %s: no se pudo interpretar la IP del cliente %r", self.id, ip)
            return False

        if self.ip_denylist:
            for entry in self._parse_ip_lines(self.ip_denylist):
                if client in entry:
                    return False

        if self.ip_allowlist:
            for entry in self._parse_ip_lines(self.ip_allowlist):
                if client in entry:
                    return True
            # La lista de permitidas no está vacía y no hay coincidencia
            return False

        return True

    def is_model_allowed(self, model_name: str) -> bool:
        """Devuelve True si *model_name* es accesible según las restricciones de modelos del token.

        Primero se revisan los modelos denegados. Si allowed_model_ids no está vacío,
        el modelo debe figurar en él. Un allowed_model_ids vacío permite todos los modelos.
        """
        self.ensure_one()
        if self.denied_model_ids:
            denied_names = self.denied_model_ids.mapped("model")
            if model_name in denied_names:
                return False
        if self.allowed_model_ids:
            allowed_names = self.allowed_model_ids.mapped("model")
            if model_name not in allowed_names:
                return False
        return True

    def get_allowed_fields(self, model_name: str) -> list | None:
        """Devuelve la lista de campos permitidos de *model_name*, o None si se permiten todos.

        Devuelve None (no una lista vacía) para distinguir «sin restricción» de
        «hay restricción pero da un conjunto vacío» (esto último sería un error de configuración).
        """
        self.ensure_one()
        if not self.field_restrictions:
            return None
        try:
            restrictions = json.loads(self.field_restrictions)
        except (json.JSONDecodeError, TypeError):
            _logger.warning(
                "Token MCP %s: JSON no válido en field_restrictions; se trata como sin restricción",
                self.id,
            )
            return None
        if not isinstance(restrictions, dict):
            return None
        model_fields = restrictions.get(model_name)
        if model_fields is None:
            return None
        if not isinstance(model_fields, list):
            return None
        return [str(f) for f in model_fields]

    # ------------------------------------------------------------------
    # Utilidades internas
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_ip_lines(text: str):
        """Interpreta un texto multilínea de IP/CIDR y genera objetos de red ipaddress.

        Se omiten las líneas en blanco y las que empiezan por #. Las entradas mal
        formadas se registran y se omiten para que una línea errónea no rompa toda la comprobación.
        """
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                yield ipaddress.ip_network(line, strict=False)
            except ValueError:
                try:
                    # Dirección individual sin notación CIDR
                    yield ipaddress.ip_network(
                        str(ipaddress.ip_address(line)), strict=False
                    )
                except ValueError:
                    _logger.warning("Token MCP: no se pudo interpretar la entrada de IP %r; se omite", line)
