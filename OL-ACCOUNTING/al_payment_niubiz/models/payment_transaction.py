from datetime import datetime, timezone

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.al_payment_niubiz import const
from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.logging import get_payment_logger

_logger = get_payment_logger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    niubiz_transaction_date = fields.Char(
        string='Fecha Niubiz',
        help="Fecha de la transacción en formato yyMMddHHmmss. Requerido para anulaciones (reversa).",
        copy=False,
    )
    niubiz_trace_number = fields.Char(
        string="Número de traza Niubiz",
        help="Número de traza único de la transacción. Requerido para devoluciones.",
        copy=False,
    )
    niubiz_cip_url = fields.Char(
        string='Constancia PagoEfectivo',
        help="URL de la constancia de pago PagoEfectivo (CIP). Solo aplica para pagos con PagoEfectivo.",
        copy=False,
    )

    # === BUSINESS METHODS - RENDERING === #

    def _get_specific_rendering_values(self, processing_values):
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'niubiz':
            return res
        # Firma la referencia: las rutas públicas de Niubiz la exigen para no
        # dejar que un tercero que adivine la referencia altere el pago.
        return {
            'reference': self.reference,
            'access_token': payment_utils.generate_access_token(self.reference, env=self.env),
        }

    # === BUSINESS METHODS - PROCESSING === #

    @api.model
    def _extract_reference(self, provider_code, payment_data):
        if provider_code != 'niubiz':
            return super()._extract_reference(provider_code, payment_data)
        return payment_data.get('reference')

    def _extract_amount_data(self, payment_data):
        if self.provider_code != 'niubiz':
            return super()._extract_amount_data(payment_data)
        return None

    def _apply_updates(self, payment_data):
        if self.provider_code != 'niubiz':
            return super()._apply_updates(payment_data)

        # Niubiz uses two different response formats:
        #   Approved (HTTP 200): fields in order.* and dataMap.*
        #   Declined (HTTP 400): fields in data.* with UPPER_CASE keys
        flat = payment_data.get('data', {})  # declined format
        order = payment_data.get('order', {})
        data_map = payment_data.get('dataMap', {})
        header = payment_data.get('header', {})

        action_code = order.get('actionCode') or flat.get('ACTION_CODE', '')
        authorization_code = order.get('authorizationCode', '')
        transaction_uuid = header.get('ecoreTransactionUUID', '')
        trace_number = order.get('traceNumber') or flat.get('TRACE_NUMBER', '')
        status = data_map.get('STATUS') or flat.get('STATUS', '')
        brand = (data_map.get('BRAND') or flat.get('BRAND', '')).lower()

        self.provider_reference = authorization_code or transaction_uuid or str(order.get('purchaseNumber', ''))

        # Store trace number (needed for devoluciones); fall back to TRANSACTION_ID for declined
        if trace_number:
            self.niubiz_trace_number = str(trace_number)
        elif flat.get('TRANSACTION_ID'):
            self.niubiz_trace_number = str(flat['TRANSACTION_ID'])

        # Store transaction date in yyMMddHHmmss format (needed for reversa)
        ecore_ts = header.get('ecoreTransactionDate')
        if ecore_ts:
            try:
                dt = datetime.fromtimestamp(int(ecore_ts) / 1000, tz=timezone.utc)
                self.niubiz_transaction_date = dt.strftime('%y%m%d%H%M%S')
            except (ValueError, OSError):
                _logger.warning("Niubiz: could not parse ecoreTransactionDate: %s", ecore_ts)

        if brand:
            payment_method = self.env['payment.method']._get_from_code(
                brand, mapping=const.PAYMENT_METHODS_MAPPING
            )
            if not payment_method:
                payment_method = self.env['payment.method'].search(
                    [('code', '=', 'card')], limit=1
                )
            self.payment_method_id = payment_method or self.payment_method_id

        if action_code in const.APPROVED_ACTION_CODES:
            _logger.info(
                "Niubiz: transaction %s authorized (code: %s, auth: %s)",
                self.reference, action_code, authorization_code
            )
            self._set_done()
        else:
            # Use _set_error (not _set_canceled) for all declines so the linked sale order
            # is preserved and the customer can retry with a different card.
            error_message = self.env['payment.provider']._niubiz_get_error_message(action_code)
            _logger.info(
                "Niubiz: transaction %s declined (code: %s, status: %s) — %s",
                self.reference, action_code, status, error_message
            )
            self._set_error(error_message)

    # === REFUND / REVERSA === #

    def _send_refund_request(self):
        """Override to send a devolución request to Niubiz.

        Devoluciones are available 48 business hours after authorization, up to 6 months.
        Supports partial amounts. Only VISA and Mastercard.
        The refund child transaction is created by the base _refund() method.
        self = the refund child transaction; source = self.source_transaction_id.
        """
        if self.provider_code != 'niubiz':
            return super()._send_refund_request()

        source_tx = self.source_transaction_id
        if not source_tx:
            raise ValidationError(_("No se encontró la transacción original para la devolución."))

        try:
            result = self.provider_id._niubiz_refund(
                tx=source_tx,
                amount=-self.amount,  # refund txs have negative amount; invert for API
                comment=_("Devolución %s", self.reference),
                external_ref=self.reference[:20],
            )
        except ValidationError:
            raise

        # Mark refund transaction as done
        devolucion_code = (result.get('data') or {}).get('CODIGODEVOLUCION', '')
        self.provider_reference = devolucion_code or self.reference
        self._set_done()
        _logger.info(
            "Niubiz: refund %s completed (devolucion code: %s)", self.reference, devolucion_code
        )

    def action_niubiz_reverse(self):
        """Trigger a Niubiz reversa (same-day void) on this transaction.

        Reversa cancels the authorization before it is settled. Must be called on the
        same business day as the original payment. After settlement, use action_refund() instead.
        Only available on done transactions.
        """
        self.ensure_one()
        if self.provider_code != 'niubiz':
            raise ValidationError(_("Esta acción solo está disponible para pagos Niubiz."))
        if self.state != 'done':
            raise ValidationError(_("Solo se pueden anular transacciones confirmadas."))
        if self.operation == 'refund':
            raise ValidationError(_("No se puede anular una transacción de devolución."))

        try:
            result = self.provider_id._niubiz_reverse(tx=self)
        except ValidationError as e:
            self._set_error(str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Error en la anulación"),
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                },
            }

        order = result.get('order', {})
        data_map = result.get('dataMap', {})
        reversa_action_code = order.get('actionCode', '')
        reversa_auth_code = order.get('authorizationCode', '') or order.get('traceNumber', '')

        if (data_map.get('STATUS') == const.REVERSAL_APPROVED_STATUS
                or reversa_action_code in const.REVERSAL_APPROVED_ACTION_CODES):
            # Odoo 19 no deja pasar de «hecho» a «cancelado» sin permitirlo
            # expresamente; la anulación devuelve el dinero el mismo día, así
            # que también se cancela el pago contable (la factura vuelve a
            # quedar pendiente).
            self._set_canceled(extra_allowed_states=('done',))
            if self.payment_id and self.payment_id.state not in ('draft', 'canceled'):
                self.payment_id.action_draft()
                self.payment_id.action_cancel()
            self.provider_reference = reversa_auth_code or self.provider_reference
            _logger.info(
                "Niubiz: transaction %s reversed (reversa code: %s)", self.reference, reversa_auth_code
            )
            msg = _("Anulación procesada exitosamente en Niubiz (código: %s).", reversa_auth_code)
            self.env.user.notify_success(message=msg) if hasattr(self.env.user, 'notify_success') else None
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Anulación exitosa"),
                    'message': msg,
                    'type': 'success',
                    'sticky': False,
                },
            }
        else:
            error_msg = _("Niubiz rechazó la anulación (código: %s, estado: %s).",
                          reversa_action_code, data_map.get('STATUS', ''))
            self._set_error(error_msg)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Anulación rechazada"),
                    'message': error_msg,
                    'type': 'danger',
                    'sticky': True,
                },
            }
