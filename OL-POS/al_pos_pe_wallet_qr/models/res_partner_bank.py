# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.tools.image import image_data_uri

QR_METHOD = 'l10n_pe_wallet'


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    l10n_pe_wallet_qr_image = fields.Image(
        string='QR de billetera',
        max_width=1024, max_height=1024,
        help='Imagen del QR de cobro de Yape, Plin u otra billetera (QR interoperable) que '
             'abona en esta cuenta. El TPV la muestra para cobrar; el cliente escribe el importe '
             'en su app.',
    )

    @api.model
    def _get_available_qr_methods(self):
        rslt = super()._get_available_qr_methods()
        rslt.append((QR_METHOD, _('QR de billetera (Yape, Plin)'), 60))
        return rslt

    def _get_error_messages_for_qr(self, qr_method, debtor_partner, currency):
        if qr_method != QR_METHOD:
            return super()._get_error_messages_for_qr(qr_method, debtor_partner, currency)
        if not self.l10n_pe_wallet_qr_image:
            return _('Suba la imagen del QR de billetera en la cuenta bancaria %s.', self.display_name)
        if currency and currency.name != 'PEN':
            return _('Yape y Plin solo cobran en soles.')
        return None

    def _get_qr_code_url(self, qr_method, amount, currency, debtor_partner, free_communication,
                         structured_communication):
        if qr_method != QR_METHOD:
            return super()._get_qr_code_url(
                qr_method, amount, currency, debtor_partner, free_communication, structured_communication)
        # El QR de la billetera es una imagen fija: no se genera, se muestra.
        return image_data_uri(self.l10n_pe_wallet_qr_image)

    def _get_qr_code_base64(self, qr_method, amount, currency, debtor_partner, free_communication,
                            structured_communication):
        if qr_method != QR_METHOD:
            return super()._get_qr_code_base64(
                qr_method, amount, currency, debtor_partner, free_communication, structured_communication)
        return image_data_uri(self.l10n_pe_wallet_qr_image)

    def _get_qr_code_generation_params(self, qr_method, amount, currency, debtor_partner,
                                       free_communication, structured_communication):
        # Odoo 20: el TPV pide el «valor» del QR (get_qr_code_value) y lo dibuja
        # él mismo. El de la billetera es una imagen fija: el valor es la propia
        # imagen y el TPV la muestra sin volver a codificarla
        # (static/src/app/pos_store.js).
        if qr_method != QR_METHOD:
            return super()._get_qr_code_generation_params(
                qr_method, amount, currency, debtor_partner, free_communication, structured_communication)
        return {'value': image_data_uri(self.l10n_pe_wallet_qr_image)}
