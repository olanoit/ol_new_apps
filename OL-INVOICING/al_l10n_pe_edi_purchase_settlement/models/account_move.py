# -*- coding: utf-8 -*-
"""Liquidación de compra electrónica (tipo 04) sobre la factura de proveedor.

El comprador la emite (R.S. 097-2012/SUNAT, capítulo XI, incorporado por la
R.S. 244-2019/SUNAT) en un diario de compras marcado como de liquidaciones:
numeración ``L###-########`` propia, retención del IGV y de la renta con
impuestos negativos, XML ``SelfBilledInvoice`` firmado y enviado con el
operador de la compañía (los servicios de ``l10n_pe_edi``, que se eligen por
el nombre del operador) y reversión con el resumen diario de reversiones (RR,
anexo 17), que SUNAT recibe en el servicio de retenciones y percepciones
(anexo 22).

``l10n_pe_edi`` solo emite comprobantes de venta (``account_edi``): la
liquidación lleva su propio ciclo de estados en la factura.
"""
import base64
from datetime import datetime, timedelta

from lxml import etree, objectify
from markupsafe import Markup
from pytz import timezone

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

# Catálogo 60: condición del domicilio del vendedor y del lugar de la operación.
CATALOG_60 = [
    ('01', 'Punto de venta'),
    ('02', 'Producción'),
    ('03', 'Extracción'),
    ('04', 'Explotación'),
    ('05', 'Otros'),
]
# Catálogo 51 (tipos de operación de la liquidación de compra). La 0502
# (anticipos) no se emite desde aquí.
LCE_OPERATION_TYPES = [
    ('0501', '0501 - Compra interna'),
    ('0503', '0503 - Compra de oro'),
]
LCE_STATUS = [
    ('to_send', 'Por enviar'),
    ('sent', 'Aceptada por SUNAT'),
    ('reversing', 'Reversión en proceso'),
    ('reversed', 'Revertida'),
]
# Catálogo 06: el vendedor es una persona natural sin RUC (DNI, carné de
# extranjería, pasaporte o cédula diplomática).
SELLER_DOC_TYPES = ('1', '4', '7', 'A')
# Afectación al IGV que admite la liquidación (catálogo 05).
IGV_CODES = ('1000', '9997', '9998')
# Plazos (días calendario): envío hasta el día siguiente a la emisión (art.
# 12.1.b) y reversión dentro de los siete días siguientes a la CDR (art. 29-F).
SEND_DAYS = 1
REVERSAL_DAYS = 7
# Servicio de SUNAT de retenciones, percepciones y resúmenes de reversiones
# (anexo 22); la liquidación misma va al servicio de facturas (anexo 6).
SUNAT_REVERSAL_WSDL = {
    'test': 'https://e-beta.sunat.gob.pe/ol-ti-itemision-otroscpe-gem-beta/billService?wsdl',
    'prod': 'https://e-factura.sunat.gob.pe/ol-ti-itemision-otroscpe-gem/billService?wsdl',
}
# Correlativo RR-AAAAMMDD-N: se comparte con la reversión del CRE si
# al_l10n_pe_retention está instalado, para que no se repita en el mismo día.
RETENTION_REVERSAL_SEQUENCE = 'al_l10n_pe_retention.reversal_sequence'
LCE_REVERSAL_SEQUENCE = 'al_l10n_pe_edi_purchase_settlement.reversal_sequence'
# Ventas del vendedor en el año que permiten emitirle liquidaciones (RCP,
# art. 6, num. 1.3).
SELLER_LIMIT_UIT = 75


