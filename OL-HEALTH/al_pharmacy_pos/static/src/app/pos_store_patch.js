import { _t } from "@web/core/l10n/translation";
import { formatCurrency } from "@web/core/currency";
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { SelectionPopup } from "@point_of_sale/app/components/popups/selection_popup/selection_popup";

patch(PosStore.prototype, {
    getPharmacyPresentations(productTemplate) {
        return this.models["pharmacy.presentation"]
            .getAll()
            .filter((presentation) => presentation.product_tmpl_id?.id === productTemplate.id)
            .sort((a, b) => a.sequence - b.sequence || a.factor - b.factor);
    },

    /**
     * Pregunta en qué presentación se vende el producto. Devuelve la
     * presentación, "unit" para la unidad suelta o undefined si se cancela.
     */
    async choosePharmacyPresentation(productTemplate, presentations, order) {
        const currencyId = this.currency.id;
        const unitPrice = productTemplate.product_variant_ids[0].getPrice(
            order.pricelist_id,
            1,
            0,
            false,
            productTemplate.product_variant_ids[0]
        );
        const list = [
            {
                id: 0,
                label: _t("Unidad — %s", formatCurrency(unitPrice, currencyId)),
                item: "unit",
            },
            ...presentations.map((presentation) => ({
                id: presentation.id,
                label: `${presentation.display_name} — ${formatCurrency(
                    presentation.price,
                    currencyId
                )}`,
                item: presentation,
            })),
        ];
        return await makeAwaitable(this.dialog, SelectionPopup, {
            title: _t("Presentación de %s", productTemplate.display_name),
            list,
        });
    },

    _pharmacyPresentationValues(vals, presentation, order) {
        const sign = order.preset_id?.is_return ? -1 : 1;
        const count = Math.abs(vals.qty || 1);
        return {
            ...vals,
            pharmacy_presentation_id: presentation,
            qty: sign * count * presentation.factor,
            // Sin redondear: la línea suma exactamente el precio de la
            // presentación (ver setUnitPrice).
            price_unit: presentation.price / presentation.factor,
        };
    },

    async addLineToOrder(vals, order, opts = {}, configure = true) {
        const productTemplate =
            typeof vals.product_tmpl_id === "number"
                ? this.data.models["product.template"].get(vals.product_tmpl_id)
                : vals.product_tmpl_id;
        if (productTemplate && !("price_unit" in vals) && !vals.pharmacy_presentation_id) {
            const presentations = this.getPharmacyPresentations(productTemplate);
            if (presentations.length) {
                const code = opts.code;
                if (code) {
                    // Código de barras de un empaque: si su unidad es la de
                    // una presentación, se vende como esa presentación.
                    const packaging = this.models["product.uom"].getAllBy("barcode")[code.code];
                    const presentation =
                        packaging &&
                        presentations.find((p) => p.uom_id?.id === packaging.uom_id?.id);
                    if (presentation) {
                        vals = this._pharmacyPresentationValues(vals, presentation, order);
                    }
                } else if (configure) {
                    const choice = await this.choosePharmacyPresentation(
                        productTemplate,
                        presentations,
                        order
                    );
                    if (!choice) {
                        return;
                    }
                    if (choice !== "unit") {
                        vals = this._pharmacyPresentationValues(vals, choice, order);
                    }
                }
            }
        }
        return await super.addLineToOrder(vals, order, opts, configure);
    },
});
