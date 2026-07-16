# -*- coding: utf-8 -*-
"""Configuración de consulta RUC/DNI por compañía.

La configuración completa de las APIs vive en el One2many
``l10n_pe_api_connection_ids`` (modelo ``l10n_pe.api.connection``): cada
compañía define sus conexiones, su prioridad y el mapeo atributo→campo,
sin depender del código.
"""
from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Activación de validaciones automáticas.
    l10n_pe_ruc_validation = fields.Boolean(
        string='Validación de RUC',
        default=lambda self: (self.country_id.code or '') == 'PE',
    )
    l10n_pe_dni_validation = fields.Boolean(
        string='Validación de DNI',
        default=lambda self: (self.country_id.code or '') == 'PE',
    )

    # Configuración completa de APIs (One2many).
    l10n_pe_api_connection_ids = fields.One2many(
        'l10n_pe.api.connection', 'company_id',
        string='Conexiones de consulta RUC/DNI')
    l10n_pe_api_use_fallback = fields.Boolean(
        string='Usar fallback en cascada',
        default=False,
        help="Desactivado (por defecto): usa solo la conexión activa de mayor "
             "prioridad; si falla, no consulta más APIs. Activado: si la "
             "primera falla, prueba la siguiente por prioridad, y así "
             "sucesivamente.")

    @api.onchange('country_id')
    def _onchange_country_id_pe_validation(self):
        is_pe = bool(self.country_id and self.country_id.code == 'PE')
        self.l10n_pe_ruc_validation = is_pe
        self.l10n_pe_dni_validation = is_pe

    def _get_pe_api_connections(self, doc_type):
        """Conexiones activas para el tipo de documento, por prioridad.

        Con fallback desactivado devuelve **solo la primera** (la principal);
        con fallback activado devuelve todas para consulta en cascada.
        """
        self.ensure_one()
        connections = self.l10n_pe_api_connection_ids.filtered(
            lambda c: c.enabled and c.document_type in (doc_type, 'both')
            and c._is_usable()
        ).sorted(lambda c: (c.sequence, c.id))
        if not self.l10n_pe_api_use_fallback:
            return connections[:1]
        return connections

    # ------------------------------------------------------------------ #
    # Semilla de conexiones por defecto (replican los proveedores previos)
    # ------------------------------------------------------------------ #

    def _l10n_pe_create_connection(self, spec):
        """Crea una conexión (con sus mapeos) desde un spec declarativo."""
        self.ensure_one()
        Field = self.env['ir.model.fields']
        spec = dict(spec)
        commands = []
        for m in spec.pop('mapping_ids', []):
            m = dict(m)
            m['field_id'] = Field._get('res.partner', m.pop('field')).id
            commands.append((0, 0, m))
        return self.env['l10n_pe.api.connection'].create(dict(
            spec, company_id=self.id, mapping_ids=commands))

    def _l10n_pe_seed_default_connections(self):
        """Crea las conexiones por defecto en compañías PE que no tengan."""
        for company in self:
            if company.l10n_pe_api_connection_ids or (
                    company.country_id and company.country_id.code != 'PE'):
                continue
            for spec in DEFAULT_CONNECTIONS:
                company._l10n_pe_create_connection(spec)

    def _l10n_pe_ensure_connection(self, name):
        """Agrega una conexión por defecto (por nombre) si la compañía no la
        tiene. Útil en migraciones al incorporar una API nueva."""
        spec = next((s for s in DEFAULT_CONNECTIONS if s['name'] == name), None)
        if not spec:
            return
        for company in self:
            if company.country_id and company.country_id.code != 'PE':
                continue
            existing = company.l10n_pe_api_connection_ids.filtered(
                lambda c: c.name == name)
            if not existing:
                company._l10n_pe_create_connection(spec)


