import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { roundPrecision } from "@web/core/utils/numbers";

/**
 * Parte cubierta que vuelve a la aseguradora en una devolución (negativa):
 * la proporción devuelta de lo cubierto en cada línea de origen, redondeada
 * por línea como en el servidor.
 */
function insuranceRefundAmount(order, currency) {
    return order.lines.reduce((total, line) => {
        const origin = line.refunded_orderline_id;
        if (!origin?.pharmacy_insurance_amount || !origin.qty) {
            return total;
        }
        const part = (origin.pharmacy_insurance_amount * line.qty) / origin.qty;
        return roundPrecision(total + roundPrecision(part, currency.rounding), currency.rounding);
    }, 0);
}

patch(PaymentScreen.prototype, {
    /**
     * Método de pago de un convenio: el monto es lo que cubre el convenio
     * (cobertura, copago y topes), calculado en el servidor línea por línea;
     * el resto se cobra al paciente con los demás métodos. La parte cubierta
     * se factura a la aseguradora en la liquidación.
     */
    async addNewPaymentLine(paymentMethod) {
        if (!paymentMethod.pharmacy_is_insurance) {
            return await super.addNewPaymentLine(paymentMethod);
        }
        const order = this.currentOrder;
        const refundAmount = insuranceRefundAmount(order, this.pos.currency);
        if (refundAmount) {
            // Devolución: vuelve a la aseguradora lo que ella pagó.
            return await this._addPharmacyInsuranceLine(paymentMethod, refundAmount);
        }
        const coverage = await this.pos.data.call("pharmacy.insurance.agreement", "get_pos_coverage", [
            paymentMethod.id,
            order.getPartner()?.id || false,
            order.getOrderlines().map((line) => ({
                product_id: line.product_id.id,
                price_unit: line.price_unit,
                qty: line.qty,
                discount: line.discount,
                tax_ids: (order.fiscal_position_id
                    ? order.fiscal_position_id.getTaxesAfterFiscalPosition(line.tax_ids)
                    : line.tax_ids
                ).map((tax) => tax.id),
            })),
            Boolean(order.pharmacy_prescription_number),
        ]);
        if (coverage.error) {
            this.dialog.add(AlertDialog, { title: _t("Convenio"), body: coverage.error });
            return false;
        }
        const amount = Math.min(coverage.amount, order.remainingDue);
        const added = await this._addPharmacyInsuranceLine(paymentMethod, amount);
        if (!added) {
            return added;
        }
        this.notification.add(
            _t("%(agreement)s cubre %(amount)s (afiliado %(affiliate)s).", {
                agreement: coverage.agreement,
                amount: this.pos.formatCurrency(amount),
                affiliate: coverage.affiliate,
            }),
            { type: "info" }
        );
        return added;
    },

    /**
     * Odoo 20: el monto de la línea se fija al crearla
     * (``getDefaultAmountDueToPayIn``); cambiarlo después no refresca el saldo.
     */
    async _addPharmacyInsuranceLine(paymentMethod, amount) {
        const order = this.currentOrder;
        order.uiState.pharmacyInsuranceAmount = amount;
        try {
            return await super.addNewPaymentLine(paymentMethod);
        } finally {
            delete order.uiState.pharmacyInsuranceAmount;
        }
    },
});

patch(PosOrder.prototype, {
    getDefaultAmountDueToPayIn(paymentMethod) {
        const amount = this.uiState?.pharmacyInsuranceAmount;
        if (paymentMethod.pharmacy_is_insurance && amount !== undefined) {
            return amount;
        }
        return super.getDefaultAmountDueToPayIn(...arguments);
    },
});

patch(OrderPaymentValidation.prototype, {
    // Una devolución de una venta con convenio devuelve al paciente solo lo
    // que pagó: la parte cubierta va con el método del convenio.
    async isOrderValid(isForceValidate) {
        const expected = insuranceRefundAmount(this.order, this.pos.currency);
        if (expected) {
            const paid = this.order.payment_ids
                .filter((line) => line.payment_method_id.pharmacy_is_insurance)
                .reduce((total, line) => total + line.getAmount(), 0);
            if (Math.abs(paid - expected) > this.pos.currency.rounding / 2) {
                this.pos.dialog.add(AlertDialog, {
                    title: _t("Convenio"),
                    body: _t(
                        "Devuelva %(amount)s con el método del convenio: es la parte que pagó la aseguradora.",
                        { amount: this.pos.formatCurrency(expected) }
                    ),
                });
                return false;
            }
        }
        return super.isOrderValid(...arguments);
    },
});
