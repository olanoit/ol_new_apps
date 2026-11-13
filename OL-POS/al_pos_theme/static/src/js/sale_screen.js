import { onMounted, useEffect, useRef, useState, useSubEnv } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { capitalize } from "@web/core/utils/strings";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { parseFloat } from "@web/views/fields/parsers";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { NumberPopup } from "@point_of_sale/app/components/popups/number_popup/number_popup";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { Orderline } from "@point_of_sale/app/components/orderline/orderline";
import { OrderDisplay } from "@point_of_sale/app/components/order_display/order_display";

/**
 * Pantalla de venta: teclado numérico configurable por caja y controles de
 * cantidad en la línea seleccionada del ticket (xml/product_screen.xml,
 * xml/order_summary.xml).
 *
 * Sólo presentación y atajos sobre la lógica del core: el −/+, la cantidad
 * escrita y el basurero pasan por `OrderSummary.updateSelectedOrderline` (el
 * mismo camino que el teclado numérico), así se respetan devoluciones,
 * combos, `disallowLineQuantityChange` y los parches de otros módulos sobre
 * `setQuantity` / `removeOrderline`.
 */

const NUMPAD_MODE_LABELS = {
    quantity: _t("cantidad"),
    discount: _t("% de descuento"),
    price: _t("precio"),
};

// Estado del teclado, compartido por la venta y el pago: si el cajero lo
// pliega en una pantalla, queda plegado en la otra. `null` = todavía no
// tocado: vale el valor de la caja (pos.config.al_theme_numpad_mode).
patch(PosStore.prototype, {
    async setup() {
        this.alptNumpadOpenState = null;
        return await super.setup(...arguments);
    },
    get alptNumpadMode() {
        return this.config.al_theme_numpad_mode || "visible";
    },
    get alptNumpadOpen() {
        const mode = this.alptNumpadMode;
        if (mode === "none") {
            return false;
        }
        return this.alptNumpadOpenState ?? mode === "visible";
    },
    alptToggleNumpad() {
        this.alptNumpadOpenState = !this.alptNumpadOpen;
    },
});

patch(ProductScreen.prototype, {
    setup() {
        super.setup(...arguments);
        // Al entrar a la venta (p. ej. al volver del pago o de Órdenes) con
        // productos y sin línea seleccionada, se selecciona la última, como
        // hace el core al agregar un producto: el teclado queda listo.
        onMounted(() => {
            const order = this.currentOrder;
            if (!order || order.isEmpty() || order.getSelectedOrderline()) {
                return;
            }
            const last = order.getOrderlines().at(-1);
            if (last) {
                this.pos.selectOrderLine(order, last.combo_parent_id || last);
            }
        });
    },
    // Botones del core; sin línea seleccionada, deshabilitados (el teclado se
    // ve igual y el panel no cambia de alto, pero no hay nada que editar).
    alptNumpadButtons() {
        const buttons = this.getNumpadButtons();
        if (this.currentOrder?.getSelectedOrderline()) {
            return buttons;
        }
        return buttons.map((button) => ({ ...button, disabled: true }));
    },
    get alptNumpadMode() {
        return this.pos.alptNumpadMode;
    },
    get alptNumpadOpen() {
        // Teléfono: flujo nativo, el teclado siempre (salvo «Sin teclado»).
        if (this.pos.isSmallProductScreen) {
            return this.alptNumpadMode !== "none";
        }
        return this.pos.alptNumpadOpen;
    },
    get alptNumpadHint() {
        const line = this.currentOrder?.getSelectedOrderline();
        if (!line) {
            return _t("Seleccione una línea para editarla");
        }
        return _t("Editando %(mode)s de %(product)s", {
            mode: NUMPAD_MODE_LABELS[this.pos.numpadMode] || this.pos.numpadMode,
            product: line.getFullProductName?.() || line.product_id?.display_name || "",
        });
    },
    alptToggleNumpad() {
        this.pos.alptToggleNumpad();
    },
});

patch(OrderSummary.prototype, {
    setup() {
        super.setup(...arguments);
        // Sólo el ticket de la venta publica estas acciones: en Órdenes y en
        // los recibos la línea queda como en el core.
        useSubEnv({
            alptStepLine: (line, delta) => this.alptStepLine(line, delta),
            alptEditLineQty: (line) => this.alptEditLineQty(line),
            alptSetLineQty: (line, qty) => this.alptSetLineQty(line, qty),
            alptRemoveLine: (line) => this.alptRemoveLine(line),
        });
    },
    /**
     * Selecciona la línea y deja el teclado en modo cantidad. Devuelve false
     * si la orden es un reembolso (mismo bloqueo que
     * ProductScreen.onNumpadClick).
     */
    _alptPrepareLine(line) {
        const order = this.currentOrder;
        if (!order || !line) {
            return false;
        }
        if (order.isRefund) {
            this.dialog.add(AlertDialog, {
                title: _t("%s update not allowed", capitalize(_t("quantity"))),
                body: _t("You can not change the %s of the refund order.", _t("quantity")),
            });
            return false;
        }
        if (!line.isSelected()) {
            this.pos.selectOrderLine(order, line);
        }
        this.numberBuffer.reset();
        this.pos.numpadMode = "quantity";
        return true;
    },
    // Cantidad nueva por el mismo camino que el teclado (0 = quitar la línea).
    async _alptApplyLineQty(qty, key) {
        await this.updateSelectedOrderline({
            buffer: qty === 0 ? null : String(qty),
            key,
        });
        this.numberBuffer.reset();
    },
    async alptStepLine(line, delta) {
        if (!this._alptPrepareLine(line)) {
            return;
        }
        const target = line.combo_parent_id || line;
        await this._alptApplyLineQty(target.getQuantity() + delta, delta > 0 ? "+" : "-");
    },
    // Tocar la cantidad en pantallas táctiles: teclado del TPV (NumberPopup).
    async alptEditLineQty(line) {
        if (!this._alptPrepareLine(line)) {
            return;
        }
        const target = line.combo_parent_id || line;
        const value = await makeAwaitable(this.dialog, NumberPopup, {
            title: _t("Cantidad"),
            subtitle: target.getFullProductName(),
            startingValue: this.env.utils.formatProductQty(target.getQuantity(), false),
            confirmButtonLabel: _t("Aplicar"),
            isValid: (buffer) => buffer !== "" && !isNaN(parseFloat(buffer)),
        });
        if (value === undefined || value === null || value === "") {
            return;
        }
        const qty = parseFloat(value);
        if (isNaN(qty)) {
            return;
        }
        await this._alptApplyLineQty(qty, "");
    },
    // Cantidad escrita en la misma línea (modo «Escribir en la línea»).
    async alptSetLineQty(line, qty) {
        if (!this._alptPrepareLine(line)) {
            return;
        }
        await this._alptApplyLineQty(qty, "");
    },
    // Basurero: quita la línea (como ⌫ con la cantidad vacía).
    async alptRemoveLine(line) {
        if (!this._alptPrepareLine(line)) {
            return;
        }
        await this._alptApplyLineQty(0, "Backspace");
    },
});

