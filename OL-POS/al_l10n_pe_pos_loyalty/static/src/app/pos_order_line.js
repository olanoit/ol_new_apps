import { patch } from "@web/core/utils/patch";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";

const PAYMENT_PROGRAM_TYPES = ["gift_card", "ewallet"];

patch(PosOrderline.prototype, {
    /** Venta de una tarjeta de regalo o recarga del monedero, o su canje: no
     * es venta de bienes y no entra en el comprobante (Informe SUNAT
     * 097-2010). Mismo criterio que pos.order.line en el servidor. */
    get isPeVoucherLine() {
        if (this.order_id?.company?.country_id?.code !== "PE") {
            return false;
        }
        if (this.is_reward_line) {
            return PAYMENT_PROGRAM_TYPES.includes(this.reward_id?.program_id?.program_type);
        }
        return Boolean(this.product_id?.l10n_pe_pos_is_voucher);
    },
});
