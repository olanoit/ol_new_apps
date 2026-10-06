import { patch } from "@web/core/utils/patch";
import { dialogService } from "@web/core/dialog/dialog_service";
import { isMarkup } from "@web/core/utils/html";
import { htmlEscape, markup } from "@odoo/owl";

/**
 * Marca blanca de diálogos del sistema.
 *
 * Varios textos del core que ve el cajero mencionan la marca del sistema
 * base ("Odoo Server Error", "…Odoo Point of Sale will operate with
 * limited functionality", mensajes de error que vienen del servidor…). Viven
 * en `_t()` de point_of_sale/web y en respuestas RPC, así que no se pueden
 * cambiar desde una traducción de este módulo. En vez de parchear cada
 * handler, se intercepta `dialog.add()` (único punto por el que pasan todos
 * los diálogos del PdV) y se reemplaza la palabra por el nombre de marca de
 * la caja en las props de texto.
 */
const BRAND_RE = /\bOdoo\b/g;
// Sin flag "g" para .test(): una regex global arrastra `lastIndex` entre llamadas.
const HAS_BRAND_RE = /\bOdoo\b/;
const TEXT_PROPS = ["title", "body", "message", "confirmLabel", "cancelLabel"];

/**
 * El nombre sale del <meta name="application-name"> del índice (siempre
 * renderizado por el servidor), no de `pos.config`: con la sesión abierta el
 * PdV arranca desde IndexedDB y ese registro puede estar desactualizado.
 */
function brandName() {
    return document.querySelector('meta[name="application-name"]')?.content || "POS";
}

export function rebrandValue(value, brand) {
    if (isMarkup(value)) {
        const text = value.toString();
        return HAS_BRAND_RE.test(text) ? markup(text.replace(BRAND_RE, () => htmlEscape(brand))) : value;
    }
    if (typeof value === "string" || value instanceof String) {
        const text = value.toString();
        return HAS_BRAND_RE.test(text) ? text.replace(BRAND_RE, () => brand) : value;
    }
    return value;
}

patch(dialogService, {
    start(env, deps) {
        const service = super.start(env, deps);
        const originalAdd = service.add;
        service.add = (dialogClass, props, options) => {
            if (props) {
                const brand = brandName();
                props = { ...props };
                for (const key of TEXT_PROPS) {
                    if (key in props) {
                        props[key] = rebrandValue(props[key], brand);
                    }
                }
            }
            return originalAdd(dialogClass, props, options);
        };
        return service;
    },
});
