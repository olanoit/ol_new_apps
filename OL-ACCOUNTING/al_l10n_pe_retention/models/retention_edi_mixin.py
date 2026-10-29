# -*- coding: utf-8 -*-
"""Comprobante de Retención Electrónico (CRE, tipo 20): lo común a cualquier
documento que lo emita.

Lo comparten el pago (``account.payment``) y el CRE sin pago de Odoo
(``l10n_pe.retention.document``: letras, compensaciones u otros pagos hechos
fuera de Odoo). Cada uno aporta los comprobantes que cita, el reparto por
comprobante y la nota; aquí van el XML, la firma y el envío por el operador
de la compañía, y la reversión del CRE con el resumen de reversiones (RR).

Reversión (R.S. 274-2015/SUNAT): un CRE aceptado se revierte con un resumen
``SummaryDocuments`` (SUNAT rechaza el tipo 20 en las comunicaciones de baja
RA, error 2308) con estado 3 e importe 0, numerado ``RR-AAAAMMDD-N`` y
enviado por ``sendSummary``; el resultado se consulta con el ticket
(``getStatus``). Los operadores de ``l10n_pe_edi`` (IAP, SUNAT directo y
Digiflow) lo hacen con sus servicios de baja; otros operadores (Factory HKA)
extienden ``_l10n_pe_edi_reversal_send`` y ``_l10n_pe_edi_reversal_status``.
"""
from datetime import datetime

from lxml import etree, objectify
from pytz import timezone

from odoo import api, fields, models
from odoo.exceptions import UserError

# Servicio de SUNAT para retenciones y percepciones (no es el de facturas).
SUNAT_RETENTION_WSDL = {
    'test': 'https://e-beta.sunat.gob.pe/ol-ti-itemision-otroscpe-gem-beta/billService?wsdl',
    'prod': 'https://e-factura.sunat.gob.pe/ol-ti-itemision-otroscpe-gem/billService?wsdl',
}
# Operadores de l10n_pe_edi que revierten con su servicio de resúmenes.
REVERSAL_PROVIDERS = ('iap', 'sunat', 'digiflow')


