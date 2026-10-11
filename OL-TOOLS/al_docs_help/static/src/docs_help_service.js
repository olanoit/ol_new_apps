/** @odoo-module **/
// Mapa pantalla → página de la documentación (al.docs.help), cargado una vez por sesión.
import { registry } from "@web/core/registry";

export const docsHelpService = {
    dependencies: ["orm"],
    start(env, { orm }) {
        let mapPromise = null;
        return {
            /** Ayuda de una pantalla (modelo o tag) o null. */
            async get(key) {
                if (!key) {
                    return null;
                }
                mapPromise ??= orm.call("al.docs.help", "get_help_map", []).catch(() => ({}));
                return (await mapPromise)[key] || null;
            },
        };
    },
};

registry.category("services").add("al_docs_help", docsHelpService);
