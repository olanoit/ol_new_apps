import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

/**
 * Íconos de métodos de pago.
 *
 * Si el método tiene imagen propia (pos.payment.method.image) se respeta;
 * sólo se reemplazan los tres PNG por defecto del core (gráficos
 * reconocibles del sistema base) por íconos SVG del tema.
 */
const DEFAULT_ICONS = {
    "/point_of_sale/static/src/img/money.png": "/al_pos_theme/static/src/img/pm-cash.svg",
    "/point_of_sale/static/src/img/card-bank.png": "/al_pos_theme/static/src/img/pm-card.svg",
    "/point_of_sale/static/src/img/pay-later.png": "/al_pos_theme/static/src/img/pm-pay-later.svg",
};

patch(PaymentScreen.prototype, {
    paymentMethodImage(id) {
        const src = super.paymentMethodImage(id);
        return DEFAULT_ICONS[src] || src;
    },
});
