import { _t } from "@web/core/l10n/translation";
import { formatCurrency } from "@web/core/currency";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { SelectionPopup } from "@point_of_sale/app/components/popups/selection_popup/selection_popup";
import { PrescriptionDialog } from "./prescription_dialog";

const PRODUCT_TYPE_LABELS = {
    generic_dci: _t("Genérico en DCI"),
    generic_brand: _t("Genérico de marca"),
    innovator: _t("Innovador o de marca"),
};

patch(PosStore.prototype, {
    // ------------------------------------------------------------------
    // Presentaciones (caja, blíster)
    // ------------------------------------------------------------------
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

    // ------------------------------------------------------------------
    // Alternativas (Ley 32033: genéricos en DCI primero, por precio)
    // ------------------------------------------------------------------
    getPharmacyAlternatives(productTemplate) {
        const key = productTemplate.pharmacy_equivalence_key;
        if (!key) {
            return [];
        }
        return this.models["product.template"]
            .getAll()
            .filter(
                (template) =>
                    template.id !== productTemplate.id &&
                    template.available_in_pos &&
                    template.pharmacy_equivalence_key === key
            )
            .sort(
                (a, b) =>
                    (a.pharmacy_product_type !== "generic_dci") -
                        (b.pharmacy_product_type !== "generic_dci") ||
                    a.list_price - b.list_price
            );
    },

    async choosePharmacyAlternative(productTemplate, alternatives) {
        const currencyId = this.currency.id;
        const label = (template, prefix) =>
            `${prefix}${template.display_name} — ${formatCurrency(
                template.list_price,
                currencyId
            )} · ${PRODUCT_TYPE_LABELS[template.pharmacy_product_type] || ""}`;
        const list = [
            { id: productTemplate.id, label: label(productTemplate, _t("Mantener: ")), item: productTemplate },
            ...alternatives.map((template) => ({
                id: template.id,
                label: label(template, ""),
                item: template,
            })),
        ];
        return await makeAwaitable(this.dialog, SelectionPopup, {
            title: _t("Alternativas de %s (genéricos primero)", productTemplate.display_name),
            list,
        });
    },

    // ------------------------------------------------------------------
    // Receta y químico farmacéutico en la caja
    // ------------------------------------------------------------------
    isPharmacistCashier() {
        const cashier = this.getCashier();
        return Boolean(cashier?.pharmacy_role === "pharmacist" || cashier?.pharmacy_is_pharmacist);
    },

    /** true si la venta puede seguir; false si se cancela o se bloquea. */
    async checkPharmacyPrescription(productTemplate, order) {
        const condition = productTemplate.pharmacy_sale_condition;
        if (!productTemplate.pharmacy_ok || !["prescription", "controlled"].includes(condition)) {
            return true;
        }
        const company = this.company;
        const isPharmacist = this.isPharmacistCashier();
        if (!isPharmacist) {
            if (company.pharmacy_pharmacist_policy === "block") {
                this.dialog.add(AlertDialog, {
                    title: _t("Se necesita un químico farmacéutico"),
                    body: _t(
                        "%s se vende con receta: debe atender un químico farmacéutico.",
                        productTemplate.display_name
                    ),
                });
                return false;
            }
            order.pharmacy_no_pharmacist_alert = true;
            this.notification.add(
                _t("Venta con receta sin químico farmacéutico en la caja: queda en el libro de ocurrencias."),
                { type: "warning" }
            );
        }
        if (order.pharmacy_prescription_number || order.pharmacy_prescriber_license) {
            return true;
        }
        if (condition !== "controlled" && (order.pharmacy_exception_employee_id || order.pharmacy_exception_user_id)) {
            return true;
        }
        const controlled = condition === "controlled";
        const result = await makeAwaitable(this.dialog, PrescriptionDialog, {
            productName: productTemplate.display_name,
            controlled,
            needsPatient: !order.getPartner(),
            allowException:
                !controlled && company.pharmacy_prescription_policy === "block" && isPharmacist,
            allowContinue: !controlled && company.pharmacy_prescription_policy === "warn",
        });
        if (!result) {
            return false;
        }
        if (result.action === "register") {
            Object.assign(order, {
                pharmacy_prescription_number: result.number,
                pharmacy_prescription_date: result.date,
                pharmacy_prescriber_name: result.prescriberName,
                pharmacy_prescriber_license: result.license,
                pharmacy_patient_name: result.patientName,
            });
        } else if (result.action === "exception") {
            const cashier = this.getCashier();
            // Con «Iniciar sesión con empleados» (pos_hr) quien atiende es un
            // empleado; si no, el usuario.
            if (this.config.module_pos_hr) {
                order.pharmacy_exception_employee_id = cashier;
            } else {
                order.pharmacy_exception_user_id = cashier;
            }
        }
        return true;
    },

    // ------------------------------------------------------------------
    async addLineToOrder(vals, order, opts = {}, configure = true) {
        let productTemplate =
            typeof vals.product_tmpl_id === "number"
                ? this.data.models["product.template"].get(vals.product_tmpl_id)
                : vals.product_tmpl_id;
        if (productTemplate && !("price_unit" in vals) && !vals.pharmacy_presentation_id) {
            if (configure && !opts.code && productTemplate.pharmacy_product_type !== "generic_dci") {
                const alternatives = this.getPharmacyAlternatives(productTemplate);
                if (alternatives.length) {
                    const chosen = await this.choosePharmacyAlternative(productTemplate, alternatives);
                    if (!chosen) {
                        return;
                    }
                    if (chosen.id !== productTemplate.id) {
                        productTemplate = chosen;
                        vals = {
                            ...vals,
                            product_tmpl_id: chosen,
                            product_id: chosen.product_variant_ids[0],
                        };
                    }
                }
            }
            if (configure && !(await this.checkPharmacyPrescription(productTemplate, order))) {
                return;
            }
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
