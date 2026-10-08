import base64
import io
import json
import re
import zipfile
from datetime import timedelta
from urllib.parse import urljoin, urlparse

import requests

from odoo import _, fields, models
from odoo.exceptions import UserError

from .sire_validation import ruc_is_valid

SIRE_AUTH_URL = 'https://api-seguridad.sunat.gob.pe/v1/clientessol/%s/oauth2/token/'
SIRE_SCOPE = 'https://api-sire.sunat.gob.pe'
SIRE_BASE_URL = 'https://api-sire.sunat.gob.pe/v1/contribuyente/migeigv'
#: (conexión, lectura): una SUNAT caída falla en 10 s y no ocupa el worker.
SIRE_TIMEOUT = (10, 60)
#: Dominio de SUNAT: el token Bearer nunca se envía a otro host (p. ej. a
#: un ``Location`` de TUS manipulado).
SIRE_ALLOWED_HOST_SUFFIX = '.sunat.gob.pe'
#: Subida de archivos: SUNAT expone un servidor TUS (el manual documenta el
#: cliente `tus-java-client` 0.5.0, que habla TUS 1.0.0).
SIRE_UPLOAD_ENDPOINT = '/libros/rvierce/receptorpropuesta/web/propuesta/upload'
#: Cargas TUS que van al preliminar (no domiciliados, nuevos CP del
#: preliminar) y a los ajustes posteriores (manuales v22, 5.5 y 5.18).
SIRE_UPLOAD_PRELIMINARY_ENDPOINT = '/libros/rvierce/receptorpreliminar/web/preliminar/upload'
SIRE_UPLOAD_ADJUSTMENT_ENDPOINT = (
    '/libros/rvierce/receptorajustesposteriores/web/ajustesposteriores/upload')
