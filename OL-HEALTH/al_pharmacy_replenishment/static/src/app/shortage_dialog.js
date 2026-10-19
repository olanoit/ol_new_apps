import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export const SHORTAGE_REASONS = [
    ["no_stock", "Sin stock"],
    ["not_carried", "No lo trabajamos"],
    ["price", "Precio"],
    ["other", "Otro"],
];

/**
 * Faltante desde la caja: lo que el cliente pidió y no se le vendió.
 * Devuelve por getPayload { productId, description, quantity, reason }.
 */
export class ShortageDialog extends Component {
    static template = "al_pharmacy_replenishment.ShortageDialog";
    static components = { Dialog };
    static props = {
        productId: { type: [Number, Boolean], optional: true },
        productName: { type: String, optional: true },
        getPayload: Function,
        close: Function,
    };

    setup() {
        this.reasons = SHORTAGE_REASONS;
        this.state = useState({
            useProduct: Boolean(this.props.productId),
            description: "",
            quantity: 1,
            reason: this.props.productId ? "no_stock" : "not_carried",
        });
    }

    get canSave() {
        const quantity = parseFloat(this.state.quantity);
        return (
            quantity > 0 &&
            ((this.state.useProduct && this.props.productId) || this.state.description.trim())
        );
    }

    save() {
        const useProduct = this.state.useProduct && this.props.productId;
        this.props.getPayload({
            productId: useProduct ? this.props.productId : false,
            description: this.state.description.trim(),
            quantity: parseFloat(this.state.quantity),
            reason: this.state.reason,
        });
        this.props.close();
    }
}
