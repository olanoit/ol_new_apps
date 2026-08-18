/** @odoo-module **/

/**
 * Configuración común de dhtmlxGantt, compartida por las dos interfaces.
 *
 * Vive en el módulo base por la misma razón que el adaptador: lo que comparten
 * el backend y el website no se duplica. Aquí no hay acceso a datos ni a
 * servicios de Odoo; solo configuración de la librería.
 */
import { _t } from "@web/core/l10n/translation";
import { applyLocale } from "@al_project_gantt_base/js/gantt_adapter";
import { computeWbsCodes, wbsColumn } from "@al_project_gantt_base/js/gantt_tools";

/** Escalas de tiempo. Punto de extensión: añadir o redefinir niveles. */
export const ZOOM_LEVELS = {
    day: {
        label: _t("Día"),
        scales: [
            { unit: "week", step: 1, format: "%d %M" },
            { unit: "day", step: 1, format: "%d" },
        ],
        cellWidth: 40,
    },
    week: {
        label: _t("Semana"),
        scales: [
            { unit: "month", step: 1, format: "%F %Y" },
            { unit: "week", step: 1, format: "S%W" },
        ],
        cellWidth: 70,
    },
    month: {
        label: _t("Mes"),
        scales: [
            { unit: "year", step: 1, format: "%Y" },
            { unit: "month", step: 1, format: "%F" },
        ],
        cellWidth: 90,
    },
    quarter: {
        label: _t("Trimestre"),
        scales: [
            { unit: "year", step: 1, format: "%Y" },
            {
                unit: "quarter",
                step: 1,
                format: (date) => `T${Math.floor(date.getMonth() / 3) + 1}`,
            },
        ],
        cellWidth: 100,
    },
};

/** Escapa texto de datos antes de inyectarlo en el HTML del tooltip. */
export function escapeText(value) {
    const node = document.createElement("span");
    node.textContent = String(value ?? "");
    return node.innerHTML;
}

/** Aplica una escala. Con `render` a false solo prepara la configuración. */
export function applyZoom(gantt, key, render = true) {
    const level = ZOOM_LEVELS[key] || ZOOM_LEVELS.week;
    gantt.config.scales = level.scales;
    gantt.config.min_column_width = level.cellWidth;
    if (render) {
        gantt.render();
    }
}

/** Contenido del tooltip de una barra. */
export function buildTooltip(gantt, task) {
    const format = gantt.templates.tooltip_date_format;
    const lines = [`<b>${escapeText(task.text)}</b>`];
    if (task.start_date) {
        lines.push(`${_t("Inicio")}: ${format(task.start_date)}`);
    }
    if (task.end_date) {
        lines.push(`${_t("Fin")}: ${format(task.end_date)}`);
    }
    if (task.al_stage) {
        lines.push(`${_t("Etapa")}: ${escapeText(task.al_stage)}`);
    }
    if (task.al_users) {
        lines.push(`${_t("Personas asignadas")}: ${escapeText(task.al_users)}`);
    }
    if (task.al_activity_state) {
        const states = {
            overdue: _t("Actividad atrasada"),
            today: _t("Actividad para hoy"),
            planned: _t("Actividad planificada"),
        };
        const label = states[task.al_activity_state] || _t("Actividad pendiente");
        const summary = task.al_activity_summary ? `: ${escapeText(task.al_activity_summary)}` : "";
        lines.push(`<b>${label}</b>${summary}`);
    }
    if (task.al_start_inferred) {
        lines.push(`<i>${_t("Inicio estimado: la tarea solo tiene fecha límite")}</i>`);
    }
    return lines.join("<br/>");
}

/** Columnas de la rejilla. Punto de extensión: envolver y añadir columnas. */
export function buildColumns(gantt, options = {}) {
    const { showCritical = false, showBaseline = false, showWbs = false } = options;
    // Formato corto: el predeterminado incluye la hora y se corta.
    const shortDate = gantt.date.date_to_str("%d/%m/%Y");
    const extra = [];
    if (showCritical) {
        extra.push({
            name: "al_slack_hours",
            label: _t("Holgura (h)"),
            align: "right",
            width: 85,
            resize: true,
            template: (task) =>
                task.al_slack_hours === null || task.al_slack_hours === undefined
                    ? ""
                    : Math.round(task.al_slack_hours),
        });
    }
    if (showBaseline) {
        extra.push({
            name: "al_baseline_variance",
            label: _t("Desvío (d)"),
            align: "right",
            width: 85,
            resize: true,
            template: (task) => {
                const variance = task.al_baseline_variance;
                if (variance === null || variance === undefined) {
                    return "";
                }
                const rounded = Math.round(variance * 10) / 10;
                const className = rounded > 0 ? "algantt-late" : rounded < 0 ? "algantt-early" : "";
                return `<span class="${className}">${rounded > 0 ? "+" : ""}${rounded}</span>`;
            },
        });
    }
    return [
        ...(showWbs ? [wbsColumn(gantt)] : []),
        { name: "text", label: _t("Tarea"), tree: true, width: "*", resize: true },
        {
            name: "start_date",
            label: _t("Inicio"),
            align: "center",
            width: 95,
            resize: true,
            template: (task) => (task.start_date ? shortDate(task.start_date) : ""),
        },
        {
            name: "end_date",
            label: _t("Fin"),
            align: "center",
            width: 95,
            resize: true,
            template: (task) => (task.end_date ? shortDate(task.end_date) : ""),
        },
        {
            name: "al_activity",
            label: "",
            align: "center",
            width: 34,
            resize: false,
            template: (task) => {
                if (!task.al_activity_state) {
                    return "";
                }
                const title = escapeText(task.al_activity_summary || task.al_activity_state);
                return `<span class="algantt-activity algantt-activity-${task.al_activity_state}" title="${title}">●</span>`;
            },
        },
        {
            name: "al_users",
            label: _t("Asignadas a"),
            align: "left",
            width: 110,
            resize: true,
            template: (task) => escapeText(task.al_users || ""),
        },
        ...extra,
    ];
}

