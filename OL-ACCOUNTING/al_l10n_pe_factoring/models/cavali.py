# -*- coding: utf-8 -*-
"""Conexión con CAVALI (registro de facturas negociables).

CAVALI ofrece tres canales (Reglamento Interno, cap. XVII, RIC v09): el
aplicativo web **Factrack** (formulario individual o masivo) y los **Servicios
Web** para los participantes y los emisores con cuenta de emisor que los
soliciten. La especificación de los servicios web no es pública: se entrega con
las credenciales. Por eso:

* **Factrack** (siempre disponible): paquete con el XML de cada comprobante y la
  información adicional (art. 3-A) para el formulario masivo, e importación de
  los estados que devuelve Factrack.
* **Servicios web**: cliente HTTP con JSON cuyas rutas, autenticación y nombres
  de campo se ajustan en la configuración al manual de CAVALI. Cada envío queda
  en el registro de CAVALI con su solicitud y su respuesta.

Operaciones (RIC v09, DV 01 a 07): registro de la información y anotación en
cuenta, transferencia al factor, redención y pago, reprogramación (nueva fecha
mayor y monto no mayor), conformidad o disconformidad del adquirente y
consulta del estado.
"""
import io
import json
import logging
import zipfile

import requests

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CAVALI_OPERATIONS = [
    ('register', 'Registro y anotación en cuenta'),
    ('transfer', 'Transferencia'),
    ('payment', 'Redención y pago'),
    ('reschedule', 'Reprogramación'),
    ('conformity', 'Conformidad del adquirente'),
    ('status', 'Consulta del estado'),
]
#: Rutas por defecto de cada operación (se cambian en Parámetros del sistema
#: ``l10n_pe_cavali.path.<operación>`` según el manual de CAVALI).
DEFAULT_PATHS = {
    'register': '/facturas/registro',
    'transfer': '/facturas/transferencia',
    'payment': '/facturas/pago',
    'reschedule': '/facturas/reprogramacion',
    'conformity': '/facturas/conformidad',
    'status': '/facturas/consulta',
}
#: Códigos de respuesta que se tratan como éxito.
OK_CODES = ('0', '00', '000', '0000', 'OK', 'ok')
#: Estados de CAVALI (texto de la respuesta o de Factrack) → evento de la factura.
STATUS_EVENTS = {
    'anotada': 'registered', 'anotado': 'registered', 'registrada': 'registered',
    'transferida': 'transferred', 'transferido': 'transferred',
    'redimida': 'paid', 'pagada': 'paid', 'pagado': 'paid',
    'protestada': 'protested', 'retirada': 'cancelled', 'anulada': 'cancelled',
    'conforme': 'accepted', 'conformidad expresa': 'accepted',
    'conformidad presunta': 'presumed', 'presunta': 'presumed',
    'disconforme': 'rejected', 'disconformidad': 'rejected',
}


