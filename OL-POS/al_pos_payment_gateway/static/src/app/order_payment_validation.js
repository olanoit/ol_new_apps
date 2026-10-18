import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

patch(OrderPaymentValidation.prototype, {
    /**
     * Las devoluciones a la tarjeta no se cobran con QR (ver
     * alRefundOnlinePayments). En una venta, una línea negativa sigue siendo
     * un error.
     */
    getRemainingOnlinePaymentLines() {
        const lines = super.getRemainingOnlinePaymentLines();
        return this.order.isRefund ? lines.filter((line) => line.getAmount() > 0) : lines;
    },

    async isOrderValid(isForceValidate) {
        if (!(await this.alCheckInvoiceBeforeOnlinePayment())) {
            return false;
        }
        if (!(await super.isOrderValid(...arguments))) {
            return false;
        }
        // Al final, con la orden ya revisada: la devolución mueve dinero.
        return await this.alRefundOnlinePayments();
    },

    /**
     * Antes de mostrar el QR de una pasarela: el servidor revisa que el
     * comprobante de la venta se podrá emitir. Si no, el cobro se haría y la
     * orden quedaría sin cerrar (el comprobante se emite al llegar el pago).
     */
    async alCheckInvoiceBeforeOnlinePayment() {
        const pending = this.getRemainingOnlinePaymentLines().filter((line) => line.getAmount() > 0);
        if (!pending.length || !this.order.isToInvoice() || this.order.isRefund) {
            return true;
        }
        await this.pos.syncAllOrders({ orders: [this.order] });
        if (!this.order.id || typeof this.order.id !== "number") {
            return true; // el flujo nativo avisa que no se pudo generar el QR
        }
        const problem = await this.pos.data.call("pos.order", "al_check_invoice_before_online_payment", [
            this.order.id,
        ]);
        if (problem) {
            this.pos.dialog.add(AlertDialog, {
                title: _t("Comprobante con errores"),
                body: problem,
            });
            return false;
        }
        return true;
    },

    /**
     * Cada línea negativa de un método en línea devuelve su importe con la
     * pasarela, sobre el cobro de la venta original. Queda «hecha» con la
     * referencia de la transacción: si la validación se repite, no se
     * devuelve dos veces.
     */
    async alRefundOnlinePayments() {
        if (!this.order.isRefund) {
            return true;
        }
        const lines = this.paymentLines.filter(
            (line) =>
                line.payment_method_id.is_online_payment &&
                line.getAmount() < 0 &&
                line.getPaymentStatus() !== "done"
        );
        if (!lines.length) {
            return true;
        }
        const refundedOrderIds = [
            ...new Set(
                this.order.lines
                    .map((line) => line.refunded_orderline_id?.order_id?.id)
                    .filter((id) => typeof id === "number")
            ),
        ];
        if (!refundedOrderIds.length) {
            this.pos.dialog.add(AlertDialog, {
                title: _t("Devolución no realizada"),
                body: _t(
                    "Solo se devuelve con una pasarela una venta que se cobró con ella: use la opción Reembolso de la orden."
                ),
            });
            return false;
        }
        for (const line of lines) {
            line.setPaymentStatus("waiting");
            let result;
            try {
                result = await this.pos.data.call("pos.order", "al_refund_online_payment", [
                    refundedOrderIds,
                    line.payment_method_id.id,
                    -line.getAmount(),
                ]);
            } catch (error) {
                line.setPaymentStatus("retry");
                throw error;
            }
            if (result.error) {
                line.setPaymentStatus("retry");
                this.pos.dialog.add(AlertDialog, {
                    title: _t("Devolución no realizada"),
                    body: result.error,
                });
                return false;
            }
            line.transaction_id = result.reference;
            line.setPaymentStatus("done");
        }
        return true;
    },
});
