import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";
import { floatIsZero } from "@web/core/utils/numbers";

patch(OrderPaymentValidation.prototype, {
    // Una venta solo de tarjetas de regalo o recargas no lleva comprobante:
    // sale con ticket, sea cual sea el tipo elegido. Se fija antes del resto
    // de controles para que no pidan cliente ni RUC.
    async isOrderValid(isForceValidate) {
        const lines = this.order.lines.filter(
            (line) => !floatIsZero(line.priceIncl, this.pos.currency.decimal_places)
        );
        if (
            this.pos.config.l10n_pe_cpe_enabled &&
            lines.length &&
            lines.every((line) => line.isPeVoucherLine)
        ) {
            this.order.l10n_pe_doc_type = "recibo";
            this.order.edi_series_id = false;
            this.order.setToInvoice(false);
        }
        return super.isOrderValid(...arguments);
    },
});
