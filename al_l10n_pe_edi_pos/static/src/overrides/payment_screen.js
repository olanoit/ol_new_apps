import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { DocTypePopup } from "@al_l10n_pe_edi_pos/app/doc_type_popup/doc_type_popup";
import { partnerCanInvoice } from "@al_l10n_pe_edi_pos/app/utils/pe_doc_utils";

patch(PaymentScreen.prototype, {
    get peShowDocTypeButton() {
        return this.pos.isPeruvianCompany?.() && this.pos.config.l10n_pe_cpe_enabled;
    },
    get peDocTypeButtonLabel() {
        const order = this.currentOrder;
        const type = order?.l10n_pe_doc_type || "boleta";
        if (type === "recibo") {
            return "Recibo";
        }
        const base = type === "factura" ? "Factura electrónica" : "Boleta electrónica";
        const serie = order?.edi_series_id?.name;
        return serie ? `${base} · ${serie}` : base;
    },
    /**
     * Modal único del comprobante: tipo (Recibo/Boleta/Factura) + serie
     * del tipo elegido, todo en un solo diálogo.
     */
    async peSelectDocType() {
        const order = this.currentOrder;
        const series = {
            boleta: this.pos.getPeSeries("boleta").map((s) => ({ id: s.id, name: s.name })),
            factura: this.pos.getPeSeries("factura").map((s) => ({ id: s.id, name: s.name })),
        };
        const fixedIds = {
            boleta: this.pos.getPeFixedSeries("boleta")?.id || null,
            factura: this.pos.getPeFixedSeries("factura")?.id || null,
        };
        const result = await makeAwaitable(this.dialog, DocTypePopup, {
            title: "Comprobante",
            currentType: order.l10n_pe_doc_type || "boleta",
            currentSerieId: order.edi_series_id?.id || false,
            currentSend: order.l10n_pe_edi_send !== false,
            series,
            fixedIds,
            onSetFixed: (docType, serieData) =>
                this.pos.setPeFixedSeries(
                    docType,
                    serieData &&
                        this.pos.getPeSeries(docType).find((s) => s.id === serieData.id)
                ),
        });
        if (result === undefined) {
            return;
        }
        order.l10n_pe_doc_type = result.type;
        order.l10n_pe_edi_send = result.send;
        if (result.type === "recibo") {
            // Ticket simple: sin CPE ni factura contable.
            order.setToInvoice(false);
            order.edi_series_id = false;
            return;
        }
        order.setToInvoice(true);
        order.edi_series_id =
            this.pos.getPeSeries(result.type).find((s) => s.id === result.serieId) ||
            false;
        // La factura necesita cliente: si aún no hay, abrir la selección.
        if (result.type === "factura") {
            if (!order.getPartner()) {
                await this.pos.selectPartner?.(order);
            }
            const partner = order.getPartner();
            if (partner && !partnerCanInvoice(partner)) {
                this.notification.add(
                    _t("El cliente %s no tiene RUC válido (11 dígitos): complételo para poder facturar.", partner.name),
                    { type: "warning" }
                );
                this.pos.editPartner(partner);
            } else if (!partner) {
                this.notification.add(
                    _t("La factura electrónica requiere un cliente con RUC."),
                    { type: "warning" }
                );
            }
        }
    },
});
