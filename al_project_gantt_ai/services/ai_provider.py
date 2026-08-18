# -*- coding: utf-8 -*-
"""Conectores HTTP a los proveedores de IA.

Dos proveedores con la **misma interfaz interna**: se les pasa un prompt de
sistema, un historial normalizado y una definición de herramienta, y devuelven
``(texto, propuesta_cruda, uso)``. Toda la lógica de Odoo (permisos, contexto,
validación) vive en ``models/gantt_ai.py``; aquí solo hay transporte.

Por qué HTTP directo y no los SDK oficiales
-------------------------------------------
Un addon de Odoo se despliega copiando una carpeta: añadir dependencias de pip
(``anthropic``, ``openai``) obliga a tocar el entorno del servidor y a
mantenerlas al día en cada instalación. ``requests`` ya viene con Odoo y las dos
APIs son REST estables, así que el módulo funciona sin instalar nada. El precio
es que aquí se escriben a mano las cabeceras y el formato de cada proveedor.

La clave de API nunca se registra en el log ni se devuelve al cliente.
"""
import json
import logging

import requests

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: Nombre de la herramienta con la que el modelo devuelve propuestas.
TOOL_NAME = 'propose_changes'

#: Versión de la API de Anthropic (cabecera obligatoria).
ANTHROPIC_VERSION = '2023-06-01'

DEFAULT_BASE_URL = {
    'anthropic': 'https://api.anthropic.com',
    'openai': 'https://api.openai.com',
    'deepseek': 'https://api.deepseek.com',
}

#: Modelo por defecto de cada proveedor.
#:
#: DeepSeek: `deepseek-chat` y no `deepseek-reasoner` porque el asistente
#: depende de *function calling* para devolver las propuestas estructuradas, y
#: el modelo de razonamiento no lo ha soportado de forma estable.
DEFAULT_MODEL = {
    'anthropic': 'claude-opus-5',
    'openai': 'gpt-5',
    'deepseek': 'deepseek-chat',
}

#: Nombre comercial de cada proveedor, para los mensajes de error.
PROVIDER_LABEL = {
    'anthropic': "Anthropic",
    'openai': "OpenAI",
    'deepseek': "DeepSeek",
}

#: Dónde crea cada uno su clave de API. Se enlaza desde los ajustes: es la
#: pregunta que se hace todo el mundo al configurar esto por primera vez.
API_KEY_DOCS = {
    'anthropic': 'https://console.anthropic.com/settings/keys',
    'openai': 'https://platform.openai.com/api-keys',
    'deepseek': 'https://platform.deepseek.com/api_keys',
}

#: Campo con el que cada API compatible con OpenAI limita la respuesta.
#: OpenAI renombró `max_tokens` a `max_completion_tokens`; DeepSeek mantiene
#: el nombre original.
OPENAI_COMPATIBLE = {
    'openai': 'max_completion_tokens',
    'deepseek': 'max_tokens',
}

#: Esquema de la propuesta. Deliberadamente **plano y pequeño**: cada elemento
#: es un cambio sobre una tarea existente. No se usa `strict` porque las dos
#: APIs lo compilan con reglas distintas; la garantía real la da la validación
#: del servidor (`_normalize_proposal`), que hay que hacer igualmente porque la
#: salida del modelo es entrada no confiable.
PROPOSAL_SCHEMA = {
    'type': 'object',
    'properties': {
        'summary': {
            'type': 'string',
            'description': "Una frase explicando el conjunto de cambios propuesto.",
        },
        'changes': {
            'type': 'array',
            'description': "Cambios propuestos, uno por tarea.",
            'items': {
                'type': 'object',
                'properties': {
                    'task_id': {
                        'type': 'integer',
                        'description': "Id de una tarea presente en el contexto.",
                    },
                    'reason': {
                        'type': 'string',
                        'description': "Por qué se propone este cambio, en una frase.",
                    },
                    'start': {
                        'type': 'string',
                        'description': "Nueva fecha de inicio en ISO 8601 UTC "
                                       "(2026-09-01T13:00:00Z). Omitir si no cambia.",
                    },
                    'end': {
                        'type': 'string',
                        'description': "Nueva fecha de fin en ISO 8601 UTC. Omitir si no cambia.",
                    },
                    'progress': {
                        'type': 'number',
                        'description': "Nuevo avance, 0-100. Omitir si no cambia.",
                    },
                    'name': {
                        'type': 'string',
                        'description': "Nuevo nombre de la tarea. Omitir si no cambia.",
                    },
                    'user_ids': {
                        'type': 'array',
                        'items': {'type': 'integer'},
                        'description': "Ids de las personas asignadas, sustituyen a las "
                                       "actuales. Omitir si no cambia.",
                    },
                },
                'required': ['task_id', 'reason'],
                'additionalProperties': False,
            },
        },
    },
    'required': ['summary', 'changes'],
    'additionalProperties': False,
}

