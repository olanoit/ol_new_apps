# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools import float_round

# Catálogo 53 para el cargo de anticipo según la afectación del IGV de la línea
# (catálogo 07): 1x gravado (10-17, incluido IVAP) → 04, 2x exonerado → 05,
# 3x inafecto → 06. La exportación (40) no tiene código de anticipo propio.
PREPAYMENT_REASON_CODES = {'1': '04', '2': '05', '3': '06'}

# Importes de ``tax_details`` que se reparten al trasladar una línea negativa a
# las positivas de su mismo impuesto. Los ``raw_*`` no se tocan: de ellos sale
# el valor bruto del ítem, y así la diferencia queda como descuento de línea.
LINE_AMOUNT_KEYS = ('total_excluded', 'total_included')
TAX_AMOUNT_KEYS = ('base_amount', 'tax_amount')


class AccountEdiXmlUbl_Pe(models.AbstractModel):
    _inherit = 'account.edi.xml.ubl_pe'

    # -------------------------------------------------------------------------
    # Líneas
    # -------------------------------------------------------------------------

    def _add_invoice_base_lines_vals(self, vals):
        super()._add_invoice_base_lines_vals(vals)
        # Una nota de crédito o débito no admite anticipos (no hay
        # PrepaidPayment en su XML): la deducción de anticipo de la factura
        # original vuelve a ser una línea más y se reparte como las demás.
        if vals['document_type'] in ('credit_note', 'debit_note') and vals.get('prepayment_lines'):
            vals['base_lines'] = vals['base_lines'] + vals['prepayment_lines']
            vals['prepayment_lines'] = []

    def _setup_base_lines(self, vals):
        super()._setup_base_lines(vals)
        is_note = vals['document_type'] in ('credit_note', 'debit_note')
        vals['base_lines'] = self._al_fold_negative_lines(vals, all_groups=is_note)

    def _al_is_taxed_group(self, taxes):
        """Grupo gravado con IGV/IVAP: su descuento global puede ir como ``02``."""
        return any(tax.l10n_pe_edi_affectation_reason and tax.l10n_pe_edi_affectation_reason.startswith('1')
                   for tax in taxes)

    def _al_fold_negative_lines(self, vals, all_groups):
        """Reparte cada línea negativa entre las positivas de su mismo impuesto.

        En facturas y boletas solo se hace en los grupos no gravados
        (exonerado, inafecto, exportación), porque SUNAT solo permite restar
        el descuento global ``02`` de la base gravada: el descuento pasa a ser
        un descuento de línea ``00`` de cada ítem. En notas de crédito y
        débito se hace en todos los grupos: su XML no admite descuentos ni
        cargos globales y el valor de cada ítem debe ser precio × cantidad.
        """
        base_lines = vals['base_lines']
        groups = defaultdict(list)
        for base_line in base_lines:
            groups[tuple(sorted(base_line['tax_ids'].ids))].append(base_line)

        folded = []
        for lines in groups.values():
            negatives = [bl for bl in lines if self._al_line_value(bl, '_currency') < 0]
            if not negatives or (not all_groups and self._al_is_taxed_group(lines[0]['tax_ids'])):
                continue
            positives = [bl for bl in lines if self._al_line_value(bl, '_currency') > 0]
            total_positive = sum(self._al_line_value(bl, '_currency') for bl in positives)
            total_negative = sum(self._al_line_value(bl, '_currency') for bl in negatives)
            if not positives or total_positive + total_negative < 0:
                raise UserError(_(
                    'Las líneas negativas (descuentos o anticipos) de %(document)s superan a las '
                    'positivas con los mismos impuestos (%(taxes)s): SUNAT no admite un valor de '
                    'venta negativo.',
                    document=vals['invoice'].display_name,
                    taxes=', '.join(lines[0]['tax_ids'].mapped('name')) or _('sin impuestos'),
                ))
            weights = [self._al_line_value(bl, '_currency') for bl in positives]
            for negative in negatives:
                self._al_distribute(negative, positives, weights, vals)
                folded.append(negative)
        return [bl for bl in base_lines if not any(bl is f for f in folded)]

    def _al_line_value(self, base_line, suffix):
        details = base_line['tax_details']
        return details[f'total_excluded{suffix}'] + details.get(f'delta_total_excluded{suffix}', 0.0)

    def _al_distribute(self, negative, positives, weights, vals):
        """Suma los importes de ``negative`` a ``positives`` en proporción a
        ``weights``, redondeando a la moneda y dejando el residuo en el ítem de
        mayor peso para no perder céntimos."""
        currencies = {'_currency': negative['currency_id'], '': vals['company_currency_id']}
        total_weight = sum(weights)
        largest = max(range(len(positives)), key=lambda i: weights[i])

        def spread(amount, currency, apply):
            shares = [currency.round(amount * w / total_weight) for w in weights]
            shares[largest] += currency.round(amount - sum(shares))
            for index, share in enumerate(shares):
                apply(positives[index], share)

        neg_details = negative['tax_details']
        for suffix, currency in currencies.items():
            for key in LINE_AMOUNT_KEYS:
                amount = neg_details[f'{key}{suffix}']
                if key == 'total_excluded':
                    amount += neg_details.get(f'delta_total_excluded{suffix}', 0.0)

                def add(base_line, share, field=f'{key}{suffix}'):
                    base_line['tax_details'][field] += share
                spread(amount, currency, add)

            for neg_tax in neg_details['taxes_data']:
                for key in TAX_AMOUNT_KEYS:
                    field = f'{key}{suffix}'

                    def add_tax(base_line, share, field=field, tax=neg_tax['tax']):
                        for tax_data in base_line['tax_details']['taxes_data']:
                            if tax_data['tax'] == tax:
                                tax_data[field] += share
                                break
                    spread(neg_tax[field], currency, add_tax)
        for base_line in positives:
            base_line['_al_folded'] = True

    # -------------------------------------------------------------------------
    # Precio y descuento de línea
    # -------------------------------------------------------------------------

    def _get_line_discount_allowance_charge_node(self, vals):
        node = super()._get_line_discount_allowance_charge_node(vals)
        if node:
            # Factor real (descuento ÷ valor bruto): incluye la parte del
            # descuento global repartida en el ítem y evita que el redondeo
            # del porcentaje descuadre la regla 3290.
            suffix = vals['currency_suffix']
            gross = vals[f'gross_subtotal{suffix}']
            if gross:
                node['cbc:MultiplierFactorNumeric'] = {
                    '_text': self.format_float(abs(vals[f'discount_amount{suffix}']) / gross, 5),
                }
        return node

    def _add_invoice_line_price_nodes(self, line_node, vals):
        super()._add_invoice_line_price_nodes(line_node, vals)
        # NC/ND: el valor del ítem debe ser precio × cantidad (regla 3271) y
        # su XML no lleva descuentos de línea: el precio se informa neto.
        if vals['document_type'] not in ('credit_note', 'debit_note'):
            return
        base_line = vals['base_line']
        if base_line['record'].l10n_pe_edi_affectation_reason in self._al_free_reasons():
            return
        quantity = base_line['quantity']
        if quantity:
            net_price = self._al_line_value(base_line, vals['currency_suffix']) / quantity
            line_node['cac:Price']['cbc:PriceAmount']['_text'] = float_round(net_price, precision_digits=10)

    def _al_free_reasons(self):
        from odoo.addons.l10n_pe_edi.models.account_edi_xml_ubl_pe import FREE_AFFECTATION_REASONS
        return FREE_AFFECTATION_REASONS

    # -------------------------------------------------------------------------
    # Anticipos
    # -------------------------------------------------------------------------

    def _get_document_allowance_charge_node(self, vals):
        node = super()._get_document_allowance_charge_node(vals)
        record = vals['base_line']['record']
        if record._get_downpayment_lines():
            code = self._al_prepayment_reason_code(record)
            if code:
                node['cbc:AllowanceChargeReasonCode'] = {'_text': code}
        return node

    def _al_prepayment_reason_code(self, line):
        reason = line.l10n_pe_edi_affectation_reason or next(
            (tax.l10n_pe_edi_affectation_reason for tax in line.tax_ids if tax.l10n_pe_edi_affectation_reason), False)
        return PREPAYMENT_REASON_CODES.get(reason[:1]) if reason else None

    def _add_invoice_header_nodes(self, document_node, vals):
        super()._add_invoice_header_nodes(document_node, vals)
        if not vals.get('prepayment_lines'):
            return
        invoice = vals['invoice']
        currency = invoice.currency_id
        amounts = defaultdict(float)
        for prepayment_line in vals['prepayment_lines']:
            # Mismo importe que el nativo (total con impuestos, sin retención).
            line_amount = invoice.direction_sign * sum(
                values['base_amount_currency'] + values['tax_amount_currency']
                for grouping_key, values in self.env['account.tax']._aggregate_base_line_tax_details(
                    prepayment_line, vals['total_grouping_function']).items()
                if grouping_key
            )
            # Se descarta solo el anticipo revertido por completo: uno con una
            # nota de crédito parcial sigue cobrado en parte y el nativo suma
            # su línea al PrepaidAmount (si se excluía, el importe se perdía
            # y SUNAT rechazaba por 2509/3220).
            downpayment_lines = prepayment_line['record']._get_downpayment_lines().filtered(
                lambda line: line.move_id.move_type == 'out_invoice'
                and line.move_id.state == 'posted'
                and line.move_id.payment_state != 'reversed')
            moves = downpayment_lines.move_id
            if not moves:
                raise UserError(_(
                    'La deducción de anticipo «%s» no está vinculada a ninguna factura de '
                    'anticipo vigente: el comprobante no puede citar el anticipo.',
                    prepayment_line['record'].name))
            if len(moves) == 1:
                amounts[moves] += line_amount
                continue
            # La misma línea de anticipo facturada en varios comprobantes: se
            # reparte según lo que cada uno facturó.
            weights = {move: sum(downpayment_lines.filtered(lambda l, m=move: l.move_id == m).mapped('price_total'))
                       for move in moves}
            total = sum(weights.values()) or 1.0
            for move, weight in weights.items():
                amounts[move] += line_amount * weight / total

        # PrepaidAmount debe ser exactamente la suma de los PaidAmount (regla
        # 2509): se redondea cada uno y el residuo va al mayor.
        expected_total = currency.round(sum(amounts.values()))
        for move in amounts:
            amounts[move] = currency.round(amounts[move])
        if amounts:
            largest = max(amounts, key=lambda m: abs(amounts[m]))
            amounts[largest] = currency.round(amounts[largest] + expected_total - sum(amounts.values()))

        references, prepaid = [], []
        issuer = {
            'cbc:ID': {
                '_text': invoice.company_id.vat,
                'schemeID': invoice.company_id.partner_id.l10n_latam_identification_type_id.l10n_pe_vat_code,
            },
        }
        for sequence, move in enumerate(sorted(amounts, key=lambda m: m.name), start=1):
            references.append({
                'cbc:ID': {'_text': move.name.replace(' ', '')},
                # Catálogo 12: 02 factura, 03 boleta, según el propio anticipo.
                'cbc:DocumentTypeCode': {'_text': '03' if move.l10n_latam_document_type_id.code == '03' else '02'},
                'cbc:DocumentStatusCode': {'_text': sequence},
                'cac:IssuerParty': {'cac:PartyIdentification': issuer},
            })
            prepaid.append({
                'cbc:ID': {'_text': sequence},
                'cbc:PaidAmount': {
                    '_text': self.format_float(amounts[move], currency.decimal_places),
                    'currencyID': currency.name,
                },
            })
        document_node['cac:AdditionalDocumentReference'] = references
        document_node['cac:PrepaidPayment'] = prepaid
