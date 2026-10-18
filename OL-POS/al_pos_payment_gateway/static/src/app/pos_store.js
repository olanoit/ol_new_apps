import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    /**
     * Antes de mostrar el QR, el servidor anota con qué método cobra el
     * cajero: la página de pago ofrece solo las pasarelas de ese método.
     * La línea que se cobra es la primera en línea sin terminar (Odoo las
     * recorre en orden y las anteriores ya están pagadas).
     */
    async updateOnlinePaymentsDataWithServer(order, next_online_payment_amount) {
        if (order.id && next_online_payment_amount) {
            const line = order.payment_ids.find(
                (payment) =>
                    payment.payment_method_id?.is_online_payment &&
                    payment.getPaymentStatus() !== "done" &&
                    payment.getAmount() > 0
            );
            if (line) {
                try {
                    await this.data.call("pos.order", "al_set_online_payment_method", [
                        order.id,
                        line.payment_method_id.id,
                    ]);
                } catch {
                    return null; // Odoo muestra «Pago en línea no disponible».
                }
            }
        }
        return super.updateOnlinePaymentsDataWithServer(...arguments);
    },

    /**
     * Odoo compara las líneas de pago en línea con los cobros que registró
     * la pasarela y quita las que no encuentra. Una devolución a la tarjeta
     * no es un cobro con QR: queda fuera de la comparación.
     */
    processOnlinePaymentsDataFromServer(order, opData) {
        if (!opData || "paid_order" in opData || !order.isRefund) {
            return super.processOnlinePaymentsDataFromServer(...arguments);
        }
        const refundLines = order.payment_ids.filter(
            (payment) => payment.payment_method_id?.is_online_payment && payment.getAmount() < 0
        );
        const statuses = refundLines.map((line) => line.getPaymentStatus());
        refundLines.forEach((line) => line.setPaymentStatus(undefined));
        try {
            return super.processOnlinePaymentsDataFromServer(order, {
                ...opData,
                online_payments: (opData.online_payments || []).filter((op) => op.amount > 0),
            });
        } finally {
            refundLines.forEach((line, index) => line.setPaymentStatus(statuses[index]));
        }
    },
});
