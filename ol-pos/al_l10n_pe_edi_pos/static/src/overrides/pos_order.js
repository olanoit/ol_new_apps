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
    get peVatLabel() {
        const vat = this.partner_id?.vat || "";
        if (vat.length === 11) {
            return "RUC";
        }
        if (vat.length === 8) {
            return "DNI";
        }
        return "Doc.";
    },
});
