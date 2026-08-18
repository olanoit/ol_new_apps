/** @odoo-module **/

/**
 * Página de Gantt del sitio web (solo usuarios internos).
 *
 * Usa el framework de «interactions» del frontend de Odoo 19. Igual que la
 * interfaz de backend, no consulta el ORM: pide los datos al endpoint
 * `/gantt/data`, que delega en `project.project.get_gantt_data()`.
 */
import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { loadCSS, loadJS } from "@web/core/assets";
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

export class GanttPage extends Interaction {
    static selector = ".algantt-page";

    setup() {
        this.gantt = null;
        this.resizeObserver = null;
        this.selectedIds = [];
        this.zoom = "week";
        this.payload = null;
        this.ganttData = null;
        // `filters` es lo aplicado; el panel se lee al pulsar Aplicar.
        this.filters = emptyFilters();
        this.editor = null;
        this.criticalPath = false;
        this.baselineId = null;
        this.rescheduleChain = true;
        this.showWbs = false;
        this.hideDone = false;
        this.expanded = true;
        this.detachContextMenu = null;
        this.containerEl = this.el.querySelector(".algantt-container");
        this.projectsEl = this.el.querySelector(".algantt-projects");
        this.noticesEl = this.el.querySelector(".algantt-notices");
        this.zoomEl = this.el.querySelector(".algantt-zoom");
        this.loadingEl = this.el.querySelector(".algantt-loading");
        this.filtersEl = this.el.querySelector(".algantt-filters");
        this.filtersToggleEl = this.el.querySelector(".algantt-filters-toggle");
        this.filtersCountEl = this.el.querySelector(".algantt-filters-count");
        this.filtersErrorEl = this.el.querySelector(".algantt-filters-error");
        this.usersEl = this.el.querySelector(".algantt-filter-users");
        this.statesEl = this.el.querySelector(".algantt-filter-states");
        this.dateFromEl = this.el.querySelector(".algantt-filter-from");
        this.dateToEl = this.el.querySelector(".algantt-filter-to");
        this.undatedEl = this.el.querySelector(".algantt-filter-undated");
        this.addTaskEl = this.el.querySelector(".algantt-add-task");
        this.criticalEl = this.el.querySelector(".algantt-critical-toggle");
        this.criticalCountEl = this.el.querySelector(".algantt-critical-count");
        this.chainWrapperEl = this.el.querySelector(".algantt-chain-wrapper");
        this.chainEl = this.el.querySelector(".algantt-chain");
        this.baselineEl = this.el.querySelector(".algantt-baseline");
        this.baselineCaptureEl = this.el.querySelector(".algantt-baseline-capture");
        this.saveStateEl = this.el.querySelector(".algantt-save-state");
        this.exportXlsxEl = this.el.querySelector(".algantt-export-xlsx");
        this.exportPdfEl = this.el.querySelector(".algantt-export-pdf");
        this.searchEl = this.el.querySelector(".algantt-search");
        this.wbsEl = this.el.querySelector(".algantt-wbs");
        this.expandEl = this.el.querySelector(".algantt-expand");
        this.hideDoneEl = this.el.querySelector(".algantt-hide-done");
        this.fullscreenEl = this.el.querySelector(".algantt-fullscreen");
    }

    async willStart() {
        // Carga perezosa: la librería solo se descarga en esta página.
        await Promise.all([loadJS(GANTT_LIB.js), loadCSS(GANTT_LIB.css)]);
        await this.fetchData();
    }

    start() {
        this.renderZoomOptions();
        this.renderProjectButtons();
        this.renderFilterOptions();
        this.bindFilterEvents();
        this.renderProTools();
        this.bindProEvents();
        this.bindViewToolEvents();
        this.bindExportEvents();
        this.renderNotices();
        this.mountGantt();
        this.setLoading(false);
    }

