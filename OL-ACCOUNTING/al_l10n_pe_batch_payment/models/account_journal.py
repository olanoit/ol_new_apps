# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    l10n_pe_batch_format = fields.Selection(
        related='bank_id.l10n_pe_batch_format', string='Formato de pago masivo')
    l10n_pe_batch_service_code = fields.Char(
        string='Código del servicio',
        help='Lo asigna el banco al afiliar el pago a proveedores. Interbank: código del '
             'servicio (04); Scotiabank: forma de pago (1, cargo en cuenta).')
    l10n_pe_batch_company_code = fields.Char(
        string='Código de la empresa',
        help='Interbank: código de la empresa en el banco (MC001 si se deja vacío).')
    l10n_pe_batch_process_type = fields.Selection(
        [('A', 'Inmediato'), ('F', 'En la fecha del lote')], string='Proceso (BBVA)',
        default='A')
    l10n_pe_batch_itf_exempt = fields.Boolean(
        string='Exonerado del ITF (BCP)',
        help='Marca de exoneración del ITF de la cabecera del archivo BCP. Solo si el banco '
             'tiene registrada la exoneración de la cuenta de cargo.')
    l10n_pe_batch_validate_idc = fields.Boolean(
        string='Validar documento del beneficiario (BCP)', default=True,
        help='El banco comprueba que el RUC o documento del proveedor sea el titular de la '
             'cuenta de abono y rechaza el abono si no coincide.')
    l10n_pe_batch_documents = fields.Boolean(
        string='Detalle de comprobantes (BCP)', default=True,
        help='Debajo de cada abono, los comprobantes que se pagan con su importe: el '
             'proveedor los ve en su estado de cuenta. Un abono con notas de crédito o con '
             'pagos sin comprobantes va sin detalle.')

    def _default_outbound_payment_methods(self):
        res = super()._default_outbound_payment_methods()
        if self._is_payment_method_available('pe_bank_txt'):
            res |= self.env.ref('al_l10n_pe_batch_payment.account_payment_method_pe_bank_txt')
        return res