def _status_event(text):
    return STATUS_EVENTS.get((text or '').strip().lower())


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_cavali_mode = fields.Selection(
        [('factrack', 'Factrack (archivos)'), ('webservice', 'Servicios web')],
        string='Conexión con CAVALI', default='factrack',
        help='Factrack: paquete para el formulario masivo e importación de estados. Servicios '
             'web: envío directo (requiere el manual y las credenciales de CAVALI).')
    l10n_pe_cavali_environment = fields.Selection(
        [('test', 'Pruebas'), ('production', 'Producción')], string='Ambiente de CAVALI', default='test')
    l10n_pe_cavali_url_test = fields.Char(string='URL de pruebas de CAVALI')
    l10n_pe_cavali_url_production = fields.Char(string='URL de producción de CAVALI')
    l10n_pe_cavali_user = fields.Char(string='Usuario de CAVALI', groups='base.group_system')
    l10n_pe_cavali_password = fields.Char(string='Clave de CAVALI', groups='base.group_system')
    l10n_pe_cavali_account_type = fields.Selection(
        [('issuer', 'Emisor con cuenta de emisor'), ('participant', 'Mediante un participante')],
        string='Cuenta en CAVALI', default='participant',
        help='Emisor con cuenta: la empresa anota sus facturas en su propia cuenta. Mediante un '
             'participante: el banco o la empresa de factoring las anota en su cuenta matriz.')
    l10n_pe_cavali_participant_id = fields.Many2one(
        'res.partner', string='Participante', help='Entidad en cuya cuenta matriz se anotan las facturas.')
    l10n_pe_cavali_participant_code = fields.Char(string='Código del participante')
    l10n_pe_cavali_rut = fields.Char(string='Código RUT', help='Código RUT de la empresa en CAVALI.')

    def _l10n_pe_cavali_enabled(self):
        self.ensure_one()
        return self.l10n_pe_cavali_mode == 'webservice' and bool(self._l10n_pe_cavali_url())

    def _l10n_pe_cavali_url(self):
        self.ensure_one()
        url = (self.l10n_pe_cavali_url_production if self.l10n_pe_cavali_environment == 'production'
               else self.l10n_pe_cavali_url_test)
        return (url or '').rstrip('/')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_cavali_mode = fields.Selection(related='company_id.l10n_pe_cavali_mode', readonly=False)
    l10n_pe_cavali_environment = fields.Selection(related='company_id.l10n_pe_cavali_environment',
                                                  readonly=False)
    l10n_pe_cavali_url_test = fields.Char(related='company_id.l10n_pe_cavali_url_test', readonly=False)
    l10n_pe_cavali_url_production = fields.Char(related='company_id.l10n_pe_cavali_url_production',
                                                readonly=False)
    l10n_pe_cavali_user = fields.Char(related='company_id.l10n_pe_cavali_user', readonly=False)
    l10n_pe_cavali_password = fields.Char(related='company_id.l10n_pe_cavali_password', readonly=False)
    l10n_pe_cavali_account_type = fields.Selection(related='company_id.l10n_pe_cavali_account_type',
                                                   readonly=False)
    l10n_pe_cavali_participant_id = fields.Many2one(related='company_id.l10n_pe_cavali_participant_id',
                                                    readonly=False)
    l10n_pe_cavali_participant_code = fields.Char(related='company_id.l10n_pe_cavali_participant_code',
                                                  readonly=False)
    l10n_pe_cavali_rut = fields.Char(related='company_id.l10n_pe_cavali_rut', readonly=False)

    def action_l10n_pe_cavali_test(self):
        """Prueba la conexión con una consulta sin factura."""
        self.ensure_one()
        log = self.env['l10n_pe.cavali.log']._call(self.company_id, 'status', {'prueba': True})
        if log.state != 'ok':
            raise UserError(self.env._('CAVALI respondió con error: %s', log.message or log.http_status))
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'type': 'success', 'message': self.env._('Conexión con CAVALI correcta.')}}


