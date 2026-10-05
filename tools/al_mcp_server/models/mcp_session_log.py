from odoo import models, fields


class McpSessionLog(models.Model):
    _name = 'mcp.session.log'
    _description = 'Registro de Llamadas a Herramientas MCP'
    _order = 'create_date desc'
    _rec_name = 'tool_name'

    session_id = fields.Many2one(
        'mcp.session', string='Sesión',
        ondelete='cascade', index=True, readonly=True,
    )
    user_id = fields.Many2one('res.users', string='Usuario', readonly=True, ondelete='set null')
    tool_name = fields.Char(string='Herramienta', readonly=True, index=True)
    odoo_model = fields.Char(string='Modelo', readonly=True)
    record_count = fields.Integer(string='Registros', readonly=True, default=0)
    duration_ms = fields.Integer(string='ms', readonly=True, default=0)
    is_error = fields.Boolean(string='Error', readonly=True, default=False)
    error_message = fields.Char(string='Detalle del Error', readonly=True)
    transport = fields.Selection(
        [('sse', 'SSE'), ('http', 'HTTP')],
        string='Transporte', readonly=True,
    )

    # Feature 4: payload capture fields — populated only when token.capture_payloads=True
    request_payload = fields.Text(
        string='Carga Útil de Solicitud',
        readonly=True,
        help='Argumentos de la herramienta codificados en JSON (PII ocultada, truncado a 4000 caracteres). '
             'Solo se captura cuando el token tiene "Capturar Cargas Útiles" activado.',
    )
    response_payload = fields.Text(
        string='Carga Útil de Respuesta',
        readonly=True,
        help='Resultado de la herramienta codificado en JSON (PII ocultada, truncado a 4000 caracteres). '
             'Solo se captura cuando el token tiene "Capturar Cargas Útiles" activado.',
    )
