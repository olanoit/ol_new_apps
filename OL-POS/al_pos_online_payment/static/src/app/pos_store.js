import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    async postSyncAllOrders(orders) {
        await super.postSyncAllOrders(...arguments);
        for (const order of orders || []) {
            this.removeLocalOnlinePaymentLines(order);
        }
    },
    /**
     * Con la orden pagada en el servidor, sus pagos en línea son los que
     * registró la pasarela. La línea local que pidió el cobro nunca se envía
     * (pos_online_payment la saca de serializeForORM): si queda, se suma al
     * pago cargado del servidor y el ticket muestra el pago dos veces y un
     * cambio igual al importe.
     */
    removeLocalOnlinePaymentLines(order) {
        if (!["paid", "done"].includes(order.state)) {
            return;
        }
        const onlineLines = order.payment_ids.filter(
            (line) => (line.payment_method_id?.type === "online")
        );
        if (!onlineLines.some((line) => line.isSynced)) {
            return;
        }
        for (const line of onlineLines.filter((line) => !line.isSynced)) {
            line.delete();
        }
    },
});
