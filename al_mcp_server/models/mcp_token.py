import hashlib
import ipaddress
import json
import logging
import secrets
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

TOKEN_TTL_DAYS = 30
REFRESH_TOKEN_TTL_DAYS = 90


def _hash_token(raw: str) -> str:
    """SHA-256 hash of a raw token — only the hash is stored in DB."""
    return hashlib.sha256(raw.encode()).hexdigest()


class McpToken(models.Model):
    _name = "mcp.token"
    _description = "Token Bearer MCP"
    _inherit = ["mail.thread", "mail.activity.mixin"]        # N3: chatter + audit trail
    _order = "create_date desc"
    _rec_name = "name"

    name = fields.Char(string="Cliente", default="MCP Client")
    token = fields.Char(string="Hash de Token (SHA-256)", readonly=True, index=True, copy=False)
    user_id = fields.Many2one("res.users", string="Usuario", required=True, ondelete="cascade", readonly=True)
    token_type = fields.Selection(
        [("oauth", "OAuth 2.0"), ("pat", "Token de Acceso Personal")],
        string="Tipo", default="oauth", readonly=True,
    )
    state = fields.Selection(
        [("active", "Activo"), ("revoked", "Revocado"), ("expired", "Caducado")],
        default="active", readonly=True,
        tracking=True,                  # N3: log state changes in chatter
    )
    expires_at = fields.Datetime(string="Caduca El", readonly=True)
    last_used = fields.Datetime(string="Último Uso", readonly=True)

    # N1: refresh token fields (OAuth only — PAT has no refresh token)
    refresh_token = fields.Char(
        string="Hash de Token de Refresco", readonly=True, index=True, copy=False,
    )
    refresh_token_expires_at = fields.Datetime(string="Caducidad del Refresco", readonly=True)

    # ------------------------------------------------------------------
    # Feature 1: Per-token scope
    # ------------------------------------------------------------------
    scope = fields.Selection(
        [("read", "Solo lectura"), ("write", "Lectura + Escritura"), ("admin", "Acceso Completo")],
        string="Alcance",
        default="write",
        required=True,
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Feature 2: IP allowlist / denylist
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
    # Feature 3: Model and field restrictions
    # ------------------------------------------------------------------
    allowed_model_ids = fields.Many2many(
        "ir.model",
        "mcp_token_allowed_model_rel",
        "token_id",
        "model_id",
        string="Modelos Permitidos",
        help="Restringe este token a modelos específicos de Odoo. "
             "Deje vacío para permitir el acceso a todos los modelos.",
        tracking=True,
    )
    denied_model_ids = fields.Many2many(
        "ir.model",
        "mcp_token_denied_model_rel",
        "token_id",
        "model_id",
        string="Modelos Denegados",
        help="Bloquea este token para modelos específicos de Odoo. "
             "La lista de denegados se evalúa antes que la lista de permitidos.",
        tracking=True,
    )
    field_restrictions = fields.Text(
        string="Restricciones de Campos (JSON)",
        help='Objeto JSON que asigna nombres de modelos a listas de campos permitidos. Ejemplo:\n'
             '{"sale.order": ["name", "partner_id", "amount_total"],\n'
             ' "res.partner": ["name", "email"]}\n\n'
             'Omitir un modelo significa que se permiten todos sus campos. '
             'Se aplica tanto a la lectura (descarta silenciosamente los campos no permitidos) '
             'como a la escritura (genera error si se escribe un campo no permitido).',
    )

    # ------------------------------------------------------------------
    # Feature 4: Payload capture opt-in
    # ------------------------------------------------------------------
    capture_payloads = fields.Boolean(
        string="Capturar Cargas Útiles",
        default=False,
        help="Cuando está activado, los argumentos y respuestas de las llamadas a herramientas se almacenan en el registro de auditoría "
             "(tras ocultar PII). Desactivado por defecto por rendimiento.",
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Token issuance
    # ------------------------------------------------------------------

    @api.model
    def issue(self, uid: int, client_name: str = "MCP Client",
              token_type: str = "oauth") -> str:
        """Issue a new access token. Returns raw access token (shown once, not stored).
        For OAuth flows with refresh token, use issue_oauth() instead."""
        raw, _ = self._issue_pair(uid, client_name, token_type)
        return raw

    @api.model
    def issue_oauth(self, uid: int, client_name: str = "MCP Client") -> tuple[str, str]:
        """Issue access + refresh token pair for OAuth flows.
        Returns (raw_access_token, raw_refresh_token)."""
        return self._issue_pair(uid, client_name, "oauth")

    @api.model
    def _issue_pair(self, uid: int, client_name: str,
                    token_type: str) -> tuple[str, str | None]:
        """Internal: create mcp.token record, return (raw_access, raw_refresh|None)."""
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

        rec = self.with_user(uid).create(vals)
        rec.message_post(body=f"Token Bearer MCP emitido — cliente: {client_name}")
        return raw_access, raw_refresh

    @api.model
    def refresh(self, raw_refresh_token: str) -> tuple[str, str] | None:
        """Exchange a refresh token for a new access + refresh token pair (rotation).
        Old token is expired. Returns (new_access, new_refresh) or None if invalid."""
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

        # Issue replacement tokens
        new_raw_access = secrets.token_urlsafe(32)
        new_raw_refresh = secrets.token_urlsafe(32)
        self.create({
            "name": rec.name,
            "token": _hash_token(new_raw_access),
            "refresh_token": _hash_token(new_raw_refresh),
            "user_id": rec.user_id.id,
            "token_type": rec.token_type,
            "expires_at": now + timedelta(days=TOKEN_TTL_DAYS),
            "refresh_token_expires_at": now + timedelta(days=REFRESH_TOKEN_TTL_DAYS),
        })
        # Expire the used token (rotation — prevent reuse)
        rec.write({"state": "expired"})
        return new_raw_access, new_raw_refresh

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_revoke(self):
        self.write({"state": "revoked"})

    def action_generate_pat(self):
        """Issue a PAT for the current user and open one-time display wizard."""
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
            "name": "Token de Acceso Personal — Guárdelo Ahora",
        }

    # ------------------------------------------------------------------
    # Governance helpers (called from token_service / tool_executor)
    # ------------------------------------------------------------------

    def is_ip_allowed(self, ip: str) -> bool:
        """Return True if *ip* is permitted by this token's IP rules.

        Evaluation order: denylist checked first, then allowlist.
        - If IP is in denylist → False
        - If allowlist is non-empty and IP is NOT in allowlist → False
        - Otherwise → True
        """
        self.ensure_one()
        try:
            client = ipaddress.ip_address(ip)
        except ValueError:
            # Unparseable IP — fail safe (deny)
            _logger.warning("MCP token %s: could not parse client IP %r", self.id, ip)
            return False

        if self.ip_denylist:
            for entry in self._parse_ip_lines(self.ip_denylist):
                if client in entry:
                    return False

        if self.ip_allowlist:
            for entry in self._parse_ip_lines(self.ip_allowlist):
                if client in entry:
                    return True
            # Allowlist is non-empty but no match
            return False

        return True

    def is_model_allowed(self, model_name: str) -> bool:
        """Return True if *model_name* is accessible under this token's model restrictions.

        Denied models are checked first. If allowed_model_ids is non-empty, the
        model must appear in it. Empty allowed_model_ids means all models are allowed.
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
        """Return the list of allowed field names for *model_name*, or None if all are allowed.

        Returns None (not an empty list) to distinguish "no restriction" from
        "restriction exists but produces empty set" (the latter would be a misconfiguration).
        """
        self.ensure_one()
        if not self.field_restrictions:
            return None
        try:
            restrictions = json.loads(self.field_restrictions)
        except (json.JSONDecodeError, TypeError):
            _logger.warning(
                "MCP token %s: invalid JSON in field_restrictions — treating as no restriction",
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
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_ip_lines(text: str):
        """Parse multi-line IP/CIDR text, yield ipaddress network/address objects.

        Blank lines and lines starting with # are skipped. Malformed entries are
        logged and skipped so one bad line does not break the entire check.
        """
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                yield ipaddress.ip_network(line, strict=False)
            except ValueError:
                try:
                    # Single address not in CIDR notation
                    yield ipaddress.ip_network(
                        str(ipaddress.ip_address(line)), strict=False
                    )
                except ValueError:
                    _logger.warning("MCP token: could not parse IP entry %r — skipping", line)
