/** @odoo-module **/

/**
 * Cronograma con recursos (P-15).
 *
 * Es el Gantt de proyectos de la suite (`al_project_gantt_backend`) heredado
 * por sus puntos de extensión, sin copiar nada de él:
 *
 * - filas: pisos, departamentos y ambientes con las etapas de cada ambiente
 *   (`construction.space.stage`) como hijas, o las tareas de la obra;
 * - columnas de monto, avance y contrata; barra clara si la etapa no tiene
 *   contrata ni cuadrilla;
 * - casillas en cascada, panel con los recursos de la selección
 *   (`get_selection_summary`, el mismo del árbol) y los botones de los
 *   asistentes W-02 a W-08;
 * - arrastrar una etapa guarda sus fechas (`action_gantt_reschedule`), que
 *   desplaza la necesidad de sus líneas y avisa a Logística;
 * - carga semanal por contrata y etapa debajo del diagrama (la vista de
 *   recursos de dhtmlxGantt es PRO: es una tabla OWL propia).
 *
 * Ids de fila en el modo «Etapas»: `t<id>` para las tareas (de solo lectura:
 * su barra resume sus etapas), `s<id>` para las etapas, para que el editor
 * del Gantt no las confunda con tareas que debe guardar él, y
 * `g<ambiente>_<etapa>` para las etapas padre (v1.8, M18-02): barras resumen
 * de sus sub etapas en el ambiente.
 */
import { useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { formatFloat } from "@web/core/utils/numbers";
import { GanttAction } from "@al_project_gantt_backend/gantt_action";
import { toPlainDate } from "@al_project_gantt_base/js/gantt_adapter";
import { escapeText } from "@al_project_gantt_base/js/gantt_setup";
import {
    stageFilterLabel,
    stageNodeState,
    toggleStageNode,
} from "../stage_filter/stage_filter";

const PLAN = "construction.resource.plan";
const STAGE = "construction.space.stage";

/** Color de la barra si la etapa del catálogo no tiene uno propio. */
const DEFAULT_STAGE_COLOR = "#3d85c6";

export function isStageRow(id) {
    return /^s\d+$/.test(String(id));
}

export function isTaskRow(id) {
    return /^t\d+$/.test(String(id));
}

export function isStageGroupRow(id) {
    return /^g\d+_\d+$/.test(String(id));
}

function rowNumber(id) {
    return Number(String(id).replace(/^[ts]/, ""));
}

/** Date local -> «AAAA-MM-DD». */
export function dateKey(date) {
    const pad = (value) => String(value).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function addDays(date, days) {
    const result = new Date(date.getTime());
    result.setDate(result.getDate() + days);
    return result;
}

/** Monto con los separadores del idioma del usuario. */
export function formatAmount(value) {
    return formatFloat(value || 0, { digits: [16, 2] });
}

/**
 * Filas del modo «Etapas»: las tareas pasan a `t<id>` y cuelgan de ellas las
 * etapas `s<id>`. Las tareas con etapas en su descendencia son de tipo
 * `project`: la librería deriva su barra de las de sus hijas.
 */
export function buildStageRows(ganttData, payload) {
    const tasks = payload.tasks || [];
    const stages = payload.construction_stages || [];
    const info = new Map(tasks.map((task) => [task.id, task.construction || {}]));
    const parentOf = new Map(tasks.map((task) => [task.id, task.parent_id]));
    const covered = new Set();
    for (const stage of stages) {
        let node = stage.space_task_id;
        while (node && !covered.has(node)) {
            covered.add(node);
            node = parentOf.get(node);
        }
    }
    const taskId = (value) => (typeof value === "number" && value ? `t${value}` : value);
    const rows = [];
    for (const row of ganttData.data) {
        if (row.al_is_project || row.al_is_milestone_record) {
            rows.push(row);
            continue;
        }
        const newRow = {
            ...row,
            ...infoFields(info.get(row.id)),
            id: `t${row.id}`,
            parent: taskId(row.parent),
            readonly: true,
            cp_task_id: row.id,
        };
        if (covered.has(row.id)) {
            newRow.type = "project";
            newRow.unscheduled = false;
            delete newRow.start_date;
            delete newRow.end_date;
        }
        rows.push(newRow);
    }
    // Etapas padre: barras resumen bajo el ambiente (o bajo otra etapa padre).
    for (const group of payload.construction_stage_groups || []) {
        rows.push({
            id: group.key,
            text: group.name,
            parent: group.parent_key || `t${group.space_task_id}`,
            type: "project",
            open: true,
            readonly: true,
            unscheduled: false,
            color: (payload.construction?.stage_colors || {})[group.stage] || DEFAULT_STAGE_COLOR,
            cp_stage_group: true,
            cp_stage_key: group.stage,
            cp_group_stages: group.stages,
            cp_space_task_id: group.space_task_id,
            cp_amount: group.amount,
            cp_progress: group.progress,
            cp_partner: "",
            cp_alerts: [],
        });
    }
    for (const stage of stages) {
        const resource = stage.partner_name || stage.role_name || "";
        rows.push({
            id: `s${stage.id}`,
            text: stage.name,
            parent: stage.group_key || `t${stage.space_task_id}`,
            type: "task",
            open: true,
            start_date: toPlainDate(stage.start),
            // dhtmlxGantt toma el fin como exclusivo: el día siguiente a las 0 h.
            end_date: addDays(toPlainDate(stage.end), 1),
            progress: (stage.progress || 0) / 100,
            color: (payload.construction?.stage_colors || {})[stage.stage] || DEFAULT_STAGE_COLOR,
            readonly: !stage.editable,
            al_users: resource,
            cp_stage: true,
            cp_stage_id: stage.id,
            cp_stage_key: stage.stage,
            cp_space_task_id: stage.space_task_id,
            cp_amount: stage.amount,
            cp_progress: stage.progress,
            cp_partner: resource,
            cp_unassigned: stage.unassigned,
            cp_blocked: stage.blocked,
            cp_alerts: stage.alerts || [],
        });
    }
    const links = [
        ...ganttData.links.map((link) => ({
            ...link,
            source: taskId(Number(link.source)),
            target: taskId(Number(link.target)),
        })),
        ...(payload.construction_stage_links || []).map((link) => ({
            id: link.id,
            source: `s${link.source}`,
            target: `s${link.target}`,
            type: "0",
        })),
    ];
    return { ...ganttData, data: rows, links };
}

function infoFields(info) {
    if (!info || !info.level) {
        return {};
    }
    return {
        cp_level: info.level,
        cp_amount: info.amount,
        cp_progress: info.progress,
        cp_partner: info.partners || "",
        cp_unit_state: info.unit_state || "",
        cp_alerts: info.alerts || [],
    };
}

export class ConstructionScheduleAction extends GanttAction {
    setup() {
        super.setup();
        const context = this.props.action?.context || {};
        this.schedule = useState({
            plans: [],
            plansLoaded: false,
            planId: context.construction_plan_id || null,
            rows: "stages",
            stages: [],
            stageTree: [],
            stageLabels: {},
            buttons: [],
            summary: null,
            load: null,
            showPanel: true,
            showLoad: true,
            panelByStage: false,
            terms: { details: _t("Módulos"), show_ml: true },
        });
        this.summaryRequest = 0;
    }

    // ------------------------------------------------------------------
    // Datos
    // ------------------------------------------------------------------
    async loadPlans() {
        const [plans, buttons] = await Promise.all([
            this.orm.searchRead(
                PLAN,
                [["state", "not in", ["cancel", "replaced"]]],
                ["id", "display_name", "project_id", "state"],
                { order: "id desc" }
            ),
            this.orm.call(PLAN, "get_tree_actions", []),
        ]);
        this.schedule.plans = plans;
        this.schedule.buttons = buttons;
        this.schedule.plansLoaded = true;
        const current =
            plans.find((plan) => plan.id === this.schedule.planId) ||
            plans.find((plan) => ["approved", "in_progress"].includes(plan.state)) ||
            plans[0];
        this.selectPlan(current);
    }

    selectPlan(plan) {
        this.schedule.planId = plan ? plan.id : null;
        if (plan) {
            this.orm.call(PLAN, "get_tree_terms", [[plan.id]]).then((terms) => {
                this.schedule.terms = terms;
            });
        }
        // Una obra por cronograma; sin plan, ningún proyecto.
        this.state.selectedIds = plan ? [plan.project_id[0]] : [-1];
        this.state.pinnedToProject = true;
        this.selection?.clear();
        this.schedule.summary = null;
    }

    async fetchData() {
        if (!this.schedule.plansLoaded) {
            await this.loadPlans();
        }
        await super.fetchData();
        await Promise.all([this.loadWeeklyLoad(), this.refreshSummary()]);
    }

    getOptions() {
        return {
            ...super.getOptions(),
            construction_schedule: true,
            construction_plan_id: this.schedule.planId,
            construction_rows: this.schedule.rows,
            construction_stages: this.schedule.stages,
        };
    }

    transformGanttData(ganttData, payload) {
        this.construction = payload.construction || {};
        this.schedule.stageLabels = this.construction.stage_labels || {};
        this.schedule.stageTree = this.construction.stage_tree || [];
        if (this.construction.rows === "stages") {
            return buildStageRows(ganttData, payload);
        }
        const info = new Map((payload.tasks || []).map((task) => [task.id, task.construction]));
        for (const row of ganttData.data) {
            Object.assign(row, infoFields(info.get(row.id)));
        }
        return ganttData;
    }

    async loadWeeklyLoad() {
        if (!this.schedule.planId || !this.schedule.showLoad || !this.showAmounts) {
            this.schedule.load = null;
            return;
        }
        this.schedule.load = await this.orm.call(PLAN, "get_schedule_load", [
            [this.schedule.planId],
            this.schedule.stages,
        ]);
    }

    configSignature() {
        // Las columnas cambian con el modo de filas: hay que rehacer la instancia.
        return JSON.stringify([super.configSignature(), this.schedule.rows]);
    }

    // ------------------------------------------------------------------
    // Diagrama
    // ------------------------------------------------------------------
    get showProjectBar() {
        return false;
    }

    get selectionEnabled() {
        return true;
    }

    get toolbarTemplate() {
        return "al_construction_planner.ScheduleToolbar";
    }

    get sidePanelTemplate() {
        return "al_construction_planner.SchedulePanel";
    }

    get bottomPanelTemplate() {
        return "al_construction_planner.ScheduleLoad";
    }

    /** Sin el grupo de montos (v1.8, M18-10) no hay columnas ni totales en soles. */
    get showAmounts() {
        return this.construction?.show_amounts !== false;
    }

    extraColumns() {
        const columns = [
            {
                name: "cp_amount",
                label: _t("Plan S/"),
                align: "right",
                width: 90,
                resize: true,
                template: (task) =>
                    task.cp_amount === undefined || task.cp_amount === null
                        ? ""
                        : formatAmount(task.cp_amount),
            },
            {
                name: "cp_progress",
                label: _t("Avance"),
                align: "right",
                width: 62,
                resize: true,
                template: (task) =>
                    task.cp_progress === undefined || task.cp_progress === null
                        ? ""
                        : `${task.cp_progress} %`,
            },
            {
                name: "cp_partner",
                label: _t("Contrata"),
                align: "left",
                width: 130,
                resize: true,
                template: (task) => {
                    const alerts = task.cp_alerts || [];
                    const icon = alerts.length
                        ? `<i class="fa fa-exclamation-triangle text-warning me-1" title="${escapeText(alerts.join(" · "))}"></i>`
                        : "";
                    if (task.cp_stage && task.cp_unassigned) {
                        return `${icon}<span class="text-muted">${escapeText(_t("Sin asignar"))}</span>`;
                    }
                    const extra = task.cp_unit_state ? ` · ${task.cp_unit_state}` : "";
                    return icon + escapeText((task.cp_partner || "") + extra);
                },
            },
        ];
        return this.showAmounts ? columns : columns.filter((col) => col.name !== "cp_amount");
    }

    setupGantt() {
        super.setupGantt();
        const gantt = this.gantt;
        if (this.schedule.rows === "stages") {
            // Las filas no son tareas que se editen aquí: fuera «+» y
            // responsables (la contrata va en su propia columna).
            gantt.config.columns = gantt.config.columns.filter(
                (column) => !["add", "al_users", "al_activity"].includes(column.name)
            );
        }
        gantt.config.grid_width = 720;
        if (this.schedule.rows === "stages") {
            // Las etapas son de días enteros y la librería guarda el fin como
            // exclusivo: la columna «Fin» muestra el último día de trabajo.
            const shortDate = gantt.date.date_to_str("%d/%m/%Y");
            const endColumn = gantt.config.columns.find((column) => column.name === "end_date");
            if (endColumn) {
                endColumn.template = (task) =>
                    task.end_date ? shortDate(addDays(task.end_date, -1)) : "";
            }
        }
        const taskClass = gantt.templates.task_class;
        gantt.templates.task_class = (start, end, task) => {
            const classes = [taskClass ? taskClass(start, end, task) : ""];
            if (task.cp_stage) {
                classes.push(`o_cp_stage o_cp_stage_${task.cp_stage_key}`);
                if (task.cp_unassigned) {
                    classes.push("o_cp_stage_unassigned");
                }
                if (task.cp_blocked) {
                    classes.push("o_cp_stage_blocked");
                }
            }
            return classes.join(" ");
        };
        const taskText = gantt.templates.task_text;
        gantt.templates.task_text = (start, end, task) => {
            if (!task.cp_stage) {
                return taskText(start, end, task);
            }
            const parts = [task.cp_partner || (task.cp_unassigned ? _t("Sin asignar") : "")];
            if (task.cp_progress) {
                parts.push(`${task.cp_progress} %`);
            }
            return escapeText(parts.filter(Boolean).join(" · "));
        };
        const tooltip = gantt.templates.tooltip_text;
        gantt.templates.tooltip_text = (start, end, task) => {
            if (!task.cp_stage) {
                return tooltip(start, end, task);
            }
            const format = gantt.date.date_to_str("%d/%m/%Y");
            const lines = [
                `<b>${escapeText(task.text)}</b>`,
                `${_t("Inicio")}: ${format(start)}`,
                `${_t("Fin")}: ${format(addDays(end, -1))}`,
                `${_t("Contrata")}: ${escapeText(task.cp_partner || (task.cp_unassigned ? _t("Sin asignar") : "—"))}`,
                ...(this.showAmounts ? [`${_t("Plan S/")}: ${formatAmount(task.cp_amount)}`] : []),
                `${_t("Avance")}: ${task.cp_progress || 0} %`,
                ...(task.cp_alerts || []).map((alert) => `<b>${escapeText(alert)}</b>`),
            ];
            return lines.join("<br/>");
        };
    }

    editorOptions() {
        return {
            // Solo las barras de las etapas (no su avance, que sale de las líneas).
            canDragRow: (id, mode) =>
                isStageRow(id) && mode !== "progress" && !this.gantt.getTask(id).readonly,
        };
    }

    onGanttReady(gantt) {
        gantt.attachEvent("onAfterTaskUpdate", (id, task) => {
            if (isStageRow(id)) {
                this.saveStage(id, task);
            }
            return true;
        });
        // Doble clic: la ficha de la etapa o de la tarea, no el formulario del
        // diagrama (que guarda tareas).
        gantt.attachEvent("onBeforeLightbox", (id) => {
            if (isStageGroupRow(id)) {
                return false;
            }
            if (isStageRow(id) || isTaskRow(id)) {
                this.openRow(id);
                return false;
            }
            return true;
        });
    }

    async saveStage(id, task) {
        const start = dateKey(task.start_date);
        const end = dateKey(new Date(task.end_date.getTime() - 1));
        this.state.saving = true;
        try {
            const result = await this.orm.call(
                STAGE,
                "action_gantt_reschedule",
                [[rowNumber(id)], start, end],
                { chain: this.state.rescheduleChain }
            );
            const notified = result.notified || [];
            this.notification.add(
                notified.length
                    ? _t(
                          "Etapa movida: %s línea(s) con nueva fecha de necesidad. Aviso a Logística: %s.",
                          result.lines,
                          notified.join(", ")
                      )
                    : _t("Etapa movida: %s línea(s) con nueva fecha de necesidad.", result.lines),
                { type: notified.length ? "warning" : "success" }
            );
            this.state.lastSavedAt = new Date().toLocaleTimeString();
        } catch (error) {
            this.notification.add(
                error?.data?.message || error?.message || _t("No se pudo mover la etapa."),
                { type: "danger" }
            );
        } finally {
            this.state.saving = false;
        }
        await this.reload();
    }

    openRow(id) {
        if (isTaskRow(id)) {
            this.openTaskForm(rowNumber(id));
            return;
        }
        this.action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: STAGE,
                res_id: rowNumber(id),
                views: [[false, "form"]],
                target: "new",
            },
            { onClose: () => this.reload() }
        );
    }

    buildContextActions(taskId, task) {
        if (isStageGroupRow(taskId)) {
            return [];
        }
        if (isStageRow(taskId)) {
            return [
                {
                    label: _t("Abrir etapa"),
                    icon: "fa-external-link",
                    run: () => this.openRow(taskId),
                },
            ];
        }
        if (isTaskRow(taskId)) {
            return [
                {
                    label: _t("Abrir en Odoo"),
                    icon: "fa-external-link",
                    run: () => this.openRow(taskId),
                },
            ];
        }
        return super.buildContextActions(taskId, task);
    }

    // ------------------------------------------------------------------
    // Selección y acciones
    // ------------------------------------------------------------------
    /**
     * La selección en el formato de los asistentes: tareas marcadas (las
     * etapas aportan su ambiente) y etapas. Marcar una tarea entera son todas
     * las etapas, salvo que el filtro de etapa esté puesto.
     */
    selectionPayload() {
        const taskIds = new Set();
        const stages = new Set();
        let allStages = false;
        for (const id of this.selection?.topIds || []) {
            if (isStageGroupRow(id)) {
                // Etapa padre marcada: su ambiente con todas sus sub etapas.
                if (this.gantt?.isTaskExists(id)) {
                    const row = this.gantt.getTask(id);
                    taskIds.add(row.cp_space_task_id);
                    for (const code of row.cp_group_stages || []) {
                        stages.add(code);
                    }
                }
                continue;
            }
            if (isStageRow(id)) {
                if (this.gantt?.isTaskExists(id)) {
                    const row = this.gantt.getTask(id);
                    taskIds.add(row.cp_space_task_id);
                    stages.add(row.cp_stage_key);
                }
                continue;
            }
            const number = isTaskRow(id) ? rowNumber(id) : /^\d+$/.test(id) ? Number(id) : null;
            if (number) {
                taskIds.add(number);
                allStages = true;
            }
        }
        let stageList = [...stages];
        if (this.schedule.stages.length) {
            // El filtro de etapas acota lo marcado (o todas las del filtro si se
            // marcó la tarea entera).
            stageList = stageList.length && !allStages
                ? stageList.filter((code) => this.schedule.stages.includes(code))
                : [...this.schedule.stages];
        } else if (allStages) {
            stageList = [];
        }
        return { taskIds: [...taskIds], stages: stageList };
    }

    onSelectionChange() {
        this.refreshSummary();
    }

    async refreshSummary() {
        const request = ++this.summaryRequest;
        const { taskIds, stages } = this.selectionPayload();
        if (!this.schedule.planId || !taskIds.length) {
            this.schedule.summary = null;
            return;
        }
        const summary = await this.orm.call(PLAN, "get_selection_summary", [
            [this.schedule.planId],
            taskIds.map(String),
            stages.length ? { stages } : {},
        ]);
        if (request === this.summaryRequest) {
            this.schedule.summary = summary.empty ? null : summary;
        }
    }

    get extraToolbarButtons() {
        const disabled = !this.schedule.planId || !this.state.selectionCount;
        const matrix = {
            key: "io_matrix",
            label: _t("Insumo-producto"),
            icon: "fa-table",
            disabled: !this.schedule.planId,
            title: _t("Recursos de la selección (o de la obra) como tabla insumo-producto"),
            run: () => this.openIoMatrix(),
        };
        return [matrix, ...this.schedule.buttons.map((button) => ({
            key: button.xmlid,
            label: button.name,
            icon: button.icon,
            disabled,
            title: disabled ? _t("Marque filas para abrir el asistente con ellas") : button.name,
            run: () => this.runPlanAction(button.xmlid),
        }))];
    }

    /** Matriz insumo-producto (M18-04) con la selección y el filtro de etapas. */
    async openIoMatrix() {
        const { taskIds, stages } = this.selectionPayload();
        await this.action.doAction({
            type: "ir.actions.client",
            tag: "al_construction_planner.io_matrix",
            name: _t("Insumo-producto"),
            context: {
                construction_plan_id: this.schedule.planId,
                construction_selection_keys: taskIds.length ? taskIds.map(String) : ["p"],
                construction_filters: { stages: stages.length ? stages : this.schedule.stages },
            },
        });
    }

    togglePanelByStage() {
        this.schedule.panelByStage = !this.schedule.panelByStage;
    }

    async runPlanAction(xmlid) {
        const { taskIds, stages } = this.selectionPayload();
        await this.action.doAction(xmlid, {
            additionalContext: {
                active_model: PLAN,
                active_id: this.schedule.planId,
                default_plan_id: this.schedule.planId,
                construction_selection_keys: taskIds.map(String),
                construction_selection_task_ids: taskIds,
                construction_selection_project: false,
                construction_selection_stages: stages,
            },
            onClose: () => this.reload(),
        });
    }

    // ------------------------------------------------------------------
    // Barra propia
    // ------------------------------------------------------------------
    get stageFilterLabel() {
        return stageFilterLabel(this.schedule.stageTree, this.schedule.stages, _t("Todas las etapas"));
    }

    stageState(node) {
        return stageNodeState(node, this.schedule.stages);
    }

    async onPlanChange(event) {
        const plan = this.schedule.plans.find((item) => item.id === Number(event.target.value));
        this.selectPlan(plan);
        await this.reload();
    }

    async onRowsChange(rows) {
        if (rows === this.schedule.rows) {
            return;
        }
        this.schedule.rows = rows;
        this.selection?.clear();
        await this.reload();
    }

    /** Filtro de etapas en árbol: la etapa padre marca o desmarca sus sub etapas. */
    async toggleStage(node) {
        this.schedule.stages = toggleStageNode(node, this.schedule.stages);
        await this.reload();
    }

    async clearStages() {
        this.schedule.stages = [];
        await this.reload();
    }

    togglePanel() {
        this.schedule.showPanel = !this.schedule.showPanel;
    }

    async toggleLoad() {
        this.schedule.showLoad = !this.schedule.showLoad;
        await this.loadWeeklyLoad();
    }

    // ------------------------------------------------------------------
    // Formato
    // ------------------------------------------------------------------
    fmt(value) {
        return formatAmount(value);
    }

    pct(value) {
        return `${Math.round((value || 0) * 1000) / 10} %`;
    }

    resourceProgress(resource) {
        if (!["contract", "labor"].includes(resource.resource_type) || !resource.qty) {
            return "—";
        }
        return this.pct(resource.executed / resource.qty);
    }

    weekLabel(isoDate) {
        const [year, month, day] = isoDate.split("-");
        return `${day}/${month}`;
    }
}

registry.category("actions").add("al_construction_planner.schedule", ConstructionScheduleAction);
