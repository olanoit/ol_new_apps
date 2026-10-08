# -*- coding: utf-8 -*-
"""Comprobante de Retención Electrónico (CRE, tipo 20) desde el pago.

La interfaz sigue al módulo oficial de Odoo ``l10n_pe_edi_withholding``
(Enterprise 19.4/20) para que al migrar se pueda cambiar a él: mismos campos
(``l10n_pe_edi_status``, ``l10n_pe_edi_warnings``,
``l10n_pe_edi_attachment_file``, ``l10n_pe_edi_retention_number``,
``l10n_pe_edi_is_required``) y mismos métodos (reparto por comprobante,
XML, nombre del archivo, envío y servicio de SUNAT). La implementación es
propia y se apoya en los servicios de firma y envío de ``l10n_pe_edi`` 19.0.

Diferencia deliberada con el oficial: la retención es el 3 % del importe
pagado **con IGV** (R.S. 037-2002/SUNAT); en los XML de prueba oficiales sale
el 3 % de la base sin IGV.
"""
from datetime import timedelta

from lxml import etree, objectify

from odoo import api, fields, models
from odoo.exceptions import UserError

# Servicio de SUNAT para retenciones y percepciones (no es el de facturas).
# R.S. 274-2015/SUNAT: el CRE se envía a SUNAT u OSE dentro de los 7 días
# calendario siguientes a su emisión; fuera de plazo no vale como CRE.
SEND_DEADLINE_DAYS = 7
SUNAT_RETENTION_WSDL = {
    'test': 'https://e-beta.sunat.gob.pe/ol-ti-itemision-otroscpe-gem-beta/billService?wsdl',
    'prod': 'https://e-factura.sunat.gob.pe/ol-ti-itemision-otroscpe-gem/billService?wsdl',
}


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    # Etiqueta en español del marco nativo
    withholding_line_ids = fields.One2many(string='Retenciones')

    l10n_pe_edi_retention_number = fields.Char(
        string='Nº comprobante de retención',
        compute='_compute_l10n_pe_edi_retention_number', store=True)
    l10n_pe_edi_status = fields.Selection(
        selection=[('to_send', 'Por enviar'), ('sent', 'Enviado'), ('cancelled', 'Anulado')],
        string='Estado del CRE', copy=False, tracking=True)
    l10n_pe_edi_warnings = fields.Json(string='Avisos del CRE', readonly=True, copy=False)
    l10n_pe_edi_attachment_file = fields.Binary(
        string='CRE firmado y CDR', attachment=True, copy=False)
    l10n_pe_edi_is_required = fields.Boolean(
        string='CRE por enviar', compute='_compute_l10n_pe_edi_is_required')
    l10n_pe_edi_deadline = fields.Date(
        string='Enviar el CRE hasta', compute='_compute_l10n_pe_edi_deadline', store=True,
        help='Plazo de 7 días calendario desde la emisión del comprobante de retención '
             '(fecha del pago) para enviarlo a SUNAT u OSE.')
    l10n_pe_edi_overdue = fields.Boolean(
        string='CRE fuera de plazo', compute='_compute_l10n_pe_edi_overdue',
        search='_search_l10n_pe_edi_overdue')
    l10n_pe_edi_error_message = fields.Char(
        string='Error del CRE', compute='_compute_l10n_pe_edi_error_message')
    # Guardado para los totales de la lista y el análisis de retenciones.
    l10n_pe_retention_amount = fields.Monetary(
        string='Importe retenido', currency_field='currency_id',
        compute='_compute_l10n_pe_retention_amount', store=True,
        help='Suma de las líneas de retención del IGV del pago.')

    def _l10n_pe_retention_lines(self):
        return self.withholding_line_ids.filtered(
            lambda l: l.tax_id == self.company_id.l10n_pe_retention_tax_id)

    @api.depends('withholding_line_ids.amount', 'withholding_line_ids.tax_id',
                 'company_id.l10n_pe_retention_tax_id')
    def _compute_l10n_pe_retention_amount(self):
        for payment in self:
            payment.l10n_pe_retention_amount = sum(
                payment._l10n_pe_retention_lines().mapped('amount'))

    @api.depends('withholding_line_ids.name')
    def _compute_l10n_pe_edi_retention_number(self):
        for payment in self:
            payment.l10n_pe_edi_retention_number = ', '.join(
                n for n in payment._l10n_pe_retention_lines().mapped('name') if n) or False

    @api.depends('state', 'l10n_pe_edi_retention_number', 'l10n_pe_edi_status', 'country_code')
    def _compute_l10n_pe_edi_is_required(self):
        for payment in self:
            payment.l10n_pe_edi_is_required = bool(
                payment.state in ('in_process', 'paid')
                and payment.l10n_pe_edi_retention_number
                and payment.country_code == 'PE'
                and payment.l10n_pe_edi_status not in ('sent', 'cancelled'))

    @api.depends('date', 'l10n_pe_edi_retention_number')
    def _compute_l10n_pe_edi_deadline(self):
        for payment in self:
            payment.l10n_pe_edi_deadline = (
                payment.date + timedelta(days=SEND_DEADLINE_DAYS)
                if payment.date and payment.l10n_pe_edi_retention_number else False)

    @api.depends('l10n_pe_edi_deadline', 'l10n_pe_edi_status')
    def _compute_l10n_pe_edi_overdue(self):
        today = fields.Date.context_today(self)
        for payment in self:
            payment.l10n_pe_edi_overdue = bool(
                payment.l10n_pe_edi_status == 'to_send'
                and payment.l10n_pe_edi_deadline and payment.l10n_pe_edi_deadline < today)

    def _search_l10n_pe_edi_overdue(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            return NotImplemented
        domain = [('l10n_pe_edi_status', '=', 'to_send'),
                  ('l10n_pe_edi_deadline', '<', fields.Date.context_today(self))]
        return domain if (operator == '=') == value else ['!', '&', *domain]

    @api.depends('l10n_pe_edi_warnings')
    def _compute_l10n_pe_edi_error_message(self):
        for payment in self:
            error = (payment.l10n_pe_edi_warnings or {}).get('edi_error') or {}
            payment.l10n_pe_edi_error_message = error.get('message') or False

    def action_post(self):
        """El comprobante de retención se numera al emitir el pago (el marco
        nativo lo haría recién al generar el asiento con el extracto, tarde
        para el flujo SUNAT) y queda por enviar."""
        res = super().action_post()
        for payment in self:
            lines = payment._l10n_pe_retention_lines()
            for line in lines.filtered(lambda l: not l.name and l.withholding_sequence_id):
                line.name = line.withholding_sequence_id.next_by_id()
            if lines and not payment.l10n_pe_edi_status:
                payment.l10n_pe_edi_status = 'to_send'
        return res

    # ------------------------------------------------------------------
    # Reparto por comprobante (misma salida que el oficial)
    # ------------------------------------------------------------------
    def _l10n_pe_edi_get_paid_per_bill(self):
        """``{bill.id: importe}`` en la moneda de cada factura, según la
        conciliación del pago. Vacío si el pago aún no tiene asiento (en 19.0
        nace al conciliar el extracto)."""
        self.ensure_one()
        result = {}
        if not self.move_id:
            return result
        payment_lines = self.move_id.line_ids
        for bill in self.reconciled_bill_ids:
            for partial in bill.line_ids.matched_debit_ids | bill.line_ids.matched_credit_ids:
                if partial.debit_move_id in payment_lines:
                    amount = partial.credit_amount_currency
                elif partial.credit_move_id in payment_lines:
                    amount = partial.debit_amount_currency
                else:
                    continue
                result[bill.id] = result.get(bill.id, 0.0) + amount
        return result

    def _l10n_pe_edi_get_retention_breakdown(self):
        """Reparto del pago y de la retención entre sus comprobantes, con las
        mismas claves que el oficial: ``bill``, ``bill_paid_currency`` (moneda
        de la factura), ``bill_paid_pen``, ``bill_retention_pen``,
        ``net_total_paid_pen`` y ``exchange_rate`` (moneda de la factura a
        soles, a la fecha del pago). Lo usan el XML, el PDF y el resumen 626.

        Sin conciliación, el pago se reparte en proporción al total de cada
        factura. La retención se reparte según lo pagado y el redondeo cae en
        la última.
        """
        self.ensure_one()
        company = self.company_id
        company_currency = company.currency_id
        bills = self.invoice_ids or self.reconciled_bill_ids
        if not bills:
            return []
        rates = {
            bill: (1.0 if bill.currency_id == company_currency
                   else self.env['res.currency']._get_conversion_rate(
                       bill.currency_id, company_currency, company, self.date))
            for bill in bills
        }
        paid_per_bill = self._l10n_pe_edi_get_paid_per_bill()
        if not any(paid_per_bill.values()):
            # importe bruto del pago (antes de retener) repartido por el total
            gross_pen = self.currency_id._convert(self.amount, company_currency, company, self.date)
            weights = {bill: abs(bill.amount_total_signed) for bill in bills}
            total_weight = sum(weights.values()) or 1.0
            paid_per_bill = {
                bill.id: bill.currency_id.round(gross_pen * weights[bill] / total_weight / rates[bill])
                for bill in bills}
        retention_pen = company_currency.round(sum(
            self.currency_id._convert(abs(line.amount), company_currency, company, self.date)
            for line in self._l10n_pe_retention_lines()))

        paid_pen = {bill: company_currency.round(paid_per_bill.get(bill.id, 0.0) * rates[bill])
                    for bill in bills}
        total_paid_pen = sum(paid_pen.values()) or 1.0
        breakdown = []
        retained_left = retention_pen
        for index, bill in enumerate(bills):
            if index == len(bills) - 1:
                retained = retained_left
            else:
                retained = company_currency.round(retention_pen * paid_pen[bill] / total_paid_pen)
                retained_left -= retained
            breakdown.append({
                'bill': bill,
                'bill_paid_currency': paid_per_bill.get(bill.id, 0.0),
                'bill_paid_pen': paid_pen[bill],
                'bill_retention_pen': retained,
                'net_total_paid_pen': paid_pen[bill] - retained,
                'exchange_rate': rates[bill],
            })
        return breakdown

    @api.model
    def _l10n_pe_edi_retention_bill_number(self, bill):
        """Serie-número del comprobante del proveedor (``F001-00000123``)."""
        if bill.l10n_latam_use_documents and bill.l10n_latam_document_number:
            number = bill.l10n_latam_document_number
        else:
            # sin documentos LATAM, el número del proveedor está en la referencia
            number = bill.ref or bill.name or ''
        return number.replace(' ', '')

    # ------------------------------------------------------------------
    # XML
    # ------------------------------------------------------------------
    def _l10n_pe_edi_generate_retention_bstr(self):
        """XML del CRE con el hueco de la firma, en ISO-8859-1."""
        self.ensure_one()
        if not self._l10n_pe_retention_lines():
            raise UserError(self.env._('El pago no tiene líneas de retención de IGV.'))
        if not (self.invoice_ids or self.reconciled_bill_ids):
            raise UserError(self.env._(
                'El pago %(payment)s no está vinculado a ninguna factura: el comprobante de '
                'retención debe citar los comprobantes pagados.', payment=self.display_name))
        xml_content = self.env['account.edi.xml.ubl_pe_withholding']._export_retention(self)
        edi_tree = objectify.fromstring(xml_content)
        ubl_version = edi_tree.find('.//{*}UBLVersionID')
        ubl_version.addprevious(objectify.fromstring(self.env['ir.qweb']._render(
            'l10n_pe_edi.ubl_pe_21_ubl_extensions_empty_signature')))
        return etree.tostring(edi_tree, xml_declaration=True, encoding='ISO-8859-1',
                              pretty_print=True)

    def _l10n_pe_edi_generate_retention_filename(self):
        """``RUC-20-R001-00000001``, como pide SUNAT para el ZIP y el XML."""
        self.ensure_one()
        return '%s-20-%s' % (self.company_id.vat,
                             (self.l10n_pe_edi_retention_number or self.name).replace('/', '-'))

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
                'Estos pagos no tienen un comprobante de retención por enviar: %s',
                ', '.join((self - ready).mapped('display_name'))))
        for payment in ready:
            if not (payment.invoice_ids or payment.reconciled_bill_ids):
                payment.write({'l10n_pe_edi_status': 'to_send', 'l10n_pe_edi_warnings': {
                    'edi_error': {'level': 'danger', 'message': self.env._(
                        'El pago no está vinculado a ninguna factura: el comprobante de '
                        'retención debe citar al menos un comprobante.')}}})
                continue
            result = payment._l10n_pe_edi_post_retention(
                payment._l10n_pe_edi_generate_retention_bstr())
            if result.get('success'):
                filename = payment._l10n_pe_edi_generate_retention_filename()
                attachment = self.env['ir.attachment'].create({
                    'name': '%s.zip' % filename,
                    'res_model': payment._name, 'res_id': payment.id,
                    'res_field': 'l10n_pe_edi_attachment_file',
                    'type': 'binary', 'raw': result['zip_document'],
                })
                payment.invalidate_recordset(['l10n_pe_edi_attachment_file'])
                payment.write({'l10n_pe_edi_status': 'sent', 'l10n_pe_edi_warnings': False})
                payment.message_post(
                    body=self.env._('Comprobante de retención %(number)s aceptado por SUNAT.',
                                    number=payment.l10n_pe_edi_retention_number),
                    attachment_ids=attachment.ids)
            else:
                payment.write({'l10n_pe_edi_status': 'to_send', 'l10n_pe_edi_warnings': {
                    'edi_error': {'level': result.get('level', 'danger'),
                                  'message': result.get('message')
                                  or self.env._('Error desconocido')}}})
        return True

    def _l10n_pe_edi_post_retention(self, edi_str):
        """Firma y envía con el proveedor de la compañía. Devuelve, como el
        oficial, ``{'success': True, 'zip_document': …}`` o
        ``{'message': …, 'level': …}``."""
        self.ensure_one()
        company = self.company_id
        # el formato UBL peruano: sus métodos de credenciales piden un registro
        edi_format = self.env.ref('l10n_pe_edi.edi_pe_ubl_2_1')
        filename = self._l10n_pe_edi_generate_retention_filename()
        if company.l10n_pe_edi_provider == 'iap':
            result = edi_format._l10n_pe_edi_sign_service_iap(company, filename, edi_str, '20')
        else:
            if company.l10n_pe_edi_provider == 'digiflow':
                credentials = edi_format._l10n_pe_edi_get_digiflow_credentials(company)
            else:
                credentials = edi_format._l10n_pe_edi_get_sunat_credentials(company)
                credentials['wsdl'] = self._l10n_pe_edi_get_retention_sunat_wsdl()
            result = edi_format._l10n_pe_edi_sign_service_sunat_digiflow_common(
                company, filename, edi_str, credentials, '20')
        if not result.get('success'):
            return {'message': result.get('error') or self.env._('Error desconocido'),
                    'level': 'warning' if result.get('blocking_level') == 'warning' else 'danger'}
        zip_document = edi_format._l10n_pe_edi_zip_edi_document([
            ('%s.xml' % filename, result['xml_document']),
            ('R-%s.xml' % filename, result['cdr']),
        ])
        return {'success': True, 'zip_document': zip_document}

    def _l10n_pe_edi_get_retention_sunat_wsdl(self):
        self.ensure_one()
        return SUNAT_RETENTION_WSDL['test' if self.company_id.l10n_pe_edi_test_env else 'prod']
