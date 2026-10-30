import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { ask } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { QRPopup } from "@point_of_sale/app/components/popups/qr_code_popup/qr_code_popup";

/** QR de billetera (Yape, Plin): el «valor» que devuelve el servidor ya es la
 * imagen del QR del comercio; se muestra tal cual en lugar de codificarla. */
patch(PosStore.prototype, {
    async showQR(payment) {
        const method = payment.payment_method_id;
        if (method?.qr_code_method !== "l10n_pe_wallet") {
            return super.showQR(...arguments);
        }
        payment.setPaymentStatus("waiting");
        let image = method.default_qr;
        try {
            image = await this.data.call("pos.payment.method", "get_qr_code_value", [
                [method.id],
                payment.amount,
                payment.pos_order_id.name,
                "",
                this.currency.id,
                payment.pos_order_id.partner_id?.id,
            ]);
        } catch {
            // Sin conexión: la misma imagen guardada en el método.
        }
        if (!image) {
            return false;
        }
        payment.qr_code = image;
        const result = await ask(this.env.services.dialog, payment.getQrPopupProps(), {}, QRPopup);
        payment.qr_code = false;
        return result;
    },
});
