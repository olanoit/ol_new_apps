# -*- coding: utf-8 -*-
"""Proveedores de consulta RUC/DNI (Strategy pattern).

Cada proveedor implementa una de dos interfaces:

  * ``RucProvider.fetch(ruc) -> RucResult``
  * ``DniProvider.fetch(dni) -> DniResult``

Se registran en los diccionarios ``RUC_PROVIDERS`` y
``DNI_PROVIDERS`` por su clave (``'api_peru'``, ``'api_net'``,
``'sunat_multi'``, ``'sunat_oficial'``) — la misma que se guarda en
``res.company.l10n_pe_api_ruc_connection`` /
``l10n_pe_api_dni_connection``.

El modelo ``res.partner`` sólo conoce las claves; busca el proveedor
en el diccionario y llama ``fetch()``. Para agregar un nuevo
proveedor: implementar la clase y registrarla aquí. No hace falta
tocar ``res.partner``.
"""
import logging
from dataclasses import dataclass, field

from . import http
from . import sunat_oficial

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------- #
# Resultados                                                              #
# ---------------------------------------------------------------------- #

@dataclass
class RucResult:
    """Resultado normalizado de una consulta de RUC.

    Todos los proveedores deben devolver una instancia de esta clase
    (o lanzar ``HttpError`` / ``UserError``). Atributos opcionales se
    dejan vacíos si el proveedor no los expone.
    """
    ruc: str = ''
    name: str = ''
    commercial_name: str = ''
    state: str = ''           # ACTIVO / BAJA DE OFICIO / ...
    condition: str = ''       # HABIDO / NO HABIDO / ...
    address: str = ''
    ubigeo: str = ''
    district: str = ''
    province: str = ''
    department: str = ''
    legal_representatives: list = field(default_factory=list)
    annexed_locals: list = field(default_factory=list)


@dataclass
class DniResult:
    dni: str = ''
    first_name: str = ''
    paternal_surname: str = ''
    maternal_surname: str = ''

    @property
    def full_name(self):
        parts = [self.first_name, self.paternal_surname, self.maternal_surname]
        return ' '.join(p for p in parts if p)


# ---------------------------------------------------------------------- #
# Proveedores de RUC                                                      #
# ---------------------------------------------------------------------- #

class _BaseRucProvider:
    code = ''         # 'api_peru' | 'api_net' | ...
    label = ''        # 'apiperu.dev' (para mensajes de error)

    def __init__(self, env, company=None):
        self.env = env
        self.company = company or env.company

    def fetch(self, ruc):  # pragma: no cover — interfaz
        raise NotImplementedError

    def _get_param(self, key, default=''):
        return self.env['ir.config_parameter'].sudo().get_param(key, default)


class ApiPeruRuc(_BaseRucProvider):
    code = 'api_peru'
    label = 'apiperu.dev'

    def fetch(self, ruc):
        base = self._get_param('api_peru.url', 'https://apiperu.dev/api')
        token = self._get_param('api_peru.token', '')
        if not token:
            raise ValueError('Falta api_peru.token en parámetros del sistema.')
        url = '%s/ruc/%s' % (base.rstrip('/'), ruc)
        r = http.get(
            url, service=self.label,
            headers={'Authorization': 'Bearer %s' % token,
                     'Accept': 'application/json'},
        )
        if r.status_code != 200:
            raise http.HttpError(
                'apiperu.dev rechazó la consulta (HTTP %s).' % r.status_code,
                status_code=r.status_code, body=r.text, service=self.label,
            )
        payload = r.json() or {}
        if not payload.get('success'):
            raise http.HttpError(
                payload.get('message') or 'apiperu.dev sin datos.',
                status_code=200, body=r.text, service=self.label,
            )
        data = payload.get('data') or {}
        return RucResult(
            ruc=data.get('ruc', ruc),
            name=data.get('nombre_o_razon_social', ''),
            state=data.get('estado', ''),
            condition=data.get('condicion', ''),
            address=data.get('direccion_completa') or data.get('direccion', ''),
            ubigeo=(data.get('ubigeo_sunat')
                    or (data.get('ubigeo') or ['', '', ''])[2]),
            district=data.get('distrito', ''),
            province=data.get('provincia', ''),
            department=data.get('departamento', ''),
        )


class ApiNetRuc(_BaseRucProvider):
    code = 'api_net'
    label = 'apis.net.pe'

    def fetch(self, ruc):
        base = self._get_param('api_net.url', 'https://api.apis.net.pe')
        token = self._get_param('api_net.token', '')
        if not token:
            raise ValueError('Falta api_net.token en parámetros del sistema.')
        url = '%s/v1/ruc?numero=%s' % (base.rstrip('/'), ruc)
        r = http.get(
            url, service=self.label,
            headers={'Authorization': 'Bearer %s' % token,
                     'Accept': 'application/json'},
        )
        if r.status_code != 200:
            raise http.HttpError(
                'apis.net.pe rechazó la consulta (HTTP %s).' % r.status_code,
                status_code=r.status_code, body=r.text, service=self.label,
            )
        d = r.json() or {}
        return RucResult(
            ruc=d.get('numeroDocumento', ruc),
            name=d.get('nombre', ''),
            state=d.get('estado', ''),
            condition=d.get('condicion', ''),
            address=d.get('direccion', ''),
            ubigeo=d.get('ubigeo', ''),
            district=d.get('distrito', ''),
            province=d.get('provincia', ''),
            department=d.get('departamento', ''),
        )


