# -*- coding: utf-8 -*-
"""Conexión a una API de consulta RUC/DNI (config-driven).

Una conexión describe **todo** lo necesario para consultar un servicio y
volcar el resultado en el partner, sin código específico por API:

  * cómo llamar (URL, endpoint, método, autenticación);
  * cómo interpretar la respuesta (raíz de datos, flag de éxito);
  * cómo mapear cada atributo de la respuesta a un campo de Odoo
    (``mapping_ids``).

El motor normaliza **toda** respuesta a un ``dict`` — sea JSON de una API
REST o el resultado de un scraper de SUNAT — y aplica el mismo mapeo. Así
se agregan APIs nuevas creando registros, no escribiendo Python.
"""
import dataclasses
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services import engine, http, sunat_oficial, ubigeo

_logger = logging.getLogger(__name__)

ENGINES = [
    ('rest_json', 'API REST / JSON'),
    ('sunat_oficial', 'SUNAT oficial (scraping)'),
    ('sunat_multi', 'SUNAT multi-consulta (scraping)'),
]

DOCUMENT_TYPES = [
    ('ruc', 'RUC'),
    ('dni', 'DNI'),
    ('both', 'RUC y DNI'),
]

# Marca de «valor descartado» en el mapeo.
_SKIP = object()

AUTH_TYPES = [
    ('none', 'Sin autenticación'),
    ('bearer', 'Token Bearer'),
    ('header', 'Cabecera personalizada'),
    ('query', 'Parámetro de URL'),
]


