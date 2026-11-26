import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { getReportUrl } from "@web/webclient/actions/reports/utils";

/**
 * URL de la vista previa: la ruta nativa del PDF con el contexto que la
 * descarga nativa envía por POST (usuario + acción) y la marca que pide la
 * cabecera «inline» al servidor.
 *
 * @param {Object} action acción ir.actions.report
 * @returns {string}
 */
export function getReportPreviewUrl(action) {
    const url = new URL(getReportUrl(action, "pdf"), browser.location.origin);
    const context = { ...user.context, ...(action.context || {}) };
    url.searchParams.set("context", JSON.stringify(context));
    url.searchParams.set("al_preview", "1");
    return url.pathname + url.search;
}

/**
 * Abre en una pestaña los reportes PDF que el servidor marca con
 * `al_preview_in_browser`. Devuelve false para que siga el flujo nativo
 * (descarga) cuando el reporte no está marcado, wkhtmltopdf no sirve o el
 * navegador bloquea la pestaña.
 */
export async function reportPreviewHandler(action, options, env) {
    if (action.report_type !== "qweb-pdf" || !action.al_preview_in_browser) {
        return false;
    }
    reportPreviewHandler.wkhtmltopdfStatusProm ||= rpc("/report/check_wkhtmltopdf");
    const status = await reportPreviewHandler.wkhtmltopdfStatusProm;
    if (!["ok", "upgrade"].includes(status)) {
        // El flujo nativo ya explica qué le pasa a wkhtmltopdf.
        return false;
    }
    const tab = browser.open(getReportPreviewUrl(action), "_blank");
    if (!tab) {
        env.services.notification.add(
            _t("El navegador bloqueó la pestaña nueva; el reporte se descarga."),
            { type: "warning" }
        );
        return false;
    }
    return true;
}

registry
    .category("ir.actions.report handlers")
    .add("al_report_preview", reportPreviewHandler, { sequence: 20 });
