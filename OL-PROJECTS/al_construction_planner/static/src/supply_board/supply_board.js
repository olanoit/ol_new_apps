/** @odoo-module **/

/**
 * Abastecimiento de la obra (P-18).
 *
 * Tabla por producto con la necesidad por semana de la etapa que lo consume,
 * stock, OC abiertas, cantidad a comprar, costo del plan y último precio con
 * su alerta. Las filas marcadas abren la compra masiva (W-02); el producto
 * abre sus precios de compra (P-16). Todo lo calcula el servidor
 * (`construction.supply.board.get_board`).
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatFloat } from "@web/core/utils/numbers";
import { formatDate, parseDate } from "@web/core/l10n/dates";

const BOARD = "construction.supply.board";
const WEEK_OPTIONS = [2, 3, 4, 6, 8, 12];

export function formatQty(value) {
    return formatFloat(value || 0, { digits: [16, 2] });
}

export class ConstructionSupplyBoard extends Component {
    static template = "al_construction_planner.SupplyBoard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.weekOptions = WEEK_OPTIONS;
        this.state = useState({
            projects: [],
            projectId: false,
            weeks: 4,
            stages: [],
            data: null,
            selected: {},
            loading: false,
        });
        onWillStart(async () => {
            const context = this.props.action?.context || {};
            this.state.projects = await this.orm.call(BOARD, "get_board_projects", []);
            const wanted = context.construction_project_id;
            const project = this.state.projects.find((p) => p.id === wanted) || this.state.projects[0];
            if (project) {
                this.state.projectId = project.id;
                await this.load();
            }
        });
    }

    get options() {
        return { weeks: this.state.weeks, stages: this.state.stages };
    }

    async load() {
        if (!this.state.projectId) {
            return;
        }
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(BOARD, "get_board", [this.state.projectId, this.options]);
            const valid = new Set(this.state.data.rows.map((row) => row.product_id));
            for (const key of Object.keys(this.state.selected)) {
                if (!valid.has(Number(key))) {
                    delete this.state.selected[key];
                }
            }
        } finally {
            this.state.loading = false;
        }
    }

    // ------------------------------------------------------------------
    // Filtros
    // ------------------------------------------------------------------
    async onProjectChange(ev) {
        this.state.projectId = parseInt(ev.target.value);
        this.state.selected = {};
        await this.load();
    }

    async onWeeksChange(ev) {
        this.state.weeks = parseInt(ev.target.value);
        await this.load();
    }

    async toggleStage(stage) {
        const stages = this.state.stages;
        const index = stages.indexOf(stage);
        if (index >= 0) {
            stages.splice(index, 1);
        } else {
            stages.push(stage);
        }
        await this.load();
    }

    // ------------------------------------------------------------------
    // Selección
    // ------------------------------------------------------------------
    get rows() {
        return this.state.data?.rows || [];
    }

    get selectedRows() {
        return this.rows.filter((row) => this.state.selected[row.product_id]);
    }

    get allSelected() {
        return this.rows.length > 0 && this.selectedRows.length === this.rows.length;
    }

    toggleRow(row) {
        if (this.state.selected[row.product_id]) {
            delete this.state.selected[row.product_id];
        } else {
            this.state.selected[row.product_id] = true;
        }
    }

    toggleAll() {
        if (this.allSelected) {
            this.state.selected = {};
        } else {
            for (const row of this.rows) {
                this.state.selected[row.product_id] = true;
            }
        }
    }

    selectToBuy() {
        this.state.selected = {};
        for (const row of this.rows.filter((r) => r.qty_to_buy > 0)) {
            this.state.selected[row.product_id] = true;
        }
    }

    get selectedAmount() {
        return this.selectedRows.reduce((sum, row) => sum + row.amount, 0);
    }

    get totalAmount() {
        return this.rows.reduce((sum, row) => sum + row.amount, 0);
    }

    // ------------------------------------------------------------------
    // Acciones
    // ------------------------------------------------------------------
    async openPurchase() {
        const productIds = this.selectedRows.map((row) => row.product_id);
        const action = await this.orm.call(BOARD, "action_open_purchase", [
            this.state.projectId,
            productIds,
            this.options,
        ]);
        await this.action.doAction(action, { onClose: () => this.load() });
    }

    async openPrices(row) {
        const action = await this.orm.call(BOARD, "action_open_prices", [
            row.product_id,
            this.state.projectId,
        ]);
        await this.action.doAction(action);
    }

    // ------------------------------------------------------------------
    // Formato
    // ------------------------------------------------------------------
    formatQty(value) {
        return formatQty(value);
    }

    formatWeek(value) {
        return formatDate(parseDate(value), { format: "dd/MM" });
    }

    formatPct(value) {
        const sign = value > 0 ? "+" : "";
        return `${sign}${formatFloat(value || 0, { digits: [16, 1] })} %`;
    }

    /**
     * Alertas de precio y de necesidad una por una; las de producto sin
     * proveedor, en una sola línea (suelen ser muchas).
     */
    get alertLines() {
        const alerts = this.state.data?.alerts || [];
        const lines = alerts.filter((alert) => alert.type !== "no_supplier");
        const noSupplier = alerts.filter((alert) => alert.type === "no_supplier");
        if (noSupplier.length) {
            const names = noSupplier.slice(0, 4).map((alert) => alert.product_name);
            const more = noSupplier.length > 4 ? ` y ${noSupplier.length - 4} más` : "";
            const label = noSupplier.length === 1 ? "producto" : "productos";
            lines.push({
                type: "no_supplier",
                message: `${noSupplier.length} ${label} sin proveedor habitual: ${names.join(", ")}${more}.`,
            });
        }
        return lines;
    }

    alertIcon(type) {
        return {
            price: "fa-arrow-up text-danger",
            no_po: "fa-clock-o text-warning",
            no_supplier: "fa-user-times text-muted",
        }[type];
    }
}

registry.category("actions").add("al_construction_planner.supply_board", ConstructionSupplyBoard);
