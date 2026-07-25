/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { SelectionPopupCustom } from "@al_pos_vendedor/js/selection_popup_custom";

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate = false) {
        if (this.pos.config.authorized_seller && !this.currentOrder.seller_id) {
            // Si no hay vendedor asignado, abrir directamente el selector en
            // lugar de bloquear con una alerta. Solo si el usuario lo cierra
            // sin elegir se le advierte que el vendedor es obligatorio.
            await this.addVendedor();
            if (!this.currentOrder.seller_id) {
                this.dialog.add(AlertDialog, {
                    title: _t("Vendedor requerido"),
                    body: _t("Debe seleccionar un vendedor antes de validar la venta."),
                });
                return;
            }
        }
        return super.validateOrder(isForceValidate);
    },

    async addVendedor() {
        const currentOrder = this.currentOrder;
        const vendedores = this.pos.getVendedores();
        const defaultSeller = this.pos.getSessionDefaultSeller();

        const selectionList = vendedores.map((v) => ({
            id: v.id,
            label: v.name,
            isSelected: currentOrder.seller_id?.id === v.id,
            item: v,
        }));

        const result = await makeAwaitable(this.dialog, SelectionPopupCustom, {
            title: "Seleccionar vendedor",
            list: selectionList,
            cancelText: "Cancelar",
            defaultId: defaultSeller ? defaultSeller.id : null,
            onSetDefault: (seller) => this.pos.setSessionDefaultSeller(seller),
        });

        // undefined = canceló (sin cambio) | null = quitó vendedor | objeto = seleccionó
        if (result !== undefined) {
            currentOrder.seller_id = result;
        }
    },

    getVendedorName() {
        return this.currentOrder?.seller_id?.name || false;
    },
});