    destroy() {
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
    // Datos
    // ------------------------------------------------------------------
    getOptions() {
        const options = filtersToOptions(this.filters);
        if (this.criticalPath) {
            options.critical_path = true;
        }
        if (this.baselineId) {
            options.baseline_id = this.baselineId;
        }
        return options;
    }

    async fetchData() {
        this.payload = await rpc("/gantt/data", {
            project_ids: this.selectedIds.length ? this.selectedIds : null,
            options: this.getOptions(),
        });
        if (!this.selectedIds.length) {
            this.selectedIds = (this.payload.projects || []).map((project) => project.id);
        }
        this.ganttData = toDhtmlxData(this.payload);
    }

    // ------------------------------------------------------------------
    // Librería
    // ------------------------------------------------------------------
    mountGantt() {
        if (!this.containerEl || !window.Gantt) {
            return;
        }
        // Instancia propia: no comparte estado con la interfaz de backend.
        const meta = this.payload.meta || {};
        this.gantt = window.Gantt.getGanttInstance();
        configureGantt(this.gantt, {
            lang: document.documentElement.lang,
            zoom: this.zoom,
            readonly: !meta.editable,
            showCritical: this.criticalPath,
            showBaseline: Boolean(this.baselineId),
            showWbs: this.showWbs,
        });
        applyWorkingCalendar(this.gantt, this.payload.calendar);
        configureLightbox(this.gantt, {
            filters: this.payload.filters || {},
            canEditProgress: Boolean(meta.can_edit_progress),
            // En otra pestaña: aquí no hay webclient al que volver, y así la
            // página del diagrama no se pierde.
            openRecord: (taskId) => window.open(`/odoo/project.task/${taskId}`, "_blank"),
        });
        if (this.baselineId) {
            enableBaselineBars(this.gantt);
        }
        if (meta.editable) {
            // Mismas reglas que en el backend: el permiso real por tarea lo
            // decide el servidor; aquí solo se enchufa la edición.
            this.editor = enableEditing(this.gantt, {
                timeZone: meta.tz,
                save: (changeset) => this.saveChanges(changeset),
                onSaved: () => this.setSaveState(_t("Guardado")),
                onError: (error) => this.onSaveError(error),
                defaultProjectId: () => this.selectedIds[0] || null,
                rescheduleChain: () => this.rescheduleChain,
            });
        }
        this.gantt.init(this.containerEl);
        parseGanttData(this.gantt, this.ganttData);
        addTodayMarker(this.gantt);
        this.detachContextMenu = attachContextMenu(
            this.gantt, this.containerEl, (taskId, task) => this.buildContextActions(taskId, task)
        );
        if (this.searchEl?.value) {
            applySearch(this.gantt, this.searchEl.value);
        }

        this.resizeObserver = new ResizeObserver(() => this.gantt?.setSizes());
        this.resizeObserver.observe(this.containerEl);
    }

    // ------------------------------------------------------------------
    // Barra de herramientas (DOM directo: en el frontend no hay OWL)
    // ------------------------------------------------------------------
    renderZoomOptions() {
        if (!this.zoomEl) {
            return;
        }
        this.zoomEl.replaceChildren();
        for (const [key, level] of Object.entries(ZOOM_LEVELS)) {
            const option = document.createElement("option");
            option.value = key;
            option.textContent = level.label;
            option.selected = key === this.zoom;
            this.zoomEl.appendChild(option);
        }
        this.addListener(this.zoomEl, "change", () => {
            this.zoom = this.zoomEl.value;
            if (this.gantt) {
                applyZoom(this.gantt, this.zoom);
            }
        });
    }

    renderProjectButtons() {
        if (!this.projectsEl) {
            return;
        }
        this.projectsEl.querySelectorAll(".algantt-project-btn, .algantt-all-btn").forEach(
            (node) => node.remove()
        );
        const projects = this.payload.projects || [];
        if (!projects.length) {
            const empty = document.createElement("span");
            empty.className = "algantt-project-btn text-muted";
            empty.textContent = _t("Ninguno visible");
            this.projectsEl.appendChild(empty);
            return;
        }
        for (const project of projects) {
            const selected = this.selectedIds.includes(project.id);
            const button = document.createElement("button");
            button.type = "button";
            button.className = `algantt-project-btn btn btn-sm ${
                selected ? "btn-primary" : "btn-outline-secondary"
            }`;
            // textContent, no innerHTML: el nombre es dato de usuario.
            button.textContent = project.name;
            const badge = document.createElement("span");
            badge.className = "badge text-bg-light ms-1";
            badge.textContent = project.task_count;
            button.appendChild(badge);
            this.addListener(button, "click", () => this.onProjectToggle(project.id));
            this.projectsEl.appendChild(button);
        }
        if (projects.length > 1) {
            const all = document.createElement("button");
            all.type = "button";
            all.className = "algantt-all-btn btn btn-sm btn-link";
            all.textContent = _t("Todos");
            this.addListener(all, "click", () => this.onSelectAll());
            this.projectsEl.appendChild(all);
        }
    }

    // ------------------------------------------------------------------
    // Filtros
    // ------------------------------------------------------------------
    renderFilterOptions() {
        const options = this.payload.filters || { states: [], users: [] };

        if (this.usersEl) {
            this.usersEl.replaceChildren();
            for (const user of options.users) {
                const option = document.createElement("option");
                option.value = user.id;
                option.textContent = `${user.name} (${user.task_count})`;
                option.selected = this.filters.userIds.includes(String(user.id));
                this.usersEl.appendChild(option);
            }
        }
        if (this.statesEl) {
            this.statesEl.replaceChildren();
            for (const state of options.states) {
                const option = document.createElement("option");
                option.value = state.value;
                option.textContent = state.label;
                option.selected = this.filters.states.includes(state.value);
                this.statesEl.appendChild(option);
            }
        }
        if (this.dateFromEl) {
            this.dateFromEl.value = this.filters.dateFrom;
        }
        if (this.dateToEl) {
            this.dateToEl.value = this.filters.dateTo;
        }
        if (this.undatedEl) {
            this.undatedEl.checked = this.filters.includeUndated;
        }
        this.renderFilterCount();
    }

    renderFilterCount() {
        if (!this.filtersCountEl) {
            return;
        }
        const count = countActiveFilters(this.filters);
        this.filtersCountEl.textContent = count || "";
        this.filtersCountEl.classList.toggle("d-none", !count);
    }

    bindFilterEvents() {
        if (this.filtersToggleEl && this.filtersEl) {
            this.addListener(this.filtersToggleEl, "click", () => {
                this.filtersEl.classList.toggle("d-none");
            });
        }
        const applyEl = this.el.querySelector(".algantt-filters-apply");
        if (applyEl) {
            this.addListener(applyEl, "click", () => this.onApplyFilters());
        }
        const clearEl = this.el.querySelector(".algantt-filters-clear");
        if (clearEl) {
            this.addListener(clearEl, "click", () => this.onClearFilters());
        }
    }

    readFilterPanel() {
        return {
            userIds: selectedValues(this.usersEl),
            states: selectedValues(this.statesEl),
            dateFrom: this.dateFromEl?.value || "",
            dateTo: this.dateToEl?.value || "",
            includeUndated: Boolean(this.undatedEl?.checked),
        };
    }

    async onApplyFilters() {
        const draft = this.readFilterPanel();
        const invalid = isInvalidRange(draft);
        this.filtersErrorEl?.classList.toggle("d-none", !invalid);
        if (invalid) {
            return;
        }
        this.filters = draft;
        await this.reload();
    }

    async onClearFilters() {
        this.filters = emptyFilters();
        this.filtersErrorEl?.classList.add("d-none");
        await this.reload();
    }

    // ------------------------------------------------------------------
    // Funciones «pro» y escritura
    // ------------------------------------------------------------------
    renderProTools() {
        const meta = this.payload.meta || {};

        this.addTaskEl?.classList.toggle("d-none", !meta.can_create);
        this.chainWrapperEl?.classList.toggle(
            "d-none", !(meta.editable && meta.can_reschedule_chain)
        );
        if (this.chainEl) {
            this.chainEl.checked = this.rescheduleChain;
        }

        const summary = meta.critical_path || { computed: false };
        this.criticalEl?.classList.toggle("btn-danger", this.criticalPath);
        this.criticalEl?.classList.toggle("btn-outline-secondary", !this.criticalPath);
        if (this.criticalCountEl) {
            const show = summary.computed;
            this.criticalCountEl.textContent = show ? summary.critical_count : "";
            this.criticalCountEl.classList.toggle("d-none", !show);
        }

        if (this.baselineEl) {
            const current = this.baselineId;
            this.baselineEl.replaceChildren();
            const none = document.createElement("option");
            none.value = "";
            none.textContent = _t("Sin línea base");
            this.baselineEl.appendChild(none);
            for (const baseline of this.payload.baselines || []) {
                const option = document.createElement("option");
                option.value = baseline.id;
                option.textContent = baseline.name;
                option.selected = String(baseline.id) === String(current);
                this.baselineEl.appendChild(option);
            }
        }
    }

    bindViewToolEvents() {
        if (this.searchEl) {
            this.addListener(this.searchEl, "input", () => {
                if (this.gantt) {
                    applySearch(this.gantt, this.searchEl.value);
                }
            });
        }
        if (this.wbsEl) {
            this.addListener(this.wbsEl, "click", async () => {
                this.showWbs = !this.showWbs;
                this.wbsEl.classList.toggle("active", this.showWbs);
                await this.remount();
            });
        }
        if (this.expandEl) {
            this.addListener(this.expandEl, "click", () => {
                this.expanded = !this.expanded;
                toggleAllBranches(this.gantt, this.expanded);
                this.expandEl.querySelector("i").className = this.expanded
                    ? "fa fa-compress"
                    : "fa fa-expand";
            });
        }
        if (this.hideDoneEl) {
            this.addListener(this.hideDoneEl, "click", async () => {
                this.hideDone = !this.hideDone;
                this.hideDoneEl.classList.toggle("active", this.hideDone);
                const closed = ["1_done", "1_canceled"];
                const available = (this.payload.filters?.states || []).map((s) => s.value);
                this.filters = {
                    ...this.filters,
                    states: this.hideDone ? available.filter((v) => !closed.includes(v)) : [],
                };
                await this.reload();
            });
        }
        if (this.fullscreenEl) {
            this.addListener(this.fullscreenEl, "click", () => toggleFullscreen(this.gantt));
        }
    }

    buildContextActions(taskId, task) {
        const isRealTask = !task.al_is_project && !task.al_is_milestone_record;
        const editable = !task.readonly;
        const actions = [];
        if (isRealTask) {
            actions.push({
                label: _t("Abrir en Odoo"),
                icon: "fa-external-link",
                run: () => window.open(`/odoo/project.task/${taskId}`, "_blank"),
            });
        }
        if (isRealTask) {
            actions.push({
                label: _t("Planificar actividad"),
                icon: "fa-clock-o",
                // En el sitio no hay webclient: se abre el asistente en Odoo.
                run: () => window.open(`/odoo/project.task/${taskId}`, "_blank"),
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

    async applyStructureChange(change) {
        if (!change) {
            return;
        }
        await this.saveChanges({ tasks: { update: [change] } });
        await this.reload();
    }

    bindProEvents() {
        if (this.criticalEl) {
            this.addListener(this.criticalEl, "click", async () => {
                this.criticalPath = !this.criticalPath;
                await this.remount();
            });
        }
        if (this.chainEl) {
            this.addListener(this.chainEl, "change", () => {
                this.rescheduleChain = this.chainEl.checked;
            });
        }
        if (this.baselineEl) {
            this.addListener(this.baselineEl, "change", async () => {
                this.baselineId = this.baselineEl.value ? Number(this.baselineEl.value) : null;
                await this.remount();
            });
        }
        if (this.baselineCaptureEl) {
            this.addListener(this.baselineCaptureEl, "click", async () => {
                if (!this.selectedIds.length) {
                    return;
                }
                const result = await this.waitFor(
                    rpc("/gantt/baseline", { project_ids: this.selectedIds })
                );
                this.baselineId = result.baselines?.[0]?.id || null;
                await this.remount();
            });
        }
        if (this.addTaskEl) {
            this.addListener(this.addTaskEl, "click", () => {
                const projectId = this.selectedIds[0];
                if (!projectId || !this.gantt) {
                    return;
                }
                this.gantt.createTask({
                    text: _t("Tarea nueva"),
                    start_date: this.gantt.getState().min_date || new Date(),
                    duration: 3,
                    al_project_id: projectId,
                });
            });
        }
    }

    /** Proyectos y opciones que definen «lo que se está viendo». */
    exportParams() {
        const options = { ...this.getOptions(), scale: this.zoom };
        return {
            projectIds: this.selectedIds.join(","),
            options: encodeURIComponent(JSON.stringify(options)),
        };
    }

    bindExportEvents() {
        if (this.exportXlsxEl) {
            this.addListener(this.exportXlsxEl, "click", () => {
                const { projectIds, options } = this.exportParams();
                window.location = `/al_project_gantt/export/xlsx?project_ids=${projectIds}&options=${options}`;
            });
        }
        if (this.exportPdfEl) {
            this.addListener(this.exportPdfEl, "click", () => {
                const { projectIds, options } = this.exportParams();
                // Ruta estándar de informes de Odoo: el PDF se compone en el
                // servidor con la misma matriz que el Excel.
                window.open(
                    `/report/pdf/al_project_gantt_base.report_gantt/${projectIds}?options=${options}`,
                    "_blank"
                );
            });
        }
    }

    async saveChanges(changeset) {
        this.setSaveState(_t("Guardando…"));
        return rpc("/gantt/apply", { changeset });
    }

    async onSaveError(error) {
        const message = error?.data?.message || error?.message || _t("No se pudo guardar el cambio.");
        this.setSaveState(message, true);
        await this.reload();
    }

    setSaveState(text, isError = false) {
        if (!this.saveStateEl) {
            return;
        }
        this.saveStateEl.textContent = text;
        this.saveStateEl.classList.toggle("text-danger", isError);
        this.saveStateEl.classList.toggle("text-muted", !isError);
    }

    /** Ruta crítica y línea base cambian columnas y capas: se rehace la instancia. */
    async remount() {
        this.setLoading(true);
        await this.waitFor(this.fetchData());
        if (this.editor) {
            this.editor.detach();
            this.editor = null;
        }
        if (this.gantt) {
            this.gantt.clearAll();
            if (typeof this.gantt.destructor === "function") {
                this.gantt.destructor();
            }
            this.gantt = null;
        }
        this.renderProjectButtons();
        this.renderFilterOptions();
        this.renderProTools();
        this.renderNotices();
        this.mountGantt();
        this.setLoading(false);
    }

    renderNotices() {
        if (!this.noticesEl) {
            return;
        }
        this.noticesEl.replaceChildren();
        const meta = this.payload.meta || {};
        const addNotice = (text, level) => {
            const alert = document.createElement("div");
            alert.className = `alert alert-${level} py-1 px-2 mb-0 mt-1 small`;
            alert.textContent = text;
            this.noticesEl.appendChild(alert);
        };
        if (meta.truncated) {
            addNotice(
                _t(
                    "Se muestran %(count)s de %(total)s tareas (límite de %(limit)s). Filtre por proyecto para ver el resto.",
                    { count: meta.count, total: meta.total, limit: meta.limit }
                ),
                "warning"
            );
        }
        if (meta.undated_count) {
            addNotice(
                this.filters.includeUndated
                    ? _t(
                          "%(count)s tarea(s) sin fecha límite se listan en la rejilla, sin barra en el diagrama.",
                          { count: meta.undated_count }
                      )
                    : _t(
                          "%(count)s tarea(s) sin fecha límite no se pueden dibujar; actívelas en Filtros ▸ «Incluir sin fecha».",
                          { count: meta.undated_count }
                      ),
                "info"
            );
        }
        if (!meta.count) {
            addNotice(
                countActiveFilters(this.filters)
                    ? _t("Ninguna tarea cumple los filtros aplicados.")
                    : _t("No hay tareas con fechas para mostrar."),
                "secondary"
            );
        }
    }

    setLoading(loading) {
        if (this.loadingEl) {
            this.loadingEl.classList.toggle("d-none", !loading);
        }
    }

    // ------------------------------------------------------------------
    // Interacción
    // ------------------------------------------------------------------
    async onProjectToggle(projectId) {
        const selected = new Set(this.selectedIds);
        if (selected.has(projectId)) {
            selected.delete(projectId);
        } else {
            selected.add(projectId);
        }
        if (!selected.size) {
            return; // nunca se deja la selección vacía
        }
        this.selectedIds = [...selected];
        await this.reload();
    }

    async onSelectAll() {
        this.selectedIds = (this.payload.projects || []).map((project) => project.id);
        await this.reload();
    }

    async reload() {
        this.setLoading(true);
        await this.waitFor(this.fetchData());
        this.renderProjectButtons();
        this.renderFilterOptions();
        this.renderProTools();
        this.renderNotices();
        if (this.gantt) {
            parseGanttData(this.gantt, this.ganttData);
        }
        this.setLoading(false);
    }
}

registry
    .category("public.interactions")
    .add("al_project_gantt_website.gantt_page", GanttPage);