/**
 * Configuración por defecto de una instancia recién creada.
 *
 * @param {Object} gantt instancia de `window.Gantt.getGanttInstance()`
 * @param {Object} [options] `lang`, `zoom`, `readonly`, `gridWidth`,
 *        `showCritical`, `showBaseline`
 */
export function configureGantt(gantt, options = {}) {
    const {
        lang = null,
        zoom = "week",
        readonly = true,
        gridWidth = 560,
        showCritical = false,
        showBaseline = false,
        showWbs = false,
    } = options;

    applyLocale(gantt, lang);
    // Únicos plugins de la edición MIT: tooltip, marker y fullscreen.
    gantt.plugins({ tooltip: true, marker: true, fullscreen: true });

    // La edición se activa aparte, con `enableEditing`, y solo si el servidor
    // dice que el usuario puede escribir (`meta.editable`).
    gantt.config.readonly = readonly;
    gantt.config.drag_progress = false;
    gantt.config.details_on_dblclick = false;
    gantt.config.row_height = 32;
    gantt.config.bar_height = 20;
    gantt.config.grid_width = gridWidth;
    gantt.config.open_tree_initially = true;
    gantt.config.show_progress = true;
    gantt.config.fit_tasks = true;
    // Tareas sin fecha (`include_undated`): se listan en la rejilla, sin barra.
    gantt.config.show_unscheduled = true;
    gantt.config.columns = buildColumns(gantt, { showCritical, showBaseline, showWbs });

    gantt.templates.task_class = (start, end, task) => {
        const classes = [];
        if (task.al_is_project) {
            classes.push("algantt-project-row");
        }
        if (task.al_start_inferred) {
            classes.push("algantt-inferred-start");
        }
        if (task.al_orphaned) {
            classes.push("algantt-orphan");
        }
        if (showCritical && task.al_critical) {
            classes.push("algantt-critical");
        }
        if (task.readonly && !task.al_is_project) {
            classes.push("algantt-locked");
        }
        return classes.join(" ");
    };
    gantt.templates.tooltip_text = (start, end, task) => buildTooltip(gantt, task);

    applyZoom(gantt, zoom, false);
}

/**
 * Dibuja la línea base como una barra fantasma bajo cada tarea.
 *
 * La edición MIT de dhtmlxGantt **elimina** la API de capas
 * (`e.mixin(e, i.layersApi), bo(e)` borra `addTaskLayer`/`addLinkLayer` en el
 * propio bundle), así que no se puede añadir una capa propia. En su lugar, la
 * barra se inyecta dentro del contenido de la tarea y se posiciona con CSS
 * relativo a la barra real; el contenedor lleva `overflow: visible` para que
 * pueda salirse cuando el plan se desvía.
 */
export function enableBaselineBars(gantt) {
    const original = gantt.templates.task_text;
    gantt.templates.task_text = (start, end, task) => {
        const text = original ? original(start, end, task) : escapeText(task.text);
        if (!task.al_baseline_start || !task.al_baseline_end || !start) {
            return text;
        }
        const barLeft = gantt.posFromDate(start);
        const left = gantt.posFromDate(task.al_baseline_start) - barLeft;
        const width = Math.max(
            gantt.posFromDate(task.al_baseline_end) - gantt.posFromDate(task.al_baseline_start),
            2
        );
        return `${text}<div class="algantt-baseline-bar" style="left:${left}px;width:${width}px"></div>`;
    };
}

/** Carga los datos ya adaptados y posiciona el scroll en el inicio del plan. */
export function parseGanttData(gantt, ganttData) {
    gantt.clearAll();
    gantt.parse({ data: ganttData.data, links: ganttData.links });
    // El código EDT depende del árbol: se recalcula con cada carga.
    computeWbsCodes(gantt);
    const starts = ganttData.data
        .map((row) => row.start_date)
        .filter(Boolean)
        .sort((a, b) => a - b);
    if (starts.length) {
        gantt.showDate(starts[0]);
    }
}
