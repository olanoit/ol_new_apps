# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import _, models
from odoo.tools.translate import code_translations

# Mensaje nativo de l10n_pe_edi que este módulo levanta (se compara con el
# original y con su traducción, porque llega ya traducido).
NEGATIVE_LINES_MESSAGE = "The credit note cannot have negative quantities or amounts on any line"


class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    def _check_move_configuration(self, move):
        res = super()._check_move_configuration(move)
        if self.code != 'pe_ubl_2_1':
            return res
        # Las líneas negativas de una nota de crédito (deducción de anticipo,
        # descuento global) se reparten en el XML entre los ítems de su mismo
        # impuesto: el bloqueo nativo sobra. Solo se exige que, por impuesto,
        # no superen a las positivas.
        # El mensaje llega traducido con el idioma del usuario o su respaldo
        # (es_PE → es_419): se acepta cualquiera de las traducciones instaladas.
        blocked = {NEGATIVE_LINES_MESSAGE} | {
            code_translations.get_python_translations('l10n_pe_edi', lang).get(NEGATIVE_LINES_MESSAGE, NEGATIVE_LINES_MESSAGE)
            for lang, _name in self.env['res.lang'].get_installed()
        }
        res = [message for message in res if str(message) not in blocked]
        # El bloqueo nativo cubría también las cantidades negativas, que no se
        # reparten: una NC con cantidad -1 saldría con CreditedQuantity
        # negativo y SUNAT la rechaza.
        # (Las de importe negativo sí se reparten: deducciones de anticipo.)
        if move.move_type == 'out_refund' and any(
                line.quantity < 0 and line.price_subtotal >= 0 for line in move.invoice_line_ids
                if line.display_type not in ('line_section', 'line_subsection', 'line_note')):
            res.append(_('La nota de crédito no puede tener cantidades negativas: use '
                         'cantidades positivas e importes negativos para las deducciones.'))
        # Misma regla que el XML (account.edi.xml.ubl_pe._al_fold_negative_lines):
        # en notas se reparten todas las líneas negativas; en facturas solo las
        # de grupos no gravados, y la deducción de anticipo va aparte.
        is_note = move.move_type == 'out_refund' or move.l10n_latam_document_type_id.code == '08'
        ubl = self.env['account.edi.xml.ubl_pe']
        lines = move.invoice_line_ids.filtered(
            lambda line: line.display_type not in ('line_section', 'line_subsection', 'line_note')
            and (is_note or not line._get_downpayment_lines()))
        totals = defaultdict(float)
        for line in lines:
            totals[line.tax_ids] += line.price_subtotal
        for taxes, total in totals.items():
            if not is_note and ubl._al_is_taxed_group(taxes):
                continue
            if move.currency_id.compare_amounts(total, 0.0) < 0:
                res.append(_(
                    'Las líneas negativas (descuentos o anticipos) superan a las positivas con los '
                    'mismos impuestos (%s): SUNAT no admite un valor de venta negativo.',
                    ', '.join(taxes.mapped('name')) or _('sin impuestos'),
                ))
        return res
