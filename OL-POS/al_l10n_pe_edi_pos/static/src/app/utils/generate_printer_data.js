import { patch } from "@web/core/utils/patch";
import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";
import { generateQRCodeDataUrl } from "@point_of_sale/utils";

/**
 * Ticket CPE del TPV (Odoo 20). El recibo se dibuja con las plantillas QWeb
 * de servidor (point_of_sale.pos_order_receipt), con datos que arma esta
 * clase en el navegador y `pos.order.receipt` en el servidor: aquí se añade
 * `extra_data.al_pe` (todo ya formateado) y la condición `al_pe_cpe`.
 *
 * Otros módulos amplían el ticket (líneas, pagos y notas) con
 * `alPeReceiptLines`, `alPeExtraPayments` y `alPeNotes`.
 */
patch(GeneratePrinterData.prototype, {
    /** Formato CPE: empresa peruana con los diarios configurados; un
     * «Recibo» (ticket simple) usa el recibo estándar. */
    get alPeActive() {
        return (
            this.company?.country_id?.code === "PE" &&
            this.config?.l10n_pe_cpe_enabled &&
            this.order?.l10n_pe_doc_type !== "recibo"
        );
    },
    alPeReceiptLines() {
        return this.order.lines;
    },
    /** Pagos que no son líneas de pago del TPV: [{name, amount}]. */
    alPeExtraPayments() {
        return [];
    },
    alPeNotes() {
        return [];
    },
    /** Importes antes de emitir el comprobante (aproximación desde el TPV). */
    alPeDraftAmounts() {
        return {
            base: this.order.priceExcl,
            igv: this.order.prices?.taxDetails?.tax_amount ?? 0,
            total: this.order.priceIncl,
        };
    },
    /**
     * Desglose SUNAT: del account.move cuando ya se publicó; si aún no se
     * facturó (impresión anticipada), aproximación desde los totales POS.
     */
    alPeTotals(move) {
        const fmt = (amount) => this.formatCurrency(amount);
        const rows = [];
        const add = (label, amount) => amount && rows.push({ label, amount: fmt(amount) });
        if (move?.state === "posted") {
            add("Op. gravadas", move.l10n_pe_edi_amount_base);
            add("Op. exoneradas", move.l10n_pe_edi_amount_exonerated);
            add("Op. inafectas", move.l10n_pe_edi_amount_unaffected);
            add("Op. exportación", move.l10n_pe_edi_amount_export);
            add("Op. gratuitas", move.l10n_pe_edi_amount_free);
            add("ISC", move.l10n_pe_edi_amount_isc);
            add("IVAP", move.l10n_pe_edi_amount_ivap);
            add("ICBPER", move.l10n_pe_edi_amount_icbper);
            add("Otros tributos", move.l10n_pe_edi_amount_others);
            rows.push({ label: move.l10n_pe_pos_igv_label || "IGV", amount: fmt(move.l10n_pe_edi_amount_igv) });
            rows.push({ label: "IMPORTE TOTAL", amount: fmt(move.amount_total), total: true });
            return rows;
        }
        const draft = this.alPeDraftAmounts();
        add("Op. gravadas", draft.base);
        rows.push({ label: "IGV", amount: fmt(draft.igv) });
        rows.push({ label: "IMPORTE TOTAL", amount: fmt(draft.total), total: true });
        // Redondeo de efectivo: el total del comprobante publicado ya lo incluye.
        if (this.order.appliedRounding) {
            rows.push({ label: "Redondeo", amount: fmt(this.order.appliedRounding) });
            rows.push({ label: "Total a pagar", amount: fmt(this.order.prices.taxDetails.total_amount) });
        }
        return rows;
    },
    generateReceiptData() {
        const data = super.generateReceiptData(...arguments);
        if (!this.alPeActive) {
            return data;
        }
        const order = this.order;
        const move = order.account_move || null;
        const issued = move?.state === "posted";
        const partner = order.partner_id;
        const company = this.company;
        const payments = order.payment_ids.map((line) => ({
            name: line.payment_method_id?.name || "",
            amount: this.formatCurrency(line.getAmount()),
        }));
        for (const payment of this.alPeExtraPayments()) {
            payments.push({ name: payment.name, amount: this.formatCurrency(payment.amount) });
        }
        data.conditions.al_pe_cpe = true;
        data.extra_data.al_pe = {
            company_name: company.name,
            company_vat: company.vat,
            company_street: company.street || "",
            company_phone: company.phone || "",
            issued,
            doc_label: order.peDocTypeLabel,
            doc_label_lower: (order.peDocTypeLabel || "").toLowerCase(),
            doc_number: issued ? move.l10n_latam_document_number : "",
            partner_name: partner?.name || "CLIENTE VARIOS",
            partner_vat_label: order.peVatLabel,
            partner_vat: order.peVatNumber,
            partner_street: partner?.street || "",
            date: order.formatDateOrTime("date_order"),
            currency_label: order.currency?.name === "USD" ? "DÓLARES AMERICANOS" : "SOLES",
            lines: this.alPeReceiptLines().map((line) => ({
                qty: line.qty,
                name: line.getFullProductName(),
                discount: line.getDiscount() || false,
                note: line.customerNote || false,
                unit: this.formatCurrency(line.unitPrices.total_included),
                total: this.formatCurrency(line.priceIncl),
            })),
            totals: this.alPeTotals(move),
            words: issued ? move.l10n_pe_pos_amount_text : false,
            payments,
            change: order.showChange ? this.formatCurrency(order.change) : false,
            cashier: order.getCashierName() || false,
            seller: order.seller_id?.name || false,
            notes: this.alPeNotes(),
            // QR generado en el navegador: funciona sin conexión.
            qr: move?.l10n_pe_pos_qr_str
                ? generateQRCodeDataUrl(move.l10n_pe_pos_qr_str, { width: 110, height: 110 })
                : false,
            footer: this.config.receipt_footer || false,
        };
        return data;
    },
});
