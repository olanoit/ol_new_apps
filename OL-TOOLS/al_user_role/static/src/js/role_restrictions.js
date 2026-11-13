/** @odoo-module **/
// Oculta Exportar y Archivar según las restricciones de los roles del usuario,
// oculta "Enviar mensaje" del chatter y avisa cuando el rol bloquea el modo
// desarrollador.
// El resto de las restricciones se aplica en el servidor (arch de las vistas,
// menús Imprimir / Acciones, dominios). Los datos llegan en session_info.
import "@web/core/debug/debug_providers";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { Chatter } from "@mail/chatter/web_portal/chatter";
import { ListController } from "@web/views/list/list_controller";
import { FormController } from "@web/views/form/form_controller";

function alRestrictions(resModel) {
    const data = session.al_role_restrictions || {};
    const spec = (data.models || {})[resModel] || {};
    return {
        hideArchive: Boolean(data.readonly_all || spec.hide_archive),
        hideExport: Boolean(spec.hide_export),
    };
}

patch(ListController.prototype, {
    setup() {
        super.setup(...arguments);
        const { hideArchive, hideExport } = alRestrictions(this.props.resModel);
        if (hideArchive) {
            this.archiveEnabled = false;
        }
        if (hideExport) {
            // setup() asigna isExportEnable en un onWillStart asíncrono: se
            // fija en false para que esa asignación no lo vuelva a activar.
            Object.defineProperty(this, "isExportEnable", {
                get: () => false,
                set: () => {},
                configurable: true,
            });
        }
    },
});

patch(FormController.prototype, {
    get archiveEnabled() {
        return !alRestrictions(this.props.resModel).hideArchive && super.archiveEnabled;
    },
});

// --- Modo desarrollador bloqueado por rol -------------------------------------
// El bloqueo real está en el servidor (ir.http._pre_dispatch quita el debug de
// la sesión). Aquí solo se avisa al usuario y se quita la opción de Ctrl+K.
const { block_debug: blockDebug, debug_blocked_notice: debugBlockedNotice } =
    session.al_role_restrictions || {};

if (blockDebug) {
    // "Activar modo desarrollador" de la paleta de comandos (al escribir
    // "debug"): con el bloqueo solo recargaría la página sin efecto.
    const commandProviders = registry.category("command_provider");
    const debugProvider = commandProviders.get("debug", null);
    if (debugProvider) {
        commandProviders.add("debug", { ...debugProvider, provide: () => [] }, { force: true });
    }
}

registry.category("services").add("al_debug_blocked_notice", {
    dependencies: ["notification"],
    start(env, { notification }) {
        if (debugBlockedNotice) {
            notification.add(_t("El modo desarrollador está bloqueado por su rol."), {
                type: "warning",
            });
        }
    },
});

// --- Chatter: solo Registrar nota ------------------------------------------------
// El servidor también rechaza el mensaje (controllers/thread.py).
patch(Chatter.prototype, {
    get alHideSendMessage() {
        return Boolean((session.al_role_restrictions || {}).hide_send_message);
    },
});
