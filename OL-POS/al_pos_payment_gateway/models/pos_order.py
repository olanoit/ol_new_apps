# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class PosOrder(models.Model):
    _inherit = 'pos.order'

    al_online_payment_method_id = fields.Many2one(
        'pos.payment.method', string='Método del cobro en línea', readonly=True, copy=False,
        help='Método de pago en línea con el que el cajero pidió el último cobro por QR.')

    @api.depends('config_id.payment_method_ids', 'al_online_payment_method_id')
    @api.depends_context('al_pos_online_provider_id')
    def _compute_online_payment_method_id(self):
        """Odoo toma el único método en línea de la caja. Con varios, vale el de
        la pasarela del pago que llega (contexto) o, en la página de pago, el
        que eligió el cajero."""
        super()._compute_online_payment_method_id()
        provider = self.env['payment.provider'].browse(self.env.context.get('al_pos_online_provider_id'))
        for order in self:
            methods = order.config_id.payment_method_ids.filtered(lambda m: m.type == 'online')
            by_provider = provider and order.config_id._al_online_payment_method_for_provider(provider)
            if by_provider:
                order.online_payment_method_id = by_provider
            elif order.al_online_payment_method_id in methods:
                order.online_payment_method_id = order.al_online_payment_method_id

    def al_set_online_payment_method(self, payment_method_id):
        """El cajero va a mostrar el QR de este método: la página de pago ofrece
        solo sus pasarelas."""
        self.ensure_one()
        method = self.config_id.payment_method_ids.filtered(
            lambda pm: (pm.type == 'online') and pm.id == payment_method_id)
        if not method:
            raise UserError(_('El método de pago no es un método en línea de esta caja.'))
        self.al_online_payment_method_id = method
        return True

    def al_check_invoice_before_online_payment(self):
        """Antes del QR: ¿se podrá emitir el comprobante de esta orden?

        Con un pago en línea la pasarela cobra primero y el comprobante se
        emite después, al registrar el pago. Si entonces falla (por ejemplo, una
        línea sin impuesto en una boleta electrónica), el cargo queda hecho y la
        orden en borrador. Aquí se arma la factura en un punto de guardado que
        siempre se deshace y se corren las mismas revisiones que al publicarla
        (las del comprobante electrónico de cada diario), sin publicarla ni
        enviarla.

        :return: el texto del problema, o ``False`` si se puede cobrar.
        """
        self.ensure_one()
        self.check_access('read')
        if not self.to_invoice or self.is_refund or self.state != 'draft' or self.account_move:
            return False
        errors = []
        try:
            with self.env.cr.savepoint() as savepoint:
                # El cajero crea las facturas del TPV con sudo (como Odoo en
                # _generate_pos_order_invoice): aquí solo se revisan y se deshacen.
                vals = self.sudo()._prepare_invoice_vals()
                invoice_sudo = self.env['account.move'].sudo().with_company(self.company_id).with_context(
                    default_move_type=vals['move_type'], linked_to_pos=True).create(vals)
                # Odoo 20: las revisiones del comprobante electrónico son avisos
                # de la factura (nivel «danger» bloquea el envío).
                if hasattr(invoice_sudo, '_l10n_pe_edi_check_move_constraints') \
                        and invoice_sudo.l10n_pe_edi_is_required:
                    errors += [alert['message'] for alert in
                               invoice_sudo._l10n_pe_edi_check_move_constraints().values()
                               if alert.get('level') == 'danger']
                savepoint.rollback()
        except (UserError, ValidationError) as error:
            errors.append(error.args[0] if error.args else str(error))
        # La factura de prueba ya no existe en la base: fuera de la caché.
        self.env.invalidate_all()
        if errors:
            return _('No se puede emitir el comprobante de esta venta; corrija esto antes de cobrar:\n\n%s',
                     '\n'.join(errors))
        return False

    def get_and_set_online_payments_data(self, next_online_payment_amount=False):
        # Una devolución no se cobra con QR. Al validarla el TPV pregunta con
        # importe 0 y Odoo borraría sus líneas de pago en línea (la devolución
        # a la tarjeta) como si fuera un cobro abandonado.
        if self.is_refund:
            next_online_payment_amount = False
        return super().get_and_set_online_payments_data(next_online_payment_amount)

    @api.model
    def al_refund_online_payment(self, refunded_order_ids, payment_method_id, amount):
        """Devuelve ``amount`` al cliente con la pasarela del método, sobre un
        cobro en línea de las órdenes que se devuelven.

        :return: ``{'reference': ...}`` con la referencia de la transacción de
            devolución (el TPV la guarda en su línea de pago) o ``{'error': ...}``.
        """
        method = self.env['pos.payment.method'].browse(payment_method_id).exists()
        if not (method.type == 'online'):
            raise UserError(_('El método de pago no es un método de pago en línea.'))
        refunded_orders = self.browse(refunded_order_ids).exists()
        refunded_orders.check_access('read')
        currency = refunded_orders.currency_id[:1] or self.env.company.currency_id
        if currency.compare_amounts(amount, 0) <= 0:
            raise UserError(_('El importe a devolver debe ser mayor que cero.'))

        # sudo: el cajero no lee pagos contables ni transacciones de pago; solo
        # se toman las de los cobros de estas órdenes con este método.
        payments_sudo = refunded_orders.sudo().payment_ids.filtered(
            lambda payment: payment.payment_method_id == method and payment.online_account_payment_id)
        txs_sudo = payments_sudo.online_account_payment_id.payment_transaction_id.filtered(
            lambda tx: tx.state == 'done' and tx.operation != 'refund')
        if not txs_sudo:
            return {'error': _('Las órdenes devueltas no tienen cobros con %s.', method.name)}

        for tx_sudo in txs_sudo.sorted('id'):
            refunds_sudo = tx_sudo.child_transaction_ids.filtered(
                lambda child: child.operation == 'refund' and child.state not in ('cancel', 'error'))
            refundable = currency.round(tx_sudo.amount + sum(refunds_sudo.mapped('amount')))
            if currency.compare_amounts(refundable, amount) >= 0:
                break
        else:
            return {'error': _(
                'El importe supera lo que queda por devolver de un cobro con %s: devuelva el '
                'resto con otro método.', method.name)}

        support = tx_sudo.provider_id.support_refund
        if support not in ('full_only', 'partial'):
            return {'error': _('%s no permite devoluciones desde Odoo.', tx_sudo.provider_id.name)}
        if support == 'full_only' and currency.compare_amounts(refundable, amount):
            return {'error': _('%s solo permite devolver el cobro completo.', tx_sudo.provider_id.name)}

        refund_tx_sudo = tx_sudo._refund(amount_to_refund=amount)
        if refund_tx_sudo.state != 'done':
            # No se lanza error: la transacción queda registrada (la pasarela
            # puede confirmarla después) y el cajero ve el motivo.
            return {'error': refund_tx_sudo.state_message or _(
                'La pasarela no confirmó la devolución (referencia %s).', refund_tx_sudo.reference)}
        # Pago contable de la devolución en el acto (la pasarela ya la confirmó).
        refund_tx_sudo.with_context(payment_safe_write=True)._post_process()
        return {'reference': refund_tx_sudo.reference}
