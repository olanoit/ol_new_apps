import base64
import hashlib
import secrets
from datetime import timedelta

from odoo import api, fields, models
from odoo.tools import consteq

CODE_TTL_MINUTES = 10


def _hash_code(raw: str) -> str:
    """Hash SHA-256 de un código de autorización en claro (igual que en mcp_token.py)."""
    return hashlib.sha256(raw.encode()).hexdigest()


class McpAuthCode(models.Model):
    """Códigos de autorización OAuth 2.0 de corta duración (PKCE S256)."""

    _name = "mcp.auth.code"
    _description = "Código de autorización OAuth MCP"
    _order = "create_date desc"

    code = fields.Char(string="Hash del código (SHA-256)", readonly=True, index=True, copy=False)
    user_id = fields.Many2one("res.users", string="Usuario", required=True, ondelete="cascade")
    client_id = fields.Char(string="ID de cliente")
    client_name = fields.Char(string="Nombre del cliente")
    redirect_uri = fields.Char(string="URI de redirección")
    code_challenge = fields.Char(string="Desafío de código", help="Desafío de código PKCE S256")
    expires_at = fields.Datetime(string="Caduca el", readonly=True)
    used = fields.Boolean(string="Usado", default=False, readonly=True)

    @api.model
    def create_code(
        self,
        uid: int,
        client_id: str,
        redirect_uri: str,
        code_challenge: str,
        client_name: str = "",
    ) -> str:
        """Emite un código de autorización de un solo uso. Guarda el hash SHA-256 y devuelve el código en claro."""
        raw = secrets.token_urlsafe(32)
        self.create(
            {
                "code": _hash_code(raw),
                "user_id": uid,
                "client_id": client_id,
                "client_name": client_name,
                "redirect_uri": redirect_uri,
                "code_challenge": code_challenge,
                "expires_at": fields.Datetime.now() + timedelta(minutes=CODE_TTL_MINUTES),
            }
        )
        return raw

    @api.model
    def exchange(self, code: str, code_verifier: str, redirect_uri: str, client_id: str = ""):
        """
        Canjea el código + verificador PKCE por el registro del código de autorización.
        Devuelve el registro (con user_id) si tiene éxito y None si falla.
        Marca el código como usado para impedir su reutilización.
        El código queda ligado al client_id que lo solicitó (RFC 6749 §4.1.3).
        """
        rec = self.search(
            [
                ("code", "=", _hash_code(code)),
                ("used", "=", False),
                ("redirect_uri", "=", redirect_uri),
                ("client_id", "=", client_id or False),
            ],
            limit=1,
        )
        if not rec:
            return None

        if fields.Datetime.now() > rec.expires_at:
            return None

        # Verifica PKCE S256: SHA-256(code_verifier) == base64url(code_challenge)
        digest = hashlib.sha256(code_verifier.encode()).digest()
        computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        if not consteq(computed, rec.code_challenge or ""):
            return None

        rec.write({"used": True})
        return rec

    @api.model
    def _vacuum_expired(self):
        """Elimina los códigos de autorización usados o caducados. Lo invoca un ir.cron cada hora."""
        deadline = fields.Datetime.now() - timedelta(minutes=CODE_TTL_MINUTES)
        old = self.search(["|", ("used", "=", True), ("expires_at", "<", deadline)])
        old.unlink()
