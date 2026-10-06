/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { EscposNetworkPrinter } from "@al_pos_network_printer/app/utils/printer/escpos_network_printer";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { AgentAuthorizationDialog } from "@al_pos_network_printer/app/components/agent_authorization_dialog/agent_authorization_dialog";

patch(PosStore.prototype, {
    async afterProcessServerData() {
        await super.afterProcessServerData(...arguments);
        // Basado en la rama que el propio core usa para `EpsonPrinter`
        // (point_of_sale/static/src/app/services/pos_store.js,
        // `afterProcessServerData`): si el recibo principal quedó
        // configurado como impresora ESC/POS genérica de red -en vez de
        // Epson, algo que `pos.config` impide combinar (ver la constraint
        // en models/pos_config.py)-, se instancia acá.
        //
        // OJO — a propósito NO se exige `this.config.other_devices` acá
        // (bug real, 2026-09-08, `TPV 1`: el ticket/comprobante se abría en
        // el navegador en vez de imprimirse en la ESC/POS, aunque
        // `escpos_printer_ip` estaba correctamente configurado y un
        // comprobante impreso desde el servidor — sin este gate — sí salía bien
        // en la misma impresora). `other_devices` es un campo del CORE que
        // controla si la sección "Impresora de red" es VISIBLE en la
        // pantalla de Ajustes (ver `res_config_settings_views.xml`,
        // `invisible="not pos_other_devices"`) — no tiene ningún significado
        // técnico propio más allá de eso, y nada en el backend
        // (`print_pdf_bytes`) lo
        // consulta: ahí la única condición real es `escpos_printer_ip`
        // truthy. Guardar `pos.config` desde la pantalla de Ajustes general
        // sin haber marcado ese toggle en esa sesión concreta lo deja en
        // `False` aunque `escpos_printer_ip` siga con un valor válido (se
        // había configurado originalmente por `odoo-bin shell`, sin pasar
        // por esa pantalla) — con el gate viejo, esa combinación (IP
        // configurada + `other_devices` en `False`) hacía que el ticket
        // cayera silenciosamente al fallback de navegador. La condición real
        // que importa es la misma que ya usa el lado Python: si hay IP, hay
        // impresora.
        // Además de la IP, el toggle "Impresora ESC/POS de red"
        // (`escpos_network_printer_enabled`, mismo criterio que
        // `pos.config._escpos_receipt_printer_active` en Python): apagado,
        // no se instancia nada y el recibo queda con la impresora que haya
        // armado el core (Epson / IoT) o el diálogo del navegador — igual
        // que en el nativo, esté o no cargada la IP. Pedido en vivo
        // 2026-09-28: antes, apagar el toggle solo ocultaba la sección y
        // el POS seguía imprimiendo en la impresora de red.
        if (this.config.escpos_network_printer_enabled && this.config.escpos_printer_ip) {
            // `escpos_printer_mode` (ver models/pos_config.py) es la única
            // fuente de verdad de si se usa el agente local — a propósito
            // NO se infiere de si `escpos_agent_url` tiene algo cargado:
            // así la URL/token pueden quedar siempre completos en Ajustes y
            // alternar entre "backend"/"agent" sin perder esa
            // configuración (pensado para poder probar el agente contra
            // una instancia local con un solo click). Con "backend" (o
            // cualquier valor viejo/vacío, instalaciones previas a este
            // campo) se pasa `agentUrl: undefined` y `EscposNetworkPrinter`
            // cae directo al `rpc()` de siempre — mismo comportamiento que
            // antes de que existiera el agente.
            const useAgent = this.config.escpos_printer_mode === "agent";
            this.hardwareProxy.printer = new EscposNetworkPrinter({
                ip: this.config.escpos_printer_ip,
                port: this.config.escpos_printer_port,
                // Camino A del agente local (Fase 1, ver
                // agent/README.md). Solo el recibo
                // principal por ahora (no las impresoras de preparación de
                // `createPrinter()`, más abajo).
                agentUrl: useAgent ? this.config.escpos_agent_url : undefined,
                agentToken: useAgent ? this.config.escpos_agent_token : undefined,
            });
        }
    },

    createPrinter(config) {
        // El core (mismo archivo, método `createPrinter`) solo sabe crear
        // `EpsonPrinter` o `HWPrinter` para las impresoras de preparación
        // (`pos.printer`). Esta rama agrega el tercer tipo, `escpos_network`.
        if (config.printer_type === "escpos_network") {
            return new EscposNetworkPrinter({
                ip: config.escpos_printer_ip,
                port: config.escpos_printer_port,
            });
        }
        return super.createPrinter(...arguments);
    },

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
        const printer = this.hardwareProxy.printer;
        if (!(printer instanceof EscposNetworkPrinter) || !printer.agentUrl) {
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
