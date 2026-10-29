import { Component, proxy, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

/**
 * Datos de la receta en la caja (BPOF 7.5.2.9). Devuelve por getPayload:
 * { action: "register", number, date, prescriberName, license, patientName }
 * { action: "exception" }  (Q.F. autoriza sin receta, si se permite)
 * { action: "continue" }   (solo aviso, según el ajuste de la compañía)
 */
export class PrescriptionDialog extends Component {
    static template = "al_pharmacy_pos.PrescriptionDialog";
    static components = { Dialog };
    props = useProps({
        productName: t.string(),
        controlled: t.boolean(),
        needsPatient: t.boolean(),
        allowException: t.boolean(),
        allowContinue: t.boolean(),
        getPayload: t.function(),
        close: t.function(),
    });

    setup() {
        this.state = proxy({
            number: "",
            date: new Date().toISOString().slice(0, 10),
            prescriberName: "",
            license: "",
            patientName: "",
        });
    }

    get canRegister() {
        const s = this.state;
        return (
            s.license.trim() &&
            s.prescriberName.trim() &&
            (!this.props.needsPatient || s.patientName.trim())
        );
    }

    register() {
        this.props.getPayload({ action: "register", ...this.state });
        this.props.close();
    }

    exception() {
        this.props.getPayload({ action: "exception" });
        this.props.close();
    }

    continueWithout() {
        this.props.getPayload({ action: "continue" });
        this.props.close();
    }
}