class SunatOficialRuc(_BaseRucProvider):
    """Scraping directo del portal e-consultaruc.sunat.gob.pe.

    Devuelve también ``legal_representatives`` y ``annexed_locals``
    si la compañía los habilitó.
    """
    code = 'sunat_oficial'
    label = 'SUNAT (oficial)'

    def fetch(self, ruc):
        return sunat_oficial.fetch_ruc(
            ruc,
            with_legal_reps=bool(self.company.legal_representatives),
            with_annex=bool(self.company.annexed_locals),
        )


class SunatMultiRuc(_BaseRucProvider):
    """Scraping del portal multi-consulta (Excel ZIP)."""
    code = 'sunat_multi'
    label = 'SUNAT (multi)'

    def fetch(self, ruc):
        return sunat_oficial.fetch_ruc_multi(ruc)


# ---------------------------------------------------------------------- #
# Proveedores de DNI                                                      #
# ---------------------------------------------------------------------- #

class _BaseDniProvider:
    code = ''
    label = ''

    def __init__(self, env, company=None):
        self.env = env
        self.company = company or env.company

    def fetch(self, dni):  # pragma: no cover — interfaz
        raise NotImplementedError

    def _get_param(self, key, default=''):
        return self.env['ir.config_parameter'].sudo().get_param(key, default)


class ApiPeruDni(_BaseDniProvider):
    code = 'api_peru'
    label = 'apiperu.dev'

    def fetch(self, dni):
        base = self._get_param('api_peru.url', 'https://apiperu.dev/api')
        token = self._get_param('api_peru.token', '')
        if not token:
            raise ValueError('Falta api_peru.token en parámetros del sistema.')
        url = '%s/dni/%s' % (base.rstrip('/'), dni)
        r = http.get(
            url, service=self.label,
            headers={'Authorization': 'Bearer %s' % token,
                     'Accept': 'application/json'},
        )
        if r.status_code != 200:
            raise http.HttpError(
                'apiperu.dev rechazó la consulta (HTTP %s).' % r.status_code,
                status_code=r.status_code, body=r.text, service=self.label,
            )
        payload = r.json() or {}
        if not payload.get('success'):
            raise http.HttpError(
                payload.get('message') or 'apiperu.dev sin datos.',
                status_code=200, body=r.text, service=self.label,
            )
        d = payload.get('data') or {}
        return DniResult(
            dni=d.get('numero', dni),
            first_name=d.get('nombres', ''),
            paternal_surname=d.get('apellido_paterno', ''),
            maternal_surname=d.get('apellido_materno', ''),
        )


class ApiNetDni(_BaseDniProvider):
    code = 'api_net'
    label = 'apis.net.pe'

    def fetch(self, dni):
        base = self._get_param('api_net.url', 'https://api.apis.net.pe')
        token = self._get_param('api_net.token', '')
        if not token:
            raise ValueError('Falta api_net.token en parámetros del sistema.')
        # v2/reniec/dni si la compañía lo selecciona, si no v1.
        version = (self.company.vision_api or 'v2')
        path = '/v2/reniec/dni' if version == 'v2' else '/v1/dni'
        url = '%s%s?numero=%s' % (base.rstrip('/'), path, dni)
        r = http.get(
            url, service=self.label,
            headers={'Authorization': 'Bearer %s' % token,
                     'Accept': 'application/json'},
        )
        if r.status_code != 200:
            raise http.HttpError(
                'apis.net.pe rechazó la consulta (HTTP %s).' % r.status_code,
                status_code=r.status_code, body=r.text, service=self.label,
            )
        d = r.json() or {}
        return DniResult(
            dni=d.get('numeroDocumento', dni),
            first_name=d.get('nombres', ''),
            paternal_surname=d.get('apellidoPaterno', ''),
            maternal_surname=d.get('apellidoMaterno', ''),
        )


# ---------------------------------------------------------------------- #
# Registro                                                                #
# ---------------------------------------------------------------------- #

RUC_PROVIDERS = {
    ApiPeruRuc.code: ApiPeruRuc,
    ApiNetRuc.code: ApiNetRuc,
    SunatOficialRuc.code: SunatOficialRuc,
    SunatMultiRuc.code: SunatMultiRuc,
}

DNI_PROVIDERS = {
    ApiPeruDni.code: ApiPeruDni,
    ApiNetDni.code: ApiNetDni,
}


def ruc_selection():
    """Selection para ``res.company.l10n_pe_api_ruc_connection``."""
    return [(p.code, p.label) for p in RUC_PROVIDERS.values()]


def dni_selection():
    """Selection para ``res.company.l10n_pe_api_dni_connection``."""
    return [(p.code, p.label) for p in DNI_PROVIDERS.values()]


def get_ruc_provider(env, code):
    """Devuelve una instancia del proveedor de RUC para la clave dada."""
    cls = RUC_PROVIDERS.get(code)
    if not cls:
        raise ValueError('Proveedor RUC desconocido: %s' % code)
    return cls(env)


def get_dni_provider(env, code):
    cls = DNI_PROVIDERS.get(code)
    if not cls:
        raise ValueError('Proveedor DNI desconocido: %s' % code)
    return cls(env)
