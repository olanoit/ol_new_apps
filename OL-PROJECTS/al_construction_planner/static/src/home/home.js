/** @odoo-module **/

/**
 * Inicio de la aplicación (P-01) con la cartera de obras (paquete 7 de
 * CREVAL, CR-59) y los pendientes por área (CR-65).
 *
 * El servidor (`construction.planner.home.get_home_data`) trae cada obra con
 * su etapa, favorita, fechas y, si está el puente de ventas, sus indicadores
 * (los mismos de la ficha). Pestañas, filtros, orden y totales se resuelven
 * aquí; el orden elegido se recuerda por usuario en el navegador. Sin
 * indicadores (sin el puente de ventas) queda la tabla de planes de P-01.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { formatFloat } from "@web/core/utils/numbers";
import {
    ConstructionIndicatorBlocks,
    INDICATOR_BLOCKS,
    formatIndex,
    formatIndicator,
    indicatorClass,
} from "@al_construction_planner/core/indicator_blocks";

const HOME = "construction.planner.home";
const STATE_BADGES = {
    draft: "text-bg-secondary",
    to_approve: "text-bg-warning",
    approved: "text-bg-info",
    in_progress: "text-bg-success",
    closed: "text-bg-dark",
};
const TABS = [
    { key: "planning", label: _t("En planificación") },
    { key: "execution", label: _t("En ejecución") },
    { key: "postsale", label: _t("Postventa") },
    { key: "all", label: _t("Todas") },
];
const LIGHT_ORDER = { red: 0, amber: 1, green: 2 };
/** Opciones de «⇅ Ordenar»: clave → (obra) → valor; `desc` de mayor a menor. */
const SORTS = [
    { key: "late", label: _t("Más atrasadas"), desc: true, value: (w) => w.indicators?.days_late ?? -1e9 },
    { key: "invoiced", label: _t("Mayor facturación"), desc: true, value: (w) => w.indicators?.invoiced || 0 },
    { key: "sale", label: _t("Mayor venta"), desc: true, value: (w) => w.indicators?.budget?.close_sale || 0 },
    { key: "to_value", label: _t("Mayor por valorizar"), desc: true, value: (w) => w.indicators?.executed?.to_value || 0 },
    { key: "margin", label: _t("Menor margen"), desc: false, value: (w) => w.indicators?.executed?.close_margin_pct ?? 1e9 },
    { key: "start", label: _t("Fecha de inicio"), desc: false, value: (w) => w.date_start || "9999" },
    { key: "end", label: _t("Fecha de fin más próxima"), desc: false, value: (w) => w.date_end || "9999" },
    { key: "name", label: _t("Nombre"), desc: false, value: (w) => (w.project_name || "").toLowerCase() },
];

function sum(works, getter) {
    return works.reduce((total, work) => total + (getter(work) || 0), 0);
}

export class ConstructionPlannerHome extends Component {
    static template = "al_construction_planner.Home";
    static components = { ConstructionIndicatorBlocks };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.tabs = TABS;
        this.sorts = SORTS;
        this.blocks = INDICATOR_BLOCKS;
        this.sortKey = `al_construction_planner.home_sort.${user.userId}`;
        let sort = "name";
        try {
            sort = browser.localStorage.getItem(this.sortKey) || "name";
        } catch {
            // Sin almacenamiento del navegador: orden por nombre.
        }
        this.state = useState({
            data: null,
            loading: false,
            tab: "execution",
            favorites: false,
            mine: false,
            red: false,
            sort,
            month: false,
            openAreas: {},
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(HOME, "get_home_data", [], {
                month: this.state.month || false,
            });
            this.state.month = this.state.data.month;
        } finally {
            this.state.loading = false;
        }
    }

    // ------------------------------------------------------------------
    // Cartera
    // ------------------------------------------------------------------
    get works() {
        return this.state.data?.works || [];
    }

