import base64
import io
import json
import logging
import zipfile
from datetime import timedelta

import requests

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

SIRE_AUTH_URL = 'https://api-seguridad.sunat.gob.pe/v1/clientessol/%s/oauth2/token/'
SIRE_SCOPE = 'https://api-sire.sunat.gob.pe'
SIRE_BASE_URL = 'https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv'
SIRE_TIMEOUT = 60
#: Subida de archivos: SUNAT expone un servidor TUS (el manual documenta el
#: cliente `tus-java-client` 0.5.0, que habla TUS 1.0.0).
SIRE_UPLOAD_ENDPOINT = '/libros/rvierce/receptorpropuesta/web/propuesta/upload'
TUS_VERSION = '1.0.0'
#: SUNAT entrega los TXT en UTF-8, pero las razones sociales con tilde han
#: llegado en latin-1 más de una vez. Se prueban en orden en vez de reventar
#: con un UnicodeDecodeError que no dice nada al usuario.
SIRE_ENCODINGS = ('utf-8', 'latin-1')


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
        """Token de acceso, reutilizando el vigente si lo hay.

        Un periodo completo encadena media docena de llamadas; sin caché
        cada una abriría su propia sesión OAuth contra SUNAT. El token se
        guarda en la compañía con su caducidad y se renueva solo.
        """
        company = company.sudo()
        now = fields.Datetime.now()
        if company.l10n_pe_sire_token and company.l10n_pe_sire_token_expiry \
                and company.l10n_pe_sire_token_expiry > now:
            return company.l10n_pe_sire_token
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
        data = response.json()
        token = data.get('access_token')
        if not token:
            raise UserError(_('SUNAT no devolvió un token de acceso.'))
        # Se descuenta un minuto del margen: la petición siguiente no debe
        # salir con un token que caduca mientras viaja.
        seconds = max(int(data.get('expires_in') or 3600) - 60, 60)
        company.write({
            'l10n_pe_sire_token': token,
            'l10n_pe_sire_token_expiry': now + timedelta(seconds=seconds),
        })
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

    def _sire_headers(self, token, extra=None):
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': 'Bearer %s' % token,
        }
        headers.update(extra or {})
        return headers

    def _sire_request(self, method, token, endpoint, params=None, headers=None,
                      data=None, url=None):
        """Petición a la API con el manejo de errores unificado."""
        try:
            response = requests.request(
                method, url or (SIRE_BASE_URL + endpoint), params=params or {},
                headers=self._sire_headers(token, headers), data=data,
                timeout=SIRE_TIMEOUT)
        except requests.RequestException as error:
            raise UserError(_('No se pudo conectar con SUNAT: %s', error)) from error
        if response.status_code not in (200, 201, 204):
            raise UserError(_(
                'SUNAT devolvió un error (HTTP %(code)s): %(text)s',
                code=response.status_code, text=self._sire_error_message(response)))
        return response

    def _sire_get(self, token, endpoint, params=None):
        return self._sire_request('GET', token, endpoint, params=params)

    def _sire_post(self, token, endpoint, params=None):
        return self._sire_request('POST', token, endpoint, params=params)

    @staticmethod
    def _sire_ticket_from(response):
        """Número de ticket de una respuesta, mire donde mire SUNAT.

        Los servicios de proceso lo devuelven en el JSON; los de carga TUS
        no lo documentan y lo han puesto en cabecera.
        """
        try:
            data = response.json()
        except ValueError:
            data = {}
        if isinstance(data, dict) and data.get('numTicket'):
            return str(data['numTicket'])
        for header in ('numTicket', 'num-ticket', 'Num-Ticket'):
            if response.headers.get(header):
                return response.headers[header]
        return ''

    def _sire_request_proposal(self, token, endpoint, period):
        """Solicita la exportación de la propuesta. Devuelve el número de ticket."""
        response = self._sire_get(token, endpoint, params={
            'codTipoArchivo': '0',      # 0 = TXT
            'codOrigenEnvio': '2',      # 2 = servicio web
        })
        ticket = self._sire_ticket_from(response)
        if not ticket:
            raise UserError(_('SUNAT no devolvió un número de ticket: %s', response.text[:300]))
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

    @staticmethod
    def _sire_decode(content):
        """Texto de un archivo de SUNAT, probando las codificaciones usadas."""
        for encoding in SIRE_ENCODINGS:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return content.decode('utf-8', errors='replace')

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
            content = self._sire_decode(archive.read(inner))
        except (zipfile.BadZipFile, IndexError) as error:
            raise UserError(_('El archivo devuelto por SUNAT no es un ZIP válido: %s', error)) from error
        return base64.b64encode(content.strip('\n').encode('utf-8'))

    # ------------------------------------------------------------------
    # Procesos sobre la propuesta
    # ------------------------------------------------------------------

    def _sire_accept_proposal(self, token, endpoint):
        """Acepta la propuesta de SUNAT. Devuelve el número de ticket."""
        response = self._sire_post(token, endpoint)
        ticket = self._sire_ticket_from(response)
        if not ticket:
            raise UserError(_(
                'SUNAT no devolvió el ticket de la aceptación: %s', response.text[:300]))
        return ticket

    def _sire_register_preliminary(self, token, endpoint):
        """Registra el preliminar del periodo.

        A diferencia del resto, no devuelve ticket: responde 200 y el
        registro queda listo para generarse en el portal.
        """
        self._sire_post(token, endpoint)
        return True

    # ------------------------------------------------------------------
    # Carga de archivos (protocolo TUS)
    # ------------------------------------------------------------------

    @staticmethod
    def _sire_tus_metadata(values):
        """Cabecera ``Upload-Metadata``: pares ``clave <valor en base64>``."""
        return ','.join(
            '%s %s' % (key, base64.b64encode(str(value).encode('utf-8')).decode())
            for key, value in values.items())

    def _sire_upload(self, token, filename, content, metadata):
        """Sube un archivo por TUS y devuelve el número de ticket.

        Dos peticiones: una crea la subida y devuelve su ubicación en
        ``Location``; la otra envía los bytes. Se implementa a mano
        —el protocolo es de dos pasos— en vez de añadir una dependencia
        de cliente TUS para esto.
        """
        create = self._sire_request(
            'POST', token, SIRE_UPLOAD_ENDPOINT,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Tus-Resumable': TUS_VERSION,
                'Upload-Length': str(len(content)),
                'Upload-Metadata': self._sire_tus_metadata(metadata),
            })
        location = create.headers.get('Location')
        if not location:
            # Algunas respuestas resuelven la carga en un solo paso.
            ticket = self._sire_ticket_from(create)
            if ticket:
                return ticket
            raise UserError(_(
                'SUNAT no indicó dónde subir el archivo %s.', filename))
        upload = self._sire_request(
            'PATCH', token, None, url=location,
            headers={
                'Content-Type': 'application/offset+octet-stream',
                'Tus-Resumable': TUS_VERSION,
                'Upload-Offset': '0',
            }, data=content)
        ticket = self._sire_ticket_from(upload)
        if not ticket:
            raise UserError(_(
                'SUNAT aceptó el archivo pero no devolvió su ticket. '
                'Compruebe el estado en SUNAT Operaciones en Línea.'))
        return ticket
