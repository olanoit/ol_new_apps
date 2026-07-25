import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { partnerCanInvoice } from "@al_l10n_pe_edi_pos/app/utils/pe_doc_utils";

patch(OrderPaymentValidation.prototype, {
    // Barrera final en el TPV (misma regla que al elegir el tipo): el
    // cobro no procede sin RUC válido, así el UserError equivalente de
    // _prepare_invoice_vals queda solo como red de seguridad.
    async isOrderValid(isForceValidate) {
        const res = await super.isOrderValid(...arguments);
        if (!res || !this.pos.isPeruvianCompany() || !this.pos.config.l10n_pe_cpe_enabled) {
            return res;
        }
        const docType = this.order.l10n_pe_doc_type || "boleta";
        if (docType === "recibo") {
            // Ticket simple elegido en el modal: sin CPE.
            this.order.setToInvoice(false);
            return res;
        }
        // Boleta/factura emiten CPE: la orden siempre se factura.
        this.order.setToInvoice(true);
        // Serie CPE resuelta al cobrar: fija de la caja > única disponible
        // (sin diálogo aquí; con varias series y ninguna elegida, la
        // factura toma la del diario en el backend).
        if (!this.order.edi_series_id) {
            const fixed = this.pos.getPeFixedSeries(docType);
            const series = this.pos.getPeSeries(docType);
            this.order.edi_series_id =
                fixed || (series.length === 1 ? series[0] : false);
        }
        if (this.order.l10n_pe_doc_type === "factura") {
            const partner = this.order.getPartner();
            if (!partnerCanInvoice(partner)) {
                if (partner) {
                    this.pos.editPartner(partner);
                }
                this.pos.dialog.add(AlertDialog, {
                    title: _t("Factura electrónica"),
                    body: _t(
                        "La factura requiere un cliente con RUC (11 dígitos). " +
                            "Seleccione el cliente o cambie a boleta."
                    ),
                });
                return false;
            }
        }
        return res;
    },
});
