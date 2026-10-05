import secrets
from urllib.parse import urlsplit

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

# Límites del registro dinámico (endpoint público): evitan abuso de espacio.
MAX_REDIRECT_URIS = 10
MAX_URI_LENGTH = 2000
_LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "[::1]", "::1")


def is_acceptable_redirect_uri(uri: str) -> bool:
    """HTTPS, o HTTP solo hacia loopback (clientes de escritorio/CLI, RFC 8252).

    Se rechazan fragmentos y esquemas como javascript:, data: o file:.
    """
    if not isinstance(uri, str) or not uri or len(uri) > MAX_URI_LENGTH:
        return False
    try:
        parts = urlsplit(uri)
    except ValueError:
        return False
    if parts.fragment or not parts.hostname:
        return False
    if parts.scheme == "https":
        return True
    return parts.scheme == "http" and parts.hostname in _LOOPBACK_HOSTS


class McpOauthClient(models.Model):
    """Cliente OAuth 2.0 público registrado (RFC 7591).

    El redirect_uri de /oauth/authorize y /oauth/token debe coincidir
    exactamente con uno de los registrados: sin esto, un enlace de autorización
    manipulado enviaría el código a un tercero.
    """

    _name = "mcp.oauth.client"
    _description = "Cliente OAuth MCP"
    _order = "create_date desc"
    _rec_name = "client_name"

    client_id = fields.Char(
        string="ID de Cliente", required=True, readonly=True, index=True, copy=False,
        default=lambda self: secrets.token_urlsafe(16),
    )
    client_name = fields.Char(string="Nombre del Cliente", default="MCP Client")
    redirect_uris = fields.Text(
        string="URIs de Redirección",
        required=True,
        help="Una URI por línea. Deben ser HTTPS, o HTTP hacia localhost/127.0.0.1.",
    )
    active = fields.Boolean(default=True)

    _client_id_unique = models.Constraint(
        "UNIQUE(client_id)",
        "El ID de cliente OAuth debe ser único.",
    )

    @api.constrains("redirect_uris")
    def _check_redirect_uris(self):
        for rec in self:
            uris = rec.get_redirect_uris()
            if not uris or len(uris) > MAX_REDIRECT_URIS:
                raise ValidationError(_("Indique entre 1 y %(max)s URIs de redirección.", max=MAX_REDIRECT_URIS))
            bad = [u for u in uris if not is_acceptable_redirect_uri(u)]
            if bad:
                raise ValidationError(_("URI de redirección no permitida: %(uri)s", uri=bad[0]))

    def get_redirect_uris(self) -> list[str]:
        self.ensure_one()
        return [line.strip() for line in (self.redirect_uris or "").splitlines() if line.strip()]

    @api.model
    def find_client(self, client_id: str, redirect_uri: str):
        """Devuelve el cliente activo si redirect_uri está registrada para él."""
        if not client_id or not redirect_uri:
            return self.browse()
        client = self.search([("client_id", "=", client_id)], limit=1)
        if client and redirect_uri in client.get_redirect_uris():
            return client
        return self.browse()
