import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";

patch(OrderReceipt.prototype, {
    /** El ticket dice lo mismo que el comprobante: sin las tarjetas ni el
     * canje entre las líneas. */
    get peReceiptLines() {
        return super.peReceiptLines.filter((line) => !line.isPeVoucherLine);
    },
    get peVoucherLines() {
        return this.order.lines.filter((line) => line.isPeVoucherLine);
    },
    /** El canje es una forma de pago del comprobante. */
    get peExtraPayments() {
        const redeemed = this.peVoucherLines.filter((line) => line.is_reward_line);
        const payments = redeemed.map((line) => ({
            name: line.reward_id?.program_id?.name || _t("Tarjeta de regalo"),
            amount: -line.priceIncl,
        }));
        return [...super.peExtraPayments, ...payments];
    },
    /** La tarjeta vendida se cobra en caja, pero fuera del comprobante. */
    get peNotes() {
        const sold = this.peVoucherLines.filter((line) => !line.is_reward_line);
        const notes = sold.map(
            (line) =>
                `${line.getFullProductName()}: ${this.formatCurrency(line.priceIncl)} ` +
                _t("(no forma parte del comprobante: se emite al canjearla)")
        );
        return [...super.peNotes, ...notes];
    },
    get peAmounts() {
        const amounts = super.peAmounts;
        if (amounts.fromMove) {
            return amounts;
        }
        // Aproximación antes de emitir: el vale no lleva impuestos.
        const voucher = this.peVoucherLines.reduce((sum, line) => sum + line.priceIncl, 0);
        return { ...amounts, base: amounts.base - voucher, total: amounts.total - voucher };
    },
});
