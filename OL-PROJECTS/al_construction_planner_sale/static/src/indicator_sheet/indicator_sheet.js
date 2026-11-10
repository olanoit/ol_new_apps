/**
 * Ficha de indicadores de la obra (paquete 7 de CREVAL, CR-60).
 *
 * Una página con el encabezado de la obra, los cuatro bloques
 * «presupuestado contra ejecutado» de la cartera (mismo cálculo y formato),
 * el seguimiento, el plazo, los gráficos «Avance físico contra valorizado» y
 * curva S de costo, y las tablas de valorizaciones, especialidades y cambios.
 * Todo lo calcula `construction.project.indicators.get_indicator_sheet`.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import {
    ConstructionIndicatorBlocks,
    formatIndex,
    formatPct,
    formatThousands,
} from "@al_construction_planner/core/indicator_blocks";

const MODEL = "construction.project.indicators";
const CHART = { width: 900, height: 240, left: 56, right: 16, top: 12, bottom: 26 };

function toTime(date) {
    return new Date(`${date}T00:00:00`).getTime();
}

export class ConstructionIndicatorSheet extends Component {
    static template = "al_construction_planner_sale.IndicatorSheet";
    static components = { ConstructionIndicatorBlocks };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.chart = CHART;
        this.state = useState({ data: null, loading: false });
        this.projectId = this.props.action?.context?.construction_project_id;
        onWillStart(() => this.load());
    }

    async load() {
        if (!this.projectId) {
            return;
        }
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(MODEL, "get_indicator_sheet", [this.projectId]);
        } finally {
            this.state.loading = false;
        }
    }

    get data() {
        return this.state.data || {};
    }

    k(value) {
        return formatThousands(value);
    }

    pct(value) {
        return formatPct(value);
    }

    idx(value) {
        return formatIndex(value);
    }

    get stageLabel() {
        return {
            planning: _t("En planificación"),
            execution: _t("En ejecución"),
            postsale: _t("Postventa"),
        }[this.data.stage] || "";
    }

    get extraClose() {
        return [
            {
                key: "eac",
                label: _t("Costo"),
                help: _t("Presup.: costo meta. Ejec.: costo final estimado = costo ejecutado + (costo meta − valor ganado) ÷ CPI."),
                budget: this.k(this.data.close?.bac),
                executed: this.k(this.data.close?.eac),
            },
        ];
    }

    // ------------------------------------------------------------------
    // Gráficos (SVG)
    // ------------------------------------------------------------------
    xScale(first, last) {
        const t0 = toTime(first);
        const span = Math.max(toTime(last) - t0, 1);
        const width = CHART.width - CHART.left - CHART.right;
        return (date) => CHART.left + (width * (toTime(date) - t0)) / span;
    }

    yScale(max) {
        const height = CHART.height - CHART.top - CHART.bottom;
        return (value) => CHART.top + height - (height * value) / (max || 1);
    }

    get progressChart() {
        const chart = this.data.charts?.progress;
        if (!chart || !chart.start) {
            return null;
        }
        const x = this.xScale(chart.start, chart.end);
        const max = 1;
        const y = this.yScale(max);
        const physical = chart.dates.map((d, i) => `${x(d)},${y(chart.physical[i])}`).join(" ");
        const stepLine = (steps) => {
            let previous = 0;
            const points = [`${x(chart.start)},${y(0)}`];
            for (const step of steps) {
                points.push(`${x(step.date)},${y(previous)}`, `${x(step.date)},${y(step.value)}`);
                previous = step.value;
            }
            points.push(`${x(chart.end)},${y(previous)}`);
            return points.join(" ");
        };
        const valuedToday = chart.valued.filter((s) => s.date <= chart.today).at(-1)?.value || 0;
        const physicalToday = chart.physical.at(-1) || 0;
        return {
            physical,
            valued: stepLine(chart.valued),
            planned: stepLine(chart.planned),
            todayX: x(chart.today),
            gapTop: y(Math.max(physicalToday, valuedToday)),
            gapBottom: y(Math.min(physicalToday, valuedToday)),
            gapLabel: this.data.show_amounts
                ? _t("por valorizar %s", this.k(chart.to_value))
                : _t("por valorizar %s", this.pct(chart.to_value_pct)),
            ticks: [0, 0.25, 0.5, 0.75, 1].map((v) => ({ y: y(v), label: `${v * 100} %` })),
            xTicks: this.xTicks(chart.start, chart.end, x),
        };
    }

    get costChart() {
        const chart = this.data.charts?.cost;
        if (!chart || !chart.dates?.length || !this.data.show_amounts) {
            return null;
        }
        const first = chart.dates[0];
        const last = chart.dates.at(-1);
        const x = this.xScale(first, last);
        const max = Math.max(...chart.planned, ...chart.earned, ...chart.actual, 1);
        const y = this.yScale(max);
        const line = (dates, values) => dates.map((d, i) => `${x(d)},${y(values[i] || 0)}`).join(" ");
        return {
            planned: line(chart.dates, chart.planned),
            earned: line(chart.actual_dates, chart.earned),
            actual: chart.actual.length ? line(chart.actual_dates, chart.actual) : "",
            todayX: x(chart.today),
            ticks: [0, 0.5, 1].map((v) => ({ y: y(max * v), label: this.k(max * v) })),
            xTicks: this.xTicks(first, last, x),
        };
    }

    xTicks(first, last, x) {
        const t0 = toTime(first);
        const t1 = toTime(last);
        const ticks = [];
        for (let i = 0; i <= 5; i++) {
            const date = new Date(t0 + ((t1 - t0) * i) / 5);
            const label = `${String(date.getDate()).padStart(2, "0")}/${String(date.getMonth() + 1).padStart(2, "0")}`;
            const iso = date.toISOString().slice(0, 10);
            ticks.push({ x: x(iso), label });
        }
        return ticks;
    }

    // ------------------------------------------------------------------
    // Accesos
    // ------------------------------------------------------------------
    async open(kind, resId = false) {
        const action = await this.orm.call(MODEL, "action_open_document", [this.projectId, kind, resId]);
        await this.action.doAction(action);
    }

    async toggleFavorite() {
        this.state.data.is_favorite = await this.orm.call(MODEL, "toggle_favorite", [this.projectId]);
    }
}

registry.category("actions").add("al_construction_planner_sale.indicator_sheet", ConstructionIndicatorSheet);
