from odoo import api, models

from ..services.bi_tools import TOOL_DEFINITIONS as _BI_TOOL_DEFINITIONS
from ..services.job_tools import TOOL_DEFINITIONS as _JOB_TOOL_DEFINITIONS
from ..services.module_tools import TOOL_DEFINITIONS as _MODULE_TOOL_DEFINITIONS
from ..services.portal_tools import TOOL_DEFINITIONS as _PORTAL_TOOL_DEFINITIONS
from ..services.artifact_tools import TOOL_DEFINITIONS as _ARTIFACT_TOOL_DEFINITIONS

# ---------------------------------------------------------------------------
# Static MCP tool definitions (schema advertised to AI clients via tools/list)
# ---------------------------------------------------------------------------

_TOOL_DEFINITIONS = [
    {
        "name": "odoo_get_models",
        "description": "Lista todos los modelos de Odoo disponibles con su nombre técnico y etiqueta",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "description": "Palabra clave opcional para filtrar los nombres de los modelos (p.ej. 'sale')",
                }
            },
        },
    },
    {
        "name": "odoo_fields_get",
        "description": "Obtiene las definiciones de campos de un modelo de Odoo",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": "Nombre técnico del modelo, p.ej. 'sale.order'",
                },
                "attributes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Atributos a recuperar (por defecto: string, type, required, readonly, help)",
                },
            },
            "required": ["model"],
        },
    },
    {
        "name": "odoo_search_read",
        "description": "Busca y lee registros de un modelo de Odoo",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Nombre técnico del modelo"},
                "domain": {
                    "type": "array",
                    "description": "Filtro de dominio de Odoo, p.ej. [['state','=','sale']]",
                    "default": [],
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Campos a leer (vacío = todos los campos)",
                },
                "limit": {"type": "integer", "default": 80},
                "offset": {"type": "integer", "default": 0},
                "order": {"type": "string", "description": "p.ej. 'name asc, date desc'"},
            },
            "required": ["model"],
        },
    },
    {
        "name": "odoo_create",
        "description": "Crea un nuevo registro en un modelo de Odoo",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string"},
                "values": {"type": "object", "description": "Valores de campo para el nuevo registro"},
            },
            "required": ["model", "values"],
        },
    },
    {
        "name": "odoo_write",
        "description": "Actualiza uno o más registros en un modelo de Odoo",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string"},
                "ids": {"type": "array", "items": {"type": "integer"}},
                "values": {"type": "object"},
            },
            "required": ["model", "ids", "values"],
        },
    },
    {
        "name": "odoo_execute_wizard",
        "description": (
            "Crea y ejecuta un asistente (TransientModel) en una sola llamada atómica. "
            "Úsalo para diálogos de confirmación, p.ej. validar una entrega sin SMS: "
            "model='confirm.stock.sms', values={'pick_ids': [[4, <picking_id>]]}, "
            "method='dont_send_sms'. "
            "Solo funciona en TransientModels — genera un error para modelos permanentes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": "Nombre del TransientModel (asistente), p.ej. 'confirm.stock.sms'",
                },
                "values": {
                    "type": "object",
                    "description": "Valores de campo para inicializar el asistente, p.ej. {\"pick_ids\": [[4, 12]]}",
                    "default": {},
                },
                "method": {
                    "type": "string",
                    "description": "Método público a llamar, p.ej. 'dont_send_sms', 'action_validate'",
                },
                "kwargs": {
                    "type": "object",
                    "description": "Argumentos con nombre opcionales para el método",
                    "default": {},
                },
            },
            "required": ["model", "method"],
        },
    },
    {
        "name": "odoo_unlink",
        "description": "Elimina uno o más registros de un modelo de Odoo",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string"},
                "ids": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["model", "ids"],
        },
    },
    {
        "name": "odoo_call_method",
        "description": (
            "Llama a cualquier método en un modelo o conjunto de registros de Odoo "
            "(p.ej. button_confirm, action_invoice_open)"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string"},
                "method": {"type": "string", "description": "Nombre del método, p.ej. 'button_confirm'"},
                "ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "IDs de registros (vacío = método de clase)",
                    "default": [],
                },
                "args": {"type": "array", "default": []},
                "kwargs": {"type": "object", "default": {}},
            },
            "required": ["model", "method"],
        },
    },
    # ------------------------------------------------------------------
    # Workflow & form tools
    # ------------------------------------------------------------------
    {
        "name": "odoo_message_post",
        "description": (
            "Publica un mensaje en el chatter de un registro (mail.thread). "
            "Úsalo para enviar notas internas, notificar a los seguidores, registrar actividades, "
            "o comunicarte con los clientes directamente desde un registro. "
            "Se acepta cuerpo en texto plano o HTML."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Nombre técnico del modelo, p.ej. 'sale.order'"},
                "id": {"type": "integer", "description": "ID del registro en el que publicar el mensaje"},
                "body": {"type": "string", "description": "Cuerpo del mensaje — texto plano o HTML"},
                "subtype": {
                    "type": "string",
                    "description": "XML ID del subtipo de mensaje. 'mail.mt_comment' (por defecto) = visible para los seguidores, 'mail.mt_note' = nota interna",
                    "default": "mail.mt_comment",
                },
                "partner_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "IDs de contactos adicionales a notificar (IDs de res.partner)",
                    "default": [],
                },
            },
            "required": ["model", "id", "body"],
        },
    },
    {
        "name": "odoo_default_get",
        "description": (
            "Obtiene los valores por defecto de los campos de un nuevo registro antes de crearlo. "
            "Llama siempre a esto antes de odoo_create para evitar campos obligatorios faltantes "
            "o valores por defecto incorrectos (p.ej. diario, compañía o moneda por defecto)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Nombre técnico del modelo"},
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Nombres de los campos para los que obtener los valores por defecto. Vacío = detectar automáticamente todos los campos escalares.",
                    "default": [],
                },
            },
            "required": ["model"],
        },
    },
    {
        "name": "odoo_get_views",
        "description": (
            "Descubre los métodos invocables, las opciones del menú de acciones, las acciones de ventana y los informes disponibles de un modelo. "
            "Cada método invocable incluye 'defined_in' que muestra qué clase/mixin lo proporciona. "
            "Úsalo antes de odoo_call_method para saber qué métodos action_* y button_* existen, "
            "o para ver qué entradas aparecen en el menú de Acción en la interfaz de Odoo. "
            "También devuelve available_reports — úsalo con odoo_print_report."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Nombre técnico del modelo"},
            },
            "required": ["model"],
        },
    },
    {
        "name": "odoo_create_attachment",
        "description": (
            "Sube un archivo a Odoo como un registro ir.attachment. "
            "El contenido debe estar codificado en base64. Puede adjuntarse a cualquier registro de Odoo "
            "(orden de venta, factura, contacto, etc.) o almacenarse como un documento independiente. "
            "Tras subirlo, usa odoo://attachment/{id} para verificar el contenido."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Nombre del archivo incluyendo la extensión, p.ej. 'contract.pdf'",
                },
                "content": {
                    "type": "string",
                    "description": "Contenido del archivo codificado en base64",
                },
                "mimetype": {
                    "type": "string",
                    "description": "Tipo MIME, p.ej. 'application/pdf', 'text/csv', 'image/png'",
                    "default": "application/octet-stream",
                },
                "model": {
                    "type": "string",
                    "description": "Nombre técnico del modelo al que adjuntar, p.ej. 'sale.order'. Déjalo vacío para un adjunto independiente.",
                    "default": "",
                },
                "record_id": {
                    "type": "integer",
                    "description": "ID del registro al que adjuntar (obligatorio si se especifica el modelo)",
                    "default": 0,
                },
            },
            "required": ["name", "content"],
        },
    },
    {
        "name": "odoo_print_report",
        "description": (
            "Obtiene la URL de descarga de un informe PDF/HTML de Odoo para uno o más registros. "
            "Úsalo para generar facturas, albaranes de entrega, órdenes de venta, órdenes de compra, "
            "informes de inventario o cualquier informe QWeb de Odoo. "
            "Si se omite 'report', se usa el primer informe PDF disponible para el modelo "
            "y se devuelve una lista de todos los informes disponibles para que puedas elegir. "
            "La download_url devuelta debe abrirse en un navegador con una sesión de Odoo activa."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": "Nombre técnico del modelo, p.ej. 'sale.order', 'account.move'",
                },
                "ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "IDs de registros a incluir en el informe",
                },
                "report": {
                    "type": "string",
                    "description": (
                        "Nombre técnico del informe, p.ej. 'sale.report_saleorder', "
                        "'account.report_invoice'. "
                        "Déjalo vacío para detectar automáticamente y listar todos los informes disponibles."
                    ),
                    "default": "",
                },
            },
            "required": ["model", "ids"],
        },
    },
    {
        "name": "odoo_onchange",
        "description": (
            "Simula el onchange de un formulario de Odoo — calcula los valores de campos dependientes cuando cambia un campo. "
            "Ejemplo: establece partner_id en una sale.order para obtener los valores correctos de pricelist_id, "
            "payment_term_id y fiscal_position_id que Odoo autocompletaría. "
            "Pasa el diccionario de nuevos valores y lista los campos que activaron el cambio. "
            "Los resultados One2many se resumen (no se expanden) para evitar el desbordamiento del contexto."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Nombre técnico del modelo"},
                "values": {
                    "type": "object",
                    "description": "Valores de campo actuales a simular (incluye el campo modificado)",
                },
                "field_onchange": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Nombres de los campos que cambiaron y deben activar sus manejadores onchange",
                },
            },
            "required": ["model", "values", "field_onchange"],
        },
    },
    # ------------------------------------------------------------------
    # Analytics tools
    # ------------------------------------------------------------------
    {
        "name": "odoo_count",
        "description": (
            "Cuenta los registros que coinciden con un dominio sin cargarlos. "
            "Úsalo para totales rápidos: '¿cuántas facturas sin pagar?', '¿cuántas órdenes de compra abiertas?'"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Nombre técnico del modelo"},
                "domain": {
                    "type": "array",
                    "description": "Filtro de dominio de Odoo",
                    "default": [],
                },
            },
            "required": ["model"],
        },
    },
    {
        "name": "odoo_name_search",
        "description": (
            "Busca registros por nombre mostrado (como un autocompletado). "
            "Úsalo para encontrar un cliente, un producto o cualquier registro por nombre parcial "
            "antes de crear o vincular registros."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Nombre técnico del modelo"},
                "name": {"type": "string", "description": "Nombre parcial a buscar"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["model", "name"],
        },
    },
    {
        "name": "odoo_read_group",
        "description": (
            "Agrega y agrupa registros — el equivalente en Odoo del GROUP BY de SQL. "
            "Úsalo para analítica de negocio: ventas totales por cliente, inventario por almacén, "
            "importes de facturas por mes, etc. "
            "sintaxis de fields: 'field_name' para agrupar, 'field_name:sum/count/avg/max/min' para agregados."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": "Nombre técnico del modelo, p.ej. 'sale.order'",
                },
                "domain": {
                    "type": "array",
                    "description": "Dominio de filtro, p.ej. [['state','=','sale']]",
                    "default": [],
                },
                "groupby": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Campos por los que agrupar, p.ej. ['partner_id', 'date_order:month']",
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Campos agregados, p.ej. ['amount_total:sum', 'id:count']",
                    "default": [],
                },
                "limit": {"type": "integer", "default": 80},
                "orderby": {
                    "type": "string",
                    "description": "Orden de clasificación, p.ej. 'amount_total desc'",
                },
            },
            "required": ["model", "groupby"],
        },
    },
    {
        "name": "odoo_get_context",
        "description": (
            "Obtiene el contexto de negocio de Odoo: información de la compañía (nombre, moneda, zona horaria), "
            "detalles del usuario actual, lista de módulos instalados y fecha del servidor. "
            "Usa esto primero para entender la instancia de Odoo antes de responder preguntas de negocio. "
            "Equivalente a leer el recurso odoo://context — se proporciona como herramienta para "
            "clientes de IA que no admiten Recursos MCP (p.ej. ChatGPT, Grok)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def get_tool_definitions() -> list:
    """Return the list of MCP tool definitions. Called by mcp_protocol on tools/list."""
    return (
        _TOOL_DEFINITIONS
        + _BI_TOOL_DEFINITIONS
        + _JOB_TOOL_DEFINITIONS
        + _PORTAL_TOOL_DEFINITIONS
        + _ARTIFACT_TOOL_DEFINITIONS
        + _MODULE_TOOL_DEFINITIONS
    )


# ---------------------------------------------------------------------------
# Odoo model — exposes tool registry as an ORM service for extensibility
# ---------------------------------------------------------------------------


class McpToolRegistry(models.AbstractModel):
    _name = "mcp.tool.registry"
    _description = "Registro de Herramientas MCP"

    @api.model
    def get_tools(self) -> list:
        """Return current MCP tool definitions (can be overridden by other modules)."""
        return get_tool_definitions()

    @api.model
    def get_installed_models(self, filter_kw: str = "") -> list:
        """Return installed non-transient models, optionally filtered by keyword."""
        domain = [("transient", "=", False)]
        if filter_kw:
            domain.append(("model", "ilike", filter_kw))
        return self.env["ir.model"].search_read(
            domain,
            ["model", "name"],
            order="model",
            limit=500,
        )
