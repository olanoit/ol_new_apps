import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";

/** Precio por vencer: la escala de la compañía se aplica al vender el lote. */
patch(PosStore.prototype, {
    async editLots(product, packLotLinesToEdit) {
        const result = await super.editLots(product, packLotLinesToEdit);
        if (result && product.product_tmpl_id?.pharmacy_ok) {
            const names = [
                ...(result.newPackLotLines || []).map((lot) => lot.lot_name),
                ...Object.values(result.modifiedPackLotLines || {}),
            ].filter(Boolean);
            if (names.length) {
                try {
                    const info = await this.data.call("pos.order.line", "get_pharmacy_lot_expiry", [
                        this.config.id,
                        product.id,
                        names,
                    ]);
                    this.pharmacyLotExpiry = this.pharmacyLotExpiry || {};
                    for (const [name, values] of Object.entries(info || {})) {
                        this.pharmacyLotExpiry[`${product.id}|${name}`] = values;
                    }
                } catch {
                    // Sin conexión no se aplica el descuento: se vende a precio normal.
                }
            }
        }
        return result;
    },

    async addLineToOrder(vals, order, opts = {}, configure = true) {
        const line = await super.addLineToOrder(vals, order, opts, configure);
        if (line) {
            this.applyPharmacyExpiryDiscount(line);
        }
        return line;
    },

    applyPharmacyExpiryDiscount(line) {
        const lotName = line.pack_lot_ids?.[0]?.lot_name;
        const info = lotName && this.pharmacyLotExpiry?.[`${line.product_id.id}|${lotName}`];
        if (info && info.discount > 0) {
            const [year, month, day] = info.expiration_date.split("-");
            line.setDiscount(info.discount);
            line.setCustomerNote(_t("Por vencer: vence %s", `${day}/${month}/${year}`));
            line.pharmacy_expiry_applied = true;
        } else if (line.pharmacy_expiry_applied) {
            // Se cambió a un lote sin descuento: la línea vuelve al precio normal.
            line.setDiscount(0);
            line.setCustomerNote("");
            line.pharmacy_expiry_applied = false;
        }
    },
});

patch(OrderSummary.prototype, {
    async editPackLotLines(line) {
        await super.editPackLotLines(line);
        this.pos.applyPharmacyExpiryDiscount(line);
    },
});
