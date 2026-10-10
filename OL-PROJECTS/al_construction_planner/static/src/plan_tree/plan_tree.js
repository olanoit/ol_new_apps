/** @odoo-module **/

/**
 * Árbol de recursos del plan (P-02): obra › piso › departamento › ambiente ›
 * módulo, cargado por niveles a demanda, con lo acumulado de cada nodo, la
 * selección en cascada y el panel de recursos de la selección.
 *
 * Todo lo acumulado lo calcula el servidor
 * (`construction.resource.plan.get_tree_nodes` y `get_selection_summary`).
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatFloat } from "@web/core/utils/numbers";
import { _t } from "@web/core/l10n/translation";
import { checkState, effectiveSelection, toggleNode } from "./selection";

const PLAN = "construction.resource.plan";
const ROOT_KEY = "p";

export class ConstructionPlanTree extends Component {
    static template = "al_construction_planner.PlanTree";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            plans: [],
            planId: false,
            options: { stages: [], resource_types: [], unit_states: [], levels: {} },
            filters: { stages: [], resource_types: [], unit_states: [], partner: "" },
            measure: "amount",
            partners: [],
            nodes: {},
            expanded: {},
            selected: {},
            summary: null,
            actions: [],
            loading: false,
        });
        onWillStart(async () => {
            const context = this.props.action?.context || {};
            const [plans, options, actions] = await Promise.all([
                this.orm.searchRead(
                    PLAN,
                    [["state", "not in", ["cancel", "replaced"]]],
                    ["display_name", "project_id", "state"],
                    { order: "id desc" }
                ),
                this.orm.call(PLAN, "get_tree_filters", []),
                this.orm.call(PLAN, "get_tree_actions", []),
            ]);
            this.state.plans = plans;
            this.state.options = options;
            this.state.actions = actions;
            const wanted = context.construction_plan_id || context.active_id;
            const plan = plans.find((p) => p.id === wanted) || plans[0];
            if (plan) {
                await this.loadPlan(plan.id);
            }
        });
    }

    // ------------------------------------------------------------------
    // Carga
    // ------------------------------------------------------------------
    get serverFilters() {
        const f = this.state.filters;
        const filters = {
            stages: f.stages,
            resource_types: f.resource_types,
            unit_states: f.unit_states,
        };
        if (f.partner === "none") {
            filters.partner_ids = [0];
        } else if (f.partner) {
            filters.partner_ids = [parseInt(f.partner)];
        }
        return filters;
    }

    async loadPlan(planId) {
        this.state.planId = planId;
        this.state.selected = {};
        this.state.summary = null;
        this.state.expanded = { [ROOT_KEY]: true };
        this.state.partners = await this.orm.call(PLAN, "get_tree_partners", [[planId]]);
        await this.reload();
    }

    /** Vuelve a cargar los nodos visibles (al cambiar de plan o de filtros). */
    async reload() {
        if (!this.state.planId) {
            return;
        }
        this.state.loading = true;
        const expanded = Object.keys(this.state.expanded);
        const [root] = await this.orm.call(PLAN, "get_tree_nodes", [
            [this.state.planId],
            "root",
            this.serverFilters,
        ]);
        const nodes = { [ROOT_KEY]: { ...root, path: [], children: null } };
        // Recarga por niveles: primero la obra, luego cada nodo abierto.
        const queue = [ROOT_KEY];
        while (queue.length) {
            const key = queue.shift();
            if (!expanded.includes(key) || !nodes[key]?.has_children) {
                continue;
            }
            await this.loadChildren(key, nodes);
            queue.push(...nodes[key].children);
        }
        this.state.nodes = nodes;
        this.state.loading = false;
        await this.refreshSummary();
    }

    async loadChildren(key, nodes = this.state.nodes) {
        const parent = nodes[key];
        const children = await this.orm.call(PLAN, "get_tree_nodes", [
            [this.state.planId],
            key,
            this.serverFilters,
        ]);
        const path = [...parent.path, key];
        for (const child of children) {
            nodes[child.key] = { ...child, path, children: null };
        }
        parent.children = children.map((child) => child.key);
    }

    async toggleExpand(key) {
        const node = this.state.nodes[key];
        if (!node?.has_children) {
            return;
        }
        if (this.state.expanded[key]) {
            delete this.state.expanded[key];
            return;
        }
        if (!node.children) {
            await this.loadChildren(key);
        }
        this.state.expanded[key] = true;
    }

    async refreshSummary() {
        const keys = effectiveSelection(this.state.nodes, this.state.selected);
        if (!keys.length) {
            this.state.summary = null;
            return;
        }
        this.state.summary = await this.orm.call(PLAN, "get_selection_summary", [
            [this.state.planId],
            keys,
            this.serverFilters,
        ]);
    }

    // ------------------------------------------------------------------
    // Selección
    // ------------------------------------------------------------------
    checkState(key) {
        return checkState(this.state.nodes, this.state.selected, key);
    }

    async toggleCheck(key) {
        this.state.selected = toggleNode(this.state.nodes, this.state.selected, key);
        await this.refreshSummary();
    }

    async clearSelection() {
        this.state.selected = {};
        await this.refreshSummary();
    }

    get selectionKeys() {
        return effectiveSelection(this.state.nodes, this.state.selected);
    }

    async runAction(xmlid) {
        const keys = this.selectionKeys;
        await this.action.doAction(xmlid, {
            additionalContext: {
                active_model: PLAN,
                active_id: this.state.planId,
                default_plan_id: this.state.planId,
                construction_selection_keys: keys,
                construction_selection_task_ids: keys
                    .filter((key) => key !== ROOT_KEY)
                    .map((key) => parseInt(key)),
                construction_selection_project: keys.includes(ROOT_KEY),
            },
            onClose: () => this.reload(),
        });
    }

    // ------------------------------------------------------------------
    // Filtros y medida
    // ------------------------------------------------------------------
    async onPlanChange(ev) {
        await this.loadPlan(parseInt(ev.target.value));
    }

    async toggleFilter(group, value) {
        const values = this.state.filters[group];
        const index = values.indexOf(value);
        if (index >= 0) {
            values.splice(index, 1);
        } else {
            values.push(value);
        }
        await this.reload();
    }

    async onPartnerChange(ev) {
        this.state.filters.partner = ev.target.value;
        await this.reload();
    }

    setMeasure(measure) {
        this.state.measure = measure;
    }

    // ------------------------------------------------------------------
    // Presentación
    // ------------------------------------------------------------------
    get rows() {
        const rows = [];
        const visit = (key, depth) => {
            const node = this.state.nodes[key];
            if (!node) {
                return;
            }
            rows.push({ node, depth });
            if (this.state.expanded[key] && node.children) {
                for (const child of node.children) {
                    visit(child, depth + 1);
                }
            }
        };
        visit(ROOT_KEY, 0);
        return rows;
    }

    get columns() {
        if (this.state.measure === "driver") {
            return [
                { field: "qty_material", label: _t("Material (cant.)") },
                { field: "qty_contract", label: _t("Driver contratas") },
                { field: "qty_total", label: _t("Cantidad total") },
            ];
        }
        return [
            { field: "material", label: _t("Material") },
            { field: "contract", label: _t("Contrata") },
            { field: "total", label: _t("Total") },
        ];
    }

    levelLabel(level) {
        if (level === "project") {
            return _t("Obra");
        }
        return this.state.options.levels[level] || "";
    }

    fmt(value, digits = 2) {
        return formatFloat(value || 0, { digits: [16, digits] });
    }

    progressLabel(node) {
        if (node.level === "module") {
            return node.unit_state_label || "";
        }
        return `${this.fmt((node.progress || 0) * 100, 1)} %`;
    }

    openTask(node) {
        if (!node.task_id) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "project.task",
            res_id: node.task_id,
            views: [[false, "form"]],
        });
    }

    async filterUnassigned() {
        this.state.filters.partner = "none";
        this.state.filters.resource_types = ["contract", "labor"];
        await this.reload();
    }
}

registry.category("actions").add("al_construction_planner.plan_tree", ConstructionPlanTree);
