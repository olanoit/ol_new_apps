import { patch } from "@web/core/utils/patch";
import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";
import { CustomerDisplayPosAdapter } from "@point_of_sale/app/customer_display/customer_display_adapter";
import { formatCurrency } from "@point_of_sale/app/models/utils/currency";

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

/**
 * Pantalla del cliente: el mismo cambio sin signo menos («Cambio  $ 50» en
 * vez de «$ -50»). Los datos de esa pantalla se arman en la caja.
 */
patch(CustomerDisplayPosAdapter.prototype, {
    formatOrderData(order) {
        super.formatOrderData(...arguments);
        if (order.change) {
            this.data.change = formatCurrency(Math.abs(order.change), order.currency);
        }
    },
});
