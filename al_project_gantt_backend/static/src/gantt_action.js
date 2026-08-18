/** @odoo-module **/

/**
 * Client action del Gantt de proyectos (interfaz de backend).
 *
 * Monta dhtmlxGantt en un contenedor propio; no hereda `web_gantt` ni ningún
 * tipo de vista de Odoo. Los datos vienen siempre del módulo base a través de
 * `project.project.get_gantt_data()`.
 */
import { Component, onMounted, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";
import { loadCSS, loadJS } from "@web/core/assets";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { GANTT_LIB, toDhtmlxData } from "@al_project_gantt_base/js/gantt_adapter";
import {
    enableBaselineBars,
    applyZoom,
    configureGantt,
    parseGanttData,
    ZOOM_LEVELS,
} from "@al_project_gantt_base/js/gantt_setup";
import { enableEditing } from "@al_project_gantt_base/js/gantt_editing";
import { configureLightbox } from "@al_project_gantt_base/js/gantt_lightbox";
import {
    addTodayMarker,
    applySearch,
    applyWorkingCalendar,
    attachContextMenu,
    indentTask,
    outdentTask,
    toggleAllBranches,
    toggleFullscreen,
} from "@al_project_gantt_base/js/gantt_tools";
import {
    countActiveFilters,
    emptyFilters,
    filtersToOptions,
    isInvalidRange,
    selectedValues,
} from "@al_project_gantt_base/js/gantt_filters";

export class GanttAction extends Component {
    static template = "al_project_gantt_backend.GanttAction";
    static components = { Layout };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.containerRef = useRef("ganttContainer");
        this.gantt = null;
        // El botón inteligente del formulario de proyecto abre esta acción con
        // el proyecto ya acotado (`action_open_gantt`).
        const contextProjectIds = this.props.action?.context?.gantt_project_ids || [];

        this.state = useState({
            loading: true,
            error: null,
            projects: [],
            selectedIds: [...contextProjectIds],
            pinnedToProject: contextProjectIds.length > 0,
            zoom: "week",
            meta: {},
            undated: [],
            taskCount: 0,
            // Filtros: `filters` es lo que se ha aplicado, `draft` lo que el
            // usuario está editando en el panel (se envía al pulsar Aplicar).
            showFilters: false,
            filters: emptyFilters(),
            draft: emptyFilters(),
            options: { states: [], users: [] },
            // Funciones «pro»
            criticalPath: false,
            rescheduleChain: true,
            baselineId: null,
            baselines: [],
            criticalSummary: { computed: false },
            // Herramientas de vista
            search: "",
            searchMatches: null,
            showWbs: false,
            hideDone: false,
            fullscreen: false,
            expanded: true,
            saving: false,
            lastSavedAt: null,
        });

        onWillStart(async () => {
            await this.loadLibrary();
            await this.fetchData();
        });
        onMounted(() => this.mountGantt());
        onWillUnmount(() => this.destroyGantt());
    }

    get display() {
        return { controlPanel: {} };
    }

    get zoomLevels() {
        return Object.entries(ZOOM_LEVELS).map(([key, level]) => ({ key, label: level.label }));
    }

    get hasTasks() {
        return this.state.taskCount > 0;
    }

    /** Carga perezosa: la librería solo se descarga al abrir esta acción. */
    async loadLibrary() {
        await Promise.all([loadJS(GANTT_LIB.js), loadCSS(GANTT_LIB.css)]);
    }

    async fetchData() {
        this.state.loading = true;
        try {
            // Los errores (p. ej. AccessError) suben al gestor de errores de
            // Odoo, que ya muestra el diálogo estándar: no se silencian aquí.
            const payload = await this.orm.call("project.project", "get_gantt_data", [
                this.state.selectedIds.length ? this.state.selectedIds : null,
                this.getOptions(),
            ]);
            this.applyPayload(payload);
        } finally {
            this.state.loading = false;
        }
    }

    /** Filtros y extras «pro», en el formato del contrato de datos. */
    getOptions() {
        const options = filtersToOptions(this.state.filters);
        if (this.state.criticalPath) {
            options.critical_path = true;
        }
        if (this.state.baselineId) {
            options.baseline_id = this.state.baselineId;
        }
        return options;
    }

    applyPayload(payload) {
        this.state.projects = payload.projects || [];
        if (!this.state.selectedIds.length) {
            this.state.selectedIds = this.state.projects.map((project) => project.id);
        }
        this.state.meta = payload.meta || {};
        this.state.taskCount = (payload.tasks || []).length;
        // Los valores de los desplegables los decide el servidor: ni estados ni
        // responsables se hardcodean en la interfaz.
        this.state.options = payload.filters || { states: [], users: [] };
        this.state.baselines = payload.baselines || [];
        this.calendar = payload.calendar || null;
        this.state.criticalSummary = this.state.meta.critical_path || { computed: false };
        this.ganttData = toDhtmlxData(payload);
        this.state.undated = this.ganttData.undated;
    }

    // ------------------------------------------------------------------
    // Filtros
    // ------------------------------------------------------------------
    get activeFilterCount() {
        return countActiveFilters(this.state.filters);
    }

    /**
     * Opciones ya marcadas para los `<select multiple>`.
     *
     * La comparación se hace aquí y no en la plantilla porque las expresiones
     * QWeb-OWL no tienen acceso a los globales de JavaScript (`String`, etc.).
     */
    get userOptions() {
        return (this.state.options.users || []).map((user) => ({
            ...user,
            selected: this.state.draft.userIds.includes(String(user.id)),
        }));
    }

    get stateOptions() {
        return (this.state.options.states || []).map((state) => ({
            ...state,
            selected: this.state.draft.states.includes(state.value),
        }));
    }

    get invalidRange() {
        return isInvalidRange(this.state.draft);
    }

    toggleFilters() {
        this.state.showFilters = !this.state.showFilters;
        if (this.state.showFilters) {
            // El panel siempre se abre mostrando lo que está aplicado.
            this.state.draft = { ...this.state.filters };
        }
    }

    onDraftSelectChange(field, event) {
        this.state.draft[field] = selectedValues(event.target);
    }

    onDraftValueChange(field, event) {
        const target = event.target;
        this.state.draft[field] = target.type === "checkbox" ? target.checked : target.value;
    }

    async applyFilters() {
        if (this.invalidRange) {
            this.notification.add(
                _t("La fecha «desde» no puede ser posterior a la fecha «hasta»."),
                { type: "warning" }
            );
            return;
        }
        this.state.filters = { ...this.state.draft };
        await this.reload();
    }

    async clearFilters() {
        this.state.draft = emptyFilters();
        this.state.filters = emptyFilters();
        await this.reload();
    }

    // ------------------------------------------------------------------
    // Librería
    // ------------------------------------------------------------------
    mountGantt() {
        if (!this.containerRef.el || !window.Gantt) {
            return;
        }
        // Instancia propia: no se comparte estado con otras vistas ni con la
        // interfaz de website si ambas están instaladas.
        this.gantt = window.Gantt.getGanttInstance();
        this.setupGantt();
        this.gantt.init(this.containerRef.el);
        this.parseData();
        addTodayMarker(this.gantt);
        this.detachContextMenu = attachContextMenu(
            this.gantt, this.containerRef.el, (taskId, task) => this.buildContextActions(taskId, task)
        );
        if (this.state.search) {
            this.state.searchMatches = applySearch(this.gantt, this.state.search);
        }

        // El contenedor cambia de alto al plegar avisos o al redimensionar la
        // ventana; sin esto la librería conserva el tamaño del primer render.
        this.resizeObserver = new ResizeObserver(() => this.gantt?.setSizes());
        this.resizeObserver.observe(this.containerRef.el);
    }

    setupGantt() {
        // Toda la configuración de la librería es común a las dos interfaces y
        // vive en el módulo base.
        configureGantt(this.gantt, {
            lang: user.lang,
            zoom: this.state.zoom,
            readonly: !this.state.meta.editable,
            showCritical: this.state.criticalPath,
            showBaseline: Boolean(this.state.baselineId),
            showWbs: this.state.showWbs,
        });
        applyWorkingCalendar(this.gantt, this.calendar);
        // Formulario de tarea con los campos reales de project.task.
        configureLightbox(this.gantt, {
            filters: this.state.options,
            canEditProgress: Boolean(this.state.meta.can_edit_progress),
            // Salida a la ficha completa desde el propio formulario, además de
            // la que ya ofrece el menú contextual.
            openRecord: (taskId) => this.openTaskForm(taskId),
        });
        if (this.state.baselineId) {
            enableBaselineBars(this.gantt);
        }
        if (this.state.meta.editable) {
            this.editor = enableEditing(this.gantt, {
                timeZone: this.state.meta.tz,
                save: (changeset) => this.saveChanges(changeset),
                onSaved: () => {
                    this.state.lastSavedAt = new Date().toLocaleTimeString();
                },
                onError: (error) => this.onSaveError(error),
                defaultProjectId: () => this.state.selectedIds[0] || null,
                rescheduleChain: () => this.state.rescheduleChain,
            });
        }
    }

    // ------------------------------------------------------------------
    // Escritura
    // ------------------------------------------------------------------
    async saveChanges(changeset) {
        this.state.saving = true;
        try {
            return await this.orm.call("project.project", "apply_gantt_changes", [changeset]);
        } finally {
            this.state.saving = false;
        }
    }

    /**
     * Si el servidor rechaza un cambio, el diagrama no puede quedarse
     * mostrando algo que no está guardado: se avisa y se recarga.
     */
    async onSaveError(error) {
        const message = error?.data?.message || error?.message || _t("No se pudo guardar el cambio.");
        this.notification.add(message, { type: "danger", sticky: false });
        await this.reload();
    }

    parseData() {
        if (this.gantt && this.ganttData) {
            parseGanttData(this.gantt, this.ganttData);
        }
    }

    destroyGantt() {
        if (this.detachContextMenu) {
            this.detachContextMenu();
            this.detachContextMenu = null;
        }
        if (this.editor) {
            this.editor.detach();
            this.editor = null;
        }
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
            this.resizeObserver = null;
        }
        if (this.gantt) {
            this.gantt.clearAll();
            if (typeof this.gantt.destructor === "function") {
                this.gantt.destructor();
            }
            this.gantt = null;
        }
    }

    // ------------------------------------------------------------------
    // Interacción
    // ------------------------------------------------------------------
    onZoomChange(event) {
        this.state.zoom = event.target.value;
        if (this.gantt) {
            applyZoom(this.gantt, this.state.zoom);
        }
    }

    async onProjectToggle(projectId) {
        const selected = new Set(this.state.selectedIds);
        if (selected.has(projectId)) {
            selected.delete(projectId);
        } else {
            selected.add(projectId);
        }
        if (!selected.size) {
            this.notification.add(_t("Seleccione al menos un proyecto."), { type: "warning" });
            return;
        }
        this.state.selectedIds = [...selected];
        await this.reload();
    }

    async onSelectAll() {
        this.state.selectedIds = this.state.projects.map((project) => project.id);
        await this.reload();
    }

    // ------------------------------------------------------------------
    // Funciones «pro»
    // ------------------------------------------------------------------
    get baselineOptions() {
        return (this.state.baselines || []).map((baseline) => ({
            ...baseline,
            selected: String(baseline.id) === String(this.state.baselineId),
        }));
    }

    get criticalLabel() {
        const summary = this.state.criticalSummary;
        return summary.computed ? summary.critical_count : null;
    }

    async onToggleCriticalPath() {
        this.state.criticalPath = !this.state.criticalPath;
        await this.remount();
    }

    onToggleRescheduleChain() {
        this.state.rescheduleChain = !this.state.rescheduleChain;
    }

    async onBaselineChange(event) {
        const value = event.target.value;
        this.state.baselineId = value ? Number(value) : null;
        await this.remount();
    }

    async onCaptureBaseline() {
        if (!this.state.selectedIds.length) {
            this.notification.add(_t("Seleccione un proyecto para capturar la línea base."), {
                type: "warning",
            });
            return;
        }
        const result = await this.orm.call("al.gantt.data", "create_baseline", [
            this.state.selectedIds,
            null,
        ]);
        const created = result.baselines?.[0];
        this.notification.add(
            _t("Línea base capturada con %s tarea(s).", created?.task_count ?? 0),
            { type: "success" }
        );
        this.state.baselineId = created?.id || null;
        await this.remount();
    }

    async onAddTask() {
        const projectId = this.state.selectedIds[0];
        if (!projectId || !this.gantt) {
            return;
        }
        // La tarea se crea en el cliente; el editor la persiste y sustituye el
        // id temporal por el real que devuelve el servidor.
        const start = this.gantt.getState().min_date || new Date();
        this.gantt.createTask({
            text: _t("Tarea nueva"),
            start_date: start,
            duration: 3,
            al_project_id: projectId,
        });
    }

    /**
     * Algunas opciones (ruta crítica, línea base) cambian columnas y capas:
     * es más limpio rehacer la instancia que parchear la configuración viva.
     */
    async remount() {
        await this.fetchData();
        this.destroyGantt();
        this.mountGantt();
    }

    // ------------------------------------------------------------------
    // Herramientas de vista
    // ------------------------------------------------------------------
    get searchLabel() {
        const count = this.state.searchMatches;
        if (count === null || !this.state.search) {
            return "";
        }
        return count === 1 ? _t("1 coincidencia") : _t("%s coincidencias", count);
    }

    onSearchInput(event) {
        this.state.search = event.target.value;
        if (this.gantt) {
            this.state.searchMatches = applySearch(this.gantt, this.state.search);
        }
    }

    clearSearch() {
        this.state.search = "";
        this.state.searchMatches = null;
        if (this.gantt) {
            applySearch(this.gantt, "");
        }
    }

    async onToggleWbs() {
        this.state.showWbs = !this.state.showWbs;
        await this.remount();
    }

    async onToggleHideDone() {
        this.state.hideDone = !this.state.hideDone;
        // «Ocultar terminadas» es un filtro de servidor: así el contador de
        // tareas y el límite siguen siendo coherentes.
        const closed = ["1_done", "1_canceled"];
        const available = (this.state.options.states || []).map((option) => option.value);
        this.state.filters = {
            ...this.state.filters,
            states: this.state.hideDone
                ? available.filter((value) => !closed.includes(value))
                : [],
        };
        await this.reload();
    }

    toggleExpand() {
        this.state.expanded = !this.state.expanded;
        if (this.gantt) {
            toggleAllBranches(this.gantt, this.state.expanded);
        }
    }

    onToggleFullscreen() {
        if (this.gantt) {
            this.state.fullscreen = toggleFullscreen(this.gantt);
        }
    }

    // ------------------------------------------------------------------
    // Exportación
    // ------------------------------------------------------------------
    /** Proyectos y opciones que definen «lo que se está viendo». */
    exportParams() {
        return {
            project_ids: this.state.selectedIds,
            options: { ...this.getOptions(), scale: this.state.zoom },
        };
    }

    onExportXlsx() {
        const { project_ids, options } = this.exportParams();
        // Descarga por URL: el fichero lo arma el servidor, sin pasar por el
        // servicio en la nube de la librería.
        this.action.doAction({
            type: "ir.actions.act_url",
            target: "self",
            url:
                "/al_project_gantt/export/xlsx" +
                `?project_ids=${encodeURIComponent(project_ids.join(","))}` +
                `&options=${encodeURIComponent(JSON.stringify(options))}`,
        });
    }

    onExportPdf() {
        const { project_ids, options } = this.exportParams();
        if (!project_ids.length) {
            this.notification.add(_t("Seleccione al menos un proyecto."), { type: "warning" });
            return;
        }
        this.action.doAction({
            type: "ir.actions.report",
            report_type: "qweb-pdf",
            report_name: "al_project_gantt_base.report_gantt",
            report_file: "al_project_gantt_base.report_gantt",
            context: { active_ids: project_ids, active_model: "project.project" },
            data: { project_ids, options },
        });
    }

    // ------------------------------------------------------------------
    // Menú contextual
    // ------------------------------------------------------------------
    buildContextActions(taskId, task) {
        const isRealTask = !task.al_is_project && !task.al_is_milestone_record;
        const editable = !task.readonly;
        const actions = [];

        if (isRealTask) {
            actions.push({
                label: _t("Abrir en Odoo"),
                icon: "fa-external-link",
                run: () => this.openTaskForm(taskId),
            });
        }
        if (isRealTask) {
            actions.push({
                label: _t("Planificar actividad"),
                icon: "fa-clock-o",
                run: () => this.scheduleActivity(taskId),
            });
        }
        if (isRealTask && editable && this.state.meta.can_create) {
            actions.push({
                label: _t("Añadir subtarea"),
                icon: "fa-level-down",
                run: () => this.addSubtask(taskId, task),
            });
        }
        if (isRealTask && editable) {
            actions.push({
                label: _t("Indentar"),
                icon: "fa-indent",
                disabled: !indentTask(this.gantt, taskId),
                run: () => this.applyStructureChange(indentTask(this.gantt, taskId)),
            });
            actions.push({
                label: _t("Desindentar"),
                icon: "fa-outdent",
                disabled: !outdentTask(this.gantt, taskId),
                run: () => this.applyStructureChange(outdentTask(this.gantt, taskId)),
            });
            actions.push({
                label: _t("Eliminar"),
                icon: "fa-trash",
                run: () => this.gantt.deleteTask(taskId),
            });
        }
        return actions;
    }

    /**
     * Abre el asistente estándar de Odoo para planificar una actividad sobre la
     * tarea. Al cerrarlo se recarga, para que el indicador de la rejilla
     * refleje la actividad recién creada.
     */
    scheduleActivity(taskId) {
        this.action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "mail.activity.schedule",
                views: [[false, "form"]],
                target: "new",
                name: _t("Planificar actividad"),
                context: {
                    active_model: "project.task",
                    active_ids: [Number(taskId)],
                    default_res_model: "project.task",
                },
            },
            { onClose: () => this.reload() }
        );
    }

    openTaskForm(taskId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "project.task",
            res_id: Number(taskId),
            views: [[false, "form"]],
            target: "current",
        });
    }

    addSubtask(parentId, parentTask) {
        this.gantt.createTask(
            {
                text: _t("Tarea nueva"),
                start_date: parentTask.start_date || new Date(),
                duration: 3,
                al_project_id: parentTask.al_project_id,
            },
            parentId
        );
    }

    async applyStructureChange(change) {
        if (!change) {
            return;
        }
        await this.saveChanges({ tasks: { update: [change] } });
        await this.reload();
    }

    /** Sale del acotado que impone el botón inteligente del proyecto. */
    async onShowAllProjects() {
        this.state.pinnedToProject = false;
        this.state.selectedIds = [];
        await this.reload();
    }

    async reload() {
        await this.fetchData();
        this.parseData();
    }

    isSelected(projectId) {
        return this.state.selectedIds.includes(projectId);
    }
}

registry.category("actions").add("al_project_gantt.backend", GanttAction);
