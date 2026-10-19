import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

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
        const added = await super.addNewPaymentLine(paymentMethod);
        if (!added) {
            return added;
        }
        const line = this.paymentLines.at(-1);
        const amount = Math.min(coverage.amount, line.amount);
        line.setAmount(amount);
        this.numberBuffer.set(amount.toString());
        this.notification.add(
            _t("%(agreement)s cubre %(amount)s (afiliado %(affiliate)s).", {
                agreement: coverage.agreement,
                amount: this.env.utils.formatCurrency(amount),
                affiliate: coverage.affiliate,
            }),
            { type: "info" }
        );
        return added;
    },
});