    get unplanned() {
        return this.state.data?.unplanned || [];
    }

    get hasIndicators() {
        return this.works.some((work) => work.indicators);
    }

    get showAmounts() {
        return this.state.data?.show_amounts;
    }

    /** Obras con plan y sin plan (estas solo en «En planificación»). */
    get allWorks() {
        return [...this.works, ...this.unplanned.map((work) => ({ ...work, unplanned: true }))];
    }

    tabCount(tab) {
        return this.allWorks.filter((work) => tab === "all" || work.stage === tab).length;
    }

    get filteredWorks() {
        const { tab, favorites, mine, red } = this.state;
        return this.works.filter(
            (work) =>
                (tab === "all" || work.stage === tab) &&
                (!favorites || work.is_favorite) &&
                (!mine || work.mine) &&
                (!red || work.indicators?.light === "red")
        );
    }

    get sortedWorks() {
        const sort = SORTS.find((s) => s.key === this.state.sort) || SORTS.at(-1);
        return [...this.filteredWorks].sort((a, b) => {
            if (a.is_favorite !== b.is_favorite) {
                return a.is_favorite ? -1 : 1;
            }
            const va = sort.value(a);
            const vb = sort.value(b);
            if (va === vb) {
                return (a.project_name || "").localeCompare(b.project_name || "");
            }
            const order = va < vb ? -1 : 1;
            return sort.desc ? -order : order;
        });
    }

    get filteredUnplanned() {
        const { tab, favorites, mine, red } = this.state;
        if (red || !["planning", "all"].includes(tab)) {
            return [];
        }
        return this.unplanned.filter((work) => (!favorites || work.is_favorite) && (!mine || work.mine));
    }

    get sortLabel() {
        return SORTS.find((s) => s.key === this.state.sort)?.label || "";
    }

    setTab(tab) {
        this.state.tab = tab;
    }

    toggleFilter(name) {
        this.state[name] = !this.state[name];
    }

    setSort(key) {
        this.state.sort = key;
        try {
            browser.localStorage.setItem(this.sortKey, key);
        } catch {
            // Sin almacenamiento: el orden vale para esta visita.
        }
    }

    async onMonthChange(ev) {
        const value = ev.target.value; // aaaa-mm
        if (!value) {
            return;
        }
        this.state.month = `${value}-01`;
        await this.load();
    }

    get monthInput() {
        return (this.state.month || "").slice(0, 7);
    }

    get monthTitle() {
        if (!this.state.month) {
            return "";
        }
        const date = new Date(`${this.state.month}T00:00:00`);
        const label = date.toLocaleDateString(user.lang?.replace("_", "-") || undefined, {
            month: "long",
            year: "numeric",
        });
        return _t("%s · venta proyectada de la empresa", label);
    }

    /** Total de la cartera: lo que respetan pestaña y filtros. */
    get totals() {
        const works = this.filteredWorks.filter((work) => work.indicators);
        const side = (name) => {
            const get = (key) => (w) => w.indicators[name][key];
            const sale = sum(works, get("sale"));
            const cost = sum(works, get("cost"));
            const closeSale = sum(works, get("close_sale"));
            // Avance y valorizado: ponderados por la venta; sin montos (sin
            // «Ve montos»), el promedio simple.
            const weighted = (key) => {
                if (closeSale) {
                    return sum(works, (w) => (w.indicators[name][key] || 0) * (w.indicators[name].close_sale || 0)) / closeSale;
                }
                return works.length ? sum(works, (w) => w.indicators[name][key]) / works.length : false;
            };
            const closeCost =
                name === "budget" ? sum(works, (w) => w.indicators.bac) : sum(works, (w) => w.indicators.eac);
            return {
                sale,
                cost,
                margin: sale - cost,
                margin_pct: sale ? (sale - cost) / sale : false,
                physical: weighted("physical"),
                valued: weighted("valued"),
                to_value: sum(works, get("to_value")),
                month_valuation: sum(works, get("month_valuation")),
                month_cost: sum(works, get("month_cost")),
                month_margin: sum(works, get("month_margin")),
                close_sale: closeSale,
                close_margin_pct: closeSale ? (closeSale - closeCost) / closeSale : false,
            };
        };
        const budget = side("budget");
        const executed = side("executed");
        if (!this.showAmounts) {
            for (const values of [budget, executed]) {
                for (const key of ["sale", "cost", "margin", "to_value", "month_valuation", "month_cost", "month_margin", "close_sale"]) {
                    values[key] = false;
                }
                values.margin_pct = false;
                values.close_margin_pct = false;
            }
        }
        return { budget, executed };
    }

