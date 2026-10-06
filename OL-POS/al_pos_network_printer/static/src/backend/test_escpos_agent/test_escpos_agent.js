/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

/**
 * Botón "Probar agente" — mismo patrón que `point_of_sale_test_epos`
 * (`point_of_sale/static/src/backend/test_epos/test_epos.js`) pero para el
 * agente local ESC/POS (`al_pos_network_printer/agent/`) en vez de una
 * impresora Epson: llama `GET <URL del agente>/health` DESDE EL NAVEGADOR
 * (no desde el backend de Odoo — el agente vive en la red del local, que el
 * servidor de Odoo no necesariamente puede alcanzar, ver
 * agent/README.md) y traduce la respuesta a un
 * mensaje accionable, en vez de solo "ok"/"error".
 *
 * A propósito NO imprime un ticket de prueba real (a diferencia del test de
 * Epson) — /health no requiere token ni toca la impresora física, mientras
 * que /print sí, y forzar una impresión real desde un botón de "probar
 * configuración" sería sorprendente. Para probar la impresión de verdad ya
 * está el botón "Test de conexión" de la GUI del agente
 * (`al_pos_local_agent_gui.py`), que sí abre el socket a la impresora.
 */
export class TestEscposAgent extends Component {
    static template = "al_pos_network_printer.TestEscposAgentButton";
    static props = {
        ...standardWidgetProps,
    };

    setup() {
        super.setup();
        this.notification = useService("notification");
    }

    async onClick() {
        const data = this.props.record.data;
        const agentUrl = data.escpos_agent_url ?? data.pos_escpos_agent_url;
        const printerIp = data.escpos_printer_ip ?? data.pos_escpos_printer_ip;
        const printerPort = data.escpos_printer_port ?? data.pos_escpos_printer_port;

        if (!agentUrl) {
            this.notification.add(_t("Complete primero la URL del agente local."), {
                type: "danger",
            });
            return;
        }

        let response;
        try {
            const url = agentUrl.replace(/\/+$/, "") + "/health";
            response = await fetch(url, { method: "GET", signal: AbortSignal.timeout(8000) });
        } catch {
            this.notification.add(
                _t(
                    "No se pudo contactar al agente en %s. Verifique que esté corriendo, que la URL " +
                        "sea correcta, y que esta pestaña esté en la misma red que el agente.",
                    agentUrl
                ),
                { type: "danger" }
            );
            return;
        }

        if (!response.ok) {
            this.notification.add(
                _t("El agente respondió con un error (HTTP %s).", response.status),
                { type: "danger" }
            );
            return;
        }

        let body;
        try {
            body = await response.json();
        } catch {
            this.notification.add(
                _t("El agente respondió, pero no con el formato esperado — ¿es realmente la URL del agente?"),
                { type: "warning" }
            );
            return;
        }

        if (!body.escpos_available) {
            this.notification.add(
                _t(
                    "El agente está alcanzable, pero le falta instalar 'python-escpos' — no puede " +
                        "imprimir todavía (ver README del agente)."
                ),
                { type: "warning" }
            );
            return;
        }

        if (printerIp) {
            const target = `${printerIp}:${printerPort || 9100}`;
            const allowed = body.allowed_printers || [];
            if (!allowed.includes(target)) {
                this.notification.add(
                    _t(
                        "El agente está alcanzable, pero %(target)s no está en su lista de impresoras " +
                            "permitidas (%(allowed)s) — hay que agregarla en la configuración del " +
                            "agente (AL_AGENT_ALLOWED_PRINTERS), no acá.",
                        { target, allowed: allowed.join(", ") || _t("ninguna") }
                    ),
                    { type: "warning" }
                );
                return;
            }
        }

        this.notification.add(_t("Agente alcanzable y listo para imprimir."), { type: "success" });
    }
}

export const TestEscposAgentWidget = {
    component: TestEscposAgent,
};
registry.category("view_widgets").add("al_test_escpos_agent", TestEscposAgentWidget);