#: Formato del ticket: AAAA + tipo de correlativo + correlativo (14 dígitos).
SIRE_TICKET_RE = re.compile(r'^\d{14}$')
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
        if not ruc_is_valid(ruc):
            raise UserError(_(
                'El RUC %(ruc)s de la compañía %(company)s no es válido: el '
                'dígito verificador no corresponde.', ruc=ruc, company=company.display_name))
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
        # sudo: las credenciales y el token son de base.group_system; el
        # contable que lanza el flujo los usa sin poder leerlos. Son del RUC:
        # una sucursal usa las de su compañía raíz, como el RUC del periodo.
        company_sudo = company.sudo().root_id
        now = fields.Datetime.now()
        if company_sudo.l10n_pe_sire_token and company_sudo.l10n_pe_sire_token_expiry \
                and company_sudo.l10n_pe_sire_token_expiry > now:
            return company_sudo.l10n_pe_sire_token
        cred = self._sire_credentials(company_sudo)
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
        data = self._sire_json(response)
        token = data.get('access_token')
        if not token:
            raise UserError(_('SUNAT no devolvió un token de acceso.'))
        # Se descuenta un minuto del margen: la petición siguiente no debe
        # salir con un token que caduca mientras viaja.
        seconds = max(int(data.get('expires_in') or 3600) - 60, 60)
        company_sudo.write({
            'l10n_pe_sire_token': token,
            'l10n_pe_sire_token_expiry': now + timedelta(seconds=seconds),
        })
        return token

    def _sire_json(self, response):
        """Cuerpo JSON (dict) de una respuesta correcta de SUNAT.

        Un 200 con HTML (proxy, mantenimiento) no debe acabar en traceback.
        """
        try:
            data = response.json()
        except ValueError as error:
            raise UserError(_(
                'SUNAT devolvió una respuesta que no es JSON: %s',
                (response.text or '')[:300])) from error
        return data if isinstance(data, dict) else {}

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
                      data=None, url=None, json_body=None, files=None):
        """Petición a la API con el manejo de errores unificado."""
        if json_body is not None:
            data = json.dumps(json_body)
        request_headers = self._sire_headers(token, headers)
        if files:
            # requests arma el multipart y su frontera: no se fija a mano.
            request_headers.pop('Content-Type', None)
        try:
            response = requests.request(
                method, url or (SIRE_BASE_URL + endpoint), params=params or {},
                headers=request_headers, data=data, files=files,
                timeout=SIRE_TIMEOUT)
        except requests.RequestException as error:
            raise UserError(_('No se pudo conectar con SUNAT: %s', error)) from error
        if response.status_code == 401:
            # Token revocado antes de caducar: se descarta para que la
            # próxima acción pida otro en vez de fallar hasta la caducidad.
            # sudo: el token es de base.group_system; solo se borra el usado.
            companies_sudo = self.env['res.company'].sudo().search(
                [('l10n_pe_sire_token', '=', token)])
            companies_sudo.write({'l10n_pe_sire_token': False,
                                  'l10n_pe_sire_token_expiry': False})
            raise UserError(_(
                'SUNAT rechazó el token de acceso (HTTP 401). Se pidió uno '
                'nuevo: vuelva a intentarlo.'))
        if response.status_code not in (200, 201, 204):
            raise UserError(_(
                'SUNAT devolvió un error (HTTP %(code)s): %(text)s',
                code=response.status_code, text=self._sire_error_message(response)))
        return response

    def _sire_get(self, token, endpoint, params=None):
        return self._sire_request('GET', token, endpoint, params=params)

    def _sire_post(self, token, endpoint, params=None):
        return self._sire_request('POST', token, endpoint, params=params)

    def _sire_send_json(self, method, token, endpoint, payload=None, params=None):
        """POST/PUT/DELETE con cuerpo JSON; SUNAT responde «OK» o un ticket."""
        return self._sire_request(method, token, endpoint, params=params,
                                  json_body=payload)

    @staticmethod
    def _sire_ticket_from(response):
        """Número de ticket de una respuesta, mire donde mire SUNAT.

        Los servicios de proceso lo devuelven en el JSON; las cargas TUS, en
        texto plano en el cuerpo de la última petición (manuales v22, p. ej.
        «20230100000124»), y alguna vez ha llegado en cabecera.
        """
        try:
            data = response.json()
        except ValueError:
            data = {}
        if isinstance(data, dict) and data.get('numTicket'):
            return str(data['numTicket'])
        if isinstance(data, (int, str)) and SIRE_TICKET_RE.match(str(data)):
            return str(data)
        text = response.text if isinstance(response.text, str) else ''
        text = text.strip().strip('"')
        if SIRE_TICKET_RE.match(text):
            return text
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

    @staticmethod
    def _sire_ticket_code(register):
        """Estado del ticket normalizado («6» → «06»).

        El Anexo III va de 01 a 06: sin código, o con uno desconocido, el
        ticket se sigue consultando (05, en proceso) en vez de darlo por
        fallido y dejar el periodo sin envío posible.
        """
        code = (register.get('detalleTicket') or {}).get('codEstadoEnvio') \
            or register.get('codEstadoProceso')
        code = str(code).strip().zfill(2) if code not in (None, '') else ''
        return code if code in ('01', '02', '03', '04', '05', '06') else '05'

    def _sire_ticket_status(self, token, period, num_ticket):
        """Consulta el estado de un ticket. Devuelve (codEstadoEnvio, nomArchivoReporte)."""
        register = self._sire_ticket_register(token, period, num_ticket)
        code = self._sire_ticket_code(register)
        filename = ''
        reports = register.get('archivoReporte') or []
        if reports:
            filename = reports[0].get('nomArchivoReporte') or ''
        return code, filename

    def _sire_ticket_register(self, token, period, num_ticket):
        """Registro completo del ticket (manual 5.16 RVIE / 5.31 RCE)."""
        response = self._sire_get(
            token, '/libros/rvierce/gestionprocesosmasivos/web/masivo/consultaestadotickets',
            params={
                'perIni': period,
                'perFin': period,
                'page': '1',
                'perPage': '30',
                'numTicket': num_ticket,
            })
        registers = self._sire_json(response).get('registros') or []
        if not registers:
            raise UserError(_('SUNAT no devolvió información para el ticket %s.', num_ticket))
        register = registers[0]
        # En el RCE la tabla declara ``detalleTicket`` como lista y el
        # ejemplo lo trae como objeto: se aceptan las dos formas.
        detail = register.get('detalleTicket')
        if isinstance(detail, list):
            register['detalleTicket'] = detail[0] if detail else {}
        return register

    @staticmethod
    def _sire_report_type(report):
        """Tipo del archivo de reporte; el manual lo escribe ``codTipoAchivoReporte`` [sic]."""
        value = report.get('codTipoAchivoReporte', report.get('codTipoArchivoReporte'))
        return 'null' if value in (None, '') else str(value)

    def _sire_download_file(self, token, report, book_code):
        """Bytes de un archivo de reporte de un ticket (manual 5.17 / 5.32)."""
        response = self._sire_get(
            token, '/libros/rvierce/gestionprocesosmasivos/web/masivo/archivoreporte',
            params={
                'nomArchivoReporte': report.get('nomArchivoReporte'),
                'codTipoArchivoReporte': self._sire_report_type(report),
                'codLibro': book_code,
            })
        return response.content

    @staticmethod
    def _sire_decode(content):
        """Texto de un archivo de SUNAT, probando las codificaciones usadas."""
        for encoding in SIRE_ENCODINGS:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return content.decode('utf-8', errors='replace')

    def _sire_download_report(self, token, period, num_ticket, book_code):
        """Descarga la propuesta de un ticket terminado (manual 5.17).

        Cada archivo de ``archivoReporte`` se pide con su nombre, su tipo y
        el ``codLibro`` del registro, como exige el servicio. SUNAT entrega
        la propuesta «zipeada y particionada»: se unen todos los TXT de
        todos los ZIP, sin repetir la cabecera. Devuelve el TXT en base64.
        """
        register = self._sire_ticket_register(token, period, num_ticket)
        reports = register.get('archivoReporte') or []
        if not reports:
            raise UserError(_('El ticket %s no tiene archivos que descargar.', num_ticket))
        lines, header = [], None
        for report in reports:
            content = self._sire_download_file(token, report, book_code)
            try:
                archive = zipfile.ZipFile(io.BytesIO(content))
            except zipfile.BadZipFile as error:
                raise UserError(_(
                    'El archivo devuelto por SUNAT no es un ZIP válido: %s', error)) from error
            for inner in sorted(archive.namelist()):
                text_lines = self._sire_decode(archive.read(inner)).splitlines()
                if not text_lines:
                    continue
                if header is None:
                    header = text_lines[0]
                    lines.append(header)
                    text_lines = text_lines[1:]
                elif text_lines[0] == header:
                    text_lines = text_lines[1:]
                lines.extend(line for line in text_lines if line.strip())
        return base64.b64encode('\n'.join(lines).encode('utf-8'))

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

    def _sire_upload(self, token, filename, content, metadata,
                     endpoint=SIRE_UPLOAD_ENDPOINT, ticket_required=True):
        """Sube un archivo por TUS y devuelve el número de ticket.

        Dos peticiones: una crea la subida y devuelve su ubicación en
        ``Location``; la otra envía los bytes. Se implementa a mano
        —el protocolo es de dos pasos— en vez de añadir una dependencia
        de cliente TUS para esto.
        """
        create = self._sire_request(
            'POST', token, endpoint,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Tus-Resumable': TUS_VERSION,
                'Upload-Length': str(len(content)),
                'Upload-Metadata': self._sire_tus_metadata(metadata),
            })
        location = create.headers.get('Location')
        if location:
            # ``Location`` puede venir relativa; y el token solo viaja a SUNAT.
            location = urljoin(SIRE_BASE_URL + endpoint, location)
            parsed = urlparse(location)
            if parsed.scheme != 'https' or not (parsed.hostname or '').endswith(
                    SIRE_ALLOWED_HOST_SUFFIX):
                raise UserError(_(
                    'SUNAT indicó una ubicación de carga fuera de su dominio (%s); '
                    'no se envía el archivo.', location))
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
        if not ticket and not ticket_required:
            # La carga de ajustes posteriores del RCE responde «OK» (5.18).
            return ''
        if not ticket:
            raise UserError(_(
                'SUNAT aceptó el archivo pero no devolvió su ticket. '
                'Compruebe el estado en SUNAT Operaciones en Línea.'))
        return ticket
