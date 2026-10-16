/** @odoo-module **/

/**
 * Recursos planificados como tabla insumo-producto (v1.8, M18-04).
 *
 * Filas: elementos del alcance en el nivel elegido. Columnas: insumos con un
 * encabezado de varios niveles (etapa padre › etapa › tipo de recurso) que se
 * pliega y despliega; un grupo plegado es una sola columna con su subtotal.
 * Todo lo calcula `construction.resource.plan.get_io_matrix`.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatFloat } from "@web/core/utils/numbers";
import { _t } from "@web/core/l10n/translation";
import { stageFilterLabel, stageNodeState, toggleStageNode } from "../stage_filter/stage_filter";

const PLAN = "construction.resource.plan";
const KINDS = ["parent", "stage", "type"];

/**
 * Columnas visibles: cada columna real o, si un grupo que la contiene está
 * plegado, una sola entrada por el grupo plegado más externo.
 */
export function visibleColumns(matrix, collapsed) {
    const groups = Object.fromEntries((matrix.groups || []).map((g) => [g.key, g]));
    const ancestors = (groupKey) => {
        const chain = [];
        let key = groupKey;
        while (key) {
            chain.unshift(groups[key]);
            key = groups[key]?.parent;
        }
        return chain;
    };
    const result = [];
    const seen = new Set();
    for (const column of matrix.columns || []) {
        const chain = ancestors(column.group);
        const folded = chain.find((group) => collapsed[group.key]);
        if (folded) {
            if (!seen.has(folded.key)) {
                seen.add(folded.key);
                result.push({ kind: "group", key: folded.key, group: folded, chain: ancestors(folded.key) });
            }
            continue;
        }
        result.push({ kind: "column", key: column.key, column, chain });
    }
    return result;
}

/** Filas del encabezado: por cada tipo de grupo, celdas unidas por grupo. */
export function headerRows(matrix, visible) {
    const kinds = KINDS.filter((kind) => (matrix.groups || []).some((g) => g.kind === kind));
    return kinds.map((kind) => {
        const cells = [];
        for (const entry of visible) {
            const group = entry.chain.find((g) => g.kind === kind) || null;
            const last = cells[cells.length - 1];
            const key = group ? group.key : null;
            if (last && last.key === key && (key || !last.group)) {
                last.span += 1;
            } else {
                cells.push({ key, group, span: 1, folded: entry.kind === "group" && entry.key === key });
            }
        }
        return { kind, cells };
    });
}

export class ConstructionIoMatrix extends Component {
    static template = "al_construction_planner.IoMatrix";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        const context = this.props.action?.context || {};
        this.keys = context.construction_selection_keys || ["p"];
        this.state = useState({
            plans: [],
            planId: context.construction_plan_id || context.active_id || false,
            options: { levels: [], values: [], stage_tree: [], show_amounts: false },
            level: context.construction_io_level || false,
            measure: "amount",
            value: "planned",
            stages: [...(context.construction_filters?.stages || [])],
            filters: context.construction_filters || {},
            matrix: null,
            collapsed: {},
            loading: false,
        });
        onWillStart(async () => {
            this.state.plans = await this.orm.searchRead(
                PLAN,
                [["state", "not in", ["cancel", "replaced"]]],
                ["display_name", "project_id"],
                { order: "id desc" }
            );
            if (!this.state.planId && this.state.plans.length) {
                this.state.planId = this.state.plans[0].id;
            }
            await this.loadOptions();
        });
    }

    get hasSelection() {
        return !(this.keys.length === 1 && this.keys[0] === "p");
    }

    async loadOptions() {
        if (!this.state.planId) {
            return;
        }
        this.state.options = await this.orm.call(PLAN, "get_io_matrix_options", [
            [this.state.planId],
        ]);
        if (!this.state.options.levels.some((level) => level.field === this.state.level)) {
            this.state.level = this.state.options.default_level;
        }
        // Sin el grupo de montos (v1.8, M18-10) la matriz va en cantidades.
        if (!this.state.options.show_amounts) {
            this.state.measure = "qty";
        }
        await this.load();
    }

    get serverFilters() {
        return { ...this.state.filters, stages: this.state.stages };
    }

    get serverOptions() {
        return { level: this.state.level, measure: this.state.measure, value: this.state.value };
    }

    async load() {
        this.state.loading = true;
        this.state.matrix = await this.orm.call(PLAN, "get_io_matrix", [
            [this.state.planId],
            this.keys,
            this.serverFilters,
            this.serverOptions,
        ]);
        this.state.loading = false;
    }

    // ------------------------------------------------------------------
    // Barra
    // ------------------------------------------------------------------
    async onPlanChange(ev) {
        this.state.planId = parseInt(ev.target.value);
        this.keys = ["p"];
        await this.loadOptions();
    }

    async onLevelChange(ev) {
        this.state.level = ev.target.value;
        await this.load();
    }

    async onValueChange(ev) {
        this.state.value = ev.target.value;
        await this.load();
    }

    async setMeasure(measure) {
        this.state.measure = measure;
        await this.load();
    }

    get stageLabel() {
        return stageFilterLabel(this.state.options.stage_tree, this.state.stages, _t("Todas las etapas"));
    }

    stageState(node) {
        return stageNodeState(node, this.state.stages);
    }

    async toggleStage(node) {
        this.state.stages = toggleStageNode(node, this.state.stages);
        await this.load();
    }

    async clearStages() {
        this.state.stages = [];
        await this.load();
    }

    async wholeProject() {
        this.keys = ["p"];
        await this.load();
    }

    async exportExcel() {
        const action = await this.orm.call(PLAN, "action_export_io_matrix", [
            [this.state.planId],
            this.keys,
            this.serverFilters,
            this.serverOptions,
        ]);
        await this.action.doAction(action);
    }

    // ------------------------------------------------------------------
    // Tabla
    // ------------------------------------------------------------------
    get visible() {
        return this.state.matrix ? visibleColumns(this.state.matrix, this.state.collapsed) : [];
    }

    get header() {
        return this.state.matrix ? headerRows(this.state.matrix, this.visible) : [];
    }

    toggleGroup(key) {
        if (!key) {
            return;
        }
        this.state.collapsed[key] = !this.state.collapsed[key];
    }

    collapseAll(kind) {
        const collapsed = {};
        for (const group of this.state.matrix?.groups || []) {
            if (group.kind === kind) {
                collapsed[group.key] = true;
            }
        }
        this.state.collapsed = collapsed;
    }

    expandAll() {
        this.state.collapsed = {};
    }

    cell(row, entry) {
        const cells = this.state.matrix.cells;
        if (entry.kind === "column") {
            return cells[`${row.id}|${entry.key}`] || 0;
        }
        return entry.group.columns.reduce((sum, key) => sum + (cells[`${row.id}|${key}`] || 0), 0);
    }

    columnTotal(entry) {
        const totals = this.state.matrix.column_totals;
        if (entry.kind === "column") {
            return totals[entry.key] || 0;
        }
        return entry.group.columns.reduce((sum, key) => sum + (totals[key] || 0), 0);
    }

    rowTotal(row) {
        return this.state.matrix.row_totals[String(row.id)] || 0;
    }

    fmt(value) {
        if (!value) {
            return "";
        }
        return formatFloat(value, { digits: [16, this.state.measure === "qty" ? 2 : 2] });
    }

    openRow(row) {
        if (!row.id) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "project.task",
            res_id: row.id,
            views: [[false, "form"]],
        });
    }
}

registry.category("actions").add("al_construction_planner.io_matrix", ConstructionIoMatrix);