class L10nPeCavaliLog(models.Model):
    _name = 'l10n_pe.cavali.log'
    _description = 'Registro de envíos a CAVALI'
    _order = 'id desc'
    _check_company_auto = True

    create_date = fields.Datetime(string='Fecha', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True)
    move_id = fields.Many2one('account.move', string='Factura', readonly=True, index='btree_not_null',
                              check_company=True, ondelete='set null')
    operation = fields.Selection(CAVALI_OPERATIONS, string='Operación', required=True, readonly=True)
    environment = fields.Selection([('test', 'Pruebas'), ('production', 'Producción')],
                                   string='Ambiente', readonly=True)
    url = fields.Char(string='URL', readonly=True)
    request_body = fields.Text(string='Solicitud', readonly=True)
    response_body = fields.Text(string='Respuesta', readonly=True)
    http_status = fields.Integer(string='Código HTTP', readonly=True)
    state = fields.Selection([('ok', 'Correcto'), ('error', 'Error')], string='Resultado', readonly=True)
    message = fields.Char(string='Mensaje', readonly=True)
    reference = fields.Char(string='Referencia de CAVALI', readonly=True)
    cavali_status = fields.Char(string='Estado en CAVALI', readonly=True)

    @api.model
    def _path(self, operation):
        return self.env['ir.config_parameter'].sudo().get_str(
            'l10n_pe_cavali.path.%s' % operation, DEFAULT_PATHS[operation])

    @api.model
    def _parse(self, response):
        """``(ok, mensaje, referencia, estado)`` de la respuesta JSON de CAVALI."""
        try:
            data = response.json()
        except ValueError:
            data = {}
        if isinstance(data, list):
            data = data[0] if data else {}
        code = str(data.get('codigo', data.get('code', '0')))
        ok = 200 <= response.status_code < 300 and code in OK_CODES
        message = data.get('mensaje') or data.get('message') or data.get('descripcion') or ''
        reference = (data.get('codigoAnotacion') or data.get('numeroAnotacion') or data.get('anotacion')
                     or data.get('id') or '')
        status = data.get('estado') or data.get('status') or ''
        return ok, str(message)[:500], str(reference), str(status)

    @api.model
    def _call(self, company, operation, payload, move=None):
        """Envía ``payload`` a CAVALI y deja el registro (nunca las credenciales)."""
        url = company._l10n_pe_cavali_url()
        if company.l10n_pe_cavali_mode != 'webservice' or not url:
            raise UserError(self.env._(
                'Configure los servicios web de CAVALI en Ajustes ▸ Contabilidad ▸ CAVALI (URL y '
                'credenciales que entrega CAVALI).'))
        # sudo: las credenciales solo las ve Administración; el envío lo hace
        # quien registra la operación.
        company_sudo = company.sudo()
        endpoint = url + self._path(operation)
        vals = {'company_id': company.id, 'move_id': move.id if move else False, 'operation': operation,
                'environment': company.l10n_pe_cavali_environment, 'url': endpoint,
                'request_body': json.dumps(payload, ensure_ascii=False, indent=1, default=str)}
        try:
            response = requests.post(
                endpoint, json=payload, timeout=30,
                auth=(company_sudo.l10n_pe_cavali_user or '', company_sudo.l10n_pe_cavali_password or ''),
                headers={'Accept': 'application/json'})
            ok, message, reference, status = self._parse(response)
            vals.update(http_status=response.status_code, response_body=response.text[:20000],
                        state='ok' if ok else 'error', message=message, reference=reference,
                        cavali_status=status)
        except requests.RequestException as error:
            _logger.warning('CAVALI %s: %s', operation, error)
            vals.update(state='error', message=str(error)[:500])
        # El registro queda aunque la operación falle después.
        return self.sudo().create(vals).sudo(False)


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_cavali_log_ids = fields.One2many('l10n_pe.cavali.log', 'move_id', string='Envíos a CAVALI')

    # ------------------------------------------------------------------
    # Datos de la factura negociable (RIC v09, DV 07 punto 3; DU 013-2020 art. 3-A)
    # ------------------------------------------------------------------
    def _l10n_pe_cavali_key(self):
        self.ensure_one()
        serie, _sep, number = (self.name or '').rpartition('-')
        document = (self.l10n_latam_document_type_id.code
                    if 'l10n_latam_document_type_id' in self._fields and self.l10n_latam_document_type_id
                    else '01')
        return {
            'rucProveedor': self.company_id.vat or '',
            'tipoComprobante': document or '01',
            'serie': serie.split(' ')[-1] if serie else '',
            'numero': number or self.name or '',
        }

    def _l10n_pe_cavali_installments(self, net):
        """Cuotas del monto neto pendiente según los vencimientos de la factura."""
        self.ensure_one()
        receivables = self.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable').sorted('date_maturity')
        total = sum(receivables.mapped('amount_currency')) or 1.0
        installments, assigned = [], 0.0
        for index, line in enumerate(receivables, start=1):
            amount = self.currency_id.round(net * line.amount_currency / total)
            if index == len(receivables):
                amount = self.currency_id.round(net - assigned)
            assigned += amount
            installments.append({'numero': index, 'monto': amount,
                                 'fechaPago': str(line.date_maturity or self.invoice_date_due or '')})
        return installments

    def _l10n_pe_cavali_xml(self):
        """XML del comprobante electrónico (el enviado a SUNAT), si está adjunto."""
        self.ensure_one()
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'account.move'), ('res_id', '=', self.id),
            '|', ('mimetype', 'in', ('application/xml', 'text/xml')), ('name', '=ilike', '%.xml')],
            order='id desc', limit=1)
        return attachment

    def _l10n_pe_cavali_payload(self):
        self.ensure_one()
        company, customer = self.company_id, self.commercial_partner_id
        net = self._l10n_pe_factoring_net_pending()
        address = lambda partner: ' '.join(filter(None, [
            partner.street, partner.street2, partner.city, partner.state_id.name])).strip()
        payload = dict(self._l10n_pe_cavali_key(), **{
            'razonSocialProveedor': company.name,
            'domicilioProveedor': address(company.partner_id),
            'rucAdquirente': customer.vat or '',
            'razonSocialAdquirente': customer.name,
            'domicilioAdquirente': address(customer),
            'fechaEmision': str(self.invoice_date or ''),
            'fechaVencimiento': str(self.invoice_date_due or ''),
            'fechaPago': str(self.l10n_pe_negotiable_due_date or self.invoice_date_due or ''),
            'moneda': self.currency_id.name,
            'montoTotal': self.amount_total,
            'montoNetoPendiente': net,
            'formaPago': 'Credito' if self.l10n_pe_is_credit else 'Contado',
            'cuotas': self._l10n_pe_cavali_installments(net),
            'tipoCuenta': company.l10n_pe_cavali_account_type,
            'codigoParticipante': company.l10n_pe_cavali_participant_code or '',
            'codigoRut': company.l10n_pe_cavali_rut or '',
        })
        xml = self._l10n_pe_cavali_xml()
        if xml:
            payload['xmlNombre'] = xml.name
            payload['xmlComprobante'] = xml.datas.decode() if xml.datas else ''
        return payload

    def _l10n_pe_cavali_missing(self):
        """Datos que faltan para registrar la factura en CAVALI."""
        self.ensure_one()
        missing = []
        if not self.company_id.vat:
            missing.append(self.env._('RUC de la empresa'))
        if not self.commercial_partner_id.vat:
            missing.append(self.env._('RUC del cliente'))
        if not self.commercial_partner_id.street:
            missing.append(self.env._('domicilio del cliente'))
        if not self.company_id.partner_id.street:
            missing.append(self.env._('domicilio de la empresa'))
        if not self.invoice_date_due:
            missing.append(self.env._('fecha de vencimiento'))
        return missing

    # ------------------------------------------------------------------
    # Envíos (servicios web)
    # ------------------------------------------------------------------
    def _l10n_pe_cavali_send(self, operation, operation_record=None, amount=0.0, date=None,
                             due_date=None, partner=None, conformity=None, reason=None):
        """Envía la operación a CAVALI y, si responde bien, registra el evento."""
        Log = self.env['l10n_pe.cavali.log']
        events = self.env['l10n_pe.negotiable.event']
        for move in self:
            date = date or fields.Date.context_today(move)
            if operation == 'register':
                missing = move._l10n_pe_cavali_missing()
                errors = move._l10n_pe_check_negotiable_event('registered')
                if missing:
                    errors.append(self.env._('%(invoice)s: falta %(data)s.', invoice=move.name,
                                             data=', '.join(missing)))
                if errors:
                    raise UserError('\n'.join(errors))
                payload = move._l10n_pe_cavali_payload()
            else:
                payload = dict(move._l10n_pe_cavali_key(), codigoAnotacion=move.l10n_pe_cavali_number or '')
                if operation == 'transfer':
                    payload.update(rucTenedor=partner.vat or '', razonSocialTenedor=partner.name,
                                   fechaTransferencia=str(date), montoNetoPendiente=amount)
                elif operation == 'payment':
                    payload.update(fechaPagoEfectiva=str(date), montoPagado=amount)
                elif operation == 'reschedule':
                    payload.update(nuevaFechaPago=str(due_date or ''), nuevoMonto=amount)
                elif operation == 'conformity':
                    payload.update(conformidad=conformity, motivo=reason or '')
            log = Log._call(move.company_id, operation, payload, move=move)
            if log.state != 'ok':
                raise UserError(self.env._('CAVALI no aceptó «%(operation)s» de %(invoice)s: %(message)s',
                                           operation=dict(CAVALI_OPERATIONS)[operation], invoice=move.name,
                                           message=log.message or log.http_status))
            reference = operation_record.name if operation_record else log.reference
            if operation == 'register':
                events |= move._l10n_pe_add_negotiable_event(
                    'registered', date=date, reference=log.reference or move.l10n_pe_cavali_number,
                    source='cavali')
            elif operation == 'transfer':
                events |= move._l10n_pe_add_negotiable_event(
                    'transferred', date=date, partner=partner, reference=reference, amount=amount,
                    source='cavali')
            elif operation == 'payment':
                events |= move._l10n_pe_add_negotiable_event(
                    'paid', date=date, reference=reference, amount=amount, source='cavali')
            elif operation == 'reschedule':
                events |= move._l10n_pe_add_negotiable_event(
                    'extended', date=date, reference=reference, amount=amount, due_date=due_date,
                    source='cavali')
            elif operation == 'conformity':
                events |= move._l10n_pe_add_negotiable_event(
                    conformity, date=date, reference=reference, note=reason, source='cavali')
            elif operation == 'status':
                event = _status_event(log.cavali_status)
                if event and not move._l10n_pe_negotiable_event_done(event) \
                        and not move._l10n_pe_check_negotiable_event(event):
                    events |= move._l10n_pe_add_negotiable_event(event, date=date, reference=log.reference,
                                                                 source='cavali')
        return events

    def _l10n_pe_negotiable_event_done(self, event):
        """La factura ya está en la situación que deja el evento."""
        self.ensure_one()
        if event in ('accepted', 'presumed', 'rejected'):
            return self.l10n_pe_conformity_state == event
        return self.l10n_pe_negotiable_state == event

    def _l10n_pe_cavali_transfer(self, factor, operation=None):
        for move in self:
            line = operation.line_ids.filtered(lambda l: l.move_id == move) if operation else False
            move._l10n_pe_cavali_send('transfer', operation_record=operation, partner=factor,
                                      date=operation.date if operation else None,
                                      amount=line.nominal_amount if line else move.amount_residual)

    def action_l10n_pe_cavali_register(self):
        """Registra y anota en cuenta en CAVALI (servicios web)."""
        self.filtered(lambda m: m.l10n_pe_negotiable_state in ('none', 'cancelled', False)) \
            ._l10n_pe_cavali_send('register')
        return True

    def action_l10n_pe_cavali_status(self):
        """Consulta a CAVALI el estado y la conformidad (consulta a demanda, DV 06)."""
        self._l10n_pe_cavali_send('status')
        return True

    @api.model
    def _cron_l10n_pe_cavali_status(self):
        """Consulta diaria del estado de las facturas anotadas con conformidad
        pendiente o transferidas (solo con los servicios web activos)."""
        for company in self.env['res.company'].search([('l10n_pe_cavali_mode', '=', 'webservice')]):
            if not company._l10n_pe_cavali_enabled():
                continue
            moves = self.search([('company_id', '=', company.id),
                                 ('l10n_pe_negotiable_state', 'in', ('registered', 'transferred'))])
            for move in moves:
                try:
                    with self.env.cr.savepoint():
                        move._l10n_pe_cavali_send('status')
                except UserError as error:
                    _logger.info('CAVALI, consulta de %s: %s', move.name, error)

    # ------------------------------------------------------------------
    # Factrack: paquete para el formulario masivo
    # ------------------------------------------------------------------
    def action_l10n_pe_factrack_package(self):
        """ZIP con el XML de cada comprobante y la información adicional en
        Excel para registrar las facturas en Factrack (formulario masivo)."""
        moves = self.filtered(lambda m: m.move_type == 'out_invoice' and m.state == 'posted')
        if not moves:
            raise UserError(self.env._('Seleccione facturas de cliente publicadas.'))
        missing = ['%s: %s' % (m.name, ', '.join(m._l10n_pe_cavali_missing()))
                   for m in moves if m._l10n_pe_cavali_missing()]
        if missing:
            raise UserError(self.env._('Faltan datos para CAVALI:\n%s', '\n'.join(missing)))
        attachment = moves._l10n_pe_factrack_attachment()
        return {'type': 'ir.actions.act_url', 'target': 'self',
                'url': '/web/content/%s?download=true' % attachment.id}

    def _l10n_pe_factrack_attachment(self):
        import xlsxwriter

        book_buffer = io.BytesIO()
        book = xlsxwriter.Workbook(book_buffer, {'in_memory': True})
        sheet = book.add_worksheet('Facturas')
        installments_sheet = book.add_worksheet('Cuotas')
        bold = book.add_format({'bold': True})
        headers = ['RUC proveedor', 'Tipo', 'Serie', 'Número', 'Fecha de emisión', 'Fecha de vencimiento',
                   'Fecha de pago', 'Moneda', 'Monto total', 'Monto neto pendiente', 'Forma de pago',
                   'RUC adquirente', 'Razón social adquirente', 'Domicilio adquirente',
                   'Domicilio proveedor', 'N.º de cuotas', 'Archivo XML']
        sheet.write_row(0, 0, headers, bold)
        installments_sheet.write_row(0, 0, ['Serie', 'Número', 'Cuota', 'Monto', 'Fecha de pago'], bold)
        archive_buffer = io.BytesIO()
        row = cuota_row = 1
        with zipfile.ZipFile(archive_buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for move in self:
                data = move._l10n_pe_cavali_payload()
                xml = move._l10n_pe_cavali_xml()
                if xml and xml.raw:
                    archive.writestr('xml/%s' % xml.name, xml.raw)
                sheet.write_row(row, 0, [
                    data['rucProveedor'], data['tipoComprobante'], data['serie'], data['numero'],
                    data['fechaEmision'], data['fechaVencimiento'], data['fechaPago'], data['moneda'],
                    data['montoTotal'], data['montoNetoPendiente'], data['formaPago'], data['rucAdquirente'],
                    data['razonSocialAdquirente'], data['domicilioAdquirente'], data['domicilioProveedor'],
                    len(data['cuotas']), xml.name if xml else ''])
                for cuota in data['cuotas']:
                    installments_sheet.write_row(cuota_row, 0, [data['serie'], data['numero'], cuota['numero'],
                                                                cuota['monto'], cuota['fechaPago']])
                    cuota_row += 1
                row += 1
            sheet.set_column(0, len(headers), 16)
            book.close()
            archive.writestr('informacion_adicional.xlsx', book_buffer.getvalue())
        return self.env['ir.attachment'].create({
            'name': 'factrack_%s.zip' % fields.Date.context_today(self),
            'raw': archive_buffer.getvalue(),
            'mimetype': 'application/zip',
            'res_model': 'res.company', 'res_id': self[:1].company_id.id,
        })


class L10nPeCavaliImport(models.TransientModel):
    """Importa los estados que devuelve Factrack (Excel o CSV)."""
    _name = 'l10n_pe.cavali.import'
    _description = 'Importar estados de CAVALI'

    file = fields.Binary(string='Archivo', required=True)
    filename = fields.Char(string='Nombre del archivo')
    result = fields.Text(string='Resultado', readonly=True)

    #: Columnas que se reconocen (sin distinguir mayúsculas ni tildes).
    COLUMNS = {
        'serie': ('serie',),
        'numero': ('numero', 'número', 'nro', 'correlativo'),
        'estado': ('estado', 'evento', 'situacion', 'situación'),
        'fecha': ('fecha', 'fecha de estado', 'fecha evento'),
        'codigo': ('codigo anotacion', 'código anotación', 'codigo de anotacion', 'anotacion', 'código'),
        'ruc_tenedor': ('ruc tenedor', 'ruc factor', 'ruc adquiriente del titulo', 'ruc titular'),
    }

    def _rows(self):
        import csv

        content = self.file.content
        name = (self.filename or '').lower()
        if name.endswith('.csv') or name.endswith('.txt'):
            text = content.decode('utf-8-sig', errors='replace')
            dialect = csv.Sniffer().sniff(text[:2048], delimiters=',;|\t')
            rows = list(csv.reader(io.StringIO(text), dialect))
        else:
            import openpyxl
            book = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            rows = [list(row) for row in book.worksheets[0].iter_rows(values_only=True)]
        if not rows:
            return []
        normalize = lambda value: str(value or '').strip().lower().replace('í', 'i').replace(
            'ó', 'o').replace('á', 'a').replace('é', 'e').replace('ú', 'u')
        header = [normalize(cell) for cell in rows[0]]
        index = {}
        for key, names in self.COLUMNS.items():
            for position, title in enumerate(header):
                if title in [normalize(n) for n in names]:
                    index[key] = position
                    break
        return [{key: row[pos] if pos < len(row) else None for key, pos in index.items()} for row in rows[1:]]

    def _find_invoice(self, serie, number):
        """Factura de cliente por serie y número (con o sin ceros a la izquierda)."""
        try:
            wanted = int(number)
        except ValueError:
            return self.env['account.move']
        candidates = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
            ('company_id', '=', self.env.company.id), ('name', 'ilike', '%s-' % serie)])
        for move in candidates:
            prefix, _sep, digits = (move.name or '').rpartition('-')
            if prefix.split(' ')[-1].upper() == serie.upper() and digits.isdigit() and int(digits) == wanted:
                return move
        return self.env['account.move']

    def action_import(self):
        self.ensure_one()
        done, skipped = [], []
        Move = self.env['account.move']
        for row in self._rows():
            serie, number = str(row.get('serie') or '').strip(), str(row.get('numero') or '').strip()
            if not number:
                continue
            number = number.split('.')[0]
            move = self._find_invoice(serie, number)
            event = _status_event(row.get('estado'))
            label = '%s-%s' % (serie, number)
            if not move or not event:
                skipped.append(self.env._('%(doc)s: %(why)s', doc=label, why=self.env._(
                    'factura no encontrada') if not move else self.env._('estado «%s» no reconocido', row.get('estado'))))
                continue
            date = row.get('fecha')
            if hasattr(date, 'date'):
                date = date.date()
            elif isinstance(date, str) and date:
                date = fields.Date.to_date(date[:10]) if '-' in date else fields.Date.to_date(
                    '-'.join(reversed(date[:10].split('/'))))
            if move._l10n_pe_negotiable_event_done(event):
                continue
            errors = move._l10n_pe_check_negotiable_event(event)
            if errors:
                skipped.append('%s: %s' % (move.name, ' '.join(errors)))
                continue
            partner = False
            if row.get('ruc_tenedor'):
                partner = self.env['res.partner'].search([('vat', '=', str(row['ruc_tenedor']).strip())], limit=1)
            move._l10n_pe_add_negotiable_event(event, date=date or None, reference=row.get('codigo') or False,
                                               partner=partner, source='cavali')
            done.append(move.name)
        self.result = self.env._('Actualizadas: %(done)s.\nOmitidas: %(skipped)s', done=len(done),
                                 skipped='\n'.join(skipped) or '0')
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'new'}
