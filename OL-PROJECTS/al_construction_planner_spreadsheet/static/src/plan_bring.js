/**
 * CREVAL, paquete 5, CR-45, punto 2: «Traer la venta» en la hoja de
 * planificación de obra, con la vista previa y la huella de mobiliario
 * (M117-22). PLAN trae por ítem solo lo vendido (ítem y partida); los APU de
 * obra (INSUMOS, APU y APU_DETALLE) no pisan lo que el planificador cambió
 * desde la última vez sin que lo marque; OBRA y PRESUPUESTO son la copia de lo
 * vendido y se reescriben.
 */
import { registries } from "@odoo/o-spreadsheet";
import { _t } from "@web/core/l10n/translation";
import {
    BringDialog,
    compareBring,
    ensureRows,
    writeTrace,
} from "@al_construction_planner_spreadsheet/bring_preview";
import {
    dispatchBatch,
    ensureSheet,
    validate,
    writeRows,
} from "@al_construction_planner_spreadsheet/send_to_planner";

const { topbarMenuRegistry } = registries;

const isBudgetPlan = (env) =>
    env.constructionSheetKind &&
    env.constructionSheetKind() === "budget" &&
    env.constructionMetadata &&
    env.constructionMetadata("construction_budget_role") === "plan";

export function applyPlanBring(model, tabs, data) {
    const commands = [];
    const traced = {};
    const counts = { new: 0, change: 0, extra: 0 };
    for (const tab of tabs) {
        const sheetId = tab.sheetId || ensureSheet(model, tab.name);
        let next = tab.last + 1;
        ensureRows(model, sheetId, next + tab.items.length + 1);
        for (const item of tab.items) {
            if (item.record) {
                traced[`${tab.name}|${item.id}`] = item.record;
            }
            if (!item.marked) {
                continue;
            }
            counts[item.kind] = (counts[item.kind] || 0) + 1;
            if (item.kind === "extra") {
                for (const col of Object.values(tab.columns)) {
                    commands.push(["UPDATE_CELL", { sheetId, col, row: item.row, content: "" }]);
                }
                continue;
            }
            const row = item.kind === "new" ? next++ : item.row;
            for (const [key, col] of Object.entries(tab.columns)) {
                commands.push([
                    "UPDATE_CELL",
                    { sheetId, col, row, content: String(item.record[key] ?? "") },
                ]);
            }
        }
    }
    dispatchBatch(model, commands);
    for (const [name, rows] of Object.entries(data.from_top || {})) {
        if (rows.length) {
            const sheetId = ensureSheet(model, name);
            ensureRows(model, sheetId, rows.length + 1);
            writeRows(model, sheetId, rows, 0);
        }
    }
    writeTrace(model, traced);
    return counts;
}

export async function bringPlanSale(env) {
    const data = await env.constructionCall("construction_plan_bring");
    const tabs = compareBring(env.model, data);
    env.constructionDialog(BringDialog, {
        tabs,
        warnings: data.warnings,
        apply: async (selected) => {
            await env.constructionCall("construction_version_before", _t("Antes de traer la venta"));
            const counts = applyPlanBring(env.model, selected, data);
            await validate(env, { quiet: true });
            env.constructionNotify(
                _t("Venta traída (versión anterior guardada): %(new)s nuevas, %(change)s cambiadas, %(extra)s quitadas.", {
                    new: counts.new,
                    change: counts.change,
                    extra: counts.extra,
                })
            );
        },
    });
}

topbarMenuRegistry.addChild("construction_budget_plan_bring", ["construction_planner"], {
    name: _t("Traer la venta…"),
    sequence: 10,
    isVisible: isBudgetPlan,
    execute: (env) => bringPlanSale(env),
});
