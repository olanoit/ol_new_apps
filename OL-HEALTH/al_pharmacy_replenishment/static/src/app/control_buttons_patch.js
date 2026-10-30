import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { ShortageDialog } from "./shortage_dialog";

patch(ControlButtons.prototype, {
    async clickPharmacyShortage() {
        const product = this.currentOrder?.getSelectedOrderline()?.product_id;
        const result = await makeAwaitable(this.dialog, ShortageDialog, {
            productId: product?.id || false,
            productName: product?.display_name || "",
        });
        if (!result) {
            return;
        }
        const cashier = this.pos.accessRight.loggedCashier;
        try {
            await this.pos.data.call("pharmacy.shortage", "create_from_pos", [
                {
                    session_id: this.pos.session.id,
                    product_id: result.productId,
                    description: result.description,
                    quantity: result.quantity,
                    reason: result.reason,
                    // Con «Iniciar sesión con empleados» (pos_hr) quien atiende es un empleado.
                    employee_id: this.pos.config.module_pos_hr ? cashier?.id || false : false,
                },
            ]);
        } catch (error) {
            this.notification.add(_t("No se pudo registrar el faltante: revise la conexión."), {
                type: "danger",
            });
            throw error;
        }
        this.notification.add(_t("Faltante registrado."), { type: "success" });
    },
});
