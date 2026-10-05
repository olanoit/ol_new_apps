import { patch } from "@web/core/utils/patch";
import { Navbar } from "@point_of_sale/app/components/navbar/navbar";

/**
 * "Instalar App" (PWA): el core usa app_id=point_of_sale, que toma el icono
 * de point_of_sale y el color púrpura del sistema base. Con app_id propio el
 * manifest sale de controllers/webmanifest.py (icono, nombre y colores de la
 * caja). El `path` sigue siendo el del PdV, así el scope de la PWA no cambia.
 */
patch(Navbar.prototype, {
    get appUrl() {
        return `/scoped_app?app_id=al_pos_theme&path=${encodeURIComponent(
            `pos/ui/${this.pos.config.id}`
        )}`;
    },
});
