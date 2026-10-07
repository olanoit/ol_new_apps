import { patch } from "@web/core/utils/patch";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { generateQRCodeDataUrl } from "@point_of_sale/utils";

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
    /** Hay comprobante electrónico publicado: si la factura falló, el ticket
     * no puede presentarse como boleta/factura con un número inventado. */
    get peIssued() {
        return this.peMove?.state === "posted";
    },
    get peDocNumber() {
        return this.peIssued ? this.peMove.l10n_latam_document_number : "";
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
                isc: move.l10n_pe_edi_amount_isc,
                ivap: move.l10n_pe_edi_amount_ivap,
                free: move.l10n_pe_edi_amount_free,
                export: move.l10n_pe_edi_amount_export,
                others: move.l10n_pe_edi_amount_others,
                igv: move.l10n_pe_edi_amount_igv,
                igvLabel: move.l10n_pe_pos_igv_label || "IGV",
                total: move.amount_total,
                words: move.l10n_pe_pos_amount_text,
                fromMove: true,
            };
        }
        return {
            base: this.order.priceExcl,
            exonerated: 0,
            unaffected: 0,
            icbper: 0,
            isc: 0,
            ivap: 0,
            free: 0,
            export: 0,
            others: 0,
            igv: this.order.prices?.taxDetails?.tax_amount_currency ?? 0,
            igvLabel: "IGV",
            total: this.order.priceIncl,
            words: null,
            fromMove: false,
        };
    },
    /** QR generado en el navegador (data URL), como el QR nativo del
     * ticket: funciona sin conexión y ya está listo cuando el ticket se
     * rasteriza para imprimir (una imagen remota podría no haber cargado). */
    get peQrUrl() {
        const qr = this.peMove?.l10n_pe_pos_qr_str;
        if (!qr) {
            return null;
        }
        return generateQRCodeDataUrl(qr, { width: 110, height: 110 });
    },
});
