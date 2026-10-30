import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    /**
     * pos_online_payment no envía las líneas de pago en línea locales (el
     * pago lo registra la pasarela). La devolución a la tarjeta sí va: la
     * pasarela ya la confirmó y el servidor enlaza su pago contable por la
     * referencia de la transacción.
     */
    serializeForORM(opts) {
        const serialized = super.serializeForORM(...arguments);
        if (!this.isRefund) {
            return serialized;
        }
        const refundLines = this.payment_ids.filter(
            (payment) =>
                !payment.isSynced &&
                (payment.payment_method_id?.type === "online") &&
                payment.getAmount() < 0 &&
                payment.transaction_id &&
                payment.getPaymentStatus() === "done"
        );
        if (refundLines.length) {
            const sent = new Set((serialized.payment_ids || []).map((cmd) => cmd.at(-1)?.uuid));
            serialized.payment_ids = [
                ...(serialized.payment_ids || []),
                ...refundLines
                    .filter((line) => !sent.has(line.uuid))
                    .map((line) => [0, 0, line.serializeForORM()]),
            ];
        }
        return serialized;
    },
});
