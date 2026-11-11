/**
 * Control semanal de instalación (paquete 1.19, M119-05): un tablero por obra,
 * centrado en los pisos. Período arriba (una o varias semanas), etapas que se
 * prenden y apagan, cuatro indicadores, el edificio piso por piso y, al hacer
 * clic, la radiografía del piso o de la celda a la derecha.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const STATUS_LABELS = {
    done: _t("Terminado"),
    late: _t("Atrasado"),
    current: _t("En curso"),
    pending: _t("Pendiente"),
    no_order: _t("Sin orden"),
};

export class InstallationBoard extends Component {
    static template = "al_construction_attendance.InstallationBoard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        const params = this.props.action?.params || {};
        this.state = useState({
            projects: [],
            projectId: params.project_id || false,
            weekFrom: null,
            weekTo: null,
            production: false,
            installation: true,
            data: null,
            selection: null,
            loading: false,
        });
        onWillStart(async () => {
            this.state.projects = await this.orm.call(
                "construction.installation.board",
                "get_projects",
                []
            );
            if (!this.state.projectId && this.state.projects.length === 1) {
                this.state.projectId = this.state.projects[0].id;
            }
            await this.load();
        });
    }

    async load() {
        if (!this.state.projectId) {
            this.state.data = null;
            return;
        }
        this.state.loading = true;
        const data = await this.orm.call("construction.installation.board", "get_data", [
            this.state.projectId,
            this.state.weekFrom,
            this.state.weekTo,
            this.state.production,
            this.state.installation,
        ]);
        this.state.data = data;
        if (!data.empty) {
            this.state.weekFrom = data.week_from;
            this.state.weekTo = data.week_to;
        }
        this.state.selection = null;
        this.state.loading = false;
    }

    // Período ---------------------------------------------------------------
    async onProject(ev) {
        this.state.projectId = parseInt(ev.target.value) || false;
        this.state.weekFrom = this.state.weekTo = null;
        await this.load();
    }
    async onFrom(ev) {
        this.state.weekFrom = parseInt(ev.target.value);
        if (this.state.weekFrom > this.state.weekTo) {
            this.state.weekTo = this.state.weekFrom;
        }
        await this.load();
    }
    async onTo(ev) {
        this.state.weekTo = parseInt(ev.target.value);
        if (this.state.weekFrom > this.state.weekTo) {
            this.state.weekFrom = this.state.weekTo;
        }
        await this.load();
    }
    async shortcut(kind) {
        const closed = this.state.data.closed_week;
        if (kind === "one") {
            this.state.weekFrom = this.state.weekTo = closed;
        } else if (kind === "four") {
            this.state.weekTo = closed;
            this.state.weekFrom = Math.max(1, closed - 3);
        } else {
            this.state.weekTo = closed;
            this.state.weekFrom = 1;
        }
        await this.load();
    }
    async move(step) {
        const last = this.state.data.weeks.length;
        const from = this.state.weekFrom + step;
        const to = this.state.weekTo + step;
        if (from < 1 || to > last) {
            return;
        }
        this.state.weekFrom = from;
        this.state.weekTo = to;
        await this.load();
    }
    async toggle(kind) {
        const other = kind === "production" ? "installation" : "production";
        // Siempre queda una etapa prendida.
        if (this.state[kind] && !this.state[other]) {
            return;
        }
        this.state[kind] = !this.state[kind];
        await this.load();
    }

    // Edificio --------------------------------------------------------------
    statusLabel(status) {
        return STATUS_LABELS[status] || status;
    }
    cellMain(cell) {
        if (cell.status === "done") {
            return _t("Terminado");
        }
        if (cell.status === "late" || (cell.status === "current" && cell.pct)) {
            return `${cell.pct} %`;
        }
        if (cell.status === "current") {
            return _t("En curso");
        }
        if (cell.status === "no_order") {
            return _t("Sin orden");
        }
        return cell.sched_week ? `S${cell.sched_week}` : "—";
    }
    cellNote(cell) {
        if (cell.status === "done") {
            return `S${cell.finish_week}` + (cell.delay_weeks ? ` · +${cell.delay_weeks} sem.` : "");
        }
        if (cell.status === "late") {
            return _t("debía S%s", cell.sched_week);
        }
        if (cell.status === "current") {
            return `S${cell.sched_week}`;
        }
        return "";
    }
    periodState() {
        const data = this.state.data;
        const closed = data.current_week - 1;
        if (this.state.weekTo <= closed) {
            return this.state.weekFrom === this.state.weekTo ? _t("Cerrada") : _t("Cerradas");
        }
        if (this.state.weekFrom > closed) {
            return _t("Sin avances validados: solo programa");
        }
        return _t("Hasta la semana %s cerrada; el resto, solo programa", closed);
    }
    cellText(cell) {
        if (cell.status === "done") {
            return `S${cell.finish_week}` + (cell.delay_weeks ? ` · +${cell.delay_weeks} sem.` : "");
        }
        if (cell.status === "late") {
            return `${cell.pct} % · S${cell.sched_week}`;
        }
        if (cell.status === "current") {
            return `${cell.pct} %`;
        }
        if (cell.status === "no_order") {
            return _t("Sin orden");
        }
        return cell.sched_week ? `S${cell.sched_week}` : "—";
    }
    inPeriod(cell) {
        return (
            cell.sched_week &&
            cell.sched_week >= this.state.weekFrom &&
            cell.sched_week <= this.state.weekTo
        );
    }
    selectCell(floor, cell) {
        this.state.selection = { kind: "cell", floor, cell };
    }
    selectFloor(floor) {
        this.state.selection = { kind: "floor", floor };
    }

    // Radiografía (como el prototipo: valor y nota en cada semáforo) -----------
    plazo(cell) {
        if (cell.status === "done") {
            return cell.delay_weeks
                ? { light: "amber", value: _t("Terminado S%s", cell.finish_week), note: _t("+%s sem. sobre S%s", cell.delay_weeks, cell.sched_week) }
                : { light: "green", value: _t("A tiempo"), note: _t("Terminado S%s", cell.finish_week) };
        }
        if (cell.status === "late") {
            return { light: "red", value: _t("Atrasado"), note: _t("Debía terminar S%s", cell.sched_week) };
        }
        if (cell.status === "current") {
            return { light: "blue", value: _t("En curso"), note: _t("Programado S%s", cell.sched_week) };
        }
        if (cell.status === "no_order") {
            return { light: "gray", value: _t("Sin orden"), note: _t("No cuenta como atrasada") };
        }
        return { light: "gray", value: _t("Pendiente"), note: _t("Programado S%s", cell.sched_week || "—") };
    }
    presupuesto(cell) {
        const budget = cell.budget || {};
        const values = { inside: _t("Dentro"), band: _t("En la banda"), outside: _t("Fuera") };
        const lights = { inside: "green", band: "amber", outside: "red" };
        if (!budget.state || budget.state === "none") {
            return { light: "gray", value: _t("Sin ejecución"), note: _t("Sin presupuesto del avance") };
        }
        const sign = budget.deviation > 0 ? "+" : "";
        const note =
            budget.unit === "amount"
                ? _t("%s%s % sobre el avance", sign, budget.deviation)
                : _t("Persona-días %s%s % sobre el avance", sign, budget.deviation);
        return { light: lights[budget.state], value: values[budget.state], note };
    }
    alcance(cell) {
        const total = cell.spaces.length;
        const light =
            cell.status === "done" ? "green" : cell.status === "late" ? "red" : cell.spaces_done ? "blue" : "gray";
        return {
            light,
            value: _t("%s de %s cocinas", cell.spaces_done, total),
            note: _t("%s de %s", cell.done, cell.planned),
        };
    }
    weekDates(number) {
        const week = this.state.data.weeks.find((w) => w.number === number);
        return week ? `${week.monday} al ${week.saturday}` : "";
    }
    /** CT-06: la sub etapa anterior del catálogo, visible o no (la envía el servidor). */
    previousText(cell) {
        const prev = cell.previous;
        if (!prev) {
            return "—";
        }
        if (prev.status === "done") {
            return _t("%(stage)s: terminado S%(week)s", { stage: prev.stage_label, week: prev.finish_week }) +
                (prev.delay_weeks ? _t(" (+%s sem.)", prev.delay_weeks) : "");
        }
        return `${prev.stage_label}: ${this.statusLabel(prev.status).toLowerCase()}` + (prev.pct ? ` ${prev.pct} %` : "");
    }
    floorTitle(floor) {
        const spaces = new Set();
        floor.cells.forEach((cell) => cell.spaces.forEach((space) => spaces.add(space.id)));
        // CT-05: el nombre del nivel tal como está en el árbol («Piso 05»).
        return _t("%(floor)s · %(count)s cocinas", { floor: floor.name, count: spaces.size });
    }
    /**
     * CT-01: departamentos y muebles del piso: una fila por ambiente, una
     * columna por sub etapa visible con su marca, y el pie «Hechos».
     */
    floorTable(floor) {
        const rows = new Map();
        for (const cell of floor.cells) {
            for (const space of cell.spaces) {
                if (!rows.has(space.id)) {
                    rows.set(space.id, {
                        id: space.id,
                        apartment: space.apartment,
                        typology: space.typology,
                        qty: space.qty,
                        marks: {},
                    });
                }
                rows.get(space.id).marks[cell.stage] = space.state;
            }
        }
        const sorted = [...rows.values()].sort((a, b) =>
            String(a.apartment).localeCompare(String(b.apartment), undefined, { numeric: true })
        );
        const columns = floor.cells.map((cell) => ({
            cell,
            label: cell.stage_label.split(" ")[0],
            done: sorted.filter((row) => row.marks[cell.stage] === "done").length,
        }));
        return { rows: sorted, columns, total: sorted.length };
    }
    /**
     * CT-01: ✓ hecho, ◐ en curso, · pendiente. (No se llama «mark»: la plantilla
     * usa ese nombre para la franja del período en las curvas.)
     */
    unitMark(state) {
        return state === "done" ? "✓" : state === "partial" ? "◐" : "·";
    }
    missing(cell) {
        return cell.spaces.filter((space) => space.state !== "done");
    }
    openProgress(cell) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Avances del piso"),
            res_model: "construction.task.progress",
            views: [[false, "list"], [false, "form"]],
            domain: [["plan_line_id", "in", cell.line_ids]],
        });
    }
    openProduction(production) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "mrp.production",
            res_id: production.id,
            views: [[false, "form"]],
        });
    }
    openControl() {
        this.action.doAction("al_construction_attendance.action_construction_labor_weekly_control", {
            additionalContext: {},
            props: {},
        });
    }

    // Curvas ----------------------------------------------------------------
    curvePath(curve, key) {
        const points = curve.points;
        const max = Math.max(1, ...points.map((p) => p.planned));
        const width = 220;
        const height = 70;
        const step = points.length > 1 ? width / (points.length - 1) : width;
        return points
            .map((p, i) => `${i ? "L" : "M"}${(i * step).toFixed(1)},${(height - (p[key] / max) * height).toFixed(1)}`)
            .join(" ");
    }
    curveMark(curve) {
        const points = curve.points;
        const step = points.length > 1 ? 220 / (points.length - 1) : 220;
        return {
            x: ((this.state.weekFrom - 1) * step).toFixed(1),
            width: Math.max(2, (this.state.weekTo - this.state.weekFrom) * step).toFixed(1),
        };
    }
    labor() {
        const labor = this.state.data.indicators.labor;
        if (labor.empty) {
            return { label: _t("Mano de obra"), value: "—", note: _t("Sin presupuesto de mano de obra") };
        }
        const sign = labor.deviation > 0 ? "+" : "";
        const fmt = (n) => Number(n).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 1 });
        return {
            label: labor.unit === "amount" ? _t("Mano de obra: soles") : _t("Mano de obra: persona-días"),
            value: `${sign}${labor.deviation} %`,
            note:
                labor.unit === "amount"
                    ? _t("S/ %s reales frente a S/ %s del presupuesto del avance, en el período. Solo etapa de instalación.", fmt(labor.real), fmt(labor.base))
                    : _t("%s reales frente a %s del presupuesto del avance, en el período. Los soles requieren «Ve montos». Solo etapa de instalación.", fmt(labor.real), fmt(labor.base)),
            light: labor.deviation <= 0 ? "green" : "red",
        };
    }
}

registry.category("actions").add("al_construction_installation_board", InstallationBoard);
