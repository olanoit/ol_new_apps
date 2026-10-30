/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { EscposNetworkPrinter } from "@al_pos_network_printer/app/utils/printer/escpos_network_printer";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { AgentAuthorizationDialog } from "@al_pos_network_printer/app/components/agent_authorization_dialog/agent_authorization_dialog";

patch(PosStore.prototype, {
    // ── Autorización del agente local (Camino A por HTTPS) ─────────────
    //
    // Confirmado en vivo (2026-09-14): con el agente en HTTPS (certificado
    // autofirmado — no tiene dominio real, no hay CA que lo firme), el
    // navegador rechaza CUALQUIER fetch() a ese origen hasta que el cajero
    // visite esa URL directo (fuera de un fetch, en una pestaña real) y
    // acepte la advertencia de seguridad — no existe ningún API de
    // "permiso de impresora" que pedir, es exactamente esto. Sin este
    // chequeo, el pago se completaba normal (`super.pay()` no sabe nada de
    // esto) y el ticket recién fallaba al imprimir DESPUÉS de haber
    // cobrado — mal momento para enterarse.
    //
    // Por eso el chequeo va acá, antes de `super.pay()` (el mismo punto
    // único por el que pasa el botón "Pagar", ver
    // point_of_sale/static/src/app/screens/product_screen/product_screen.xml)
    // y no dentro de PaymentScreen: si falta autorizar, ni siquiera se
    // navega para allá.
    async pay() {
        if (!(await this._alCheckPrinterAuthorized())) {
            return;
        }
        return super.pay(...arguments);
    },

    /**
     * `true` si se puede pagar sin trabas (no hay impresora de red, modo
     * "backend", o agente por HTTP simple — ver más abajo), o si el
     * agente ya está confirmado como alcanzable. `false` solo cuando de
     * verdad hacía falta el diálogo de autorización y el cajero lo
     * canceló.
     */
    async _alCheckPrinterAuthorized() {
        // Interruptor general (ver models/pos_config.py::
        // escpos_require_agent_authorization) — inactivo por defecto: el
        // pago sigue igual que siempre, sin este chequeo previo, hasta que
        // se confirme que el agente por HTTPS autoriza bien de punta a
        // punta y se lo activa a propósito. Agregado en vivo (2026-09-15)
        // porque bloqueaba el cobro mientras se terminaba de ajustar
        // CORS/Private Network Access del lado del agente — ver
        // agent/README.md §Problemas conocidos.
        if (!this.config.escpos_require_agent_authorization) {
            return true;
        }
        // Odoo 20: las instancias viven en las impresoras de recibo del
        // plugin de impresión (ver pos_ticket_printer_plugin.js).
        const printer = this.ticketPrinter.receiptPrinters
            .map((p) => p._instance)
            .find((instance) => instance instanceof EscposNetworkPrinter && instance.agentUrl);
        if (!printer) {
            return true;
        }
        // Un agente por http:// (no https) contra un Odoo servido en
        // https queda bloqueado por "mixed content" del navegador — un
        // bloqueo real, pero sin ningún arreglo que el cajero pueda hacer
        // desde acá (no hay advertencia que aceptar, el navegador nunca
        // ni intenta la conexión). Bloquear el pago acá sería un
        // callejón sin salida; ese caso lo tiene que arreglar quien
        // administra el sistema pasando el agente a https://, así que se
        // deja pasar y el error real aparece al imprimir, como antes de
        // que existiera este chequeo.
        if (!printer.agentUrl.startsWith("https://")) {
            return true;
        }
        if (this._alAgentAuthorized) {
            return true;
        }
        if (await this._alPingAgent(printer.agentUrl)) {
            this._alAgentAuthorized = true;
            return true;
        }
        const authorized = await makeAwaitable(this.env.services.dialog, AgentAuthorizationDialog, {
            agentUrl: printer.agentUrl,
            checkAgentReachable: () => this._alPingAgent(printer.agentUrl),
        });
        if (authorized) {
            // Una vez por pestaña: el navegador ya recuerda la excepción
            // de certificado para ese origen mientras dure la sesión (y
            // normalmente bastante más), así que no tiene sentido volver
            // a mostrar el diálogo en cada venta.
            this._alAgentAuthorized = true;
        }
        return Boolean(authorized);
    },

    async _alPingAgent(agentUrl) {
        try {
            const response = await fetch(agentUrl + "/health", {
                method: "GET",
                signal: AbortSignal.timeout(5000),
            });
            return response.ok;
        } catch {
            return false;
        }
    },
});
