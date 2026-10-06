import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

/**
 * Formulario del libro de reclamaciones: muestra los datos del representante
 * solo para menores de edad y evita envíos dobles.
 */
export class ComplaintForm extends Interaction {
    static selector = ".o_l10n_pe_complaints_book .lr-form";
    dynamicContent = {
        "#lr_is_minor": { "t-on-change": this.onMinorChange },
        _root: { "t-on-submit": this.onSubmit },
    };

    onMinorChange(ev) {
        const guardian = this.el.querySelector(".lr-guardian");
        guardian.classList.toggle("d-none", !ev.currentTarget.checked);
        this.el.querySelector("#lr_guardian_name").required = ev.currentTarget.checked;
    }

    onSubmit() {
        const button = this.el.querySelector("button[type=submit]");
        if (button) {
            button.disabled = true;
        }
    }
}

registry.category("public.interactions").add("al_l10n_pe_complaints_book.complaint_form", ComplaintForm);
