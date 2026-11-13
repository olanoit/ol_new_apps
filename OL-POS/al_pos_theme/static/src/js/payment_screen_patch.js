import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
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

// Montos rápidos de efectivo: como máximo tres además de «Exacto».
const QUICK_AMOUNTS_MAX = 3;

/**
 * Los parches van sobre `PaymentScreen.prototype`, así que valen para la
 * pantalla de pago nativa (teléfono) y para el pago en el panel
 * (`AlptInlinePayment`, subclase de PaymentScreen).
 */
patch(PaymentScreen.prototype, {
    paymentMethodImage(id) {
        const src = super.paymentMethodImage(id);
        return DEFAULT_ICONS[src] || src;
    },

    // --- Medios de pago en uso (xml/payment_screen.xml) ----------------------
    alptMethodLines(paymentMethod) {
        return (this.paymentLines || []).filter(
            (line) => line.payment_method_id?.id === paymentMethod.id
        );
    },
    // "" sin pagos · "used" con pagos · "selected" si es el de la línea elegida.
    alptMethodState(paymentMethod) {
        if (!this.alptMethodLines(paymentMethod).length) {
            return "";
        }
        return this.selectedPaymentLine?.payment_method_id?.id === paymentMethod.id
            ? "selected"
            : "used";
    },
    alptMethodAmountLabel(paymentMethod) {
        const total = this.alptMethodLines(paymentMethod).reduce(
            (sum, line) => sum + line.getAmount(),
            0
        );
        return this.env.utils.formatCurrency(total);
    },
    /**
     * El clic en un medio lo selecciona o lo quita: no agrega líneas
     * repetidas del mismo medio. Medios distintos siguen permitiendo pagos
     * divididos. Con cobros ya procesados del medio y saldo pendiente, agrega
     * otra línea (camino nativo) sin tocar lo cobrado.
     */
    async alptTogglePaymentMethod(paymentMethod) {
        if (this.alptPaymentMethodBusy) {
            return;
        }
        this.alptPaymentMethodBusy = true;
        try {
            if (this.alptMethodLines(paymentMethod).length) {
                if (this.alptCanClearMethod(paymentMethod)) {
                    this.alptClearMethod(paymentMethod);
                } else if (this.alptCanAddAfterProcessed(paymentMethod)) {
                    return await this.addNewPaymentLine(paymentMethod);
                } else {
                    this.notification.add(
                        _t(
                            "Un pago procesado o en curso no se puede quitar aquí. Use las acciones de la línea de pago."
                        ),
                        { type: "warning" }
                    );
                }
                return;
            }
            return await this.addNewPaymentLine(paymentMethod);
        } finally {
            this.alptPaymentMethodBusy = false;
        }
    },
    alptPaymentMethodKeydown(event, paymentMethod) {
        // Los botones hijos (la ×) conservan su propio comportamiento.
        if (event.target !== event.currentTarget || !["Enter", " "].includes(event.key)) {
            return;
        }
        event.preventDefault();
        event.stopPropagation();
        return this.alptTogglePaymentMethod(paymentMethod);
    },
    // Sólo líneas sin procesar (o en reintento) de una orden en borrador y
    // sin transacción de terminal en curso.
    alptCanClearMethod(paymentMethod) {
        const lines = this.alptMethodLines(paymentMethod);
        return (
            this.currentOrder?.state === "draft" &&
            !this.pos.paymentTerminalInProgress &&
            lines.length > 0 &&
            lines.every(
                (line) =>
                    !line.getPaymentStatus() ||
                    ["pending", "retry"].includes(line.getPaymentStatus())
            )
        );
    },
    alptCanAddAfterProcessed(paymentMethod) {
        const order = this.currentOrder;
        const lines = this.alptMethodLines(paymentMethod);
        return Boolean(
            order?.state === "draft" &&
                !this.pos.paymentTerminalInProgress &&
                !order.electronicPaymentInProgress() &&
                lines.length > 0 &&
                lines.every((line) => line.getPaymentStatus() === "done") &&
                order.currency.isPositive(order.remainingDue)
        );
    },
    alptClearMethodLabel(paymentMethod) {
        return _t("Quitar los pagos con %s", paymentMethod.name);
    },
    alptClearMethod(paymentMethod) {
        // No reemplaza la anulación ni la reversa de un terminal. Se vuelve a
        // comprobar aquí por si el estado cambió desde el render.
        if (!this.alptCanClearMethod(paymentMethod)) {
            return;
        }
        const uuids = this.alptMethodLines(paymentMethod).map((line) => line.uuid);
        for (const uuid of uuids) {
            this.deletePaymentLine(uuid);
        }
    },

    // --- Montos rápidos de efectivo (xml/inline_payment.xml) -----------------
    /**
     * «Exacto» y los redondeos hacia arriba a las monedas y billetes de la
     * caja (pos.bill, Configuración ▸ Monedas/billetes) que tengan sentido para el
     * monto: sólo denominaciones de al menos un décimo de lo que falta.
     * Mismo camino que el teclado (`numberBuffer.set` +
     * `updateSelectedPaymentline`), con las validaciones del core.
     */
    get alptQuickAmounts() {
        const line = this.selectedPaymentLine;
        const order = this.currentOrder;
        if (!line || !order || this.isRefundOrder || !line.payment_method_id?.is_cash_count) {
            return [];
        }
        if (line.payment_status && line.payment_status !== "pending") {
            return [];
        }
        const others = order.payment_ids
            .filter((payment) => payment !== line)
            .reduce((sum, payment) => sum + payment.getAmount(), 0);
        const need = order.currency.round(order.totalDue - others);
        if (need <= 0) {
            return [];
        }
        const bills = (this.pos.models["pos.bill"]?.getAll() || [])
            .map((bill) => bill.value)
            .filter((value) => value > 0 && value >= need / 10)
            .sort((a, b) => a - b);
        const rounded = [];
        for (const bill of bills) {
            const value = order.currency.round(Math.ceil(need / bill - 1e-9) * bill);
            if (value > need && !rounded.includes(value)) {
                rounded.push(value);
            }
        }
        rounded.sort((a, b) => a - b);
        if (!rounded.length) {
            return [];
        }
        return [
            { value: need, label: _t("Exacto") },
            ...rounded.slice(0, QUICK_AMOUNTS_MAX).map((value) => ({
                value,
                label: this.env.utils.formatCurrency(value),
            })),
        ];
    },
    alptSetQuickAmount(value) {
        // `set` no dispara `triggerAtInput`: se aplica igual que el teclado.
        this.numberBuffer.set(String(value));
        this.updateSelectedPaymentline();
    },

    // --- Teclado de montos: mismo estado que el de la venta (js/sale_screen.js)
    get alptNumpadMode() {
        return this.pos.alptNumpadMode;
    },
    get alptNumpadOpen() {
        return this.pos.alptNumpadOpen;
    },
    alptToggleNumpad() {
        this.pos.alptToggleNumpad();
    },
});
