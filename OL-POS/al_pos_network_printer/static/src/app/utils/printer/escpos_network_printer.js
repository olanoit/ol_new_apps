/** @odoo-module */

// NOTA DE MIGRACIÓN: en Odoo 18, `BasePrinter` vivía en
// `@point_of_sale/app/printer/base_printer`. En Odoo 19 se movió a
// `@point_of_sale/app/utils/printer/base_printer` (junto a sus pares
// nativos `EpsonPrinter` y `HWPrinter`). Importar desde la ruta vieja rompe
// la carga de assets en silencio, sin ningún error obvio en la consola.
import { BasePrinter } from "@point_of_sale/app/utils/printer/base_printer";
import { rpc } from "@web/core/network/rpc";

/**
 * Impresora ESC/POS genérica de red (no Epson).
 *
 * Odoo 19 ya resuelve la impresión de red sin IoT Box para impresoras
 * Epson (`EpsonPrinter`, protocolo ePOS-XML, impresión directa navegador ->
 * impresora). Las impresoras térmicas ESC/POS genéricas (Xprinter, Zjiang,
 * Gainscha, etc.) no hablan ese protocolo, y el navegador no puede abrir un
 * socket TCP crudo, así que la imagen del ticket necesita que ALGO con
 * acceso a sockets la reenvíe.
 *
 * Camino A del agente local (2026-09-08, ver
 * agent/README.md, Camino A): con `agentUrl` configurado
 * (pasado por `pos_store.js::afterProcessServerData` solo cuando
 * `pos.config.escpos_printer_mode === "agent"` — esta clase no sabe nada de
 * ese campo, solo recibe `agentUrl` ya resuelto), ese "algo" es un agente
 * HTTP standalone en la misma red que la impresora
 * (`agent/al_pos_local_agent.py`) — el
 * navegador del cajero, que YA está físicamente en esa red, le habla
 * directo, sin pasar por el backend de Odoo en absoluto. Es la salida para
 * cuando el backend NO tiene ruta de red hacia la impresora (Odoo.sh, o
 * cualquier hosting fuera de la LAN del local).
 *
 * Sin `agentUrl` (el caso por defecto, instalación on-premise normal como
 * la de este proyecto) el comportamiento es exactamente el de siempre: la
 * imagen se manda al backend de Odoo (`PosNetworkPrinterController`), y es
 * el servidor el que abre el socket ESC/POS hacia la impresora. Los dos
 * caminos son mutuamente excluyentes por request — nunca se intentan los
 * dos a la vez.
 */
export class EscposNetworkPrinter extends BasePrinter {
    setup({ ip, port, agentUrl, agentToken }) {
        super.setup(...arguments);
        this.ip = ip;
        this.port = parseInt(port, 10) || 9100;
        // Sin barra final, para poder concatenar "/print" directo sin
        // duplicarla ni dejarla faltando según cómo la haya tipeado el
        // administrador en Ajustes.
        this.agentUrl = (agentUrl || "").replace(/\/+$/, "") || null;
        this.agentToken = agentToken || null;
    }

    async sendPrintingJob(img) {
        if (!this.ip) {
            return { result: false, errorCode: "PRINTER_NOT_CONFIGURED" };
        }
        const receipt = { ip: this.ip, port: this.port, img };
        if (this.agentUrl) {
            return this._sendToAgent("/print", receipt);
        }
        try {
            return await rpc("/al_pos_network_printer/print_receipt", { receipt });
        } catch (error) {
            console.error("al_pos_network_printer: network error while printing", error);
            return { result: false, errorCode: "PRINTER_NOT_REACHABLE", canRetry: true };
        }
    }

    async openCashbox() {
        if (!this.ip) {
            return;
        }
        const receipt = { ip: this.ip, port: this.port };
        if (this.agentUrl) {
            await this._sendToAgent("/open_cashbox", receipt);
            return;
        }
        try {
            await rpc("/al_pos_network_printer/open_cashbox", { receipt });
        } catch (error) {
            console.error("al_pos_network_printer: error opening the cash drawer", error);
        }
    }

    /**
     * POST plano (no JSON-RPC — el agente es un proceso standalone sin
     * Odoo, no implementa ese envoltorio) al agente local configurado.
     * Mismo contrato `{ip, port, img?}` -> `{result, errorCode?}` que ya
     * expone `PosNetworkPrinterController`, solo cambia el transporte y el
     * destino — ver `agent/al_pos_local_agent.py` del lado servidor.
     */
    async _sendToAgent(path, body) {
        const headers = { "Content-Type": "application/json" };
        if (this.agentToken) {
            headers["X-Agent-Token"] = this.agentToken;
        }
        let response;
        try {
            response = await fetch(this.agentUrl + path, {
                method: "POST",
                headers,
                body: JSON.stringify(body),
            });
        } catch (error) {
            console.error("al_pos_network_printer: no se pudo contactar al agente local", error);
            return { result: false, errorCode: "AGENT_NOT_REACHABLE", canRetry: true };
        }
        if (!response.ok) {
            console.error(
                "al_pos_network_printer: el agente local respondió",
                response.status, response.statusText
            );
            return { result: false, errorCode: "AGENT_ERROR", canRetry: true };
        }
        return response.json();
    }
}