class L10nPeRetentionEdiMixin(models.AbstractModel):
    _name = 'l10n_pe.retention.edi.mixin'
    _description = 'Comprobante de retención electrónico'

    l10n_pe_edi_reversal_reason = fields.Char(
        string='Motivo de la reversión', copy=False, tracking=True,
        help='Por qué se revierte el comprobante de retención (queda en el historial).')
    l10n_pe_edi_reversal_filename = fields.Char(
        string='Archivo de la reversión', copy=False, readonly=True,
        help='RUC-RR-AAAAMMDD-N. Se reutiliza en los reintentos para no cambiar el '
             'correlativo (SUNAT rechaza con el error 2220 un correlativo distinto).')
    l10n_pe_edi_reversal_ticket = fields.Char(
        string='Ticket de la reversión', copy=False, readonly=True,
        help='Ticket que devuelve SUNAT al recibir el resumen de reversiones.')
    l10n_pe_edi_reversal_message = fields.Html(
        string='Estado de la reversión', copy=False, readonly=True, sanitize=False)
    l10n_pe_edi_reversal_available = fields.Boolean(
        string='Reversión disponible', compute='_compute_l10n_pe_edi_reversal_available')

    # ------------------------------------------------------------------
    # Tipo de comprobante (el mixin también lo usa el comprobante de
    # percepción, tipo 40, de al_l10n_pe_perception)
    # ------------------------------------------------------------------
    def _l10n_pe_edi_cpe_type(self):
        """Código SUNAT del comprobante (catálogo 01): 20 retención."""
        return '20'

    def _l10n_pe_edi_cpe_label(self):
        """Nombre corto del comprobante en los mensajes."""
        return 'CRE'

    def _l10n_pe_edi_cpe_number(self):
        """Serie-número del comprobante emitido."""
        self.ensure_one()
        return self.l10n_pe_edi_retention_number

    def _l10n_pe_edi_cpe_export(self):
        """XML UBL del comprobante, sin firma (bytes UTF-8)."""
        self.ensure_one()
        return self.env['account.edi.xml.ubl_pe_withholding']._export_retention(self)

    # ------------------------------------------------------------------
    # Lo que aporta cada documento
    # ------------------------------------------------------------------
    def _l10n_pe_retention_bills(self):
        """Comprobantes del proveedor que cita el CRE."""
        raise NotImplementedError()

    def _l10n_pe_retention_note(self):
        """Nota libre del CRE (``cbc:Note``)."""
        return False

    def _l10n_pe_retention_check_ready(self):
        """Error de usuario si el documento no tiene retención que informar."""
        self.ensure_one()

    def _l10n_pe_edi_get_retention_breakdown(self):
        raise NotImplementedError()

    @api.model
    def _l10n_pe_retention_deduction_entries(self, deductions):
        """Notas de crédito descontadas en el CRE (art. 2 de la R.S.
        037-2002/SUNAT), con las claves del reparto: cada una va como
        documento 07 sin pago, con la retención descontada en negativo y ese
        mismo importe sumado al neto pagado, de modo que los totales del CRE
        cuadran con lo retenido de verdad."""
        return [{
            'bill': deduction.credit_note_id,
            'bill_paid_currency': 0.0,
            'bill_paid_pen': 0.0,
            'bill_retention_pen': -deduction.amount,
            'net_total_paid_pen': deduction.amount,
            'exchange_rate': 1.0,
        } for deduction in deductions]

    # ------------------------------------------------------------------
    # Datos del XML
    # ------------------------------------------------------------------
    def _l10n_pe_edi_retention_bill_number(self, bill):
        """Serie-número del comprobante del proveedor (``F001-00000123``)."""
        if bill.l10n_latam_use_documents and bill.l10n_latam_document_number:
            number = bill.l10n_latam_document_number
        else:
            # sin documentos LATAM, el número del proveedor está en la referencia
            number = bill.ref or bill.name or ''
        return number.replace(' ', '')

    def _l10n_pe_edi_retention_payment_index(self, bill):
        """Número de pago a ``bill`` que informa este CRE (``cac:Payment/
        cbc:ID``): 1 para el primer pago al comprobante, 2 para el segundo…
        contando los CRE anteriores no anulados de ese comprobante, se hayan
        emitido desde un pago o sin pago (R.S. 274-2015/SUNAT; la guía XML
        del CRE: «este valor no se puede repetir para un mismo comprobante»)."""
        self.ensure_one()
        history = bill._l10n_pe_retention_cre_history()
        key = (self.date, self._name, self.id)
        return 1 + sum(1 for entry in history
                       if entry[:3] < key and (entry[1], entry[2]) != (self._name, self.id))

    def _l10n_pe_edi_generate_retention_bstr(self):
        """XML del CRE con el hueco de la firma, en ISO-8859-1."""
        self.ensure_one()
        self._l10n_pe_retention_check_ready()
        if not self._l10n_pe_retention_bills():
            raise UserError(self.env._(
                '%(document)s no cita ninguna factura: el comprobante de retención debe '
                'citar los comprobantes pagados.', document=self.display_name))
        xml_content = self._l10n_pe_edi_cpe_export()
        edi_tree = objectify.fromstring(xml_content)
        ubl_version = edi_tree.find('.//{*}UBLVersionID')
        ubl_version.addprevious(objectify.fromstring(self.env['ir.qweb']._render(
            'l10n_pe_edi.ubl_pe_21_ubl_extensions_empty_signature')))
        return etree.tostring(edi_tree, xml_declaration=True, encoding='ISO-8859-1',
                              pretty_print=True)

    def _l10n_pe_edi_generate_retention_filename(self):
        """``RUC-20-R001-00000001``, como pide SUNAT para el ZIP y el XML."""
        self.ensure_one()
        return '%s-%s-%s' % (self.company_id.vat, self._l10n_pe_edi_cpe_type(),
                             (self._l10n_pe_edi_cpe_number() or self.display_name).replace('/', '-'))

    def action_l10n_pe_generate_cre_xml(self):
        """Descarga el XML del CRE sin firmar (para revisión)."""
        self.ensure_one()
        attachment = self.env['ir.attachment'].create({
            'name': '%s.xml' % self._l10n_pe_edi_generate_retention_filename(),
            'res_model': self._name, 'res_id': self.id,
            'raw': self._l10n_pe_edi_generate_retention_bstr(), 'mimetype': 'application/xml'})
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%d?download=true' % attachment.id,
            'target': 'self',
        }

    # ------------------------------------------------------------------
    # Envío
    # ------------------------------------------------------------------
    def action_l10n_pe_edi_send_retention(self):
        """Firma el CRE y lo envía con el proveedor electrónico de la compañía."""
        ready = self.filtered('l10n_pe_edi_is_required')
        if self - ready:
            raise UserError(self.env._(
                'Estos documentos no tienen un comprobante de retención por enviar: %s',
                ', '.join((self - ready).mapped('display_name'))))
        for document in ready:
            if not document._l10n_pe_retention_bills():
                document.write({'l10n_pe_edi_status': 'to_send', 'l10n_pe_edi_warnings': {
                    'edi_error': {'level': 'danger', 'message': self.env._(
                        'No cita ninguna factura: el comprobante de retención debe citar al '
                        'menos un comprobante.')}}})
                continue
            result = document._l10n_pe_edi_post_retention(
                document._l10n_pe_edi_generate_retention_bstr())
            if result.get('success'):
                filename = document._l10n_pe_edi_generate_retention_filename()
                attachment = self.env['ir.attachment'].create({
                    'name': '%s.zip' % filename,
                    'res_model': document._name, 'res_id': document.id,
                    'res_field': 'l10n_pe_edi_attachment_file',
                    'type': 'binary', 'raw': result['zip_document'],
                })
                document.invalidate_recordset(['l10n_pe_edi_attachment_file'])
                document.write({'l10n_pe_edi_status': 'sent', 'l10n_pe_edi_warnings': False})
                document.message_post(
                    body=document._l10n_pe_edi_cpe_accepted_message(),
                    attachment_ids=attachment.ids)
            else:
                document.write({'l10n_pe_edi_status': 'to_send', 'l10n_pe_edi_warnings': {
                    'edi_error': {'level': result.get('level', 'danger'),
                                  'message': result.get('message')
                                  or self.env._('Error desconocido')}}})
        return True

    def _l10n_pe_edi_cpe_accepted_message(self):
        self.ensure_one()
        return self.env._('Comprobante de retención %(number)s aceptado por SUNAT.',
                          number=self._l10n_pe_edi_cpe_number())

    def _l10n_pe_edi_post_retention(self, edi_str):
        """Firma y envía con el proveedor de la compañía. Devuelve, como el
        oficial, ``{'success': True, 'zip_document': …}`` o
        ``{'message': …, 'level': …}``."""
        self.ensure_one()
        filename = self._l10n_pe_edi_generate_retention_filename()
        result = self._l10n_pe_edi_sign_retention(filename, edi_str)
        if not result.get('success'):
            return {'message': result.get('error') or self.env._('Error desconocido'),
                    'level': 'warning' if result.get('blocking_level') == 'warning' else 'danger'}
        zip_document = self.env['account.move']._l10n_pe_edi_zip_edi_document([
            ('%s.xml' % filename, result['xml_document']),
            ('R-%s.xml' % filename, result['cdr']),
        ])
        return {'success': True, 'zip_document': zip_document}

    def _l10n_pe_edi_sign_retention(self, filename, edi_str):
        """Firma y envía el CRE (tipo 20) por el operador de la compañía
        (``l10n_pe.edi.cpe.service``); los módulos de otros operadores (p. ej.
        Factory HKA) lo extienden. SUNAT lo recibe en su servicio de
        retenciones y percepciones; Estela, en el habitual."""
        self.ensure_one()
        return self.env['l10n_pe.edi.cpe.service']._send_bill(
            self.company_id, filename, edi_str, self._l10n_pe_edi_cpe_type(),
            self._l10n_pe_edi_get_retention_sunat_wsdl())

    def _l10n_pe_edi_get_retention_sunat_wsdl(self):
        self.ensure_one()
        return SUNAT_RETENTION_WSDL['test' if self.company_id.l10n_pe_edi_test_env else 'prod']

    # ------------------------------------------------------------------
    # Reversión del CRE (resumen de reversiones RR)
    # ------------------------------------------------------------------
    @api.depends('company_id.l10n_pe_edi_provider')
    def _compute_l10n_pe_edi_reversal_available(self):
        for document in self:
            document.l10n_pe_edi_reversal_available = document._l10n_pe_edi_reversal_supported()

    def _l10n_pe_edi_reversal_supported(self):
        """El operador de la compañía revierte CRE. Los de ``l10n_pe_edi``
        sí; otros operadores lo declaran en su módulo."""
        self.ensure_one()
        return self.company_id.l10n_pe_edi_provider in REVERSAL_PROVIDERS

    def _l10n_pe_edi_reversal_values(self):
        """Nombre de archivo e identificador del resumen RR. El ``cbc:ID`` va
        sin el RUC (error 2220); el archivo, con él. En los reintentos se
        reutiliza el guardado para no gastar otro correlativo."""
        self.ensure_one()
        today = datetime.now(tz=timezone('America/Lima')).date()
        filename = self.l10n_pe_edi_reversal_filename
        if not filename:
            number = self.env['ir.sequence'].with_context(ir_sequence_date=today).next_by_code(
                'al_l10n_pe_retention.reversal_sequence')
            filename = '%s-%s' % (self.company_id.vat, number)
            self.l10n_pe_edi_reversal_filename = filename
        return {'filename': filename, 'number': filename.split('-', 1)[1], 'issue_date': today}

    def _l10n_pe_edi_generate_reversal_bstr(self, values):
        self.ensure_one()
        serie, _sep, folio = self._l10n_pe_edi_cpe_number().partition('-')
        return self.env['ir.qweb']._render('al_l10n_pe_retention.cre_reversal_summary', {
            'company': self.company_id,
            'document_type': self._l10n_pe_edi_cpe_type(),
            'reversal_number': values['number'],
            'reference_date': self.date,
            'issue_date': values['issue_date'],
            'serie': serie,
            'folio': int(folio) if folio.isdigit() else folio,
        }).encode()

    def _l10n_pe_edi_reversal_send(self, filename, edi_str):
        """Paso 1: envía el resumen RR. ``{'xml_document', 'cdr', 'cdr_number'}``
        o ``{'error', 'blocking_level'}``."""
        self.ensure_one()
        return self.env['l10n_pe.edi.cpe.service']._send_summary(
            self.company_id, filename, edi_str, self._l10n_pe_edi_get_retention_sunat_wsdl())

    def _l10n_pe_edi_reversal_status(self, ticket):
        """Paso 2: consulta el ticket. ``{'success': True, 'cdr': …}`` o
        ``{'error', 'blocking_level'}`` (``info``: SUNAT aún procesa)."""
        self.ensure_one()
        return self.env['l10n_pe.edi.cpe.service']._get_status(
            self.company_id, ticket, self._l10n_pe_edi_get_retention_sunat_wsdl())

    def action_l10n_pe_edi_reverse_retention(self):
        """Paso 1: envía el resumen de reversiones (sendSummary) y guarda el ticket."""
        for document in self:
            if not document.l10n_pe_edi_reversal_available:
                raise UserError(self.env._(
                    'El operador electrónico de %s no revierte comprobantes de retención (o la '
                    'reversión está desactivada).', document.company_id.display_name))
            if document.l10n_pe_edi_status != 'sent':
                raise UserError(self.env._(
                    'Solo se revierte un comprobante de retención aceptado por SUNAT.'))
            if not document.l10n_pe_edi_reversal_reason:
                raise UserError(self.env._('Indique el motivo de la reversión.'))
            values = document._l10n_pe_edi_reversal_values()
            res = document._l10n_pe_edi_reversal_send(
                values['filename'], document._l10n_pe_edi_generate_reversal_bstr(values))
            if res.get('error'):
                document.l10n_pe_edi_reversal_message = res['error']
                continue
            attachment = self.env['ir.attachment'].create({
                'name': '%s.xml' % values['filename'], 'res_model': document._name,
                'res_id': document.id, 'type': 'binary', 'raw': res['xml_document'],
                'mimetype': 'application/xml'})
            document.write({
                'l10n_pe_edi_status': 'reversing',
                'l10n_pe_edi_reversal_ticket': res['cdr_number'],
                'l10n_pe_edi_reversal_message': False,
            })
            document.message_post(body=self.env._(
                'Reversión del %(label)s %(number)s enviada a SUNAT (ticket %(ticket)s). Motivo: %(reason)s',
                label=document._l10n_pe_edi_cpe_label(),
                number=document._l10n_pe_edi_cpe_number(), ticket=res['cdr_number'],
                reason=document.l10n_pe_edi_reversal_reason), attachment_ids=attachment.ids)
        return True

    def action_l10n_pe_edi_check_reversal(self):
        """Paso 2: consulta el ticket (getStatus) hasta que SUNAT acepta la reversión."""
        for document in self:
            if document.l10n_pe_edi_status != 'reversing' or not document.l10n_pe_edi_reversal_ticket:
                raise UserError(self.env._(
                    'Este documento no tiene una reversión del CRE en proceso.'))
            res = document._l10n_pe_edi_reversal_status(document.l10n_pe_edi_reversal_ticket)
            if res.get('error'):
                # 'info': SUNAT aún procesa (código 98), se vuelve a consultar.
                document.l10n_pe_edi_reversal_message = res['error']
                continue
            attachment = self.env['ir.attachment'].create({
                'name': 'CDR-%s.xml' % document.l10n_pe_edi_reversal_filename,
                'res_model': document._name, 'res_id': document.id,
                'type': 'binary', 'raw': res['cdr'],
                'mimetype': 'application/xml'})
            document.write({
                'l10n_pe_edi_status': 'cancelled',
                'l10n_pe_edi_reversal_message': False,
            })
            document.message_post(body=document._l10n_pe_edi_reversal_done_message(),
                                  attachment_ids=attachment.ids)
            document._l10n_pe_edi_after_reversal()
        return True

    def _l10n_pe_edi_reversal_done_message(self):
        self.ensure_one()
        return self.env._(
            'SUNAT aceptó la reversión del CRE %(number)s. Si el pago también debe '
            'anularse o corregirse, restablézcalo a borrador: la retención se rehace con un '
            'número nuevo al volver a confirmarlo.', number=self.l10n_pe_edi_retention_number)

    def _l10n_pe_edi_after_reversal(self):
        """Lo que cada documento hace con su asiento cuando SUNAT acepta la
        reversión (el CRE sin pago anula su asiento)."""
        return True
