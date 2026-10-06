/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

/**
 * Diálogo bloqueante que se abre desde `pos_store.js::pay()` cuando el
 * agente local usa HTTPS y el navegador todavía no confía en su
 * certificado autofirmado — no hay ningún API de "permiso de impresora"
 * que pedir, así que lo único que puede desbloquear esto es que el cajero
 * visite la URL del agente directo (fuera de un `fetch()`) y acepte la
 * advertencia de seguridad, una vez por navegador. Ver `checkAgentReachable`
 * (pasado por quien abre este diálogo) para el reintento real.
 *
 * Se usa con `makeAwaitable` (@point_of_sale/app/utils/make_awaitable_dialog,
 * mismo helper que usan otros diálogos del TPV para sus propios
 * diálogos de diagnóstico) — resuelve `true` si el agente quedó
 * alcanzable, `false`/`undefined` si el cajero canceló.
 */
export class AgentAuthorizationDialog extends Component {
    static template = "al_pos_network_printer.AgentAuthorizationDialog";
    static components = { Dialog };
    static props = {
        close: { type: Function },
        agentUrl: { type: String },
        checkAgentReachable: { type: Function },
        getPayload: { type: Function, optional: true },
    };

    setup() {
        this.state = useState({ checking: false, failed: false });
    }

    onOpenAgent() {
        // Cualquier ruta del agente sirve para el propósito de esto (lo
        // único que importa es que el navegador cargue ese ORIGEN fuera de
        // un fetch(), para poder mostrar la advertencia de certificado y
        // que el cajero la acepte) — se usa /health por ser la única ruta
        // sin autenticación ni efectos secundarios.
        window.open(this.props.agentUrl + "/health", "_blank", "noopener");
    }

    async onRetry() {
        this.state.checking = true;
        this.state.failed = false;
        const reachable = await this.props.checkAgentReachable();
        this.state.checking = false;
        if (reachable) {
            this.props.getPayload?.(true);
            this.props.close();
        } else {
            this.state.failed = true;
        }
    }

    onCancel() {
        this.props.getPayload?.(false);
        this.props.close();
    }
}
