# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_round

DETRACTION_OPERATION_TYPES = ('1001', '1002', '1003', '1004')
# Catálogo 51 de SUNAT: tipo de operación 100x según el código del
# catálogo 54 (los demás van con 1001).
DETRACTION_OPERATION_BY_CODE = {
    '004': '1002',  # recursos hidrobiológicos
    '026': '1003',  # transporte de pasajeros
    '027': '1004',  # transporte de bienes (carga)
}
DEFAULT_MIN_AMOUNT = 700.0

# Tabla 5.5 del instructivo de depósito masivo del Banco de la Nación:
# tipos de operación sujetas al sistema.
BN_OPERATION_TYPES = [
    ('01', '01 - Venta de bienes, prestación de servicios o contratos de '
           'construcción gravados con el IGV'),
    ('02', '02 - Retiro de bienes gravados con el IGV'),
    ('03', '03 - Traslado de bienes fuera del centro de producción que no se '
           'origina en una venta'),
    ('04', '04 - Venta de bienes gravada con el IGV a través de la Bolsa de '
           'Productos'),
    ('05', '05 - Venta de bienes exonerada del IGV'),
]


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_detraction_operation_type = fields.Selection(
        BN_OPERATION_TYPES,
        string='Tipo de operación de la detracción', default='01',
        help='Tipo de operación sujeta al sistema (tabla 5.5 del instructivo '
             'del Banco de la Nación). Se informa en el archivo de depósito '
             'masivo de detracciones.')

    l10n_pe_detraction_applies = fields.Boolean(
        string='Sujeta a detracción',
        compute='_compute_l10n_pe_detraction_applies', store=True)
    l10n_pe_detraction_type_id = fields.Many2one(
        'l10n_pe.detraction.type', string='Tipo de detracción',
        compute='_compute_l10n_pe_detraction_type_id', store=True,
        readonly=False,
        help='Código dominante (mayor porcentaje) entre los productos de '
             'la factura; puede corregirse manualmente en borrador.')
    l10n_pe_detraction_percent = fields.Float(
        string='% detracción', digits=(5, 2),
        compute='_compute_l10n_pe_detraction_percent', store=True,
        readonly=False)
    l10n_pe_detraction_amount = fields.Monetary(
        string='Monto de detracción',
        currency_field='company_currency_id',
        compute='_compute_l10n_pe_detraction_amount', store=True,
        help='Detracción en soles, redondeada a enteros (regla SUNAT), '
             'sobre el importe total con IGV convertido a soles al T.C. venta oficial de la fecha de emisión.')
    l10n_pe_detraction_net = fields.Monetary(
        string='Neto tras detracción',
        currency_field='company_currency_id',
        compute='_compute_l10n_pe_detraction_net',
        help='Importe total en soles menos la detracción: lo que se '
             'cobra/paga a la contraparte fuera del Banco de la Nación.')

    def _l10n_pe_detraction_eligible(self):
        self.ensure_one()
        return (self.move_type in ('out_invoice', 'in_invoice')
                and self.country_code == 'PE')

    def _l10n_pe_detraction_base(self):
        """Importe de la operación en soles, IGV incluido, para el SPOT.

        En moneda extranjera se convierte con la tasa oficial (venta SBS) de
        la fecha de emisión, como manda la R.S. 183-2004/SUNAT y como hace el
        XML nativo (``_l10n_pe_edi_get_spot``). No se usa el total en soles
        de la factura: depende del T.C. que esta aplique (compra, con
        ``al_l10n_pe_currency``, o editado a mano) y la detracción salía
        distinta en la contabilidad y en el XML.
        """
        self.ensure_one()
        company_currency = self.company_currency_id or self.company_id.currency_id
        if not self.currency_id or self.currency_id == company_currency:
            return abs(self.amount_total)
        currency = self.currency_id.with_context(l10n_pe_exchange_rate_type=False)
        return abs(currency._convert(
            self.amount_total, company_currency, self.company_id,
            self.invoice_date or self.date or fields.Date.context_today(self)))

    @staticmethod
    def _l10n_pe_product_detraction_percent(product):
        dtype = product.l10n_pe_detraction_type_id
        return dtype.percentage if dtype else product.l10n_pe_withhold_percentage

    # Cadena de cálculo en tres pasos (tipo → porcentaje → aplicabilidad):
    # así el tipo o el porcentaje corregidos a mano en borrador arrastran
    # al resto en vez de perderse con el siguiente recálculo del importe.
    # No se depende de los campos del catálogo: cambiar un porcentaje no
    # debe reescribir facturas ya publicadas.
    @api.depends('invoice_line_ids.product_id', 'move_type', 'company_id',
                 'country_code')
    def _compute_l10n_pe_detraction_type_id(self):
        for move in self:
            best_type = self.env['l10n_pe.detraction.type']
            if move._l10n_pe_detraction_eligible():
                best_percent = 0.0
                for product in move.invoice_line_ids.product_id:
                    percent = self._l10n_pe_product_detraction_percent(product)
                    if percent > best_percent:
                        best_percent = percent
                        best_type = product.product_tmpl_id._l10n_pe_detraction_type()
            move.l10n_pe_detraction_type_id = best_type

    @api.depends('l10n_pe_detraction_type_id', 'invoice_line_ids.product_id',
                 'move_type', 'country_code')
    def _compute_l10n_pe_detraction_percent(self):
        for move in self:
            percent = 0.0
            if move._l10n_pe_detraction_eligible():
                if move.l10n_pe_detraction_type_id:
                    percent = move.l10n_pe_detraction_type_id.percentage
                else:
                    percent = max(
                        (self._l10n_pe_product_detraction_percent(product)
                         for product in move.invoice_line_ids.product_id),
                        default=0.0)
            move.l10n_pe_detraction_percent = percent

    @api.depends('l10n_pe_detraction_percent', 'l10n_pe_detraction_type_id',
                 'amount_total', 'currency_id', 'invoice_date', 'date',
                 'move_type', 'country_code')
    def _compute_l10n_pe_detraction_applies(self):
        for move in self:
            dtype = move.l10n_pe_detraction_type_id
            min_amount = dtype.min_amount if dtype else DEFAULT_MIN_AMOUNT
            move.l10n_pe_detraction_applies = bool(
                move._l10n_pe_detraction_eligible()
                and move.l10n_pe_detraction_percent
                and move._l10n_pe_detraction_base() > min_amount)

    @api.depends('l10n_pe_detraction_applies', 'l10n_pe_detraction_percent',
                 'amount_total', 'currency_id', 'invoice_date', 'date')
    def _compute_l10n_pe_detraction_amount(self):
        for move in self:
            base = move._l10n_pe_detraction_base() if move.l10n_pe_detraction_applies else 0.0
            amount = 0.0
            if move.l10n_pe_detraction_applies:
                # depósito sin decimales, igual criterio que el XML nativo
                amount = float_round(
                    base * move.l10n_pe_detraction_percent / 100.0,
                    precision_rounding=1.0)
            move.l10n_pe_detraction_amount = amount

    @api.depends('amount_total_signed', 'l10n_pe_detraction_amount')
    def _compute_l10n_pe_detraction_net(self):
        """El neto va en su propio cómputo, y no es capricho de estilo.

        Comparte fórmula con el monto pero no su almacenamiento: con un
        único método, leer el neto —que no se almacena— arrastraba un
        recálculo que **escribía** el monto almacenado. Odoo 19 lo avisa,
        y en tests el aviso es un error.
        """
        for move in self:
            move.l10n_pe_detraction_net = (
                abs(move.amount_total_signed) - move.l10n_pe_detraction_amount)

    def _post(self, soft=True):
        # el XML UBL nativo solo emite el bloque «Detraccion» con un tipo
        # de operación 100x: se fija automáticamente si el usuario no lo hizo
        for move in self:
            if (move.l10n_pe_detraction_applies
                    and move.move_type == 'out_invoice'
                    and move.l10n_pe_edi_operation_type
                    not in DETRACTION_OPERATION_TYPES):
                move.l10n_pe_edi_operation_type = (
                    DETRACTION_OPERATION_BY_CODE.get(
                        move.l10n_pe_detraction_type_id.code, '1001'))
            if (move.company_id.l10n_pe_detraction_split
                    and move.state == 'draft'
                    and move.move_type in ('out_invoice', 'in_invoice')):
                # al reeditar en borrador, la sincronización de términos
                # puede reutilizar la línea de detracción: normalizar
                # siempre y repartir de cero si aplica
                move._l10n_pe_normalize_detraction_terms()
                if move.l10n_pe_detraction_applies:
                    move._l10n_pe_apply_detraction_split()
        return super()._post(soft=soft)

    # ------------------------------------------------------------------
    # Reparto de la detracción dentro del MISMO asiento de la factura
    # ------------------------------------------------------------------
    def _l10n_pe_detraction_split_account(self):
        self.ensure_one()
        company = self.company_id
        if self.move_type == 'out_invoice':
            account = company.l10n_pe_detraction_receivable_account_id
        else:
            account = company.l10n_pe_detraction_payable_account_id
        if not account:
            raise UserError(self.env._(
                'La opción «Separar la detracción en el asiento» está '
                'activa pero falta configurar la cuenta de detracciones '
                '%(kind)s en Ajustes ▸ Perú.',
                kind=self.env._('por cobrar')
                if self.move_type == 'out_invoice'
                else self.env._('por pagar')))
        return account

    def _l10n_pe_standard_counterpart_account(self):
        self.ensure_one()
        partner = self.commercial_partner_id.with_company(self.company_id)
        if self.move_type == 'out_invoice':
            return partner.property_account_receivable_id
        return partner.property_account_payable_id

    def _l10n_pe_normalize_detraction_terms(self):
        """Deshace cualquier reparto previo antes de recalcular: devuelve
        las líneas de término que quedaron en cuentas de detracción (por
        una edición en borrador) a la cuenta estándar del tercero."""
        self.ensure_one()
        company = self.company_id
        det_accounts = (company.l10n_pe_detraction_receivable_account_id
                        | company.l10n_pe_detraction_payable_account_id)
        if not det_accounts:
            return
        term_lines = self.line_ids.filtered(
            lambda l: l.display_type == 'payment_term')
        det_lines = term_lines.filtered(
            lambda l: l.account_id in det_accounts)
        if not det_lines:
            return
        normal_lines = term_lines - det_lines
        if normal_lines:
            main = max(normal_lines, key=lambda l: abs(l.balance))
            self.with_context(dynamic_unlink=True).write({'line_ids': [
                (1, main.id, {
                    'balance': main.balance
                    + sum(det_lines.mapped('balance')),
                    'amount_currency': main.amount_currency
                    + sum(det_lines.mapped('amount_currency')),
                })] + [(2, line.id) for line in det_lines]})
        else:
            det_lines.write({
                'account_id':
                    self._l10n_pe_standard_counterpart_account().id})

    def _l10n_pe_apply_detraction_split(self):
        """Divide la línea por cobrar/pagar del propio asiento: neto en la
        cuenta del tercero y detracción en la cuenta configurada. No se
        crea un segundo asiento. Se ejecuta siempre tras
        ``_l10n_pe_normalize_detraction_terms``."""
        self.ensure_one()
        account = self._l10n_pe_detraction_split_account()
        det_amount = self.l10n_pe_detraction_amount  # soles, positivo
        if self.company_currency_id.is_zero(det_amount):
            return
        term_lines = self.line_ids.filtered(
            lambda l: l.display_type == 'payment_term')
        if not term_lines:
            return
        main = max(term_lines, key=lambda l: abs(l.balance))
        if abs(main.balance) <= det_amount:
            # repartir en silencio dejaría la factura sin separar sin que
            # nadie lo note: se avisa para ajustar el plazo de pago
            raise UserError(self.env._(
                'No se puede separar la detracción de %(move)s: su cuota '
                'mayor (%(term)s) no supera la detracción (%(det)s). Ajuste '
                'el plazo de pago o desactive el reparto en Ajustes ▸ Perú.',
                move=self.display_name,
                term=self.company_currency_id.format(abs(main.balance)),
                det=self.company_currency_id.format(det_amount)))
        sign = 1 if main.balance > 0 else -1
        det_balance = sign * det_amount
        ratio = det_balance / main.balance
        det_amount_currency = main.currency_id.round(
            main.amount_currency * ratio)
        label = self.env._(
            'Detracción SPOT %(code)s',
            code=self.l10n_pe_detraction_type_id.code or '')
        self.write({'line_ids': [
            (1, main.id, {
                'balance': main.balance - det_balance,
                'amount_currency':
                    main.amount_currency - det_amount_currency,
            }),
            (0, 0, {
                'name': label,
                'account_id': account.id,
                'partner_id': main.partner_id.id,
                'currency_id': main.currency_id.id,
                'balance': det_balance,
                'amount_currency': det_amount_currency,
                'date_maturity': main.date_maturity,
                'display_type': 'payment_term',
            }),
        ]})

    def _l10n_pe_edi_get_spot(self):
        # El XML nativo toma el mayor porcentaje de los productos; se alinea
        # con el tipo, el porcentaje y el monto de la factura, que pueden
        # haberse corregido a mano y son los que van a la contabilidad.
        spot = super()._l10n_pe_edi_get_spot()
        if spot and self.l10n_pe_detraction_applies:
            percent = self.l10n_pe_detraction_percent
            pen = self.env.ref('base.PEN')
            spot.update({
                'payment_means_id': (self.l10n_pe_detraction_type_id.code
                                     or spot['payment_means_id']),
                'payment_percent': percent,
                'amount': self.l10n_pe_detraction_amount,
                'spot_amount': float_round(
                    self.amount_total * percent / 100.0,
                    precision_rounding=(1 if self.currency_id == pen
                                        else self.currency_id.rounding)),
            })
        return spot

    def action_open_detraction_deposit(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Registrar depósito de detracción'),
            'res_model': 'l10n_pe.detraction.deposit.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_move_id': self.id},
        }
