/**
 * Paquete 1.18, M118-02, puntos 3 y 4: si algún paso de la ruta de INICIO está
 * en «Falta», «Enviar al planificador» muestra la lista con su efecto en el
 * plan y deja elegir entre volver a la hoja (por defecto) o enviar igual. Lo
 * enviado con pendientes queda anotado en la conversación de la obra.
 */
import { Component, xml } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import {
    beforeSendHooks,
    collectSheets,
} from "@al_construction_planner_spreadsheet/send_to_planner";

const START_SHEET = "INICIO";
// Filas de la ruta y columna auxiliar K (planning_sheets.py).
const FIRST_STEP_ROW = 12;
const LAST_ROW = 20;
const PENDING_COL = 10;

/** Efecto en el plan de cada paso pendiente, por el nombre del paso. */
const EFFECTS = [
    ["Traer la venta", _t("El contrato y el ingreso no se arman con la venta.")],
    ["Tablero de cada acabado", _t("Los acabados sin tablero no llevan material.")],
    ["Muebles y módulos", _t("Las tipologías sin módulos no generan plan.")],
    ["Materiales y piezas", _t("Las tipologías sin materiales generan plan sin material.")],
    ["Actividades a hitos", _t("Las actividades sin tarifa entran a costo 0 y sin precio no hay ingreso.")],
    ["Rendimientos", _t("Las actividades sin rendimiento no suman al presupuesto de mano de obra.")],
    ["Programa por piso", _t("«Generar plan» propone las fechas de la obra.")],
    ["Validar y enviar", _t("La hoja no se validó después del último cambio.")],
    ["Aviso: margen negativo", _t("La obra pierde con la venta neta y los costos estimados.")],
];

export function pendingSteps(model) {
    const rows = collectSheets(model, [START_SHEET])[START_SHEET] || [];
    const pending = [];
    for (let row = FIRST_STEP_ROW; row <= LAST_ROW; row++) {
        const text = String((rows[row - 1] || [])[PENDING_COL] || "").trim();
        if (text) {
            const effect = EFFECTS.find(([name]) => text.includes(name));
            pending.push({ text, effect: effect ? effect[1] : "" });
        }
    }
    return pending;
}

class PendingSendDialog extends Component {
    static components = { Dialog };
    static props = ["close", "pending", "resolve"];
    static template = xml`
        <Dialog title="title" size="'lg'">
            <p>La ruta de INICIO tiene pasos pendientes. Lo que se envíe así llega incompleto al planificador:</p>
            <ul class="o_construction_pending_list">
                <li t-foreach="props.pending" t-as="item" t-key="item_index">
                    <strong t-esc="item.text"/>
                    <div t-if="item.effect" class="text-muted small" t-esc="item.effect"/>
                </li>
            </ul>
            <t t-set-slot="footer">
                <button class="btn btn-primary o_construction_pending_back" t-on-click="() => this.answer(false)">Volver a la hoja</button>
                <button class="btn btn-secondary o_construction_pending_send" t-on-click="() => this.answer(true)">Enviar igual</button>
            </t>
        </Dialog>
    `;

    get title() {
        return _t("Enviar con pasos pendientes");
    }

    answer(value) {
        this.props.resolve(value);
        this.props.close();
    }
}

beforeSendHooks.push(async (env) => {
    if (!env.model.getters.getSheetIdByName(START_SHEET)) {
        return true;
    }
    const pending = pendingSteps(env.model);
    if (!pending.length) {
        return true;
    }
    const proceed = await new Promise((resolve) => {
        env.constructionDialog(PendingSendDialog, { pending, resolve }, { onClose: () => resolve(false) });
    });
    if (!proceed) {
        return false;
    }
    return {
        after: () =>
            env.constructionCall(
                "construction_log_pending_send",
                pending.map((item) => item.text)
            ),
    };
});