TOOL_DESCRIPTION = (
    "Propone cambios concretos sobre las tareas del cronograma. Úsala solo cuando el "
    "usuario pida un cambio o cuando detectes un problema y quieras sugerir un ajuste. "
    "Los cambios no se aplican: la persona los revisa y decide. Acompaña siempre la "
    "llamada con una explicación en texto."
)


def call_provider(env, config, system, messages):
    """Llama al proveedor configurado.

    :param env: entorno de Odoo, solo para traducir los mensajes de error.
    :param dict config: ``provider``, ``api_key``, ``model``, ``base_url``,
        ``max_tokens``, ``effort``, ``timeout``.
    :param str system: prompt de sistema.
    :param list messages: ``[{'role': 'user'|'assistant', 'content': str}, ...]``
    :returns: ``(answer, raw_proposal, usage)``
    :rtype: tuple
    """
    provider = config['provider']
    if provider == 'anthropic':
        return _call_anthropic(env, config, system, messages)
    if provider in OPENAI_COMPATIBLE:
        return _call_openai_compatible(env, config, system, messages)
    raise UserError(env._("Proveedor de IA desconocido: %s", provider))


# ----------------------------------------------------------------------
# Anthropic (Claude) — Messages API
# ----------------------------------------------------------------------
def _call_anthropic(env, config, system, messages):
    url = _base(config, 'anthropic') + '/v1/messages'
    headers = {
        'x-api-key': config['api_key'],
        'anthropic-version': ANTHROPIC_VERSION,
        'content-type': 'application/json',
    }
    body = {
        'model': config['model'],
        'max_tokens': config['max_tokens'],
        'system': system,
        'messages': messages,
        'tools': [{
            'name': TOOL_NAME,
            'description': TOOL_DESCRIPTION,
            'input_schema': PROPOSAL_SCHEMA,
        }],
    }
    # El esfuerzo controla cuánto razona el modelo. Solo lo aceptan los modelos
    # recientes (Opus/Sonnet 4.6 en adelante): con «auto» no se envía.
    if config.get('effort') and config['effort'] != 'auto':
        body['output_config'] = {'effort': config['effort']}

    data = _post(env, url, headers, body, config, PROVIDER_LABEL['anthropic'])

    # Los clasificadores de seguridad pueden declinar la petición: llega un 200
    # con `stop_reason: refusal` y `content` vacío. Hay que mirarlo **antes** de
    # leer el contenido.
    if data.get('stop_reason') == 'refusal':
        details = data.get('stop_details') or {}
        raise UserError(env._(
            "El proveedor rechazó la consulta por sus políticas de uso%s.",
            " (%s)" % details.get('category') if details.get('category') else "",
        ))

    answer_parts, proposal = [], None
    for block in data.get('content') or []:
        if block.get('type') == 'text':
            answer_parts.append(block.get('text') or '')
        elif block.get('type') == 'tool_use' and block.get('name') == TOOL_NAME:
            proposal = block.get('input') or {}

    usage = data.get('usage') or {}
    return (
        "\n".join(part for part in answer_parts if part).strip(),
        proposal,
        {
            'input_tokens': usage.get('input_tokens'),
            'output_tokens': usage.get('output_tokens'),
            'model': data.get('model') or config['model'],
        },
    )


