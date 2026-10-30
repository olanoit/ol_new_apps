import { patch } from "@web/core/utils/patch";
import { PosTicketPrinterPlugin } from "@point_of_sale/app/plugins/pos_ticket_printer_plugin";
import { EscposNetworkPrinter } from "@al_pos_network_printer/app/utils/printer/escpos_network_printer";

/**
 * Odoo 20: el plugin de impresión crea la instancia de cada `pos.printer`
 * de la caja (recibo y preparación) y el core solo conoce ePOS. Aquí se
 * agrega el tipo `escpos_network`. El agente local (modo "agent" de la caja)
 * solo aplica a la impresora de recibo.
 */
patch(PosTicketPrinterPlugin.prototype, {
    async createPrinterInstance(printer) {
        if (printer.printer_type === "escpos_network") {
            const useAgent =
                printer.use_type === "receipt" && this.config.escpos_printer_mode === "agent";
            return new EscposNetworkPrinter({
                printer,
                agentUrl: useAgent ? this.config.escpos_agent_url : undefined,
                agentToken: useAgent ? this.config.escpos_agent_token : undefined,
            });
        }
        return super.createPrinterInstance(...arguments);
    },
});
