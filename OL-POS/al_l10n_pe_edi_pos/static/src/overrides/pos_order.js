import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

export const PE_DOC_LABELS = {
    "01": "FACTURA ELECTRÓNICA",
    "03": "BOLETA DE VENTA ELECTRÓNICA",
    "07": "NOTA DE CRÉDITO ELECTRÓNICA",
    "08": "NOTA DE DÉBITO ELECTRÓNICA",
};

patch(PosOrder.prototype, {
    setup(vals) {
        super.setup(vals);
        if (!this.l10n_pe_doc_type) {
            this.l10n_pe_doc_type = "boleta";
        }
        if (this.l10n_pe_edi_send === undefined || this.l10n_pe_edi_send === null) {
            this.l10n_pe_edi_send = true;
        }
    },
    get peDocTypeLabel() {
        // Con factura creada manda su código real; antes, la selección de caja.
        const code = this.account_move?.l10n_pe_pos_doc_code;
        if (code && PE_DOC_LABELS[code]) {
            return PE_DOC_LABELS[code];
        }
        if (this.l10n_pe_doc_type === "recibo") {
            return "TICKET DE VENTA";
        }
        return this.l10n_pe_doc_type === "factura"
            ? PE_DOC_LABELS["01"]
            : PE_DOC_LABELS["03"];
    },
    /** Etiqueta del documento del cliente según su código SUNAT
     * (Odoo 20: el DNI ya no va en vat, sino en additional_identifiers). */
    get peVatLabel() {
        const labels = { 6: "RUC", 1: "DNI", 4: "C.E.", 7: "Pasaporte" };
        return labels[this.partner_id?.l10n_pe_sunat_id_code] || "Doc.";
    },
    /** Número del documento SUNAT del cliente. */
    get peVatNumber() {
        return this.partner_id?.l10n_pe_sunat_id_value || this.partner_id?.vat || "";
    },
});