# ----------------------------------------------------------------------
# OpenAI y compatibles (DeepSeek) — Chat Completions
# ----------------------------------------------------------------------
def _call_openai_compatible(env, config, system, messages):
    """Un solo camino para las APIs con forma de *Chat Completions*.

    DeepSeek expone la misma interfaz que OpenAI, así que compartir el código es
    lo correcto: si divergiera, habría que arreglar dos veces cada detalle del
    *function calling*. Lo único que cambia entre ellos está declarado en
    ``OPENAI_COMPATIBLE`` y ``DEFAULT_BASE_URL``.
    """
    provider = config['provider']
    label = PROVIDER_LABEL[provider]
    url = _base(config, provider) + '/v1/chat/completions'
    headers = {
        'Authorization': 'Bearer %s' % config['api_key'],
        'content-type': 'application/json',
    }
    body = {
        'model': config['model'],
        OPENAI_COMPATIBLE[provider]: config['max_tokens'],
        'messages': [{'role': 'system', 'content': system}] + messages,
        'tools': [{
            'type': 'function',
            'function': {
                'name': TOOL_NAME,
                'description': TOOL_DESCRIPTION,
                'parameters': PROPOSAL_SCHEMA,
            },
        }],
        'tool_choice': 'auto',
    }

    data = _post(env, url, headers, body, config, label)

    choices = data.get('choices') or []
    if not choices:
        raise UserError(env._("%s devolvió una respuesta vacía.", label))
    message = choices[0].get('message') or {}

    proposal = None
    for call in message.get('tool_calls') or []:
        function = call.get('function') or {}
        if function.get('name') != TOOL_NAME:
            continue
        try:
            proposal = json.loads(function.get('arguments') or '{}')
        except ValueError:
            _logger.warning("Argumentos de herramienta no son JSON válido; se descartan.")

    usage = data.get('usage') or {}
    return (
        (message.get('content') or '').strip(),
        proposal,
        {
            'input_tokens': usage.get('prompt_tokens'),
            'output_tokens': usage.get('completion_tokens'),
            'model': data.get('model') or config['model'],
        },
    )


# ----------------------------------------------------------------------
# Transporte común
# ----------------------------------------------------------------------
def _base(config, provider):
    return (config.get('base_url') or DEFAULT_BASE_URL[provider]).rstrip('/')


def _post(env, url, headers, body, config, label):
    """POST con manejo de errores traducido a mensajes accionables.

    Ojo con el tiempo de espera: el de ``requests`` es **por trozo recibido**,
    no de reloj total. Basta para cortar un proveedor caído, pero una respuesta
    que gotea puede tardar más que el valor configurado.
    """
    timeout = config.get('timeout') or 60
    try:
        response = requests.post(url, headers=headers, json=body, timeout=(10, timeout))
    except requests.Timeout:
        raise UserError(env._(
            "%(provider)s no respondió en %(timeout)s segundos. Vuelva a intentarlo o "
            "suba el tiempo de espera en los ajustes.",
            provider=label, timeout=timeout,
        ))
    except requests.RequestException as error:
        _logger.warning("Error de red hablando con %s: %s", label, error)
        raise UserError(env._("No se pudo contactar con %s. Revise la conexión del servidor.", label))

    if response.status_code >= 400:
        raise UserError(_build_http_error(env, response, label))

    try:
        return response.json()
    except ValueError:
        raise UserError(env._("%s devolvió una respuesta que no es JSON.", label))


def _build_http_error(env, response, label):
    """Mensaje de error legible; nunca incluye la clave de API."""
    detail = ''
    try:
        payload = response.json()
        error = payload.get('error') or {}
        detail = error.get('message') or payload.get('message') or ''
    except ValueError:
        detail = (response.text or '')[:200]

    status = response.status_code
    if status == 401:
        return env._("%s rechazó la clave de API. Revísela en Ajustes ▸ Gantt IA.", label)
    if status == 403:
        return env._("La clave de %s no tiene permiso para usar este modelo.", label)
    if status == 404:
        return env._("%(provider)s no reconoce el modelo «%(detail)s». Revise el nombre del modelo "
                 "en los ajustes.", provider=label, detail=detail or '?')
    if status == 429:
        return env._("%s ha limitado las peticiones (429). Espere unos segundos y reintente.", label)
    if status >= 500:
        return env._("%s no está disponible ahora mismo (%s).", label, status)
    return env._("%(provider)s rechazó la petición (%(status)s): %(detail)s",
             provider=label, status=status, detail=detail or env._("sin detalle"))