# Definición declarativa de las conexiones por defecto. Cada mapping usa
# 'field' = nombre técnico del campo de res.partner (se resuelve a field_id).
DEFAULT_CONNECTIONS = [
    {
        'name': 'apiperu.dev',
        'engine': 'rest_json',
        'document_type': 'both',
        'sequence': 10,
        'enabled': True,
        'base_url': 'https://apiperu.dev/api',
        'endpoint_ruc': '/ruc/{doc}',
        'endpoint_dni': '/dni/{doc}',
        'auth_type': 'bearer',
        'success_path': 'success',
        'data_root': 'data',
        'ubigeo_path': 'ubigeo_sunat',
        'district_path': 'distrito',
        'province_path': 'provincia',
        'department_path': 'departamento',
        'mapping_ids': [
            {'for_document': 'ruc', 'sequence': 10, 'source_path': 'nombre_o_razon_social', 'field': 'name'},
            {'for_document': 'ruc', 'sequence': 20, 'source_path': 'estado', 'field': 'state'},
            {'for_document': 'ruc', 'sequence': 30, 'source_path': 'condicion', 'field': 'sunat_condition'},
            {'for_document': 'ruc', 'sequence': 40, 'source_path': 'direccion', 'field': 'street'},
            {'for_document': 'ruc', 'sequence': 50, 'source_path': 'direccion_completa', 'field': 'street'},
            {'for_document': 'dni', 'sequence': 60,
             'source_path': '{nombres} {apellido_paterno} {apellido_materno}',
             'field': 'name', 'transform': 'title'},
        ],
    },
    {
        'name': 'json.pe',
        'engine': 'rest_json',
        'document_type': 'both',
        'sequence': 15,
        'enabled': False,
        'base_url': 'https://api.json.pe/api',
        'endpoint_ruc': '/ruc',
        'endpoint_dni': '/dni',
        'http_method': 'post',
        'body_ruc': '{"ruc": "{doc}"}',
        'body_dni': '{"dni": "{doc}"}',
        'auth_type': 'bearer',
        'success_path': 'success',
        'data_root': 'data',
        'ubigeo_path': 'ubigeo_sunat',
        'district_path': 'distrito',
        'province_path': 'provincia',
        'department_path': 'departamento',
        'mapping_ids': [
            {'for_document': 'ruc', 'sequence': 10, 'source_path': 'nombre_o_razon_social', 'field': 'name'},
            {'for_document': 'ruc', 'sequence': 20, 'source_path': 'estado', 'field': 'state'},
            {'for_document': 'ruc', 'sequence': 30, 'source_path': 'condicion', 'field': 'sunat_condition'},
            {'for_document': 'ruc', 'sequence': 40, 'source_path': 'direccion', 'field': 'street'},
            {'for_document': 'ruc', 'sequence': 50, 'source_path': 'direccion_completa', 'field': 'street'},
            {'for_document': 'dni', 'sequence': 60, 'source_path': 'nombre_completo',
             'field': 'name', 'transform': 'title'},
        ],
    },
    {
        'name': 'apis.net.pe',
        'engine': 'rest_json',
        'document_type': 'both',
        'sequence': 20,
        'enabled': True,
        'base_url': 'https://api.apis.net.pe',
        'endpoint_ruc': '/v1/ruc?numero={doc}',
        'endpoint_dni': '/v2/reniec/dni?numero={doc}',
        'auth_type': 'bearer',
        'data_root': '',
        'ubigeo_path': 'ubigeo',
        'district_path': 'distrito',
        'province_path': 'provincia',
        'department_path': 'departamento',
        'mapping_ids': [
            {'for_document': 'ruc', 'sequence': 10, 'source_path': 'nombre', 'field': 'name'},
            {'for_document': 'ruc', 'sequence': 20, 'source_path': 'estado', 'field': 'state'},
            {'for_document': 'ruc', 'sequence': 30, 'source_path': 'condicion', 'field': 'sunat_condition'},
            {'for_document': 'ruc', 'sequence': 40, 'source_path': 'direccion', 'field': 'street'},
            {'for_document': 'dni', 'sequence': 50,
             'source_path': '{nombres} {apellidoPaterno} {apellidoMaterno}',
             'field': 'name', 'transform': 'title'},
        ],
    },
    {
        'name': 'SUNAT (oficial)',
        'engine': 'sunat_oficial',
        'document_type': 'ruc',
        'sequence': 30,
        'enabled': True,
        'ubigeo_path': 'ubigeo',
        'district_path': 'district',
        'province_path': 'province',
        'department_path': 'department',
        'mapping_ids': [
            {'for_document': 'ruc', 'sequence': 10, 'source_path': 'name', 'field': 'name'},
            {'for_document': 'ruc', 'sequence': 20, 'source_path': 'commercial_name', 'field': 'commercial_name'},
            {'for_document': 'ruc', 'sequence': 30, 'source_path': 'state', 'field': 'state'},
            {'for_document': 'ruc', 'sequence': 40, 'source_path': 'condition', 'field': 'sunat_condition'},
            {'for_document': 'ruc', 'sequence': 50, 'source_path': 'address', 'field': 'street'},
        ],
    },
]
