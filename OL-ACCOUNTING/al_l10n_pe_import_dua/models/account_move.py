# -*- coding: utf-8 -*-
"""DUA de importación como documento de compra.

La DUA (DAM, tipo 50; 52 la simplificada) se registra como una factura de
proveedor a nombre de la Aduana. El asistente «Generar líneas» arma:

* una línea por derecho (ad valorem, ISC, otros): costos en destino del
  producto (``landed_cost_ok``);
* la base imponible del IGV (valor en aduana + derechos) con el IGV de compras
  (16 % + IPM 2 %), que da el crédito fiscal, y su compensación en negativo,
  ambas en la cuenta puente: la DUA suma lo que se paga a la Aduana (derechos
  + IGV) y el registro de compras lee la base del impuesto.
"""
import re

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.stock_landed_costs.models.stock_landed_cost import SPLIT_METHOD

DUA_DOC_CODES = ('50', '52')
DUA_LINE_KINDS = [
    ('ad_valorem', 'Ad valorem'),
    ('isc', 'ISC'),
    ('other', 'Otros derechos'),
    ('base', 'Base imponible del IGV'),
    ('offset', 'Compensación de la base'),
]


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_dua_is_dua = fields.Boolean(
        string='Es DUA', compute='_compute_l10n_pe_dua_is_dua', store=True)
    l10n_pe_dua_customs_code = fields.Char(
        string='Aduana', size=3, copy=False,
        help='Código de la aduana de despacho (tabla 11 de SUNAT), p. ej. 118 Callao marítima.')
    l10n_pe_dua_year = fields.Char(string='Año', size=4, copy=False)
    l10n_pe_dua_regime = fields.Char(
        string='Régimen', size=2, default='10', copy=False,
        help='10: importación para el consumo.')
    l10n_pe_dua_sequence = fields.Char(string='Número de la DAM', size=8, copy=False)
    l10n_pe_dua_customs_value = fields.Monetary(
        string='Valor en aduana', copy=False,
        help='Valor CIF de la mercancía en la moneda de la DUA (normalmente soles, al tipo '
             'de cambio de la fecha de numeración).')
    l10n_pe_dua_ad_valorem = fields.Monetary(string='Ad valorem', copy=False)
    l10n_pe_dua_isc = fields.Monetary(string='ISC de la DUA', copy=False)
    l10n_pe_dua_other_duties = fields.Monetary(
        string='Otros derechos', copy=False,
        help='Derechos específicos, antidumping, tasa de despacho y otros que forman la base '
             'del IGV.')
    l10n_pe_dua_igv_tax_id = fields.Many2one(
        'account.tax', string='IGV de importación', check_company=True, copy=False,
        domain="[('type_tax_use', '=', 'purchase')]",
        help='IGV 16 % + IPM 2 %: el IGV de compras del 18 %.')
    l10n_pe_dua_perception = fields.Monetary(
        string='Percepción aduanera', copy=False,
        help='Percepción del IGV que cobra la Aduana (3,5 %, 5 % o 10 % del valor más los '
             'tributos). Se registra con «Percepciones del IGV» si el módulo está instalado.')
    l10n_pe_dua_tax_base = fields.Monetary(
        string='Base imponible del IGV', compute='_compute_l10n_pe_dua_tax_base')
    l10n_pe_dua_foreign_invoice_ids = fields.Many2many(
        'account.move', string='Facturas del exterior',
        compute='_compute_l10n_pe_dua_foreign_invoice_ids',
        inverse='_inverse_l10n_pe_dua_foreign_invoice_ids',
        domain="[('move_type', '=', 'in_invoice'), ('company_id', '=', company_id)]",
        help='Facturas del proveedor del exterior que nacionaliza esta DUA (en el registro de '
             'compras llevan la referencia a la DUA).')
    l10n_pe_dua_picking_ids = fields.Many2many(
        'stock.picking', 'al_l10n_pe_dua_picking_rel', 'move_id', 'picking_id',
        string='Recepciones', copy=False, check_company=True,
        domain="[('picking_type_code', '=', 'incoming'), ('state', '=', 'done')]")
    l10n_pe_dua_expense_move_ids = fields.Many2many(
        'account.move', 'al_l10n_pe_dua_expense_rel', 'dua_id', 'expense_id',
        string='Gastos de aduana', copy=False, check_company=True,
        domain="[('move_type', '=', 'in_invoice'), ('state', '=', 'posted')]",
        help='Facturas de agente de aduana, flete, almacén, etc.: sus líneas de costo en '
             'destino se suman al costo de la importación.')
    l10n_pe_dua_split_method = fields.Selection(
        SPLIT_METHOD, string='Repartir costos', default='by_current_cost_price', copy=False)
    l10n_pe_dua_perception_count = fields.Integer(
        string='Percepciones', compute='_compute_l10n_pe_dua_perception_count')

    @api.depends('l10n_latam_document_type_id.code')
    def _compute_l10n_pe_dua_is_dua(self):
        for move in self:
            move.l10n_pe_dua_is_dua = move.l10n_latam_document_type_id.code in DUA_DOC_CODES

    @api.depends('l10n_pe_dua_customs_value', 'l10n_pe_dua_ad_valorem', 'l10n_pe_dua_isc',
                 'l10n_pe_dua_other_duties')
    def _compute_l10n_pe_dua_tax_base(self):
        for move in self:
            move.l10n_pe_dua_tax_base = (
                move.l10n_pe_dua_customs_value + move.l10n_pe_dua_ad_valorem
                + move.l10n_pe_dua_isc + move.l10n_pe_dua_other_duties)

    def _compute_l10n_pe_dua_foreign_invoice_ids(self):
        Move = self.env['account.move']
        for move in self:
            move.l10n_pe_dua_foreign_invoice_ids = Move.search(
                [('l10n_pe_dua_invoice_id', '=', move.id)]) if isinstance(move.id, int) else Move

    def _inverse_l10n_pe_dua_foreign_invoice_ids(self):
        for move in self:
            current = self.env['account.move'].search([('l10n_pe_dua_invoice_id', '=', move.id)])
            (current - move.l10n_pe_dua_foreign_invoice_ids).write({'l10n_pe_dua_invoice_id': False})
            (move.l10n_pe_dua_foreign_invoice_ids - current).write({'l10n_pe_dua_invoice_id': move.id})

    def _compute_l10n_pe_dua_perception_count(self):
        perceptions = self._l10n_pe_dua_perceptions()
        for move in self:
            move.l10n_pe_dua_perception_count = len(perceptions.filtered(
                lambda p: move in p.line_ids.bill_id)) if perceptions else 0

    def _l10n_pe_dua_perceptions(self):
        """Percepciones aduaneras registradas para estas DUA (vacío si el módulo de
        percepciones no está instalado)."""
        if 'l10n_pe.perception.received' not in self.env or not self.ids:
            return self.env['account.move'].browse()
        return self.env['l10n_pe.perception.received'].search([
            ('document_kind', '=', 'dua'), ('state', '!=', 'cancel'),
            ('line_ids.bill_id', 'in', self.ids)])

    # ------------------------------------------------------------------
    # Número de la DAM: aduana-año-régimen-número (lo leen el PLE y el SIRE)
    # ------------------------------------------------------------------
    @api.onchange('l10n_pe_dua_customs_code', 'l10n_pe_dua_year', 'l10n_pe_dua_regime',
                  'l10n_pe_dua_sequence')
    def _onchange_l10n_pe_dua_number(self):
        for move in self.filtered('l10n_pe_dua_is_dua'):
            number = move._l10n_pe_dua_number()
            if number:
                move.l10n_latam_document_number = number

    def _l10n_pe_dua_number(self):
        self.ensure_one()
        parts = (self.l10n_pe_dua_customs_code, self.l10n_pe_dua_year,
                 self.l10n_pe_dua_regime, self.l10n_pe_dua_sequence)
        if not all(parts):
            return False
        return '%s-%s-%s-%s' % (parts[0].strip(), parts[1].strip(), parts[2].strip().zfill(2),
                                parts[3].strip().zfill(6))

    @api.constrains('l10n_pe_dua_customs_code', 'l10n_pe_dua_year', 'l10n_pe_dua_regime',
                    'l10n_pe_dua_sequence')
    def _check_l10n_pe_dua_number(self):
        for move in self.filtered('l10n_pe_dua_is_dua'):
            checks = (
                (move.l10n_pe_dua_customs_code, r'\d{3}', self.env._('La aduana tiene 3 dígitos.')),
                (move.l10n_pe_dua_year, r'\d{4}', self.env._('El año tiene 4 dígitos.')),
                (move.l10n_pe_dua_regime, r'\d{1,2}', self.env._('El régimen tiene 2 dígitos.')),
                (move.l10n_pe_dua_sequence, r'\d{1,8}', self.env._('El número de la DAM es numérico.')),
            )
            for value, pattern, message in checks:
                if value and not re.fullmatch(pattern, value.strip()):
                    raise ValidationError(message)

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        moves._l10n_pe_dua_sync_number()
        return moves

    def write(self, vals):
        res = super().write(vals)
        if {'l10n_pe_dua_customs_code', 'l10n_pe_dua_year', 'l10n_pe_dua_regime',
                'l10n_pe_dua_sequence', 'l10n_latam_document_type_id'} & set(vals):
            self._l10n_pe_dua_sync_number()
        return res

    def _l10n_pe_dua_sync_number(self):
        for move in self.filtered(lambda m: m.l10n_pe_dua_is_dua and m.state == 'draft'):
            number = move._l10n_pe_dua_number()
            if number and move.l10n_latam_document_number != number:
                super(AccountMove, move).write({'l10n_latam_document_number': number})

    # ------------------------------------------------------------------
    # Liquidación de la DUA → líneas
    # ------------------------------------------------------------------
    def _l10n_pe_dua_default_igv_tax(self):
        self.ensure_one()
        return self.env['account.chart.template'].with_company(self.company_id).ref(
            'purchase_tax_igv_18', raise_if_not_found=False)

    def action_l10n_pe_dua_generate_lines(self):
        """Reemplaza las líneas generadas de la DUA con su liquidación."""
        for move in self:
            if not move.l10n_pe_dua_is_dua:
                raise UserError(self.env._('%s no es una DUA (tipo 50 o 52).', move.display_name))
            if move.state != 'draft':
                raise UserError(self.env._('La DUA %s ya no está en borrador.', move.display_name))
            company = move.company_id
            offset = company.l10n_pe_dua_offset_account_id
            if not offset:
                raise UserError(self.env._(
                    'Configure la «Cuenta puente del valor en aduana» en Ajustes ▸ Perú ▸ '
                    'Importaciones (DUA).'))
            tax = move.l10n_pe_dua_igv_tax_id or move._l10n_pe_dua_default_igv_tax()
            if not tax:
                raise UserError(self.env._('Indique el IGV de importación de la DUA.'))
            products = {
                'ad_valorem': self.env.ref('al_l10n_pe_import_dua.product_dua_ad_valorem'),
                'isc': self.env.ref('al_l10n_pe_import_dua.product_dua_isc'),
                'other': self.env.ref('al_l10n_pe_import_dua.product_dua_other'),
            }
            commands = [Command.delete(line.id) for line in move.invoice_line_ids
                        if line.l10n_pe_dua_line_kind]
            for kind, amount in (('ad_valorem', move.l10n_pe_dua_ad_valorem),
                                 ('isc', move.l10n_pe_dua_isc),
                                 ('other', move.l10n_pe_dua_other_duties)):
                if move.currency_id.is_zero(amount):
                    continue
                product = products[kind]
                commands.append(Command.create({
                    'l10n_pe_dua_line_kind': kind,
                    # El onchange del producto no corre al crear por código.
                    'is_landed_costs_line': True,
                    'product_id': product.id,
                    'name': product.display_name,
                    'quantity': 1.0,
                    'price_unit': amount,
                    'tax_ids': [Command.clear()],
                }))
            base = move.l10n_pe_dua_tax_base
            if not move.currency_id.is_zero(base):
                commands += [
                    Command.create({
                        'l10n_pe_dua_line_kind': 'base',
                        'name': self.env._('Base imponible del IGV (valor en aduana y derechos)'),
                        'account_id': offset.id,
                        'quantity': 1.0,
                        'price_unit': base,
                        'tax_ids': [Command.set(tax.ids)],
                    }),
                    Command.create({
                        'l10n_pe_dua_line_kind': 'offset',
                        'name': self.env._('Compensación de la base: el valor en aduana se paga '
                                           'al proveedor del exterior'),
                        'account_id': offset.id,
                        'quantity': 1.0,
                        'price_unit': -base,
                        'tax_ids': [Command.clear()],
                    }),
                ]
            move.write({'l10n_pe_dua_igv_tax_id': tax.id, 'invoice_line_ids': commands})
        return True

    # ------------------------------------------------------------------
    # Publicación: percepción aduanera
    # ------------------------------------------------------------------
    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        posted.filtered('l10n_pe_dua_is_dua')._l10n_pe_dua_register_perception()
        return posted

    def _l10n_pe_dua_register_perception(self):
        """La percepción aduanera se registra con el módulo de percepciones
        (al_l10n_pe_perception): asiento a «percepciones por aplicar» contra la
        Aduana, para aplicarla en el F.V. 621. Sin el módulo, queda solo el dato."""
        if 'l10n_pe.perception.received' not in self.env:
            return
        existing = self._l10n_pe_dua_perceptions()
        for move in self:
            if move.currency_id.is_zero(move.l10n_pe_dua_perception) \
                    or move in existing.line_ids.bill_id:
                continue
            amount = move.currency_id._convert(
                move.l10n_pe_dua_perception, move.company_id.currency_id, move.company_id,
                move.invoice_date or move.date)
            base = move.currency_id._convert(
                move.l10n_pe_dua_tax_base + move.amount_tax, move.company_id.currency_id,
                move.company_id, move.invoice_date or move.date)
            perception = self.env['l10n_pe.perception.received'].with_company(
                move.company_id).create({
                    'company_id': move.company_id.id,
                    'partner_id': move.partner_id.id,
                    'kind': 'import',
                    'document_kind': 'dua',
                    'date': move.invoice_date or move.date,
                    'l10n_pe_series': (move.l10n_pe_dua_customs_code or '')[:4] or False,
                    'l10n_pe_number': move.l10n_latam_document_number or move.name,
                    'line_ids': [Command.create({
                        'bill_id': move.id,
                        'reference': move.l10n_latam_document_number or move.name,
                        'base_amount': base,
                        'amount': amount,
                    })],
                })
            perception.action_post()

    def action_l10n_pe_dua_view_perceptions(self):
        self.ensure_one()
        perceptions = self._l10n_pe_dua_perceptions()
        return perceptions._get_records_action(name=self.env._('Percepción aduanera'))

    # ------------------------------------------------------------------
    # Costos en destino
    # ------------------------------------------------------------------
    def action_l10n_pe_dua_create_landed_costs(self):
        """Costo en destino con los derechos de la DUA y los gastos de aduana,
        sobre sus recepciones, repartido con el método elegido."""
        self.ensure_one()
        if self.state != 'posted':
            raise UserError(self.env._('Publique la DUA antes de crear los costos en destino.'))
        if not self.l10n_pe_dua_picking_ids:
            raise UserError(self.env._('Indique las recepciones de la importación.'))
        lines = (self | self.l10n_pe_dua_expense_move_ids).line_ids.filtered(
            lambda l: l.display_type == 'product'
            and (l.is_landed_costs_line or l.product_id.landed_cost_ok))
        if not lines:
            raise UserError(self.env._(
                'La DUA y los gastos de aduana no tienen líneas de costo en destino.'))
        landed = self.env['stock.landed.cost'].with_company(self.company_id).create({
            'vendor_bill_id': self.id,
            'picking_ids': [Command.set(self.l10n_pe_dua_picking_ids.ids)],
            'description': self.env._('Importación %s', self.l10n_latam_document_number or self.name),
            'cost_lines': [Command.create({
                'product_id': line.product_id.id,
                'name': '%s · %s' % (line.move_id.l10n_latam_document_number or line.move_id.name,
                                     line.product_id.name),
                'account_id': line.product_id.product_tmpl_id.get_product_accounts()['expense'].id,
                'price_unit': (-1 if line.move_id.move_type == 'in_refund' else 1)
                * line.company_currency_id.round(abs(line.balance)),
                'split_method': self.l10n_pe_dua_split_method or 'equal',
            }) for line in lines],
        })
        landed.compute_landed_cost()
        action = self.env['ir.actions.actions']._for_xml_id(
            'stock_landed_costs.action_stock_landed_cost')
        return dict(action, view_mode='form', res_id=landed.id, views=[(False, 'form')])


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    l10n_pe_dua_line_kind = fields.Selection(
        DUA_LINE_KINDS, string='Concepto de la DUA', copy=False,
        help='Línea generada por la liquidación de la DUA.')
