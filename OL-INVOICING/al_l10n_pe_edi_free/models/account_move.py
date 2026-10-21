from odoo import _, models
from odoo.exceptions import UserError

from .account_chart_template import FREE_EXEMPT_TAX_XMLID
from .account_edi_xml_ubl_pe import (
    FREE_AFFECTATION_REASONS, FREE_EXEMPT_REASONS, FREE_TAXED_REASONS,
)

#: Leyenda del catálogo 52 de las transferencias gratuitas.
FREE_LEGEND = '1002'
#: Códigos de tributo (catálogo 05) usados para elegir el grupo gratuito.
TAX_CODE_IGV = '1000'
TAX_CODE_FREE = '9996'
TAX_CODE_EXONERATED = '9997'


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _l10n_pe_free_applies(self):
        self.ensure_one()
        return self.country_code == 'PE' and self.move_type in ('out_invoice', 'out_refund')

    def _l10n_pe_free_lines(self):
        return self.invoice_line_ids.filtered(
            lambda line: line.display_type == 'product'
            and line.l10n_pe_edi_affectation_reason in FREE_AFFECTATION_REASONS)

    def _l10n_pe_edi_get_payment_means(self):
        # Una factura enteramente gratuita no tiene nada que cobrar: con un
        # plazo de pago salía «Credito» con importe 0.
        if self.move_type == 'out_invoice' and self._l10n_pe_free_lines() \
                and self.currency_id.is_zero(self.amount_total):
            return 'Contado'
        return super()._l10n_pe_edi_get_payment_means()

    def _post(self, soft=True):
        for move in self.filtered(lambda m: m._l10n_pe_free_applies()):
            move._l10n_pe_free_prepare()
        return super()._post(soft)

    def _l10n_pe_free_prepare(self):
        """Antes de publicar: reglas de SUNAT, leyenda 1002 y forma de pago."""
        self.ensure_one()
        free_lines = self._l10n_pe_free_lines()
        if not free_lines:
            # La leyenda exige un total gratuito (regla 2416).
            if self.l10n_pe_edi_legend == FREE_LEGEND:
                self.l10n_pe_edi_legend = False
            return
        errors = [error for line in free_lines for error in self._l10n_pe_free_line_errors(line)]
        if errors:
            raise UserError(_(
                'SUNAT rechazaría los ítems gratuitos de %(move)s:\n%(errors)s',
                move=self.display_name, errors='\n'.join('· %s' % error for error in errors)))
        # El nativo usa la leyenda para descartar los impuestos de ajuste
        # («-Base», IGV al gasto); sin ella salen al XML como tributos vacíos.
        if self.l10n_pe_edi_legend and self.l10n_pe_edi_legend != FREE_LEGEND:
            raise UserError(_(
                '%(move)s tiene ítems gratuitos: la leyenda debe ser «1002 - Transferencia '
                'gratuita» y no la %(legend)s.', move=self.display_name,
                legend=self.l10n_pe_edi_legend))
        self.l10n_pe_edi_legend = FREE_LEGEND
        if self.move_type == 'out_invoice' and self.currency_id.is_zero(self.amount_total):
            self.invoice_payment_term_id = False
            self.invoice_date_due = self.invoice_date or self.date

    def _l10n_pe_free_line_errors(self, line):
        """Reglas de SUNAT que incumple un ítem gratuito."""
        name = line.name or line.product_id.display_name or '-'
        reason = line.l10n_pe_edi_affectation_reason
        free_taxes = line.tax_ids.flatten_taxes_hierarchy().filtered(
            lambda tax: tax.l10n_pe_edi_tax_code == TAX_CODE_FREE)
        errors = []
        if line.price_unit <= 0:
            errors.append(_(
                '%(line)s: el precio unitario de un ítem gratuito es su valor referencial '
                'y no puede ser 0 (2641, 3224).', line=name))
        if reason in FREE_TAXED_REASONS and not any(tax.amount > 0 for tax in free_taxes):
            errors.append(_(
                '%(line)s: un retiro gravado (afectación %(reason)s) lleva IGV sobre el valor '
                'referencial (3111): use el impuesto «18%% Free Group».', line=name, reason=reason))
        if reason in FREE_EXEMPT_REASONS and any(tax.amount for tax in free_taxes):
            errors.append(_(
                '%(line)s: una gratuita exonerada o inafecta (afectación %(reason)s) no lleva '
                'IGV (3110): use el impuesto «0%% Gratuito exonerado/inafecto».',
                line=name, reason=reason))
        if not line.currency_id.is_zero(line.price_total):
            errors.append(_(
                '%(line)s: el ítem gratuito se está cobrando (%(amount)s). Use un grupo '
                'gratuito («18%% Free Group» o «0%% Gratuito exonerado/inafecto»), que lo '
                'deja en 0.', line=name, amount=line.price_total))
        return errors

    def action_l10n_pe_free_transfer(self):
        """Convierte la factura en una transferencia gratuita.

        Lo gravado pasa a «18% Free Group» (retiro, afectación del impuesto);
        lo exonerado, al grupo gratuito con afectación 21, y lo inafecto o sin
        impuesto, al mismo grupo con la 37. El precio queda como valor
        referencial.
        """
        for move in self:
            if move.state != 'draft' or not move._l10n_pe_free_applies():
                raise UserError(_('Solo se convierte un comprobante de venta peruano en borrador.'))
            ref = self.env['account.chart.template'].with_company(move.company_id.root_id).ref
            taxed_group = ref('tax_free_group', raise_if_not_found=False)
            exempt_group = ref(FREE_EXEMPT_TAX_XMLID, raise_if_not_found=False)
            if not taxed_group or not exempt_group:
                raise UserError(_(
                    'Faltan los impuestos gratuitos del plan peruano en %s.', move.company_id.name))
            for line in move.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
                codes = set(line.tax_ids.flatten_taxes_hierarchy().mapped('l10n_pe_edi_tax_code'))
                if line.l10n_pe_edi_affectation_reason in FREE_AFFECTATION_REASONS:
                    continue
                if TAX_CODE_IGV in codes:
                    line.tax_ids = taxed_group
                else:
                    line.tax_ids = exempt_group
                    if TAX_CODE_EXONERATED in codes:
                        line.l10n_pe_edi_affectation_reason = '21'
            move.l10n_pe_edi_legend = FREE_LEGEND
        return True
