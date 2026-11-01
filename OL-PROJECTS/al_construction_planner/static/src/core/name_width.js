/** @odoo-module **/

/**
 * Nombres largos (paquete 1.16, M116-08 y CR-25): el ancho máximo de la
 * compañía (Ajustes › Planificación de obra) queda en la variable CSS
 * `--o-cp-name-max-width`, que usan la clase común `o_cp_wrap_names` y el
 * panel del Cronograma.
 */
import { session } from "@web/session";

export const DEFAULT_NAME_MAX_WIDTH = 360;

export function applyNameMaxWidth(width, root = document.documentElement) {
    const value = Number(width) > 0 ? Number(width) : DEFAULT_NAME_MAX_WIDTH;
    root.style.setProperty("--o-cp-name-max-width", `${value}px`);
    return value;
}

applyNameMaxWidth(session.construction_name_max_width);
