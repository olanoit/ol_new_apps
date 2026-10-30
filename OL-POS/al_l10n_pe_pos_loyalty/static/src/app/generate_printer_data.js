import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";

/** El ticket CPE dice lo mismo que el comprobante (Odoo 20: los datos del
 * recibo los arma GeneratePrinterData; ver al_l10n_pe_edi_pos). */
patch(GeneratePrinterData.prototype, {
    alPeVoucherLines() {
        return this.order.lines.filter((line) => line.isPeVoucherLine);
    },
    /** Sin las tarjetas ni el canje entre las líneas. */
    alPeReceiptLines() {
        return super.alPeReceiptLines(...arguments).filter((line) => !line.isPeVoucherLine);
    },
    /** El canje es una forma de pago del comprobante. */
    alPeExtraPayments() {
        const redeemed = this.alPeVoucherLines().filter((line) => line.is_reward_line);
        const payments = redeemed.map((line) => ({
            name: line.reward_id?.program_id?.name || _t("Tarjeta de regalo"),
            amount: -line.priceIncl,
        }));
        return [...super.alPeExtraPayments(...arguments), ...payments];
    },
    /** La tarjeta vendida se cobra en caja, pero fuera del comprobante. */
    alPeNotes() {
        const sold = this.alPeVoucherLines().filter((line) => !line.is_reward_line);
        const notes = sold.map(
            (line) =>
                `${line.getFullProductName()}: ${this.formatCurrency(line.priceIncl)} ` +
                _t("(no forma parte del comprobante: se emite al canjearla)")
        );
        return [...super.alPeNotes(...arguments), ...notes];
    },
    /** Aproximación antes de emitir: el vale no lleva impuestos. */
    alPeDraftAmounts() {
        const amounts = super.alPeDraftAmounts(...arguments);
        const voucher = this.alPeVoucherLines().reduce((sum, line) => sum + line.priceIncl, 0);
        return { ...amounts, base: amounts.base - voucher, total: amounts.total - voucher };
    },
});
