# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import _, models
from odoo.exceptions import UserError


#: Reglas propias que bloquean la publicación (en 20 las del núcleo solo son
#: avisos al enviar; una factura numerada ya no se puede corregir).
BLOCKING_KEYS = ('al_pe_negative_quantity', 'al_pe_negative_group')


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=True):
        for move in self.filtered('l10n_pe_edi_is_required'):
            alerts = move._l10n_pe_edi_check_move_constraints()
            messages = [alerts[key]['message'] for key in BLOCKING_KEYS if key in alerts]
            if messages:
                raise UserError('\n'.join(messages))
        return super()._post(soft=soft)

    def _l10n_pe_edi_check_move_constraints(self):
        res = super()._l10n_pe_edi_check_move_constraints()
        # Odoo impide notas de crédito y débito con descuento de línea. Con
        # este módulo el XML de la nota informa el precio neto de cada ítem
        # (valor ÷ cantidad), como exige SUNAT (regla 3271).
        res.pop('l10n_pe_no_discount_on_credit_debit', None)
        # Las líneas negativas de una nota de crédito (deducción de anticipo,
        # descuento global) se reparten en el XML entre los ítems de su mismo
        # impuesto: el bloqueo nativo sobra. Solo se exige que, por impuesto,
        # no superen a las positivas.
        res.pop('l10n_pe_negative_line', None)
        product_lines = self.invoice_line_ids.filtered(
            lambda line: line.display_type not in ('line_section', 'line_subsection', 'line_note'))
        # El bloqueo nativo cubría también las cantidades negativas, que no se
        # reparten: una NC con cantidad -1 saldría con CreditedQuantity
        # negativo y SUNAT la rechaza.
        # (Las de importe negativo sí se reparten: deducciones de anticipo.)
        if self.move_type == 'out_refund' and any(
                line.quantity < 0 and line.price_subtotal >= 0 for line in product_lines):
            res['al_pe_negative_quantity'] = {
                'message': _('La nota de crédito no puede tener cantidades negativas: use '
                             'cantidades positivas e importes negativos para las deducciones.'),
                'level': 'danger'}
        # Misma regla que el XML (account.edi.xml.ubl_pe._al_fold_negative_lines):
        # en notas se reparten todas las líneas negativas; en facturas solo las
        # de grupos no gravados, y la deducción de anticipo va aparte.
        is_note = self.move_type == 'out_refund' or self.l10n_latam_document_type_id.code == '08'
        ubl = self.env['account.edi.xml.ubl_pe']
        totals = defaultdict(float)
        for line in product_lines.filtered(lambda line: is_note or not line._get_downpayment_lines()):
            totals[line.tax_ids] += line.price_subtotal
        for taxes, total in totals.items():
            if not is_note and ubl._al_is_taxed_group(taxes):
                continue
            if self.currency_id.compare_amounts(total, 0.0) < 0:
                res['al_pe_negative_group'] = {
                    'message': _(
                        'Las líneas negativas (descuentos o anticipos) superan a las positivas con los '
                        'mismos impuestos (%s): SUNAT no admite un valor de venta negativo.',
                        ', '.join(taxes.mapped('name')) or _('sin impuestos')),
                    'level': 'danger'}
        return res