class L10nPeApiConnection(models.Model):
    _name = 'l10n_pe.api.connection'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Conexión de consulta RUC/DNI'
    _order = 'sequence, id'
    _check_company_auto = True

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, ondelete='cascade', index=True,
        default=lambda self: self.env.company)
    name = fields.Char(string='Nombre', required=True, tracking=True)
    sequence = fields.Integer(
        string='Prioridad', default=10, help="Orden de prioridad: la consulta usa la primera "
                         "conexión activa que responda; si falla, pasa a la "
                         "siguiente.",
        tracking=True)
    enabled = fields.Boolean(
        string='Habilitada', default=True,
        help="Desactívala para dejar de consultar esta conexión sin borrarla "
             "ni archivarla — sigue visible en la lista para reactivarla.",
        tracking=True)
    engine = fields.Selection(ENGINES, required=True, default='rest_json', tracking=True)
    document_type = fields.Selection(
        DOCUMENT_TYPES, required=True, default='ruc', string='Tipo de documento',
        tracking=True)

    # --- Conexión REST (engine = rest_json) ---
    base_url = fields.Char(string='URL base', tracking=True)
    endpoint_ruc = fields.Char(
        string='Endpoint RUC',
        help="Ruta relativa; usa {doc} como marcador del número. "
             "Ej.: '/ruc/{doc}' o '/v1/ruc?numero={doc}'.")
    endpoint_dni = fields.Char(string='Endpoint DNI', help="Usa {doc}.")
    http_method = fields.Selection(
        [('get', 'GET'), ('post', 'POST')], default='get', required=True)
    body_ruc = fields.Char(
        string='Body RUC (POST)',
        help="Plantilla JSON del cuerpo para POST, con {doc}. "
             "Ej.: '{\"ruc\": \"{doc}\"}'. Solo si el número va en el body.")
    body_dni = fields.Char(
        string='Body DNI (POST)',
        help="Plantilla JSON del cuerpo para POST, con {doc}. "
             "Ej.: '{\"dni\": \"{doc}\"}'.")
    timeout = fields.Integer(default=10, string='Tiempo de espera (s)')
    auth_type = fields.Selection(AUTH_TYPES, string='Autenticación', default='bearer', required=True)
    auth_key = fields.Char(
        string='Nombre de clave',
        help="Nombre de la cabecera o parámetro cuando la autenticación es "
             "'Cabecera' o 'Parámetro de URL' (p. ej. 'X-Api-Key').")
    # Solo administradores: el token es una credencial de pago. El resto de
    # usuarios consulta igual, porque el motor lo lee con sudo().
    token = fields.Char(string='Token / clave', groups='base.group_system')

    # --- Interpretación de la respuesta (rest_json) ---
    success_path = fields.Char(
        string='Ruta de éxito',
        help="Ruta a un flag de éxito en la respuesta (p. ej. 'success'). "
             "Si viene falso, la consulta se considera fallida. Opcional.")
    data_root = fields.Char(
        string='Raíz de datos',
        help="Ruta a la sección con los datos (p. ej. 'data'). Los atributos "
             "del mapeo son relativos a ella. Vacío = raíz de la respuesta.")

    # --- Ubigeo (resolución geográfica desde la respuesta) ---
    ubigeo_path = fields.Char(string='Atributo ubigeo')
    district_path = fields.Char(string='Atributo distrito')
    province_path = fields.Char(string='Atributo provincia')
    department_path = fields.Char(string='Atributo departamento')

    # --- Scrapers SUNAT ---
    import_legal_reps = fields.Boolean(
        string='Importar representantes',
        help="Solo scraper SUNAT oficial.")
    import_annexed_locals = fields.Boolean(
        string='Importar locales anexos', help="Solo scraper SUNAT oficial.")

    mapping_ids = fields.One2many(
        'l10n_pe.api.field.mapping', 'connection_id', string='Mapeo de campos',
        copy=True)

    # ==================================================================== #
    # Entry point: consulta + mapeo a valores de partner                   #
    # ==================================================================== #

    def _is_usable(self):
        """Una conexión REST que exige token pero no lo tiene nunca funcionará
        (siempre daría 401); se considera no utilizable hasta configurarla."""
        self.ensure_one()
        # sudo(): ``token`` es solo de administradores, pero cualquier usuario
        # que consulta un RUC necesita saber si la conexión tiene token.
        connection_sudo = self.sudo()
        if (self.engine == 'rest_json' and self.auth_type != 'none'
                and not connection_sudo.token):
            return False
        return True

    def run(self, document, doc_type, quick=False):
        """Consulta la API y devuelve ``(vals, extra)``.

        ``quick`` (consulta automática al escribir): sin reintentos y con
        timeout corto, para no bloquear el formulario.

        - ``vals``: dict {campo_odoo: valor} listo para ``partner.write``.
        - ``extra``: dict con estructuras especiales (representantes
          legales, locales anexos) para post-procesar.

        Lanza ``http.HttpError`` / ``UserError`` / ``ValueError`` si la
        consulta falla; el llamador decide si prueba la siguiente conexión.
        """
        self.ensure_one()
        data = self._fetch_data(document, doc_type, quick=quick)
        if not data:
            raise http.HttpError(
                _('La conexión "%s" no devolvió datos.', self.name),
                service=self.name)
        vals = self._apply_mappings(data, doc_type)
        vals.update(self._resolve_ubigeo(data))
        extra = {
            'legal_representatives': data.get('legal_representatives') or [],
            'annexed_locals': data.get('annexed_locals') or [],
        }
        return vals, extra

    # ------------------------------------------------------------------ #
    # 1. Obtener la respuesta como dict (según engine)                   #
    # ------------------------------------------------------------------ #

    def _fetch_data(self, document, doc_type, quick=False):
        self.ensure_one()
        if self.engine == 'rest_json':
            return self._fetch_rest(document, doc_type, quick=quick)
        if self.engine == 'sunat_oficial':
            result = sunat_oficial.fetch_ruc(
                document, with_legal_reps=self.import_legal_reps and not quick,
                with_annex=self.import_annexed_locals and not quick, quick=quick)
            return dataclasses.asdict(result)
        if self.engine == 'sunat_multi':
            return dataclasses.asdict(sunat_oficial.fetch_ruc_multi(document, quick=quick))
        raise UserError(_('Engine de conexión no soportado: %s', self.engine))

    def _fetch_rest(self, document, doc_type, quick=False):
        # sudo(): el token es solo de administradores; se lee aquí para
        # autenticar la consulta sin exponerlo al usuario que la lanza.
        token = self.sudo().token
        endpoint = self.endpoint_dni if doc_type == 'dni' else self.endpoint_ruc
        if not self.base_url or not endpoint:
            raise ValueError(
                _('La conexión "%s" no tiene URL base o endpoint configurado.',
                  self.name))
        url = self.base_url.rstrip('/') + '/' + endpoint.lstrip('/')
        url = url.replace('{doc}', document)
        headers = {'Accept': 'application/json'}
        params = {}
        if self.auth_type == 'bearer' and token:
            headers['Authorization'] = 'Bearer %s' % token
        elif self.auth_type == 'header' and self.auth_key:
            headers[self.auth_key] = token or ''
        elif self.auth_type == 'query' and self.auth_key:
            params[self.auth_key] = token or ''
        # Cuerpo JSON para POST (APIs que reciben el número en el body).
        json_body = None
        if self.http_method == 'post':
            body_tmpl = self.body_dni if doc_type == 'dni' else self.body_ruc
            if body_tmpl:
                try:
                    json_body = json.loads(body_tmpl.replace('{doc}', document))
                except json.JSONDecodeError as exc:
                    raise ValueError(_(
                        'Body JSON inválido en la conexión "%(name)s": %(err)s',
                        name=self.name, err=exc))
        timeout = self.timeout or 10
        if quick:
            timeout = min(timeout, 5)
        response = http.request(
            self.http_method.upper(), url, service=self.name,
            headers=headers, params=params or None, json=json_body,
            timeout=timeout, retries=0 if quick else 2)
        if response.status_code != 200:
            # Extraer el mensaje de la API (p. ej. "Su plan ha vencido...")
            # para que el error sea accionable, no un genérico "HTTP 401".
            detail = ''
            try:
                body = response.json()
                detail = body.get('message') or '' if isinstance(body, dict) else ''
            except ValueError:
                detail = ''
            raise http.HttpError(
                _('%(name)s: %(msg)s (HTTP %(code)s)', name=self.name,
                  msg=detail or _('rechazó la consulta'),
                  code=response.status_code),
                status_code=response.status_code, body=response.text,
                service=self.name)
        try:
            payload = response.json() or {}
        except ValueError as exc:
            raise http.HttpError(
                _('%(name)s: la respuesta no es JSON válido.', name=self.name),
                status_code=200, body=response.text,
                service=self.name) from exc
        if self.success_path and not engine.truthy(
                engine.get_path(payload, self.success_path)):
            message = engine.get_path(payload, 'message') or _('sin datos')
            raise http.HttpError(
                _('%(name)s: %(msg)s', name=self.name, msg=message),
                status_code=200, body=response.text, service=self.name)
        data = engine.get_path(payload, self.data_root) if self.data_root else payload
        if not isinstance(data, dict):
            # Una lista o un texto donde se esperaba el objeto del
            # contribuyente rompía el mapeo con un traceback.
            raise http.HttpError(
                _('%(name)s: la respuesta no tiene el formato esperado.', name=self.name),
                status_code=200, body=response.text, service=self.name)
        return data

    # ------------------------------------------------------------------ #
    # 2. Aplicar el mapeo genérico                                        #
    # ------------------------------------------------------------------ #

    def _apply_mappings(self, data, doc_type):
        self.ensure_one()
        vals = {}
        Partner = self.env['res.partner']
        for mapping in self.mapping_ids:
            if mapping.for_document not in ('both', doc_type):
                continue
            field_name = mapping.field_name
            if not field_name or field_name not in Partner._fields:
                continue
            raw = engine.render_source(data, mapping.source_path)
            value = engine.apply_transform(raw, mapping.transform)
            if value in (None, '') and mapping.default_value:
                value = mapping.default_value
            if value in (None, '') and mapping.skip_if_empty:
                continue
            value = self._coerce(Partner._fields[field_name], value)
            if value is _SKIP:
                continue
            vals[field_name] = value
        return vals

    def _coerce(self, field, value):
        """Convierte el valor extraído al tipo del campo destino.

        En selecciones, un valor que no está entre las opciones se descarta
        (con aviso en el log): escribirlo haría fallar toda la consulta.
        SUNAT recorta sus estados a 20 caracteres, así que se prueba también
        el valor recortado.
        """
        if field.type == 'boolean':
            return engine.truthy(value)
        if field.type == 'selection':
            text = '' if value is None else str(value).strip()
            valid = field.get_values(self.env)
            for candidate in (text, text.upper(), text.upper()[:20].strip()):
                if candidate in valid:
                    return candidate
            _logger.warning(
                '[%s] Valor «%s» no válido para %s; se ignora.',
                self.name, text, field.name)
            return _SKIP
        if field.type in ('char', 'text'):
            return '' if value is None else str(value)
        return value

    # ------------------------------------------------------------------ #
    # 3. Ubigeo (resolución geográfica → M2o)                             #
    # ------------------------------------------------------------------ #

    def _resolve_ubigeo(self, data):
        self.ensure_one()
        if not any([self.ubigeo_path, self.district_path,
                    self.province_path, self.department_path]):
            return {}
        code = engine.render_source(data, self.ubigeo_path) if self.ubigeo_path else ''
        return ubigeo.resolve(
            self.env,
            ubigeo_code=str(code or ''),
            district=str(engine.render_source(data, self.district_path) or '')
            if self.district_path else '',
            city=str(engine.render_source(data, self.province_path) or '')
            if self.province_path else '',
            state=str(engine.render_source(data, self.department_path) or '')
            if self.department_path else '',
        )
