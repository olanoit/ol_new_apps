import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

/**
 * Tratamientos del cliente que toca reponer. getPayload recibe true si el
 * cajero los agrega al pedido.
 */
export class TreatmentRefillDialog extends Component {
    static template = "al_pharmacy_care.TreatmentRefillDialog";
    static components = { Dialog };
    static props = {
        partnerName: String,
        treatments: Array,
        getPayload: Function,
        close: Function,
    };

    formatDate(value) {
        if (!value) {
            return "";
        }
        const [year, month, day] = value.split("-");
        return `${day}/${month}/${year}`;
    }

    add() {
        this.props.getPayload(true);
        this.props.close();
    }

    skip() {
        this.props.getPayload(false);
        this.props.close();
    }
}
