# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Solo el primer pedido cuando se facturan varios juntos (el resto
    # queda en ``invoice_origin``).
    sale_id = fields.Many2one(
        'sale.order', string='Orden de venta', index='btree_not_null',
        copy=False, check_company=True)
    external_purchase = fields.Char(
        string='OC. externa', copy=False,
        help='Orden de compra externa del cliente, tomada del pedido de venta.')
    is_credit = fields.Boolean(
        string='Es Crédito', compute='_compute_is_credit', store=True)

    @api.depends('invoice_date', 'invoice_date_due')
    def _compute_is_credit(self):
        """Contado o crédito con el mismo criterio que el XML de la factura
        electrónica (``_l10n_pe_edi_get_payment_means``): crédito si vence
        después de la emisión.

        Antes se decidía por «el plazo de pago tiene líneas», pero en v19
        todos los plazos las tienen —también «Pago inmediato»—, y el PDF
        imprimía CRÉDITO en ventas al contado que el XML declaraba Contado.
        """
        for move in self:
            move.is_credit = move._l10n_pe_edi_get_payment_means() == 'Credito'

    def _l10n_pe_report_exchange_rate(self):
        """Tipo de cambio que usó la factura (moneda de la compañía por
        unidad de la moneda del documento), o 0 si está en la moneda de la
        compañía.

        Antes el reporte buscaba una tasa con fecha idéntica a la de emisión
        y no mostraba nada si ese día no se había cargado.
        """
        self.ensure_one()
        if self.currency_id == self.company_currency_id or not self.invoice_currency_rate:
            return 0.0
        return 1.0 / self.invoice_currency_rate

    def _l10n_pe_report_company_address(self):
        """Dirección de la compañía en una línea (ver ``_l10n_pe_report_address``)."""
        self.ensure_one()
        return self._l10n_pe_report_address(self.company_id.partner_id)

    def _l10n_pe_report_partner_address(self):
        """Dirección del cliente o proveedor en una línea, sin su nombre."""
        self.ensure_one()
        return self._l10n_pe_report_address(self.partner_id)

    @api.model
    def _l10n_pe_report_address(self, partner):
        """Dirección en una línea, sin el nombre del contacto.

        ``contact_address`` incluye el nombre (repetido bajo el título del
        reporte) y separa las partes con saltos de línea que el PDF no
        muestra. Tampoco sirve ``_display_address``: el formato peruano de
        ``l10n_pe`` es ``%(zip)s%(city)s``, sin espacio («15046San Isidro»).
        """
        district = partner.l10n_pe_district.name if 'l10n_pe_district' in partner._fields else ''
        parts = [partner.street, partner.street2, district, partner.city,
                 partner.state_id.name, partner.zip]
        address = []
        for part in parts:
            part = ' '.join((part or '').split())
            # Distrito y ciudad suelen coincidir («San Isidro, San Isidro»).
            if part and (not address or address[-1].lower() != part.lower()):
                address.append(part)
        return ', '.join(address)

    # ------------------------------------------------------------------
    # Datos auxiliares para las plantillas
    # El QR y el monto en letras NO se recalculan aquí: los provee el core
    # (l10n_pe_edi) vía _l10n_pe_edi_get_extra_report_values(), que extrae
    # el QR oficial (con hash de la firma) del XML firmado, y
    # _l10n_pe_edi_amount_to_text().
    # ------------------------------------------------------------------
    def _get_report_base_filename_custom(self):
        name_custom = self._get_move_display_name()
        name_client = self.partner_id.parent_id.name or self.partner_id.name
        return f'{name_custom} {name_client}'

    def get_amount_discount(self):
        """Descuento total del comprobante, en base imponible (sin IGV),
        igual que las «Op. gravadas» junto a las que se imprime.

        Suma los dos tipos de descuento:

        * el porcentaje por línea: lo que la línea valdría sin descuento
          menos su subtotal;
        * el descuento global: líneas en negativo.

        Antes solo sumaba las líneas negativas y con IGV (``price_total``),
        mientras que la fila se mostraba según el porcentaje por línea: con
        descuento % salía 0.00 y con descuento global no salía la fila.
        """
        self.ensure_one()
        amount = 0.0
        lines = self.invoice_line_ids.filtered(
            lambda x: x.display_type in ('product', 'discount'))
        for line in lines:
            if line.price_subtotal < 0:
                amount += abs(line.price_subtotal)
            elif line.discount:
                undiscounted = line.tax_ids.compute_all(
                    line.price_unit, currency=self.currency_id,
                    quantity=line.quantity, product=line.product_id,
                    partner=self.partner_id)['total_excluded']
                amount += undiscounted - line.price_subtotal
        return self.currency_id.round(amount)

    def get_data_dues(self):
        """Cuotas de crédito a mostrar en el reporte, con el mismo criterio
        que el XML (``_add_invoice_payment_terms_nodes`` de l10n_pe_edi):
        una cuota por apunte de vencimiento, ordenadas por fecha, y a la
        primera se le descuenta la detracción.

        Antes se usaba ``payment_term_details``, que el core solo llena
        mientras la factura está pendiente: al reimprimir una factura
        pagada salía una sola cuota de 0.00.
        """
        self.ensure_one()
        spot = self._l10n_pe_edi_get_spot() if self.is_sale_document() else {}
        spot_amount = spot.get('spot_amount', 0.0) if spot else 0.0
        dues = []
        term_lines = self.line_ids.filtered(
            lambda l: l.display_type == 'payment_term').sorted('date_maturity')
        for idx, line in enumerate(term_lines):
            amount = abs(line.amount_currency)
            if idx == 0:
                amount -= spot_amount
            dues.append({
                'nro': idx + 1,
                'amount': amount,
                'date': line.date_maturity.strftime('%d/%m/%Y') if line.date_maturity else '',
            })
        return dues

    def _l10n_pe_report_currency_label(self):
        """Nombre de la moneda del documento para el reporte. Antes era
        fijo («SOLES» salvo USD): una factura en euros imprimía SOLES."""
        self.ensure_one()
        labels = {'PEN': 'SOLES', 'USD': 'DÓLARES AMERICANOS', 'EUR': 'EUROS'}
        currency = self.currency_id
        return labels.get(currency.name) or (
            currency.currency_unit_label or currency.full_name or currency.name or '').upper()

    def _l10n_pe_report_igv_label(self):
        """Etiqueta del IGV con la tasa realmente aplicada: 18 % general o
        10 % (MYPE de restaurantes y hoteles). Con tasas mezcladas o sin
        IGV, solo «IGV»."""
        self.ensure_one()
        rates = set(self.invoice_line_ids.tax_ids.flatten_taxes_hierarchy().filtered(
            lambda t: t.l10n_pe_edi_tax_code == '1000').mapped('amount'))
        if len(rates) == 1:
            return 'IGV (%s%%)' % ('%g' % rates.pop())
        return 'IGV'

    def _l10n_pe_report_origin_move(self):
        """Documento que modifica una nota de crédito (``reversed_entry_id``)
        o de débito (``debit_origin_id``)."""
        self.ensure_one()
        return self.reversed_entry_id or self.debit_origin_id

    def _l10n_pe_get_national_bank_account_number(self):
        """Cuenta del Banco de la Nación de la compañía, para el bloque de
        detracción del reporte (mismo criterio que usa el core en
        ``_l10n_pe_edi_get_spot``)."""
        self.ensure_one()
        national_bank = self.env.ref(
            'l10n_pe.peruvian_national_bank', raise_if_not_found=False)
        if not national_bank:
            return ''
        account = self.company_id.bank_ids.filtered(
            lambda b: b.bank_id == national_bank)
        return account[0].acc_number if account else ''

    # ------------------------------------------------------------------
    # Detalle tributario SUNAT — campos almacenados, un solo cálculo
    # ------------------------------------------------------------------
    l10n_pe_edi_amount_exonerated = fields.Monetary(
        string='Monto Exonerado', compute='_compute_tax_amounts_stored', store=True)
    l10n_pe_edi_amount_igv = fields.Monetary(
        string='IGV', compute='_compute_tax_amounts_stored', store=True)
    l10n_pe_edi_amount_base = fields.Monetary(
        string='Base Imponible', compute='_compute_tax_amounts_stored', store=True)
    l10n_pe_edi_amount_ivap = fields.Monetary(
        string='IVAP', compute='_compute_tax_amounts_stored', store=True)
    l10n_pe_edi_amount_isc = fields.Monetary(
        string='ISC', compute='_compute_tax_amounts_stored', store=True)
    l10n_pe_edi_amount_unaffected = fields.Monetary(
        string='Operaciones Inafectas', compute='_compute_tax_amounts_stored', store=True)
    l10n_pe_edi_amount_export = fields.Monetary(
        string='Operaciones de Exportación', compute='_compute_tax_amounts_stored', store=True)
    l10n_pe_edi_amount_free = fields.Monetary(
        string='Operaciones Gratuitas', compute='_compute_tax_amounts_stored', store=True)
    l10n_pe_edi_amount_others = fields.Monetary(
        string='Otros Tributos', compute='_compute_tax_amounts_stored', store=True)
    l10n_pe_edi_amount_icbper = fields.Monetary(
        string='ICBPER', compute='_compute_tax_amounts_stored', store=True)

    _TAX_MOVE_TYPES = ('out_invoice', 'in_invoice', 'out_refund', 'in_refund')

    # Campo del desglose → clave de ``_compute_tax_breakdown``.
    _TAX_AMOUNT_FIELDS = {
        'l10n_pe_edi_amount_base': 'base',
        'l10n_pe_edi_amount_igv': 'igv',
        'l10n_pe_edi_amount_ivap': 'ivap',
        'l10n_pe_edi_amount_isc': 'isc',
        'l10n_pe_edi_amount_icbper': 'icbper',
        'l10n_pe_edi_amount_unaffected': 'unaffected',
        'l10n_pe_edi_amount_exonerated': 'exonerated',
        'l10n_pe_edi_amount_export': 'export',
        'l10n_pe_edi_amount_free': 'free',
        'l10n_pe_edi_amount_others': 'others',
    }

    @api.depends('move_type', 'company_id', 'line_ids.tax_ids',
                 'line_ids.tax_ids.l10n_pe_edi_tax_code',
                 'line_ids.price_subtotal', 'amount_total', 'currency_id')
    def _compute_tax_amounts_stored(self):
        # Solo comprobantes de compañías peruanas: el desglose es la
        # representación impresa SUNAT y no tiene sentido en el resto.
        # Sin try/except: un error del agregador EDI es un fallo real y
        # se deja ver en vez de guardar ceros.
        for move in self:
            if move.move_type not in move._TAX_MOVE_TYPES or move.country_code != 'PE':
                move._reset_tax_amounts_stored()
                continue
            move._update_stored_tax_amounts(
                move._compute_tax_breakdown(move._prepare_edi_tax_details()))

    def _update_stored_tax_amounts(self, tax_amounts):
        self.update({
            field: round(tax_amounts[key], 2)
            for field, key in self._TAX_AMOUNT_FIELDS.items()
        })

    def _reset_tax_amounts_stored(self):
        self.update(dict.fromkeys(self._TAX_AMOUNT_FIELDS, 0.0))

    def _compute_tax_breakdown(self, tax_details):
        """Clasifica los impuestos del detalle EDI nativo según el código de
        tributo SUNAT (catálogo 05, ``l10n_pe`` ``account_tax.py``):

        * 1000 IGV, 1016 IVAP, 2000 ISC, 7152 ICBPER y 9999 otros → importe;
        * 9995 exportación, 9996 gratuito, 9997 exonerado, 9998 inafecto →
          base (valor de la operación).

        Antes el 9996 (gratuito) iba a «otros» y el 9995 (exportación) no
        se contaba: el PDF no cuadraba con el XML en esas operaciones.
        """
        tax_amounts = dict.fromkeys(self._TAX_AMOUNT_FIELDS.values(), 0.0)
        tax_keys = {'1000': 'igv', '1016': 'ivap', '2000': 'isc',
                    '7152': 'icbper', '9999': 'others'}
        base_keys = {'9995': 'export', '9996': 'free',
                     '9997': 'exonerated', '9998': 'unaffected'}
        for tax_detail in tax_details.get('tax_details', {}).values():
            tax = tax_detail.get('grouping_key', self.env['account.tax'])
            tax_code = tax.l10n_pe_edi_tax_code if tax else ''
            # Claves *_currency: moneda del documento (igual a la de compañía
            # en facturas PEN). Con 'tax_amount'/'base_amount' (moneda de
            # compañía) una factura USD mostraba el desglose en soles junto a
            # un importe total en dólares.
            amount = tax_detail.get('tax_amount_currency', 0.0)
            base = tax_detail.get('base_amount_currency', 0.0)
            if tax_code == '1000':
                tax_amounts['base'] += base
            if tax_code in tax_keys:
                tax_amounts[tax_keys[tax_code]] += amount
            elif tax_code in base_keys:
                tax_amounts[base_keys[tax_code]] += base

        # Líneas sin impuesto se consideran exoneradas según SUNAT
        tax_amounts['exonerated'] += sum(self.invoice_line_ids.filtered(
            lambda l: not l.tax_ids).mapped('price_subtotal'))
        return tax_amounts
