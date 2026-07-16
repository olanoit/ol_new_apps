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

AUTH_TYPES = [
    ('none', 'Sin autenticación'),
    ('bearer', 'Bearer token'),
    ('header', 'Cabecera personalizada'),
    ('query', 'Parámetro de URL'),
]


class L10nPeApiConnection(models.Model):
    _name = 'l10n_pe.api.connection'
    _description = 'Conexión de consulta RUC/DNI'
    _order = 'sequence, id'

    company_id = fields.Many2one(
        'res.company', required=True, ondelete='cascade', index=True,
        default=lambda self: self.env.company)
    name = fields.Char(required=True)
    sequence = fields.Integer(
        default=10, help="Orden de prioridad: la consulta usa la primera "
                         "conexión activa que responda; si falla, pasa a la "
                         "siguiente.")
    enabled = fields.Boolean(
        string='Habilitada', default=True,
        help="Desactívala para dejar de consultar esta conexión sin borrarla "
             "ni archivarla — sigue visible en la lista para reactivarla.")
    engine = fields.Selection(ENGINES, required=True, default='rest_json')
    document_type = fields.Selection(
        DOCUMENT_TYPES, required=True, default='ruc', string='Tipo de documento')

    # --- Conexión REST (engine = rest_json) ---
    base_url = fields.Char(string='URL base')
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
    timeout = fields.Integer(default=10, string='Timeout (s)')
    auth_type = fields.Selection(AUTH_TYPES, default='bearer', required=True)
    auth_key = fields.Char(
        string='Nombre de clave',
        help="Nombre de la cabecera o parámetro cuando la autenticación es "
             "'Cabecera' o 'Parámetro de URL' (p. ej. 'X-Api-Key').")
    token = fields.Char(string='Token / clave')

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
        string='Importar representantes legales',
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
        if self.engine == 'rest_json' and self.auth_type != 'none' and not self.token:
            return False
        return True

    def run(self, document, doc_type):
        """Consulta la API y devuelve ``(vals, extra)``.

        - ``vals``: dict {campo_odoo: valor} listo para ``partner.write``.
        - ``extra``: dict con estructuras especiales (representantes
          legales, locales anexos) para post-procesar.

        Lanza ``http.HttpError`` / ``UserError`` / ``ValueError`` si la
        consulta falla; el llamador decide si prueba la siguiente conexión.
        """
        self.ensure_one()
        data = self._fetch_data(document, doc_type)
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

    def _fetch_data(self, document, doc_type):
        self.ensure_one()
        if self.engine == 'rest_json':
            return self._fetch_rest(document, doc_type)
        if self.engine == 'sunat_oficial':
            result = sunat_oficial.fetch_ruc(
                document, with_legal_reps=self.import_legal_reps,
                with_annex=self.import_annexed_locals)
            return dataclasses.asdict(result)
        if self.engine == 'sunat_multi':
            return dataclasses.asdict(sunat_oficial.fetch_ruc_multi(document))
        raise UserError(_('Engine de conexión no soportado: %s', self.engine))

    def _fetch_rest(self, document, doc_type):
        endpoint = self.endpoint_dni if doc_type == 'dni' else self.endpoint_ruc
        if not self.base_url or not endpoint:
            raise ValueError(
                _('La conexión "%s" no tiene URL base o endpoint configurado.',
                  self.name))
        url = self.base_url.rstrip('/') + '/' + endpoint.lstrip('/')
        url = url.replace('{doc}', document)
        headers = {'Accept': 'application/json'}
        params = {}
        if self.auth_type == 'bearer' and self.token:
            headers['Authorization'] = 'Bearer %s' % self.token
        elif self.auth_type == 'header' and self.auth_key:
            headers[self.auth_key] = self.token or ''
        elif self.auth_type == 'query' and self.auth_key:
            params[self.auth_key] = self.token or ''
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
        response = http.request(
            self.http_method.upper(), url, service=self.name,
            headers=headers, params=params or None, json=json_body,
            timeout=self.timeout or 10)
        if response.status_code != 200:
            # Extraer el mensaje de la API (p. ej. "Su plan ha vencido...")
            # para que el error sea accionable, no un genérico "HTTP 401".
            detail = ''
            try:
                detail = (response.json() or {}).get('message') or ''
            except ValueError:
                detail = ''
            raise http.HttpError(
                _('%(name)s: %(msg)s (HTTP %(code)s)', name=self.name,
                  msg=detail or _('rechazó la consulta'),
                  code=response.status_code),
                status_code=response.status_code, body=response.text,
                service=self.name)
        payload = response.json() or {}
        if self.success_path and not engine.truthy(
                engine.get_path(payload, self.success_path)):
            message = engine.get_path(payload, 'message') or _('sin datos')
            raise http.HttpError(
                _('%(name)s: %(msg)s', name=self.name, msg=message),
                status_code=200, body=response.text, service=self.name)
        if self.data_root:
            return engine.get_path(payload, self.data_root) or {}
        return payload

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
            vals[field_name] = self._coerce(Partner._fields[field_name], value)
        return vals

    @staticmethod
    def _coerce(field, value):
        """Convierte el valor extraído al tipo del campo destino."""
        if field.type == 'boolean':
            return engine.truthy(value)
        if field.type in ('char', 'text', 'selection'):
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
