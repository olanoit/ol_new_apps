import { patch } from "@web/core/utils/patch";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";

patch(OrderReceipt.prototype, {
    /** El formato CPE aplica en empresas peruanas con los diarios
     * configurados; un "Recibo" (ticket simple) usa el recibo estándar. */
    get peActive() {
        return (
            this.order.company?.country_id?.code === "PE" &&
            this.order.config?.l10n_pe_cpe_enabled &&
            this.order.l10n_pe_doc_type !== "recibo"
        );
    },
    /** Factura contable de la orden (llega con la sincronización del pago). */
    get peMove() {
        return this.order.account_move || null;
    },
    get peDocNumber() {
        return this.peMove?.l10n_latam_document_number || this.order.pos_reference;
    },
    /**
     * Desglose SUNAT: del account.move cuando existe; si aún no se
     * facturó (impresión anticipada), aproximación desde los totales POS.
     */
    get peAmounts() {
        const move = this.peMove;
        if (move && move.state === "posted") {
            return {
                base: move.l10n_pe_edi_amount_base,
                exonerated: move.l10n_pe_edi_amount_exonerated,
                unaffected: move.l10n_pe_edi_amount_unaffected,
                icbper: move.l10n_pe_edi_amount_icbper,
                igv: move.l10n_pe_edi_amount_igv,
                total: move.amount_total,
                words: move.l10n_pe_pos_amount_text,
            };
        }
        return {
            base: this.order.priceExcl,
            exonerated: 0,
            unaffected: 0,
            icbper: 0,
            igv: this.order.prices?.taxDetails?.tax_amount_currency ?? 0,
            total: this.order.priceIncl,
            words: null,
        };
    },
    get peQrUrl() {
        const qr = this.peMove?.l10n_pe_pos_qr_str;
        if (!qr) {
            return null;
        }
        return (
            "/report/barcode/?barcode_type=QR&value=" +
            encodeURIComponent(qr) +
            "&width=110&height=110&quiet=0"
        );
    },
});
