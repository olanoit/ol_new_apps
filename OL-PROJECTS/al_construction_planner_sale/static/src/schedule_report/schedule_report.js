/** @odoo-module **/

/**
 * Cronograma valorizado de la obra (P-22).
 *
 * Curva S con costo, ingreso y cobrado acumulados (plan y real) y la tabla
 * semanal de costo, ingreso devengado, margen, valorización, facturado y
 * cobrado. Todo lo calcula el servidor
 * (`construction.schedule.report.get_schedule`), que recalcula la obra al
 * abrirla; el pivote y el gráfico nativos leen las mismas filas.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatFloat } from "@web/core/utils/numbers";

const REPORT = "construction.schedule.report";
const CHART = { width: 900, height: 260, left: 70, right: 16, top: 12, bottom: 28 };
// Series de la curva S: escenario, columna acumulada, clase y leyenda.
const SERIES = [
    { scenario: "plan", key: "cost_cum", css: "o_cp_s_cost", dashed: true, label: "Costo previsto" },
    { scenario: "plan", key: "revenue_cum", css: "o_cp_s_revenue", dashed: true, label: "Ingreso previsto" },
    { scenario: "plan", key: "collection_cum", css: "o_cp_s_collection", dashed: true, label: "Cobrado previsto" },
    { scenario: "real", key: "cost_cum", css: "o_cp_s_cost", label: "Costo real" },
    { scenario: "real", key: "revenue_cum", css: "o_cp_s_revenue", label: "Ingreso real" },
    { scenario: "real", key: "collection_cum", css: "o_cp_s_collection", label: "Cobrado real" },
];

export class ConstructionScheduleReport extends Component {
    static template = "al_construction_planner.ScheduleReport";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.chart = CHART;
        this.state = useState({
            projects: [],
            projectId: false,
            scenario: "plan",
            data: null,
            loading: false,
        });
        onWillStart(async () => {
            const context = this.props.action?.context || {};
            this.state.projects = await this.orm.call(REPORT, "get_schedule_projects", []);
            const wanted = context.construction_project_id;
            const project = this.state.projects.find((p) => p.id === wanted) || this.state.projects[0];
            if (project) {
                this.state.projectId = project.id;
                await this.load();
            }
        });
    }

    async load() {
        if (!this.state.projectId) {
            return;
        }
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(REPORT, "get_schedule", [this.state.projectId]);
        } finally {
            this.state.loading = false;
        }
    }

    async onProjectChange(ev) {
        this.state.projectId = parseInt(ev.target.value);
        await this.load();
    }

    setScenario(scenario) {
        this.state.scenario = scenario;
    }

    get rows() {
        return this.state.data?.rows || [];
    }

    get totals() {
        return this.state.data?.totals?.[this.state.scenario] || {};
    }

    get otherTotals() {
        const other = this.state.scenario === "plan" ? "real" : "plan";
        return this.state.data?.totals?.[other] || {};
    }

    // ------------------------------------------------------------------
    // Curva S (SVG)
    // ------------------------------------------------------------------
    get maxValue() {
        let max = 0;
        for (const row of this.rows) {
            for (const serie of SERIES) {
                max = Math.max(max, row[serie.scenario][serie.key]);
            }
        }
        return max || 1;
    }

    x(index) {
        const span = CHART.width - CHART.left - CHART.right;
        const count = Math.max(this.rows.length - 1, 1);
        return CHART.left + (span * index) / count;
    }

    y(value) {
        const span = CHART.height - CHART.top - CHART.bottom;
        return CHART.top + span - (span * value) / this.maxValue;
    }

    get series() {
        const rows = this.rows;
        const realUntil = this.state.data?.real_until;
        return SERIES.map((serie) => {
            // La serie real llega hasta hoy o hasta lo último registrado.
            const points = rows
                .map((row, index) => ({ row, index }))
                .filter(({ row }) => serie.scenario === "plan" || !realUntil || row.week_start <= realUntil)
                .map(({ row, index }) => `${this.x(index)},${this.y(row[serie.scenario][serie.key])}`);
            return { ...serie, points: points.join(" ") };
        });
    }

    get yTicks() {
        const max = this.maxValue;
        return [0, 0.25, 0.5, 0.75, 1].map((ratio) => ({
            y: this.y(max * ratio),
            label: formatFloat(max * ratio, { digits: [16, 0] }),
        }));
    }

    get xTicks() {
        const rows = this.rows;
        const step = Math.max(1, Math.ceil(rows.length / 10));
        return rows
            .map((row, index) => ({ index, label: row.label.split(" – ")[0] }))
            .filter(({ index }) => index % step === 0)
            .map(({ index, label }) => ({ x: this.x(index), label }));
    }

    get todayX() {
        const index = this.rows.findIndex((row) => row.week_start === this.state.data?.today_week);
        return index >= 0 ? this.x(index) : false;
    }

    // ------------------------------------------------------------------
    // Acciones
    // ------------------------------------------------------------------
    async exportXlsx() {
        const action = await this.orm.call(REPORT, "action_export_xlsx", [this.state.projectId]);
        await this.action.doAction(action);
    }

    async openAnalysis() {
        const action = await this.orm.call(REPORT, "action_open_analysis", [this.state.projectId]);
        await this.action.doAction(action);
    }

    // ------------------------------------------------------------------
    // Formato
    // ------------------------------------------------------------------
    money(value) {
        if (!value) {
            return "—";
        }
        return formatFloat(value, { digits: [16, 2] });
    }

    moneyAlways(value) {
        return formatFloat(value || 0, { digits: [16, 2] });
    }

    isTodayWeek(row) {
        return row.week_start === this.state.data?.today_week;
    }
}

registry.category("actions").add("al_construction_planner.schedule_report", ConstructionScheduleReport);
