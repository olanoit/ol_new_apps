import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";

/**
 * Pago en el panel derecho, sin cambiar de pantalla (escritorio/tablet).
 *
 * En vez de navegar a PaymentScreen, el panel de la orden de ProductScreen
 * se transforma en el panel de pago. Toda la lógica es la nativa:
 * `AlptInlinePayment` es una subclase de `PaymentScreen` (métodos, líneas,
 * numpad, validación con `OrderPaymentValidation`, y los parches de otros
 * módulos del TPV (al_pos_vendedor, al_l10n_pe_edi_pos…),
 * que se aplican sobre `PaymentScreen.prototype` y por lo tanto se heredan).
 *
 * El enganche es `PosStore.navigate`: cualquier flujo que pida
 * "PaymentScreen" (el `pay()` del core, pos_settle_due…)
 * abre el pago en el panel. En teléfono se mantiene el flujo nativo.
 */
export class AlptInlinePayment extends PaymentScreen {
    static template = "al_pos_theme.InlinePayment";

    alptClose() {
        this.pos.alptInlinePaymentOrderUuid = null;
    }
}
// El core identifica la pantalla por `constructor.name`:
// - useRouterParamsChecker() busca sus parámetros en el registro `pos_pages`
//   (la ruta actual, ProductScreen, trae el mismo `orderUuid`, así que la
//   verificación pasa);
// - number_buffer quita su entrada de la pila por ese nombre al destruirse.
// Con el nombre "PaymentScreen" ambos se comportan igual que en el nativo.
Object.defineProperty(AlptInlinePayment, "name", { value: "PaymentScreen" });

patch(PosStore.prototype, {
    async setup() {
        // uuid de la orden que se está pagando en el panel (o null).
        this.alptInlinePaymentOrderUuid = null;
        return super.setup(...arguments);
    },

    alptUseInlinePayment() {
        return !this.ui?.isSmall;
    },

    navigate(routeName, routeParams = {}) {
        if (routeName === "PaymentScreen" && this.alptUseInlinePayment()) {
            const orderUuid = routeParams.orderUuid || this.selectedOrderUuid;
            const order = this.models["pos.order"].getBy("uuid", orderUuid);
            if (order && !order.finalized) {
                if (
                    this.router.state.current !== "ProductScreen" ||
                    this.router.state.params?.orderUuid !== orderUuid
                ) {
                    super.navigate("ProductScreen", { orderUuid });
                }
                this.alptInlinePaymentOrderUuid = orderUuid;
                return true;
            }
        }
        if (this.alptInlinePaymentOrderUuid) {
            // Igual que el core con PaymentScreen: el temporizador de
            // inactividad no manda al reposo en pleno cobro.
            if (routeName === "SaverScreen") {
                return false;
            }
            this.alptInlinePaymentOrderUuid = null;
        }
        return super.navigate(routeName, routeParams);
    },
});

ProductScreen.components = { ...ProductScreen.components, AlptInlinePayment };

patch(ProductScreen.prototype, {
    get alptInlinePayment() {
        const uuid = this.pos.alptInlinePaymentOrderUuid;
        return Boolean(uuid) && uuid === this.currentOrder?.uuid && this.pos.alptUseInlinePayment();
    },

    // Mientras se cobra, un escaneo no debe agregar productos ni descuentos
    // a la orden (en el nativo PaymentScreen no los procesa).
    async _barcodeProductAction() {
        if (this.alptInlinePayment) {
            return;
        }
        return super._barcodeProductAction(...arguments);
    },
    _barcodeDiscountAction() {
        if (this.alptInlinePayment) {
            return;
        }
        return super._barcodeDiscountAction(...arguments);
    },
    async _barcodeGS1Action() {
        if (this.alptInlinePayment) {
            return;
        }
        return super._barcodeGS1Action(...arguments);
    },
});