def _lima_today():
    return datetime.now(tz=timezone('America/Lima')).date()


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_lce_required = fields.Boolean(
        string='Es liquidación de compra', compute='_compute_l10n_pe_lce_required',
        help='Factura de proveedor del diario de liquidaciones de compra electrónicas.')
    l10n_pe_lce_operation_type = fields.Selection(
        LCE_OPERATION_TYPES, string='Tipo de operación de la liquidación',
        compute='_compute_l10n_pe_lce_operation_type', store=True, readonly=False,
        help='Catálogo 51 de SUNAT: compra interna o compra de oro.')
    l10n_pe_lce_partner_address_type = fields.Selection(
        CATALOG_60, string='Condición del domicilio del vendedor',
        compute='_compute_l10n_pe_lce_partner_address_type', store=True, readonly=False,
        help='Catálogo 60: el domicilio del vendedor es punto de venta, de producción, de '
             'extracción o de explotación de los productos.')
    l10n_pe_lce_place_street = fields.Char(
        string='Lugar de la operación', compute='_compute_l10n_pe_lce_place_street', store=True,
        readonly=False,
        help='Dirección y referencias del lugar donde se realiza la compra. Se propone el '
             'domicilio del vendedor.')
    l10n_pe_lce_place_district_id = fields.Many2one(
        'l10n_pe.res.city.district', string='Distrito del lugar de la operación',
        compute='_compute_l10n_pe_lce_place_district_id', store=True, readonly=False,
        help='Su ubigeo (catálogo 13), provincia y departamento van en el XML.')
    l10n_pe_lce_place_type = fields.Selection(
        CATALOG_60, string='Condición del lugar de la operación',
        compute='_compute_l10n_pe_lce_place_type', store=True, readonly=False,
        help='Catálogo 60: punto de venta, producción, extracción, explotación u otros.')
    l10n_pe_lce_ir_exempt = fields.Boolean(
        string='Operación exonerada o inafecta de la renta', copy=False,
        help='El vendedor no está sujeto a la retención del impuesto a la renta por esta '
             'operación (R.S. 234-2005/SUNAT, art. 4).')
    l10n_pe_lce_license_plate = fields.Char(
        string='Placa del vehículo', size=8,
        help='Con la placa, la liquidación aceptada sustenta el traslado de los bienes '
             '(art. 29-D).')
    l10n_pe_lce_trailer_plate = fields.Char(
        string='Placa del remolque o semirremolque', size=8,
        help='Solo en una combinación de vehículos.')
    l10n_pe_lce_igv_amount = fields.Monetary(
        string='IGV - Crédito', compute='_compute_l10n_pe_lce_amounts',
        help='IGV de la operación que retiene el comprador y paga con el formulario 1662.')
    l10n_pe_lce_ir_amount = fields.Monetary(
        string='IR - Retención', compute='_compute_l10n_pe_lce_amounts',
        help='Retención del impuesto a la renta (PDT 617, tributo 3039).')
    l10n_pe_lce_subtotal = fields.Monetary(
        string='Sub total de la liquidación', compute='_compute_l10n_pe_lce_amounts',
        help='Total valor de venta más el IGV.')
    l10n_pe_lce_status = fields.Selection(
        LCE_STATUS, string='Estado SUNAT de la liquidación', copy=False, readonly=True,
        tracking=True)
    l10n_pe_lce_message = fields.Html(
        string='Respuesta de SUNAT', copy=False, readonly=True, sanitize=False)
    l10n_pe_lce_accepted_date = fields.Date(
        string='Fecha de la constancia de recepción', copy=False, readonly=True,
        help='Día (hora de Lima) en que SUNAT aceptó la liquidación: desde el día siguiente '
             'corren los siete días para revertirla.')
    l10n_pe_lce_reversal_reason = fields.Char(
        string='Motivo de la reversión', copy=False, size=100, tracking=True,
        help='Solo por error en los nombres o el documento del vendedor, o en el producto, la '
             'cantidad o la unidad (art. 29-F).')
    l10n_pe_lce_reversal_filename = fields.Char(
        string='Archivo de la reversión', copy=False, readonly=True,
        help='RUC-RR-AAAAMMDD-N. Se reutiliza en los reintentos para no cambiar el correlativo.')
    l10n_pe_lce_reversal_ticket = fields.Char(
        string='Ticket de la reversión', copy=False, readonly=True)
    l10n_pe_lce_seller_warning = fields.Char(
        string='Aviso de ventas del vendedor', compute='_compute_l10n_pe_lce_seller_warning')

    # ------------------------------------------------------------------
    # Cálculos
    # ------------------------------------------------------------------
    @api.depends('journal_id.l10n_pe_lce_journal', 'move_type')
    def _compute_l10n_pe_lce_required(self):
        for move in self:
            move.l10n_pe_lce_required = (move.move_type == 'in_invoice'
                                         and move.journal_id.l10n_pe_lce_journal)

    @api.depends('journal_id.l10n_pe_lce_journal', 'move_type')
    def _compute_l10n_pe_lce_operation_type(self):
        for move in self:
            if not move.l10n_pe_lce_required:
                move.l10n_pe_lce_operation_type = False
            else:
                move.l10n_pe_lce_operation_type = move.l10n_pe_lce_operation_type or '0501'

    def _l10n_pe_lce_proposes_place(self):
        """Solo en borrador se propone el domicilio del vendedor; después se
        conserva lo guardado (o lo que el usuario corrigió)."""
        self.ensure_one()
        return self.l10n_pe_lce_required and self.state == 'draft'

    # Cada campo tiene su cálculo: si uno llega en los valores de creación,
    # Odoo no calcula los demás de un cálculo compartido.
    @api.depends('partner_id', 'journal_id.l10n_pe_lce_journal', 'move_type')
    def _compute_l10n_pe_lce_place_street(self):
        """Propone como lugar de la operación el domicilio del vendedor."""
        for move in self:
            move.l10n_pe_lce_place_street = (
                move.partner_id.commercial_partner_id.street or False
                if move._l10n_pe_lce_proposes_place() else move.l10n_pe_lce_place_street)

    @api.depends('partner_id', 'journal_id.l10n_pe_lce_journal', 'move_type')
    def _compute_l10n_pe_lce_place_district_id(self):
        for move in self:
            move.l10n_pe_lce_place_district_id = (
                move.partner_id.commercial_partner_id.l10n_pe_district
                if move._l10n_pe_lce_proposes_place() else move.l10n_pe_lce_place_district_id)

    @api.depends('journal_id.l10n_pe_lce_journal', 'move_type')
    def _compute_l10n_pe_lce_place_type(self):
        for move in self:
            move.l10n_pe_lce_place_type = move.l10n_pe_lce_place_type or (
                '01' if move.l10n_pe_lce_required else False)

    @api.depends('journal_id.l10n_pe_lce_journal', 'move_type')
    def _compute_l10n_pe_lce_partner_address_type(self):
        for move in self:
            move.l10n_pe_lce_partner_address_type = move.l10n_pe_lce_partner_address_type or (
                '01' if move.l10n_pe_lce_required else False)

    @api.depends('line_ids.balance', 'line_ids.tax_line_id', 'amount_untaxed')
    def _compute_l10n_pe_lce_amounts(self):
        for move in self:
            igv = ir = 0.0
            if move.l10n_pe_lce_required:
                ir_taxes = move._l10n_pe_lce_ir_taxes()
                sign = -1 if move.is_inbound() else 1
                for line in move.line_ids.filtered('tax_line_id'):
                    if line.tax_line_id.l10n_pe_edi_tax_code == '1000':
                        igv += sign * line.amount_currency
                    elif line.tax_line_id in ir_taxes:
                        ir -= sign * line.amount_currency
            move.l10n_pe_lce_igv_amount = igv
            move.l10n_pe_lce_ir_amount = ir
            move.l10n_pe_lce_subtotal = move.amount_untaxed + igv if move.l10n_pe_lce_required else 0.0

    @api.depends('partner_id', 'invoice_date', 'amount_untaxed', 'journal_id.l10n_pe_lce_journal')
    def _compute_l10n_pe_lce_seller_warning(self):
        """Aviso si las liquidaciones al vendedor en el año pasan de 75 UIT.

        El límite es de las ventas del vendedor (a cualquier comprador) y se
        consulta en SUNAT Operaciones en Línea (art. 29-H): aquí solo se ven
        nuestras compras, que son un mínimo de esas ventas."""
        for move in self:
            move.l10n_pe_lce_seller_warning = False
            partner = move.partner_id.commercial_partner_id
            if not move.l10n_pe_lce_required or not partner:
                continue
            date = move.invoice_date or fields.Date.context_today(move)
            others = self.search([
                ('company_id', 'child_of', move.company_id.root_id.id),
                ('journal_id.l10n_pe_lce_journal', '=', True),
                ('move_type', '=', 'in_invoice'),
                ('state', '=', 'posted'),
                ('commercial_partner_id', '=', partner.id),
                ('invoice_date', '>=', date.replace(month=1, day=1)),
                ('invoice_date', '<=', date),
                ('id', 'not in', move.ids),
            ])
            purchases = abs(sum(others.mapped('amount_untaxed_signed'))) + abs(move.amount_untaxed_signed)
            uit = move.company_id._l10n_pe_lce_uit(date.year)
            limit = SELLER_LIMIT_UIT * uit
            if float_compare(purchases, limit, precision_digits=2) > 0:
                move.l10n_pe_lce_seller_warning = self.env._(
                    'Las liquidaciones de compra a %(seller)s en %(year)s suman S/ %(amount).2f y '
                    'pasan de 75 UIT (S/ %(limit).2f). Si sus ventas del año superan ese límite '
                    'ya no corresponde emitirle liquidaciones: consúltelo en SUNAT Operaciones en '
                    'Línea.', seller=partner.name, year=date.year, amount=purchases, limit=limit)

    # ------------------------------------------------------------------
    # Tipo de documento y numeración
    # ------------------------------------------------------------------
    def _get_l10n_latam_documents_domain(self):
        self.ensure_one()
        if self.journal_id.l10n_pe_lce_journal and self.move_type == 'in_invoice':
            return [('code', '=', '04'), ('country_id.code', '=', 'PE')]
        return super()._get_l10n_latam_documents_domain()

    def _is_manual_document_number(self):
        # El comprador numera la liquidación con su serie (no la digita).
        if self.journal_id.l10n_pe_lce_journal and self.move_type == 'in_invoice':
            return False
        return super()._is_manual_document_number()

    def _get_starting_sequence(self):
        if self.journal_id.l10n_pe_lce_journal and self.l10n_latam_document_type_id.code == '04':
            return '%s %s-00000000' % (self.l10n_latam_document_type_id.doc_code_prefix,
                                       self.journal_id.l10n_pe_lce_serie or 'L001')
        return super()._get_starting_sequence()

    def _search_default_journal(self):
        """El menú de liquidaciones abre su diario; las facturas de proveedor
        normales no lo proponen."""
        Journal = self.env['account.journal']
        company = self.company_id or self.env.company
        if self.env.context.get('l10n_pe_lce_default_journal'):
            journal = Journal.search([*Journal._check_company_domain(company),
                                      ('l10n_pe_lce_journal', '=', True)], limit=1)
            if journal:
                return journal
        journal = super()._search_default_journal()
        if journal.l10n_pe_lce_journal:
            other = Journal.search([*Journal._check_company_domain(company),
                                    ('type', '=', journal.type),
                                    ('l10n_pe_lce_journal', '=', False)], limit=1)
            journal = other or journal
        return journal

    def _l10n_pe_lce_serie_folio(self):
        """(serie, número) de ``L001-00000001``."""
        self.ensure_one()
        serie, _sep, folio = (self.l10n_latam_document_number or '').partition('-')
        return serie, folio

    def _l10n_pe_lce_number(self):
        serie, folio = self._l10n_pe_lce_serie_folio()
        return '%s-%s' % (serie, folio)

    def _l10n_pe_lce_filename(self):
        """``RUC-04-L001-00000001`` (anexo 6, numeral 6.1.3)."""
        self.ensure_one()
        return '%s-04-%s' % (self.company_id.vat, self._l10n_pe_lce_number())

    # ------------------------------------------------------------------
    # Retenciones
    # ------------------------------------------------------------------
    def _l10n_pe_lce_ir_taxes(self):
        company = self.company_id
        return company.l10n_pe_lce_ir_tax_id | company.l10n_pe_lce_ir_gold_tax_id

    def _l10n_pe_lce_withholding_taxes(self):
        return self.company_id.l10n_pe_lce_igv_tax_id | self._l10n_pe_lce_ir_taxes()

    def _l10n_pe_lce_ir_applies(self):
        """La renta se retiene salvo operación exonerada o inafecta, o importe
        de la operación (sin tributos, en soles) de hasta S/ 700."""
        self.ensure_one()
        if self.l10n_pe_lce_ir_exempt:
            return False
        lines = self.invoice_line_ids.filtered(lambda line: line.display_type == 'product')
        untaxed = sum(lines.mapped('price_subtotal'))
        company = self.company_id
        untaxed_pen = self.currency_id._convert(
            untaxed, company.currency_id, company,
            self.invoice_date or fields.Date.context_today(self))
        return float_compare(untaxed_pen, company.l10n_pe_lce_ir_min_amount, precision_digits=2) > 0

    def _l10n_pe_lce_sync_taxes(self):
        """Pone en cada línea las retenciones que corresponden: el IGV
        retenido en las gravadas y la retención de renta (4 % en el oro)."""
        for move in self.filtered(lambda m: m.l10n_pe_lce_required and m.state == 'draft'):
            company = move.company_id
            igv_tax = company.l10n_pe_lce_igv_tax_id
            ir_tax, gold_tax = company.l10n_pe_lce_ir_tax_id, company.l10n_pe_lce_ir_gold_tax_id
            if not (igv_tax and ir_tax and gold_tax):
                raise UserError(self.env._(
                    'Configure los impuestos de la liquidación de compra en Ajustes ▸ Perú.'))
            withholdings = move._l10n_pe_lce_withholding_taxes()
            ir_applies = move._l10n_pe_lce_ir_applies()
            for line in move.invoice_line_ids.filtered(lambda line: line.display_type == 'product'):
                taxes = line.tax_ids - withholdings
                igv = taxes.filtered(lambda tax: tax.l10n_pe_edi_tax_code == '1000')
                if igv:
                    if any(float_compare(tax.amount, -igv_tax.amount, precision_digits=2)
                           for tax in igv):
                        raise UserError(self.env._(
                            'La línea «%(line)s» tiene un IGV distinto del %(rate)s %% que retiene '
                            '«%(tax)s».', line=line.name, rate=-igv_tax.amount, tax=igv_tax.name))
                    taxes |= igv_tax
                if ir_applies:
                    gold = line.product_id.l10n_pe_lce_gold or move.l10n_pe_lce_operation_type == '0503'
                    taxes |= gold_tax if gold else ir_tax
                if taxes != line.tax_ids:
                    line.tax_ids = taxes

    @api.onchange('invoice_line_ids', 'l10n_pe_lce_ir_exempt', 'l10n_pe_lce_operation_type')
    def _onchange_l10n_pe_lce_withholdings(self):
        if self.l10n_pe_lce_required and self.company_id.l10n_pe_lce_igv_tax_id:
            self._l10n_pe_lce_sync_taxes()

    def action_l10n_pe_lce_compute_withholdings(self):
        self._l10n_pe_lce_sync_taxes()
        return True

    # ------------------------------------------------------------------
    # Validación y confirmación
    # ------------------------------------------------------------------
    def _l10n_pe_lce_check(self):
        """Datos que exige el anexo 6 antes de confirmar la liquidación."""
        self.ensure_one()
        errors = []
        company = self.company_id
        partner = self.partner_id.commercial_partner_id
        if not (company.vat and len(company.vat) == 11):
            errors.append(self.env._('La compañía no tiene un RUC válido.'))
        doc_type = partner.l10n_latam_identification_type_id.l10n_pe_vat_code
        if doc_type not in SELLER_DOC_TYPES or not partner.vat:
            errors.append(self.env._(
                'El vendedor debe ser una persona natural sin RUC identificada con DNI, carné de '
                'extranjería, pasaporte o cédula diplomática. Si su RUC fue dado de baja, '
                'identifíquelo con su DNI.'))
        if not partner.street or not partner.l10n_pe_district:
            errors.append(self.env._('Falta el domicilio del vendedor (dirección y distrito).'))
        if not self.l10n_pe_lce_partner_address_type:
            errors.append(self.env._('Indique la condición del domicilio del vendedor.'))
        if not self.l10n_pe_lce_place_street or not self.l10n_pe_lce_place_district_id \
                or not self.l10n_pe_lce_place_type:
            errors.append(self.env._(
                'Indique el lugar de la operación (dirección, distrito y condición).'))
        lines = self.invoice_line_ids.filtered(lambda line: line.display_type == 'product')
        if not lines:
            errors.append(self.env._('La liquidación de compra no tiene líneas.'))
        if len(lines) > 999:
            errors.append(self.env._('La liquidación de compra admite hasta 999 ítems.'))
        for line in lines:
            igv = line.tax_ids.filtered(lambda tax: tax.l10n_pe_edi_tax_code in IGV_CODES)
            if len(igv) != 1:
                errors.append(self.env._(
                    'La línea «%s» debe tener un solo impuesto de IGV: gravado, exonerado o '
                    'inafecto.', line.name))
            if line.quantity <= 0 or line.price_unit < 0:
                errors.append(self.env._(
                    'La línea «%s» debe tener cantidad y precio positivos.', line.name))
        if self.l10n_pe_lce_license_plate and len(self.l10n_pe_lce_license_plate.replace('-', '')) > 8:
            errors.append(self.env._('La placa tiene más de ocho caracteres.'))
        if errors:
            raise UserError(self.env._('No se puede confirmar la liquidación de compra %(name)s:\n%(errors)s',
                                       name=self.display_name,
                                       errors='\n'.join('· %s' % error for error in errors)))

    def _post(self, soft=True):
        settlements = self.filtered(lambda m: m.l10n_pe_lce_required and m.state == 'draft')
        for move in settlements:
            move._l10n_pe_lce_sync_taxes()
            move._l10n_pe_lce_check()
        posted = super()._post(soft)
        posted_settlements = posted.filtered('l10n_pe_lce_required')
        posted_settlements.filtered(lambda m: not m.l10n_pe_lce_status).l10n_pe_lce_status = 'to_send'
        to_send = posted_settlements.filtered(
            lambda m: m.company_id.l10n_pe_lce_send_on_post and m.l10n_pe_lce_status == 'to_send')
        if to_send:
            to_send.action_l10n_pe_lce_send()
        return posted

    def button_draft(self):
        """Una liquidación aceptada por SUNAT no vuelve a borrador: se revierte."""
        for move in self:
            if move.l10n_pe_lce_status in ('sent', 'reversing'):
                raise UserError(self.env._(
                    'La liquidación de compra %s fue aceptada por SUNAT: para anularla, '
                    'reviértala.', move.display_name))
        return super().button_draft()

    def _l10n_pe_lce_values(self):
        """Datos del XML y de la representación impresa."""
        self.ensure_one()
        company = self.company_id
        partner = self.partner_id.commercial_partner_id
        currency = self.currency_id
        ir_taxes = self._l10n_pe_lce_ir_taxes()
        withholdings = self._l10n_pe_lce_withholding_taxes()
        base_lines, _tax_lines = self._get_rounded_base_and_tax_lines()
        lines = []
        totals = {'1000': [0.0, 0.0], '9997': [0.0, 0.0], '9998': [0.0, 0.0]}
        ir_base = ir_total = 0.0
        for index, base_line in enumerate(
                [bl for bl in base_lines if bl['record'] and bl['record'].display_type == 'product'], 1):
            line = base_line['record']
            details = base_line['tax_details']
            untaxed = line.price_subtotal
            igv_amount = ir_amount = 0.0
            igv_rate = ir_rate = 0.0
            for tax_data in details['taxes_data']:
                tax = tax_data['tax']
                if tax.l10n_pe_edi_tax_code == '1000':
                    igv_amount += tax_data['tax_amount_currency']
                    igv_rate = tax.amount
                elif tax in ir_taxes:
                    ir_amount -= tax_data['tax_amount_currency']
                    ir_rate = -tax.amount
            igv_tax = (line.tax_ids - withholdings).filtered(
                lambda tax: tax.l10n_pe_edi_tax_code in IGV_CODES)[:1]
            igv_code = igv_tax.l10n_pe_edi_tax_code or '1000'
            totals.setdefault(igv_code, [0.0, 0.0])
            totals[igv_code][0] += untaxed
            totals[igv_code][1] += igv_amount
            if ir_amount:
                ir_base += untaxed
                ir_total += ir_amount
            quantity = line.quantity
            lines.append({
                'record': line,
                'sequence': index,
                'quantity': quantity,
                'uom_code': line.product_uom_id.l10n_pe_edi_measure_unit_code or 'NIU',
                'uom_name': line.product_uom_id.name or '',
                'description': (line.name or line.product_id.display_name or '').replace('\n', ' ')[:500],
                'default_code': line.product_id.default_code or '',
                'unspsc': line.product_id.unspsc_code_id.code or '',
                'price_unit': untaxed / quantity if quantity else 0.0,
                'price_with_tax': (untaxed + igv_amount) / quantity if quantity else 0.0,
                'untaxed': untaxed,
                'igv': igv_amount,
                'igv_rate': igv_rate,
                'igv_code': igv_code,
                'affectation': igv_tax.l10n_pe_edi_affectation_reason or '10',
                'ir': ir_amount,
                'ir_rate': ir_rate,
                'igv_label': self._l10n_pe_lce_rate_label(igv_rate),
                'ir_label': self._l10n_pe_lce_rate_label(ir_rate) if ir_rate else '-',
            })
        untaxed = sum(line['untaxed'] for line in lines)
        igv = sum(line['igv'] for line in lines)
        ir = sum(line['ir'] for line in lines)
        # Gravadas siempre (anexo 6, dato 35); exoneradas e inafectas si las hay.
        tax_subtotals = [(code, base, tax) for code, (base, tax) in totals.items()
                         if code == '1000' or base]
        tax_subtotals.append(('3000', ir_base or untaxed, ir_total))
        subtotal = untaxed + igv
        return {
            'number': self._l10n_pe_lce_number(),
            'buyer_address': self._l10n_pe_lce_address(
                company.partner_id.street, company.partner_id.street2, company.partner_id.l10n_pe_district),
            'seller_vat': partner.vat,
            'seller_doc_type': partner.l10n_latam_identification_type_id.l10n_pe_vat_code,
            'seller_doc_name': partner.l10n_latam_identification_type_id.name,
            'seller_name': partner.name,
            'seller_address': self._l10n_pe_lce_address(
                partner.street, partner.street2, partner.l10n_pe_district),
            'place_address': self._l10n_pe_lce_address(
                self.l10n_pe_lce_place_street, False, self.l10n_pe_lce_place_district_id),
            'lines': lines,
            'tax_subtotals': tax_subtotals,
            'untaxed': untaxed,
            'taxed_base': totals['1000'][0],
            'exonerated_base': totals['9997'][0],
            'unaffected_base': totals['9998'][0],
            'igv': igv,
            'ir': ir,
            'tax_amount': igv,
            'subtotal': subtotal,
            'net': subtotal - igv - ir,
            'currency': currency,
        }

    @api.model
    def _l10n_pe_lce_rate_label(self, rate):
        """«1,5 %», «18 %»."""
        return '%s %%' % ('%g' % rate).replace('.', ',')

    @api.model
    def _l10n_pe_lce_address(self, street, urbanization, district):
        """Dirección con distrito, provincia, departamento y ubigeo."""
        city = district.city_id
        return {
            'street': (street or '').strip()[:250],
            'urbanization': (urbanization or '').strip()[:25],
            'ubigeo': district.code or '',
            'district': district.name or '',
            'province': city.name or '',
            'department': city.state_id.name or '',
        }

    # ------------------------------------------------------------------
    # XML, firma y envío
    # ------------------------------------------------------------------
    def _l10n_pe_lce_generate_xml(self):
        """XML con el hueco de la firma (``ds:Signature Id="placeholder"``),
        listo para el servicio de firma del operador."""
        self.ensure_one()
        xml_content = self.env['account.edi.xml.ubl_pe_lce']._export_purchase_settlement(self)
        edi_tree = objectify.fromstring(xml_content)
        edi_tree.find('{*}UBLVersionID').addprevious(objectify.fromstring(
            self.env['ir.qweb']._render('l10n_pe_edi.ubl_pe_21_ubl_extensions_empty_signature')))
        return etree.tostring(edi_tree, xml_declaration=True, encoding='UTF-8')

    def action_l10n_pe_lce_download_xml(self):
        """Descarga el XML sin firmar (para revisión)."""
        self.ensure_one()
        attachment = self.env['ir.attachment'].create({
            'name': '%s.xml' % self._l10n_pe_lce_filename(),
            'res_model': self._name, 'res_id': self.id,
            'raw': self._l10n_pe_lce_generate_xml(), 'mimetype': 'application/xml'})
        return {'type': 'ir.actions.act_url', 'target': 'self',
                'url': '/web/content/%d?download=true' % attachment.id}

    def _l10n_pe_lce_sign_and_send(self, edi_format, filename, edi_str):
        """Firma y envía con el operador de la compañía. Los servicios de
        ``l10n_pe_edi`` (``_l10n_pe_edi_sign_service_<operador>``) comparten
        contrato, y los operadores de otros módulos (Factory HKA) lo siguen:
        se eligen por nombre. Con SUNAT directo la liquidación va al servicio
        de facturas (anexo 6)."""
        self.ensure_one()
        company = self.company_id
        provider = company.l10n_pe_edi_provider
        service = getattr(edi_format, '_l10n_pe_edi_sign_service_%s' % provider, None)
        if not service:
            return {'error': self.env._(
                'El operador electrónico «%s» no envía liquidaciones de compra.', provider),
                'blocking_level': 'error'}
        return service(company, filename, edi_str, '04')

    def _l10n_pe_lce_retrieve_cdr(self, edi_format, result):
        """SUNAT ya tenía la liquidación (códigos 1033 y 4000, p. ej. un envío
        anterior que no se llegó a guardar): se recupera su CDR."""
        self.ensure_one()
        if result.get('code') not in ('1033', '4000'):
            return result
        serie, folio = self._l10n_pe_lce_serie_folio()
        retrieved = edi_format._l10n_pe_edi_retrieve_cdr(
            self.company_id.l10n_pe_edi_provider, self.company_id,
            {'serie': serie, 'folio': folio}, '04')
        if retrieved.get('error') or not retrieved.get('cdr'):
            return result
        self.message_post(body=self.env._(
            'SUNAT ya tenía registrada la liquidación de compra: se recuperó su constancia.'))
        return {'success': True, 'xml_document': result.get('xml_document'), 'cdr': retrieved['cdr']}

    def action_l10n_pe_lce_send(self):
        """Firma la liquidación de compra y la envía con el operador de la compañía."""
        edi_format = self.env.ref('l10n_pe_edi.edi_pe_ubl_2_1')
        for move in self:
            if not move.l10n_pe_lce_required or move.state != 'posted' \
                    or move.l10n_pe_lce_status != 'to_send':
                raise UserError(self.env._(
                    '%s no es una liquidación de compra confirmada por enviar.', move.display_name))
            move._l10n_pe_lce_check_deadline()
            filename = move._l10n_pe_lce_filename()
            result = move._l10n_pe_lce_sign_and_send(edi_format, filename, move._l10n_pe_lce_generate_xml())
            if result.get('error'):
                result = move._l10n_pe_lce_retrieve_cdr(edi_format, result)
            if result.get('error'):
                move.l10n_pe_lce_message = result['error']
                continue
            documents = [('%s.xml' % filename, result['xml_document'])]
            if result.get('cdr'):
                documents.append(('R-%s.xml' % filename, result['cdr']))
            attachment = self.env['ir.attachment'].create({
                'name': '%s.zip' % filename, 'res_model': move._name, 'res_id': move.id,
                'type': 'binary', 'mimetype': 'application/zip',
                'raw': edi_format._l10n_pe_edi_zip_edi_document(documents),
            })
            move.write({
                'l10n_pe_lce_status': 'sent',
                'l10n_pe_lce_message': False,
                'l10n_pe_lce_accepted_date': _lima_today(),
            })
            if move.company_id.l10n_pe_edi_test_env:
                body = self.env._('Liquidación de compra %s aceptada en el entorno de prueba: no '
                                  'tiene validez ante SUNAT.', move._l10n_pe_lce_number())
            else:
                body = self.env._('Liquidación de compra %s aceptada por SUNAT.',
                                  move._l10n_pe_lce_number())
            move.message_post(body=body, attachment_ids=attachment.ids)
        return True

    def action_l10n_pe_lce_print(self):
        """Representación impresa de la liquidación de compra."""
        if self.filtered(lambda move: not move.l10n_pe_lce_required or move.state == 'draft'):
            raise UserError(self.env._('Solo se imprimen liquidaciones de compra confirmadas.'))
        return self.env.ref('al_l10n_pe_edi_purchase_settlement.action_report_purchase_settlement') \
            .report_action(self)

    def _l10n_pe_lce_check_deadline(self):
        """Avisa (sin bloquear) si se envía después del día siguiente a la
        emisión: SUNAT ya no la tiene como liquidación de compra."""
        self.ensure_one()
        deadline = self.invoice_date + timedelta(days=SEND_DAYS)
        if _lima_today() > deadline:
            self.message_post(body=self.env._(
                'Envío fuera de plazo: la liquidación de compra emitida el %(date)s debía enviarse '
                'hasta el %(deadline)s (R.S. 097-2012/SUNAT, art. 12.1.b). Fuera de plazo no tiene '
                'calidad de comprobante.', date=self.invoice_date.strftime('%d/%m/%Y'),
                deadline=deadline.strftime('%d/%m/%Y')))

    def _l10n_pe_lce_xml_attachment(self):
        """ZIP con el XML firmado y la constancia de SUNAT."""
        self.ensure_one()
        return self.env['ir.attachment'].search([
            ('res_model', '=', self._name), ('res_id', '=', self.id),
            ('name', '=', '%s.zip' % self._l10n_pe_lce_filename())], limit=1, order='id desc')

    def _l10n_pe_lce_digest(self):
        """Valor resumen (``DigestValue``) del XML firmado, para la
        representación impresa."""
        self.ensure_one()
        attachment = self._l10n_pe_lce_xml_attachment()
        if not attachment:
            return ''
        edi_format = self.env['account.edi.format']
        try:
            xml = edi_format._l10n_pe_edi_unzip_edi_document(attachment.raw)
            digest = etree.fromstring(xml).find('.//{http://www.w3.org/2000/09/xmldsig#}DigestValue')
        except (etree.LxmlError, ValueError, KeyError):
            return ''
        return digest.text if digest is not None and digest.text else ''

    # ------------------------------------------------------------------
    # Reversión (resumen diario de reversiones RR)
    # ------------------------------------------------------------------
    def _l10n_pe_lce_reversal_sequence_code(self):
        # Un solo correlativo RR por RUC: con al_l10n_pe_retention se usa el suyo.
        if self.env['ir.sequence'].sudo().search_count(
                [('code', '=', RETENTION_REVERSAL_SEQUENCE)], limit=1):
            return RETENTION_REVERSAL_SEQUENCE
        return LCE_REVERSAL_SEQUENCE

    def _l10n_pe_lce_reversal_values(self):
        """Nombre de archivo e identificador del resumen RR. El ``cbc:ID`` va
        sin el RUC; el archivo, con él. En los reintentos se reutiliza."""
        self.ensure_one()
        today = _lima_today()
        filename = self.l10n_pe_lce_reversal_filename
        if not filename:
            # La secuencia es técnica y global (sin compañía): el contable
            # puede no tener acceso de escritura a ir.sequence.
            sequence_sudo = self.env['ir.sequence'].sudo().with_context(ir_sequence_date=today)
            number = sequence_sudo.next_by_code(self._l10n_pe_lce_reversal_sequence_code())
            filename = '%s-%s' % (self.company_id.vat, number)
            self.l10n_pe_lce_reversal_filename = filename
        return {'filename': filename, 'number': filename.split('-', 1)[1], 'issue_date': today}

    def _l10n_pe_lce_generate_reversal_xml(self, values):
        self.ensure_one()
        serie, folio = self._l10n_pe_lce_serie_folio()
        return self.env['ir.qweb']._render('al_l10n_pe_edi_purchase_settlement.lce_reversal_summary', {
            'company': self.company_id,
            'reversal_number': values['number'],
            'reference_date': self.invoice_date,
            'issue_date': values['issue_date'],
            'lines': [{'serie': serie, 'folio': int(folio) if folio.isdigit() else folio,
                       'reason': self.l10n_pe_lce_reversal_reason}],
        }).encode()

    def _l10n_pe_lce_reversal_credentials(self, edi_format):
        """SUNAT recibe los resúmenes de reversiones en el servicio de
        retenciones y percepciones (anexo 22); Digiflow, en el suyo."""
        self.ensure_one()
        company = self.company_id
        if company.l10n_pe_edi_provider == 'digiflow':
            return edi_format._l10n_pe_edi_get_digiflow_credentials(company)
        credentials = edi_format._l10n_pe_edi_get_sunat_credentials(company)
        credentials['wsdl'] = SUNAT_REVERSAL_WSDL['test' if company.l10n_pe_edi_test_env else 'prod']
        return credentials

    def _l10n_pe_lce_reversal_send(self, edi_format, filename, edi_str):
        """Paso 1 (sendSummary): ``{'xml_document', 'cdr', 'cdr_number'}`` o
        ``{'error', 'blocking_level'}``, como los servicios de baja."""
        self.ensure_one()
        company = self.company_id
        provider = company.l10n_pe_edi_provider
        if provider in ('sunat', 'digiflow'):
            return edi_format._l10n_pe_edi_cancel_invoices_step_1_sunat_digiflow_common(
                company, self, filename, edi_str, self._l10n_pe_lce_reversal_credentials(edi_format))
        service = getattr(edi_format, '_l10n_pe_edi_cancel_invoices_step_1_%s' % provider, None)
        if not service:
            return {'error': self.env._(
                'El operador electrónico «%s» no envía resúmenes de reversiones.', provider),
                'blocking_level': 'error'}
        return service(company, self, filename, edi_str)

    def _l10n_pe_lce_reversal_status(self, edi_format, ticket):
        """Paso 2 (getStatus): ``{'success', 'cdr'}`` o ``{'error',
        'blocking_level'}`` (``info``: SUNAT aún procesa)."""
        self.ensure_one()
        company = self.company_id
        provider = company.l10n_pe_edi_provider
        if provider in ('sunat', 'digiflow'):
            return edi_format._l10n_pe_edi_cancel_invoices_step_2_sunat_digiflow_common(
                company, [], ticket, self._l10n_pe_lce_reversal_credentials(edi_format))
        service = getattr(edi_format, '_l10n_pe_edi_cancel_invoices_step_2_%s' % provider, None)
        if not service:
            return {'error': self.env._(
                'El operador electrónico «%s» no consulta resúmenes de reversiones.', provider),
                'blocking_level': 'error'}
        return service(company, [], ticket)

    def action_l10n_pe_lce_reverse(self):
        """Paso 1: envía el resumen diario de reversiones y guarda el ticket."""
        edi_format = self.env.ref('l10n_pe_edi.edi_pe_ubl_2_1')
        for move in self:
            if move.l10n_pe_lce_status != 'sent':
                raise UserError(self.env._('Solo se revierte una liquidación de compra aceptada por SUNAT.'))
            if not move.l10n_pe_lce_reversal_reason:
                raise UserError(self.env._('Indique el motivo de la reversión.'))
            accepted = move.l10n_pe_lce_accepted_date or move.invoice_date
            if _lima_today() > accepted + timedelta(days=REVERSAL_DAYS):
                raise UserError(self.env._(
                    'El plazo para revertir la liquidación de compra %(name)s venció el %(date)s: '
                    'son siete días calendario desde el día siguiente a su aceptación (art. 29-F).',
                    name=move.display_name,
                    date=(accepted + timedelta(days=REVERSAL_DAYS)).strftime('%d/%m/%Y')))
            values = move._l10n_pe_lce_reversal_values()
            result = move._l10n_pe_lce_reversal_send(
                edi_format, values['filename'], move._l10n_pe_lce_generate_reversal_xml(values))
            if result.get('error'):
                move.l10n_pe_lce_message = result['error']
                continue
            attachment = self.env['ir.attachment'].create({
                'name': '%s.xml' % values['filename'], 'res_model': move._name, 'res_id': move.id,
                'type': 'binary', 'raw': result['xml_document'], 'mimetype': 'application/xml'})
            move.write({
                'l10n_pe_lce_status': 'reversing',
                'l10n_pe_lce_reversal_ticket': result['cdr_number'],
                'l10n_pe_lce_message': False,
            })
            move.message_post(body=self.env._(
                'Reversión de la liquidación de compra %(number)s enviada a SUNAT (ticket '
                '%(ticket)s). Motivo: %(reason)s', number=move._l10n_pe_lce_number(),
                ticket=result['cdr_number'], reason=move.l10n_pe_lce_reversal_reason),
                attachment_ids=attachment.ids)
        return True

    def action_l10n_pe_lce_check_reversal(self):
        """Paso 2: consulta el ticket; con la reversión aceptada, anula el
        asiento (el número no se vuelve a usar)."""
        edi_format = self.env.ref('l10n_pe_edi.edi_pe_ubl_2_1')
        for move in self:
            if move.l10n_pe_lce_status != 'reversing' or not move.l10n_pe_lce_reversal_ticket:
                raise UserError(self.env._(
                    '%s no tiene una reversión en proceso.', move.display_name))
            result = move._l10n_pe_lce_reversal_status(edi_format, move.l10n_pe_lce_reversal_ticket)
            if result.get('error'):
                move.l10n_pe_lce_message = result['error']
                if result.get('blocking_level') != 'info':
                    # Rechazada (p. ej. hay pagos registrados en SUNAT): la
                    # liquidación sigue vigente; un nuevo intento usa otro RR.
                    move.write({'l10n_pe_lce_status': 'sent', 'l10n_pe_lce_reversal_ticket': False,
                                'l10n_pe_lce_reversal_filename': False})
                continue
            attachment = self.env['ir.attachment'].create({
                'name': 'R-%s.xml' % move.l10n_pe_lce_reversal_filename,
                'res_model': move._name, 'res_id': move.id, 'type': 'binary',
                'datas': base64.b64encode(result['cdr']), 'mimetype': 'application/xml'})
            move.write({'l10n_pe_lce_status': 'reversed', 'l10n_pe_lce_message': False})
            body = self.env._('SUNAT aceptó la reversión de la liquidación de compra %s.',
                              move._l10n_pe_lce_number())
            if move.state == 'posted':
                if move.line_ids.filtered(lambda line: line.reconciled or line.matched_debit_ids
                                          or line.matched_credit_ids):
                    body = Markup('%s<br/>%s') % (body, self.env._(
                        'El asiento tiene pagos conciliados: rompa la conciliación y anúlelo.'))
                else:
                    move.button_draft()
                    move.button_cancel()
            move.message_post(body=body, attachment_ids=attachment.ids)
        return True
