/**
 * Control semanal de instalación (paquete 1.19, M119-05): un tablero por obra,
 * centrado en los pisos. Período arriba (una o varias semanas), etapas que se
 * prenden y apagan, cuatro indicadores, el edificio piso por piso y, al hacer
 * clic, la radiografía del piso o de la celda a la derecha.
 *
 * Correcciones del tablero (11-nov-2026): la disposición y los textos del
 * prototipo aprobado (CT-07 a CT-14).
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useSetupAction } from "@web/search/action_hook";

const STATUS_LABELS = {
    done: _t("Terminado"),
    late: _t("Atrasado"),
    current: _t("En curso"),
    pending: _t("Pendiente"),
    no_order: _t("Sin orden"),
};
const number = (value, digits = 0) =>
    Number(value || 0).toLocaleString("en-US", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
    });
const plural = (count, one, many) => (count === 1 ? one : many);

export class InstallationBoard extends Component {
    static template = "al_construction_attendance.InstallationBoard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        const params = this.props.action?.params || {};
        // Al volver por la ruta (por ejemplo, desde el control semanal), el
        // tablero sigue en la obra, el período, las etapas y lo elegido.
        const saved = this.props.state || {};
        // CT-07: desde la obra, la ruta lleva de vuelta a ella; desde el menú
        // Ejecución, la lista de obras.
        this.fromProject = Boolean(params.project_id);
        this.state = useState({
            projects: [],
            projectId: saved.projectId || params.project_id || false,
            weekFrom: saved.weekFrom ?? null,
            weekTo: saved.weekTo ?? null,
            production: saved.production ?? false,
            installation: saved.installation ?? true,
            data: null,
            // Lo elegido antes de salir: ``reselect`` lo busca en los datos.
            selection: saved.selection || null,
            loading: false,
        });
        useSetupAction({
            getLocalState: () => {
                const selection = this.state.selection;
                return {
                    projectId: this.state.projectId,
                    weekFrom: this.state.weekFrom,
                    weekTo: this.state.weekTo,
                    production: this.state.production,
                    installation: this.state.installation,
                    selection: selection && {
                        kind: selection.kind,
                        floor: { id: selection.floor.id },
                        cell: selection.cell ? { stage: selection.cell.stage } : null,
                    },
                };
            },
        });
        onWillStart(async () => {
            if (!this.fromProject) {
                this.state.projects = await this.orm.call(
                    "construction.installation.board",
                    "get_projects",
                    []
                );
                if (!this.state.projectId && this.state.projects.length === 1) {
                    this.state.projectId = this.state.projects[0].id;
                }
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
        this.reselect();
        this.state.loading = false;
    }

    /** Lo elegido sigue elegido al cambiar el período o las etapas. */
    reselect() {
        const old = this.state.selection;
        this.state.selection = null;
        if (!old || !this.state.data || this.state.data.empty) {
            return;
        }
        const floor = this.state.data.floors.find((f) => f.id === old.floor.id);
        if (!floor) {
            return;
        }
        if (old.kind === "floor") {
            this.state.selection = { kind: "floor", floor };
            return;
        }
        const cell = floor.cells.find((c) => c.stage === old.cell.stage);
        this.state.selection = cell ? { kind: "cell", floor, cell } : { kind: "floor", floor };
    }

    // Cabecera y período ------------------------------------------------------
    async onProject(ev) {
        this.state.projectId = parseInt(ev.target.value) || false;
        this.state.weekFrom = this.state.weekTo = null;
        this.state.selection = null;
        await this.load();
    }
    openProject() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "project.project",
            res_id: this.state.data.project_id,
            views: [[false, "form"]],
        });
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
        this.state.weekTo = closed;
        this.state.weekFrom = kind === "one" ? closed : kind === "four" ? Math.max(1, closed - 3) : 1;
        await this.load();
    }
    /** CT-08: el atajo que corresponde al período queda marcado. */
    shortcutActive(kind) {
        const { weekFrom: from, weekTo: to } = this.state;
        const closed = this.state.data.closed_week;
        if (kind === "one") {
            return from === to;
        }
        if (kind === "four") {
            return to - from === 3;
        }
        return from === 1 && to >= closed && to - from !== 3 && from !== to;
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
    weekOption(week) {
        return `S${week.number} · ${week.monday}` + (week.state === "current" ? _t(" (en curso)") : "");
    }
    periodState() {
        const closed = this.state.data.current_week - 1;
        if (this.state.weekTo <= closed) {
            return this.state.weekFrom === this.state.weekTo ? _t("Cerrada") : _t("Cerradas");
        }
        if (this.state.weekFrom > closed) {
            return _t("Sin avances validados: solo programa");
        }
        return _t("Hasta la semana %s cerrada; el resto, solo programa", closed);
    }

    // Indicadores (CT-09, CT-14) ---------------------------------------------
    kpiPeriod() {
        const { weekFrom: from, weekTo: to } = this.state;
        const closed = this.state.data.closed_week;
        const period = this.state.data.indicators.period;
        const single = from === to;
        const label = single ? _t("Pisos de la semana") : _t("Pisos del período");
        if (from > closed) {
            return {
                label,
                value: "—",
                note: _t("Período sin avances validados todavía."),
                tone: "o_cib_tone_muted",
            };
        }
        let note = single
            ? _t("Terminados de los programados para la semana.")
            : _t("Terminados de los programados en las %s semanas.", to - from + 1);
        if (to > closed) {
            note += _t(" Incluye semanas sin cerrar.");
        }
        return {
            label,
            value: _t("%(done)s de %(total)s", { done: period.done, total: period.total }),
            note,
            tone: period.done < period.total ? "o_cib_tone_bad" : "o_cib_tone_ok",
        };
    }
    lateText() {
        const items = this.state.data.indicators.late.items;
        if (!items.length) {
            return _t("Ningún piso atrasado.");
        }
        return items.map((item) => `${item.floor} · ${item.number} (${item.pct} %)`).join(", ");
    }
    finishedText() {
        const parts = this.state.data.indicators.finished.per_stage.map(
            (item) => `${item.number}: ${item.done}/${item.total}`
        );
        return parts.join(" · ") + _t(" (programados a la fecha)");
    }
    labor() {
        const labor = this.state.data.indicators.labor;
        const amounts = this.state.data.show_amounts;
        const label = amounts ? _t("Mano de obra: soles") : _t("Mano de obra: persona-días");
        if (labor.empty) {
            return {
                label,
                value: "—",
                note: _t("Sin presupuesto de mano de obra en el período."),
                tone: "o_cib_tone_muted",
            };
        }
        const sign = labor.deviation > 0 ? "+" : "";
        const tone =
            labor.deviation <= 0
                ? "o_cib_tone_ok"
                : labor.deviation <= (labor.band || 0)
                  ? "o_cib_tone_warn"
                  : "o_cib_tone_bad";
        const currency = this.state.data.currency;
        const note =
            labor.unit === "amount"
                ? _t("%(cur)s %(real)s reales frente a %(cur)s %(base)s del presupuesto del avance, en el período.", {
                      cur: currency,
                      real: number(labor.real),
                      base: number(labor.base),
                  })
                : _t("%(real)s reales frente a %(base)s del presupuesto del avance, en el período. Los soles requieren «Ve montos».", {
                      real: number(labor.real, 1),
                      base: number(labor.base, 1),
                  });
        return {
            label,
            value: `${sign}${number(labor.deviation, 1)} %`,
            note: note + _t(" Solo etapa de instalación."),
            tone,
        };
    }
    /** CT-14: el control semanal de mano de obra de la obra, en el período. */
    async openControl() {
        const data = this.state.data;
        const action = await this.orm.call("construction.installation.board", "action_labor_control", [
            data.project_id,
            data.period_start,
            data.period_last_monday,
        ]);
        await this.action.doAction(action);
    }

    // Edificio (CT-10) --------------------------------------------------------
    statusLabel(status) {
        return STATUS_LABELS[status] || status;
    }
    cellMain(cell) {
        if (cell.status === "done") {
            return _t("Terminado");
        }
        if (cell.status === "late") {
            return `${cell.pct} %`;
        }
        if (cell.status === "current") {
            return cell.pct ? `${cell.pct} %` : _t("En curso");
        }
        if (cell.status === "no_order") {
            return _t("Sin orden");
        }
        return cell.sched_week ? `S${cell.sched_week}` : "—";
    }
    cellNote(cell) {
        if (cell.status === "done") {
            return `S${cell.finish_week}` + (cell.delay_weeks ? _t(" · +%s sem.", cell.delay_weeks) : "");
        }
        if (cell.status === "late") {
            return _t("debía S%s", cell.sched_week);
        }
        if (cell.status === "current") {
            return `S${cell.sched_week}`;
        }
        return "";
    }
    barWidth(cell) {
        if (cell.status === "done") {
            return 100;
        }
        return cell.status === "pending" || cell.status === "no_order" ? 0 : cell.pct || 0;
    }
    inPeriod(cell) {
        return (
            cell.sched_week &&
            cell.sched_week >= this.state.weekFrom &&
            cell.sched_week <= this.state.weekTo
        );
    }
    isFloorSelected(floor) {
        const selection = this.state.selection;
        return Boolean(selection && selection.kind === "floor" && selection.floor.id === floor.id);
    }
    isCellSelected(cell) {
        const selection = this.state.selection;
        return Boolean(
            selection &&
                selection.kind === "cell" &&
                selection.cell.floor_id === cell.floor_id &&
                selection.cell.stage === cell.stage
        );
    }
    selectCell(floor, cell) {
        this.state.selection = { kind: "cell", floor, cell };
    }
    selectFloor(floor) {
        this.state.selection = { kind: "floor", floor };
    }

    // Radiografía de una celda (CT-12) ---------------------------------------
    closeHint() {
        const { weekFrom: from, weekTo: to } = this.state;
        return from === to
            ? _t("Estado al cierre de la semana %s.", to)
            : _t("Estado al cierre de la semana %(to)s (período %(from)s a %(to)s).", { from, to });
    }
    plazo(cell) {
        if (cell.status === "done") {
            return cell.delay_weeks
                ? {
                      light: "amber",
                      value: _t("Terminado S%s", cell.finish_week),
                      note: _t("+%(d)s sem. sobre S%(w)s", { d: cell.delay_weeks, w: cell.sched_week }),
                  }
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
        const currency = this.state.data.currency;
        if (!budget.state || budget.state === "none") {
            let note = _t("Sin presupuesto");
            if (budget.floor_amount !== undefined) {
                note = _t("%(cur)s %(amount)s presupuestado", {
                    cur: currency,
                    amount: number(budget.floor_amount),
                });
            } else if (budget.floor_pd) {
                note = _t("%s p-días presupuestados", number(budget.floor_pd, 1));
            }
            return { light: "gray", value: _t("Sin ejecución"), note };
        }
        const values = { inside: _t("Dentro"), band: _t("En la banda"), outside: _t("Fuera") };
        const lights = { inside: "green", band: "amber", outside: "red" };
        const sign = budget.deviation > 0 ? "+" : "";
        let note = `${sign}${number(budget.deviation, 1)} %` + _t(" sobre el avance");
        if (budget.unit === "person_days") {
            note = _t("Persona-días ") + note + _t("; se paga por avance");
        }
        return { light: lights[budget.state], value: values[budget.state], note };
    }
    alcance(cell) {
        const total = cell.spaces.length;
        const light =
            cell.status === "done" ? "green" : cell.status === "late" ? "red" : cell.spaces_done ? "blue" : "gray";
        const digits = Number.isInteger(cell.planned) ? 0 : 2;
        return {
            light,
            value: _t("%(done)s de %(total)s cocinas", { done: cell.spaces_done, total }),
            note: `${number(cell.done, digits)} de ${number(cell.planned, digits)} ${cell.unit || ""}`.trim(),
        };
    }
    previousText(cell) {
        const prev = cell.previous;
        if (!prev) {
            return "—";
        }
        if (prev.status === "done") {
            return (
                _t("%(stage)s: terminado S%(week)s", { stage: prev.stage_label, week: prev.finish_week }) +
                (prev.delay_weeks ? _t(" (+%s sem.)", prev.delay_weeks) : "")
            );
        }
        return (
            `${prev.stage_label}: ${this.statusLabel(prev.status).toLowerCase()}` +
            (prev.pct ? ` ${prev.pct} %` : "")
        );
    }
    facts(cell) {
        const budget = cell.budget || {};
        const currency = this.state.data.currency;
        const facts = [
            { k: _t("Ejecuta"), v: cell.executor },
            {
                k: _t("Programado"),
                v: cell.sched_week ? _t("Semana %(w)s (%(d)s)", { w: cell.sched_week, d: cell.sched_dates }) : "—",
            },
            { k: _t("Terminado"), v: cell.finish_week ? _t("Semana %s", cell.finish_week) : "—" },
            {
                k: _t("Avance"),
                v:
                    cell.status === "no_order"
                        ? _t("Sin orden de fabricación")
                        : cell.status === "done"
                          ? "100 %"
                          : `${cell.pct} %`,
            },
            { k: _t("Etapa anterior"), v: this.previousText(cell) },
        ];
        if (budget.floor_amount !== undefined) {
            facts.push(
                { k: _t("Presupuesto"), v: `${currency} ${number(budget.floor_amount)} (${budget.basis})` },
                {
                    k: _t("Del avance / real"),
                    v: `${currency} ${number(budget.advance_amount)} / ${currency} ${number(budget.real_amount)}`,
                }
            );
        }
        if (budget.floor_pd !== undefined) {
            facts.push({
                k: _t("Persona-días"),
                v: _t("%(real)s reales / %(advance)s del avance", {
                    real: number(budget.real_pd, 1),
                    advance: number(budget.advance_pd, 1),
                }),
            });
        }
        return facts;
    }
    formatQty(qty) {
        return Number.isInteger(qty) ? String(qty) : number(qty, 2);
    }
    /** «✓ Hecho», «Falta» (la semana programada ya pasó) o «Pendiente». */
    spaceState(cell, space) {
        if (space.state === "done") {
            return { kind: "done", text: _t("✓ Hecho") };
        }
        return cell.status === "late"
            ? { kind: "missing", text: _t("Falta") }
            : { kind: "pending", text: _t("Pendiente") };
    }
    missing(cell) {
        return cell.spaces.filter((space) => space.state !== "done");
    }
    cellMissing(cell) {
        const missing = this.missing(cell);
        if (!missing.length) {
            return _t("Nada: el piso está completo en esta sub etapa.");
        }
        const names = missing.map((space) => space.apartment).join(", ");
        return `${missing.length} ${plural(missing.length, _t("cocina"), _t("cocinas"))} (${names}).`;
    }
    openProduction(production) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "mrp.production",
            res_id: production.id,
            views: [[false, "form"]],
        });
    }
    async openProgress(cell) {
        const action = await this.orm.call("construction.installation.board", "action_cell_progress", [
            this.state.data.project_id,
            cell.line_ids,
            _t("Avances de %(stage)s en el %(floor)s", { stage: cell.stage_label, floor: cell.floor }),
        ]);
        await this.action.doAction(action);
    }
    async openAttendance(cell) {
        const data = this.state.data;
        const action = await this.orm.call("construction.installation.board", "action_cell_attendance", [
            data.project_id,
            cell.partner_ids,
            cell.stage,
            data.period_start,
            data.period_end,
            _t("Marcaciones de %s en el período", cell.stage_label),
        ]);
        await this.action.doAction(action);
    }

    // Radiografía de un piso (CT-13, CT-01) ------------------------------------
    worstStatus(floor) {
        const statuses = floor.cells.map((cell) => cell.status);
        if (statuses.includes("late")) {
            return "late";
        }
        if (statuses.length && statuses.every((status) => status === "done")) {
            return "done";
        }
        if (statuses.some((status) => status === "done" || status === "current")) {
            return "current";
        }
        return "pending";
    }
    floorTitle(floor) {
        // CT-05: el nombre del nivel tal como está en el árbol («Piso 05»).
        let title = `${floor.name} · ${floor.spaces} ${plural(floor.spaces, _t("cocina"), _t("cocinas"))}`;
        if (floor.qty) {
            title += ` · ${number(floor.qty, 2)} ${floor.unit}`;
        }
        return title;
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
                const row = rows.get(space.id);
                row.marks[cell.stage] = space.state;
                // La cantidad, en la medida del piso (la de instalación).
                if (cell.unit === floor.unit) {
                    row.qty = space.qty;
                }
            }
        }
        const sorted = [...rows.values()].sort((a, b) =>
            String(a.apartment).localeCompare(String(b.apartment), undefined, { numeric: true })
        );
        const columns = floor.cells.map((cell) => ({
            cell,
            label: cell.stage_number,
            done: sorted.filter((row) => row.marks[cell.stage] === "done").length,
        }));
        return { rows: sorted, columns, total: sorted.length };
    }
    /**
     * CT-01: ✓ hecho, ◐ en curso, · pendiente. (No se llama «mark»: la
     * plantilla usaba ese nombre para la franja del período en las curvas.)
     */
    unitMark(state) {
        return state === "done" ? "✓" : state === "partial" ? "◐" : "·";
    }
    markKind(cell, state) {
        if (state === "done" || state === "partial") {
            return state;
        }
        return cell.status === "late" ? "late" : "pending";
    }
    floorMissing(floor) {
        const parts = [];
        for (const cell of floor.cells) {
            const missing = this.missing(cell).length;
            if (cell.status === "done") {
                continue;
            }
            if (cell.status === "pending") {
                parts.push(
                    _t("%(stage)s programada S%(week)s", {
                        stage: cell.stage_number,
                        week: cell.sched_week || "—",
                    })
                );
            } else if (cell.status === "no_order") {
                parts.push(_t("%s sin orden", cell.stage_number));
            } else if (missing) {
                parts.push(
                    `${cell.stage_number} ${missing} ${plural(missing, _t("cocina"), _t("cocinas"))}` +
                        (cell.status === "late" ? _t(", atrasada") : "")
                );
            }
        }
        return parts.length
            ? parts.join(" · ") + "."
            : _t("Nada: el piso está completo en las etapas visibles.");
    }
    openTree() {
        this.action.doAction("al_construction_planner.action_construction_plan_tree", {
            additionalContext: { construction_plan_id: this.state.data.plan_id },
        });
    }

    // Curvas (CT-11) ----------------------------------------------------------
    curveGeometry(curve) {
        const points = curve.points;
        const count = Math.max(points.length, 2);
        const x = (week) => ((Math.min(Math.max(week, 1), count) - 1) * 300) / (count - 1);
        const total = curve.total || Math.max(1, ...points.map((p) => p.planned));
        const y = (value) => (66 - (value / total) * 62).toFixed(1);
        const plan = points.map((p) => `${x(p.week).toFixed(1)},${y(p.planned)}`).join(" ");
        const real = points
            .filter((p) => p.week <= this.state.weekTo)
            .map((p) => `${x(p.week).toFixed(1)},${y(p.real)}`)
            .join(" ");
        const from = x(this.state.weekFrom);
        const to = x(this.state.weekTo);
        return {
            plan,
            real,
            rangeX: from.toFixed(1),
            rangeW: Math.max(2, to - from).toFixed(1),
            selX: to.toFixed(1),
        };
    }
    curveText(curve, index) {
        const stage = this.state.data.indicators.finished.per_stage[index] || { done: 0, total: 0 };
        return _t("%(done)s de %(total)s a la fecha · %(all)s en total", {
            done: stage.done,
            total: stage.total,
            all: curve.total,
        });
    }
}

registry.category("actions").add("al_construction_installation_board", InstallationBoard);
