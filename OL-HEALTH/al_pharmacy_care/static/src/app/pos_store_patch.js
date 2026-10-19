import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { TreatmentRefillDialog } from "./treatment_dialog";

patch(PosStore.prototype, {
    async selectPartner(currentOrder = this.getOrder()) {
        const previous = currentOrder?.getPartner();
        const partner = await super.selectPartner(...arguments);
        if (partner && partner.id && partner.id !== previous?.id) {
            await this.offerPharmacyTreatmentRefill(partner);
        }
        return partner;
    },

    /** Avisa los tratamientos crónicos por reponer y los agrega al pedido. */
    async offerPharmacyTreatmentRefill(partner) {
        let treatments = [];
        try {
            treatments = await this.data.call("pharmacy.treatment", "get_pos_due_treatments", [
                partner.id,
                this.config.id,
            ]);
        } catch {
            // Sin conexión: la venta sigue sin el aviso.
            return;
        }
        if (!treatments?.length) {
            return;
        }
        const add = await makeAwaitable(this.dialog, TreatmentRefillDialog, {
            partnerName: partner.name,
            treatments,
        });
        if (!add) {
            return;
        }
        for (const treatment of treatments) {
            const template = this.models["product.template"].get(treatment.product_tmpl_id);
            if (template) {
                await this.addLineToCurrentOrder({ product_tmpl_id: template });
            }
        }
    },
});
