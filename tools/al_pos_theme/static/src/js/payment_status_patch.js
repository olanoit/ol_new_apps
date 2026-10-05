import { patch } from "@web/core/utils/patch";
import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";

/**
 * "Cambio" sin signo menos.
 *
 * En v19 `order.change` (pos_order_accounting.js) se calcula como
 * |total| − |pagado| y queda NEGATIVO cuando se paga de más; la pantalla
 * mostraba "Cambio  $ -50". Sólo se corrige la presentación (la etiqueta ya
 * dice "Cambio"): el valor del modelo, que también alimenta
 * `amount_return`, no se toca.
 */
patch(PaymentScreenStatus.prototype, {
    get amountText() {
        if (!this.isRemaining) {
            return this.env.utils.formatCurrency(Math.abs(this.order.change));
        }
        return super.amountText;
    },
});
