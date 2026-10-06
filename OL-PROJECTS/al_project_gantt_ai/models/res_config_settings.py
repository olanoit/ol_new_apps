# -*- coding: utf-8 -*-
"""Ajustes del asistente.

Todo vive en ``ir.config_parameter`` (prefijo ``al_gantt_ai.``): no hace falta
una tabla propia para siete valores, y así la clave queda donde Odoo guarda el
resto de credenciales de servicios externos — legible solo por administradores.
La clave solo viaja al navegador de un administrador, en esta pantalla; nunca
al de quien usa el asistente.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..services import ai_provider
from .gantt_ai import DEFAULTS, MAX_TIMEOUT, PARAM_PREFIX

#: Parámetro de «Enviar personas asignadas». Se guarda a mano (ver
#: ``set_values``): con ``config_parameter`` un False borra el parámetro y
#: el asistente vuelve a su valor por defecto, que es True.
SHARE_ASSIGNEES_PARAM = PARAM_PREFIX + 'share_assignees'


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    al_gantt_ai_provider = fields.Selection(
        selection=[
            ('anthropic', "Anthropic (Claude)"),
            ('openai', "OpenAI"),
            ('deepseek', "DeepSeek"),
        ],
        string="Proveedor de IA",
        default=DEFAULTS['provider'],
        config_parameter=PARAM_PREFIX + 'provider',
    )
    al_gantt_ai_api_key = fields.Char(
        string="Clave de API",
        config_parameter=PARAM_PREFIX + 'api_key',
        groups='base.group_system',
        help="Se guarda en los parámetros del sistema. Solo la ven los "
             "administradores; nunca llega al navegador de quien usa el asistente.",
    )
    al_gantt_ai_model = fields.Char(
        string="Modelo",
        config_parameter=PARAM_PREFIX + 'model',
        help="Por ejemplo claude-opus-5 (Anthropic), gpt-5 (OpenAI) o "
             "deepseek-chat (DeepSeek). El modelo debe admitir «function "
             "calling»: es como el asistente devuelve las propuestas. Si se "
             "deja vacío se usa el modelo por defecto del proveedor.",
    )
    al_gantt_ai_base_url = fields.Char(
        string="URL base",
        config_parameter=PARAM_PREFIX + 'base_url',
        help="Solo para pasarelas o proxies compatibles. Vacío = servicio oficial.",
    )
    al_gantt_ai_effort = fields.Selection(
        selection=[
            ('auto', "Por defecto del modelo"),
            ('low', "Bajo"),
            ('medium', "Medio"),
            ('high', "Alto"),
        ],
        string="Esfuerzo de razonamiento",
        default=DEFAULTS['effort'],
        config_parameter=PARAM_PREFIX + 'effort',
        help="Solo lo aplica Anthropic, y únicamente en sus modelos recientes; "
             "con OpenAI y DeepSeek se ignora. Con «Por defecto del modelo» no "
             "se envía el parámetro.",
    )
    al_gantt_ai_max_tokens = fields.Integer(
        string="Tokens máximos de respuesta",
        default=DEFAULTS['max_tokens'],
        config_parameter=PARAM_PREFIX + 'max_tokens',
        help="Techo de la respuesta. Incluye el razonamiento interno del modelo, "
             "así que conviene dejar holgura.",
    )
    al_gantt_ai_timeout = fields.Integer(
        string="Tiempo de espera (s)",
        default=DEFAULTS['timeout'],
        config_parameter=PARAM_PREFIX + 'timeout',
    )
    al_gantt_ai_context_limit = fields.Integer(
        string="Tareas por consulta",
        default=DEFAULTS['context_limit'],
        config_parameter=PARAM_PREFIX + 'context_limit',
        help="Máximo de tareas visibles que se resumen y envían al proveedor.",
    )
    # Sin config_parameter a propósito: ver SHARE_ASSIGNEES_PARAM.
    al_gantt_ai_share_assignees = fields.Boolean(
        string="Enviar personas asignadas",
        default=DEFAULTS['share_assignees'],
        help="Necesario para que el asistente pueda proponer reasignaciones. "
             "Desactívelo si no quiere que salgan nombres de empleados.",
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        res['al_gantt_ai_share_assignees'] = self.env['al.gantt.ai']._get_config()['share_assignees']
        return res

    def set_values(self):
        super().set_values()
        # Se guarda siempre como texto explícito: un parámetro ausente
        # significa «por defecto» (True), no «desactivado».
        self.env['ir.config_parameter'].sudo().set_param(
            SHARE_ASSIGNEES_PARAM, 'True' if self.al_gantt_ai_share_assignees else 'False',
        )

    @api.constrains('al_gantt_ai_max_tokens', 'al_gantt_ai_timeout', 'al_gantt_ai_context_limit',
                    'al_gantt_ai_base_url')
    def _check_al_gantt_ai_limits(self):
        for record in self:
            if record.al_gantt_ai_max_tokens and record.al_gantt_ai_max_tokens < 512:
                raise ValidationError(_("Los tokens máximos de respuesta no pueden bajar de 512."))
            if record.al_gantt_ai_timeout and not 5 <= record.al_gantt_ai_timeout <= MAX_TIMEOUT:
                raise ValidationError(_(
                    "El tiempo de espera debe estar entre 5 y %s segundos: por encima, "
                    "el servidor corta la petición antes que el proveedor.", MAX_TIMEOUT,
                ))
            if record.al_gantt_ai_base_url and not ai_provider.is_safe_base_url(record.al_gantt_ai_base_url):
                raise ValidationError(_(
                    "La URL base debe empezar por https:// (la clave de API viaja en cada petición)."
                ))
            if record.al_gantt_ai_context_limit and not 1 <= record.al_gantt_ai_context_limit <= 1000:
                raise ValidationError(_("Las tareas por consulta deben estar entre 1 y 1000."))

    @api.onchange('al_gantt_ai_provider')
    def _onchange_al_gantt_ai_provider(self):
        """Sugiere el modelo por defecto al cambiar de proveedor."""
        for record in self:
            if record.al_gantt_ai_provider:
                record.al_gantt_ai_model = ai_provider.DEFAULT_MODEL.get(
                    record.al_gantt_ai_provider
                )
