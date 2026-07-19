import base64
import io
import json
import logging
import zipfile

import requests

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

SIRE_AUTH_URL = 'https://api-seguridad.sunat.gob.pe/v1/clientessol/%s/oauth2/token/'
SIRE_SCOPE = 'https://api-sire.sunat.gob.pe'
SIRE_BASE_URL = 'https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv'
SIRE_TIMEOUT = 60


class L10nPeSireApi(models.AbstractModel):
    """Cliente REST de la API SIRE de SUNAT (RVIE/RCE).

    Autenticación OAuth2 con credenciales SOL + client_id/client_secret
    generados en el buzón SOL. Todas las peticiones de negocio llevan
    ``Authorization: Bearer <token>``.
    """
    _name = 'l10n_pe.sire.api'
    _description = 'Cliente API SIRE SUNAT'

    def _sire_check_ruc(self, company):
        ruc = (company.vat or '').strip()
        if len(ruc) != 11 or not ruc.isdigit():
            raise UserError(_(
                'La compañía %s no tiene un RUC válido de 11 dígitos.', company.display_name))
        return ruc

    def _sire_credentials(self, company):
        ruc = self._sire_check_ruc(company)
        missing = [
            label for field, label in [
                ('l10n_pe_sire_sol_user', _('Usuario SOL (SIRE)')),
                ('l10n_pe_sire_sol_password', _('Clave SOL (SIRE)')),
                ('l10n_pe_sire_client_id', _('Client ID API SIRE')),
                ('l10n_pe_sire_client_secret', _('Client Secret API SIRE')),
            ] if not company[field]
        ]
        if missing:
            raise UserError(_(
                'Faltan credenciales de la API SIRE en Ajustes → Perú → SIRE (RVIE / RCE): %s.',
                ', '.join(missing)))
        return {
            'ruc': ruc,
            'user': company.l10n_pe_sire_sol_user,
            'password': company.l10n_pe_sire_sol_password,
            'client_id': company.l10n_pe_sire_client_id,
            'client_secret': company.l10n_pe_sire_client_secret,
        }

    def _sire_get_token(self, company):
        cred = self._sire_credentials(company)
        payload = {
            'grant_type': 'password',
            'scope': SIRE_SCOPE,
            'client_id': cred['client_id'],
            'client_secret': cred['client_secret'],
            'username': '%s%s' % (cred['ruc'], cred['user']),
            'password': cred['password'],
        }
        try:
            response = requests.post(
                SIRE_AUTH_URL % cred['client_id'], data=payload,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=SIRE_TIMEOUT)
        except requests.RequestException as error:
            raise UserError(_('No se pudo conectar con SUNAT: %s', error)) from error
        if response.status_code != 200:
            raise UserError(_(
                'SUNAT rechazó la autenticación (HTTP %(code)s): %(text)s',
                code=response.status_code, text=self._sire_error_message(response)))
        token = response.json().get('access_token')
        if not token:
            raise UserError(_('SUNAT no devolvió un token de acceso.'))
        return token

    def _sire_error_message(self, response):
        """Extrae los mensajes de error del cuerpo JSON de SUNAT."""
        try:
            data = json.loads(response.text)
        except ValueError:
            return response.text[:500]
        if isinstance(data, dict):
            if data.get('errors'):
                return '\n'.join(e.get('msg', str(e)) for e in data['errors'])
            for key in ('msg', 'message', 'error_description', 'error'):
                if data.get(key):
                    return str(data[key])
        return response.text[:500]

    def _sire_get(self, token, endpoint, params=None):
        try:
            response = requests.get(
                SIRE_BASE_URL + endpoint, params=params or {},
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'Authorization': 'Bearer %s' % token,
                }, timeout=SIRE_TIMEOUT)
        except requests.RequestException as error:
            raise UserError(_('No se pudo conectar con SUNAT: %s', error)) from error
        if response.status_code != 200:
            raise UserError(_(
                'SUNAT devolvió un error (HTTP %(code)s): %(text)s',
                code=response.status_code, text=self._sire_error_message(response)))
        return response

    def _sire_request_proposal(self, token, endpoint, period):
        """Solicita la exportación de la propuesta. Devuelve el número de ticket."""
        response = self._sire_get(token, endpoint, params={
            'codTipoArchivo': '0',      # 0 = TXT
            'codOrigenEnvio': '2',      # 2 = servicio web
        })
        data = response.json()
        ticket = data.get('numTicket')
        if not ticket:
            raise UserError(_('SUNAT no devolvió un número de ticket: %s', data))
        return ticket

    def _sire_ticket_status(self, token, period, num_ticket):
        """Consulta el estado de un ticket. Devuelve (codEstadoEnvio, nomArchivoReporte)."""
        response = self._sire_get(
            token, '/libros/rvierce/gestionprocesosmasivos/web/masivo/consultaestadotickets',
            params={
                'perIni': period,
                'perFin': period,
                'page': '1',
                'perPage': '30',
                'numTicket': num_ticket,
            })
        registers = response.json().get('registros') or []
        if not registers:
            raise UserError(_('SUNAT no devolvió información para el ticket %s.', num_ticket))
        register = registers[0]
        code = (register.get('detalleTicket') or {}).get('codEstadoEnvio') or '00'
        filename = ''
        reports = register.get('archivoReporte') or []
        if reports:
            filename = reports[0].get('nomArchivoReporte') or ''
        return code, filename

    def _sire_download_report(self, token, period, num_ticket, report_name):
        """Descarga el ZIP del reporte y devuelve el TXT interior (base64)."""
        response = self._sire_get(
            token, '/libros/rvierce/gestionprocesosmasivos/web/masivo/archivoreporte',
            params={
                'nomArchivoReporte': report_name,
                'codTipoArchivoReporte': '00',
                'perTributario': period,
                'codProceso': '10',
                'numTicket': num_ticket,
            })
        try:
            archive = zipfile.ZipFile(io.BytesIO(response.content))
            inner = archive.namelist()[0]
            content = archive.read(inner).decode('utf-8')
        except (zipfile.BadZipFile, IndexError, UnicodeDecodeError) as error:
            raise UserError(_('El archivo devuelto por SUNAT no es un ZIP válido: %s', error)) from error
        return base64.b64encode(content.strip('\n').encode('utf-8'))