/**
 * Al tocar la cantidad: ¿escribir en la línea o abrir el teclado del TPV?
 * pos.config.al_theme_qty_edit_mode: "inline" / "popup" / "auto". En "auto"
 * se escribe en la línea si el equipo tiene un puntero fino (mouse o
 * trackpad), señal de un PC de caja con teclado físico; en pantallas sólo
 * táctiles se abre el teclado del TPV (un campo de texto abriría el teclado
 * del sistema operativo). El navegador no permite detectar el teclado físico.
 */
function alptQtyEditsInline(config) {
    const mode = config?.al_theme_qty_edit_mode || "auto";
    if (mode !== "auto") {
        return mode === "inline";
    }
    return Boolean(window.matchMedia?.("(any-pointer: fine)").matches);
}

patch(Orderline.prototype, {
    setup() {
        super.setup(...arguments);
        this.alptQtyState = useState({ editing: false });
        this.alptQtyInput = useRef("alptQtyInput");
        useEffect(
            (editing) => {
                const input = this.alptQtyInput.el;
                if (editing && input) {
                    input.focus();
                    input.select();
                }
            },
            () => [this.alptQtyState.editing]
        );
    },
    // Controles sólo en la línea seleccionada del ticket de la venta: las
    // demás líneas quedan con el diseño del core.
    get alptShowLineActions() {
        const line = this.line;
        return Boolean(
            this.env.alptStepLine &&
                this.props.mode === "display" &&
                line.isSelected() &&
                !line.combo_parent_id &&
                !line.isTipLine?.()
        );
    },
    get alptQtyLabel() {
        return this.env.utils.formatProductQty(this.line.getQuantity(), false);
    },
    get alptStepperLabel() {
        return _t("Cantidad de %s", this.line.getFullProductName?.() || "");
    },
    get alptRemoveLabel() {
        return _t("Quitar %s de la orden", this.line.getFullProductName?.() || "");
    },
    alptStep(delta) {
        this.env.alptStepLine(this.line, delta);
    },
    alptEditQty() {
        if (alptQtyEditsInline(this.env.services.pos?.config)) {
            this.alptQtyState.editing = true;
        } else {
            this.env.alptEditLineQty(this.line);
        }
    },
    // Campo de la línea: Enter o salir del campo aplica, Escape cancela.
    alptOnQtyKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            ev.target.blur();
        } else if (ev.key === "Escape") {
            ev.preventDefault();
            this.alptQtyState.editing = false;
        }
        // El teclado físico no debe llegar al buffer numérico del TPV.
        ev.stopPropagation();
    },
    async alptCommitQty(ev) {
        if (!this.alptQtyState.editing) {
            return; // ya cancelado con Escape
        }
        this.alptQtyState.editing = false;
        const raw = (ev.target.value || "").trim();
        if (!raw) {
            return;
        }
        let qty;
        try {
            qty = parseFloat(raw);
        } catch {
            return;
        }
        if (isNaN(qty) || qty === this.line.getQuantity()) {
            return;
        }
        await this.env.alptSetLineQty(this.line, qty);
    },
    alptRemove() {
        this.env.alptRemoveLine(this.line);
    },
});

/**
 * Ticket de la venta sin saltos: el core hace `scrollIntoView({ block:
 * "start" })` de la línea seleccionada en CADA render, así que cada −/+ o
 * cambio de cantidad desplazaba la lista. En el ticket de la venta
 * (`env.alptStepLine`) se desplaza sólo lo necesario para que la línea se
 * vea (`block: "nearest"`): si ya se ve, no se mueve. Órdenes y recibos
 * quedan como en el core.
 */
patch(OrderDisplay.prototype, {
    setup() {
        super.setup(...arguments);
        if (!this.env.alptStepLine) {
            return;
        }
        const scrollable = this.scrollableRef;
        // El efecto del core lee `this.scrollableRef.el`: sin elemento no
        // hace nada. La referencia real (t-ref="scrollable") sigue viva.
        this.scrollableRef = { el: null };
        useEffect(() => {
            scrollable.el
                ?.querySelector(".orderline.selected")
                ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
        });
    },
});
