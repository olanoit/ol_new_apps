import { patch } from "@web/core/utils/patch";
import { Notification } from "@web/core/notifications/notification";

/**
 * Notificaciones del PdV: al cerrarse (✕ o fin del temporizador) suben y
 * se desvanecen antes de desaparecer (pedido explícito). El core las quita
 * del DOM al instante (`Transition leaveDuration="0"` en
 * NotificationContainer), así que no hay animación de salida que estilar:
 * se marca la tarjeta con `alpt-notification-leaving` (animación en
 * navbar.scss) y recién después se llama al cierre nativo. Sólo carga en
 * el bundle del PdV; el backend no cambia.
 */
const LEAVE_MS = 250;

patch(Notification.prototype, {
    close() {
        const el = this.autocloseProgress?.el?.closest(".o_notification");
        if (!el || this._alptLeaving) {
            return super.close(...arguments);
        }
        this._alptLeaving = true;
        el.classList.add("alpt-notification-leaving");
        setTimeout(() => super.close(), LEAVE_MS);
    },
});