    // ------------------------------------------------------------------
    // Fila de la obra
    // ------------------------------------------------------------------
    cell(work, row, item) {
        return formatIndicator(item, work.indicators?.[row]?.[item.key]);
    }

    cellClass(work, item) {
        const ind = work.indicators || {};
        return indicatorClass(item, ind.budget?.[item.key], ind.executed?.[item.key], ind.lights || {});
    }

    idx(value) {
        return formatIndex(value);
    }

    lightClass(light) {
        return `o_cp_dot o_cp_dot_${light || "none"}`;
    }

    async toggleFavorite(work) {
        work.is_favorite = await this.orm.call(HOME, "toggle_favorite", [work.project_id]);
    }

    async openWork(work) {
        if (work.indicators) {
            await this.action.doAction({
                type: "ir.actions.client",
                tag: "al_construction_planner_sale.indicator_sheet",
                name: _t("Ficha · %s", work.project_name),
                context: { construction_project_id: work.project_id },
            }, { onClose: () => this.load() });
            return;
        }
        const action = await this.orm.call(HOME, "action_open_plan", [work.plan_id]);
        await this.action.doAction(action);
    }

    async openPlan(work) {
        const action = await this.orm.call(HOME, "action_open_plan", [work.plan_id]);
        await this.action.doAction(action);
    }

    async openSchedule(work) {
        await this.action.doAction({
            type: "ir.actions.client",
            tag: "al_construction_planner.schedule_report",
            name: "Cronograma valorizado",
            context: { construction_project_id: work.project_id },
        });
    }

    async runUnplanned(work, action) {
        const result = await this.orm.call("project.project", action.method, [[work.project_id]]);
        await this.action.doAction(result);
    }

    // ------------------------------------------------------------------
    // Pendientes por área (CR-65)
    // ------------------------------------------------------------------
    get pending() {
        return this.state.data?.pending || [];
    }

    get pendingTotal() {
        return sum(this.pending, (item) => item.count);
    }

    get pendingAreas() {
        const areas = this.state.data?.areas || [];
        return areas
            .map(([key, label]) => {
                const items = this.pending.filter((item) => (item.area || "other") === key);
                return {
                    key,
                    label,
                    items: items.filter((item) => item.count),
                    zero: items.filter((item) => !item.count),
                    total: sum(items, (item) => item.count),
                };
            })
            .filter((area) => area.items.length || area.zero.length);
    }

    toggleArea(key) {
        this.state.openAreas[key] = !this.state.openAreas[key];
    }

    async openPending(item) {
        await this.action.doAction(item.action, { onClose: () => this.load() });
    }

    // ------------------------------------------------------------------
    // Formato (tabla de planes sin el puente de ventas)
    // ------------------------------------------------------------------
    money(value) {
        if (value === false || value === undefined) {
            return "—";
        }
        return formatFloat(value, { digits: [16, 2] });
    }

    pct(value) {
        if (value === false || value === undefined) {
            return "—";
        }
        return `${formatFloat(value * 100, { digits: [16, 1] })} %`;
    }

    badge(state) {
        return STATE_BADGES[state] || "text-bg-light";
    }
}

registry.category("actions").add("al_construction_planner.home", ConstructionPlannerHome);
