/**
 * Paquete 1.17, M117-08: las acciones masivas escriben por tramos, con el avance a la
 * vista y la pantalla viva. «Cancelar» detiene la escritura y vuelve a la versión
 * guardada antes de empezar.
 */
import { Component, reactive, useState, xml } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { dispatchBatch } from "@al_construction_planner_spreadsheet/send_to_planner";

/** Comandos por tramo: cada pausa deja pintar la pantalla, que recalcula la hoja. */
export const PROGRESS_CHUNK = 2000;

class ProgressDialog extends Component {
    static components = { Dialog };
    static props = ["close", "progress"];
    static template = xml`
        <Dialog title="title" size="'md'">
            <p class="o_construction_progress_label">
                <t t-esc="state.progress.sheet"/>: <t t-esc="state.progress.done"/> de <t t-esc="state.progress.total"/>
            </p>
            <div class="progress mb-2">
                <div class="progress-bar" role="progressbar" t-att-style="'width: ' + percent + '%'"/>
            </div>
            <t t-set-slot="footer">
                <button class="btn btn-secondary o_construction_progress_cancel"
                        t-att-disabled="state.progress.cancelled or state.progress.locked" t-on-click="cancel">Cancelar</button>
            </t>
        </Dialog>
    `;

    setup() {
        this.title = _t("Escribiendo en la hoja");
        this.state = useState({ progress: this.props.progress });
    }

    get percent() {
        const { done, total } = this.state.progress;
        return total ? Math.round((done * 100) / total) : 0;
    }

    cancel() {
        this.state.progress.cancelled = true;
    }
}

export class CancelledError extends Error {}

/** Abre el cuadro de avance; ``finish`` lo cierra. */
export function openProgress(env, total) {
    const progress = reactive({ sheet: "", done: 0, total, cancelled: false, locked: false });
    const close = env.constructionDialog(ProgressDialog, { progress });
    return {
        progress,
        finish: () => close && close(),
        /**
         * Escribe ``commands`` por tramos; con «Cancelar», se detiene. Con ``locked``
         * no se puede cancelar: una ampliación a medias dejaría filas sin fórmulas.
         */
        async write(model, sheet, commands, { locked = false } = {}) {
            progress.sheet = sheet;
            progress.locked = locked;
            for (let start = 0; start < commands.length; start += PROGRESS_CHUNK) {
                if (progress.cancelled) {
                    throw new CancelledError();
                }
                const chunk = commands.slice(start, start + PROGRESS_CHUNK);
                dispatchBatch(model, chunk);
                progress.done += chunk.length;
                // Un respiro real: con 0 ms el navegador no llega a pintar.
                await new Promise((resolve) => setTimeout(resolve, 30));
            }
        },
    };
}
