/** @odoo-module **/

/**
 * Adaptador compartido: traduce el formato neutral que devuelve
 * `project.project.get_gantt_data()` al formato que consume dhtmlxGantt.
 *
 * Vive en el módulo base para que las dos interfaces (backend y website) usen
 * exactamente la misma traducción. Es código puro, sin dependencias de OWL ni
 * del webclient, para poder cargarse igual en `web.assets_backend` y en
 * `web.assets_frontend`.
 *
 * Punto de extensión: todas las funciones se exportan por separado; para
 * cambiar el aspecto de una fila basta con envolver `taskToRow`.
 */

const MILESTONE_PREFIX = "m";
const PROJECT_PREFIX = "p";

/**
 * Convierte un instante UTC a la hora de pared de `timeZone`, devuelta como
 * Date en hora local del navegador — que es lo que dhtmlxGantt espera.
 * Sin esto, un usuario con tz de Odoo distinta a la del navegador vería las
 * barras desplazadas.
 */
export function toUserDate(isoString, timeZone) {
    if (!isoString) {
        return null;
    }
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) {
        return null;
    }
    if (!timeZone) {
        return date;
    }
    let parts;
    try {
        parts = new Intl.DateTimeFormat("en-US", {
            timeZone,
            hourCycle: "h23",
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
        }).formatToParts(date);
    } catch {
        // Zona horaria desconocida para el navegador: se usa la local.
        return date;
    }
    const value = {};
    for (const part of parts) {
        value[part.type] = part.value;
    }
    return new Date(
        Number(value.year),
        Number(value.month) - 1,
        Number(value.day),
        Number(value.hour),
        Number(value.minute),
        Number(value.second)
    );
}

/**
 * Inversa de `toUserDate`: un Date cuyos componentes son la hora de pared en
 * `timeZone` -> instante en ISO 8601 UTC, que es lo que espera el servidor.
 * Sin esto, guardar lo que se arrastra desplazaría las fechas por el desfase
 * entre la zona del navegador y la del usuario de Odoo.
 */
export function fromUserDate(date, timeZone) {
    if (!date) {
        return null;
    }
    if (!timeZone) {
        return date.toISOString();
    }
    const asUtc = new Date(
        Date.UTC(
            date.getFullYear(),
            date.getMonth(),
            date.getDate(),
            date.getHours(),
            date.getMinutes(),
            date.getSeconds()
        )
    );
    // Diferencia entre la hora de pared de esa zona y la que queremos fijar.
    const wall = toUserDate(asUtc.toISOString(), timeZone);
    const offset = wall.getTime() - date.getTime();
    return new Date(asUtc.getTime() - offset).toISOString();
}

/** Fecha sin hora (hitos, fechas de proyecto) -> Date local a medianoche. */
export function toPlainDate(isoDate) {
    if (!isoDate) {
        return null;
    }
    const [year, month, day] = isoDate.split("-").map(Number);
    if (!year || !month || !day) {
        return null;
    }
    return new Date(year, month - 1, day);
}

/** Una tarea del contrato neutral -> fila de dhtmlxGantt. */
export function taskToRow(task, options = {}) {
    const { timeZone = null, groupByProject = false } = options;
    const start = toUserDate(task.start, timeZone);
    const end = toUserDate(task.end, timeZone);
    let parent = task.parent_id || 0;
    if (!parent && groupByProject && task.project_id) {
        parent = `${PROJECT_PREFIX}${task.project_id}`;
    }
    return {
        id: task.id,
        text: task.name,
        start_date: start,
        end_date: end,
        parent,
        progress: (task.progress || 0) / 100,
        type: task.is_milestone ? "milestone" : "task",
        open: true,
        // `color` y `textColor` son propiedades nativas de dhtmlxGantt.
        color: task.color,
        textColor: task.text_color,
        // Datos propios, disponibles en las plantillas de la UI.
        al_state: task.state,
        al_stage: task.stage_name,
        al_users: (task.user_ids || []).map((user) => user.name).join(", "),
        al_allocated_hours: task.allocated_hours,
        // Campos que edita el formulario del diagrama. Los identificadores van
        // como texto porque es lo que devuelven los `<select>` del formulario.
        al_stage_id: task.stage_id ? String(task.stage_id) : "",
        al_user_ids: (task.user_ids || []).map((user) => String(user.id)),
        al_tag_ids: (task.tag_ids || []).map(String),
        al_priority: String(task.priority ?? "0"),
        al_progress_pct: Math.round(task.progress || 0),
        // Actividades pendientes de `mail.activity`.
        al_activity_state: task.activity_state || "",
        al_activity_summary: task.activity_summary || "",
        al_activity_icon: task.activity_icon || "",
        al_partner_name: task.partner_name || "",
        al_start_inferred: task.start_is_inferred,
        al_orphaned: task.orphaned,
        al_project_id: task.project_id,
        al_progress_derived: task.progress_is_derived,
        // Extras «pro»: solo vienen si se pidieron al servidor.
        al_critical: Boolean(task.critical),
        al_slack_hours: task.slack_hours ?? null,
        al_baseline_start: task.baseline_start ? toUserDate(task.baseline_start, timeZone) : null,
        al_baseline_end: task.baseline_end ? toUserDate(task.baseline_end, timeZone) : null,
        al_baseline_variance: task.baseline_variance_days ?? null,
        readonly: !task.editable,
    };
}

/** Un proyecto -> fila contenedora (solo si se agrupa por proyecto). */
export function projectToRow(project) {
    const row = {
        id: `${PROJECT_PREFIX}${project.id}`,
        text: project.name,
        type: "project",
        open: true,
        readonly: true,
        al_is_project: true,
        al_task_count: project.task_count,
    };
    // Las fechas se omiten si el proyecto no las tiene: una fila de tipo
    // `project` con fechas nulas rompe el parseo y se lleva por delante a sus
    // hijas. Sin fechas, la librería las deriva del rango de las tareas.
    const start = toPlainDate(project.date_start);
    const end = toPlainDate(project.date_end);
    if (start) {
        row.start_date = start;
    }
    if (end) {
        row.end_date = end;
    }
    return row;
}

/** Un hito de `project.milestone` -> fila de tipo milestone. */
export function milestoneToRow(milestone, options = {}) {
    const { groupByProject = false } = options;
    const date = toPlainDate(milestone.date);
    return {
        id: `${MILESTONE_PREFIX}${milestone.id}`,
        text: milestone.name,
        start_date: date,
        end_date: date,
        type: "milestone",
        parent: groupByProject && milestone.project_id ? `${PROJECT_PREFIX}${milestone.project_id}` : 0,
        readonly: true,
        al_is_milestone_record: true,
        al_is_reached: milestone.is_reached,
    };
}

/** Dependencia neutral -> enlace de dhtmlxGantt (0 = fin-comienzo). */
export function linkToRow(link) {
    const types = { FS: "0", SS: "1", FF: "2", SF: "3" };
    return {
        id: link.id,
        source: link.source,
        target: link.target,
        type: types[link.type] || "0",
    };
}

/**
 * Traduce la respuesta completa.
 *
 * @param {Object} payload respuesta de `get_gantt_data`
 * @param {Object} [options] `groupByProject` (por defecto true si hay más de
 *        un proyecto), `includeMilestones` (por defecto true)
 * @returns {{data: Array, links: Array, undated: Array, meta: Object, colors: Object}}
 */
export function toDhtmlxData(payload, options = {}) {
    const meta = payload.meta || {};
    const projects = payload.projects || [];
    const groupByProject =
        options.groupByProject === undefined ? projects.length > 1 : options.groupByProject;
    const includeMilestones =
        options.includeMilestones === undefined ? true : options.includeMilestones;
    const rowOptions = { timeZone: meta.tz, groupByProject };

    const data = [];
    const undated = [];

    if (groupByProject) {
        for (const project of projects) {
            data.push(projectToRow(project));
        }
    }
    for (const task of payload.tasks || []) {
        if (task.undated) {
            // Sin fecha de fin no hay barra que dibujar. Si el servidor las
            // devolvió es porque se pidieron (`include_undated`): se muestran
            // en la rejilla como «no planificadas», sin barra en el timeline.
            undated.push(task);
            data.push({
                ...taskToRow(task, rowOptions),
                unscheduled: true,
                start_date: null,
                end_date: null,
            });
            continue;
        }
        data.push(taskToRow(task, rowOptions));
    }
    if (includeMilestones) {
        for (const milestone of payload.milestones || []) {
            if (milestone.date) {
                data.push(milestoneToRow(milestone, rowOptions));
            }
        }
    }

    return {
        data,
        links: (payload.links || []).map(linkToRow),
        undated,
        meta,
        colors: payload.colors || { states: {}, fallback: {} },
        fieldMap: payload.field_map || {},
    };
}

/**
 * Traducción al español de las etiquetas de la librería.
 *
 * El paquete npm de dhtmlxGantt 10 ya no incluye los archivos de idioma, así
 * que se define aquí el subconjunto que usa la versión 1 (nombres de meses y
 * días, columnas, tipos y unidades). Ampliar al añadir edición.
 */
const LOCALE_ES = {
    date: {
        month_full: ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
            "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"],
        month_short: ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep",
            "Oct", "Nov", "Dic"],
        day_full: ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"],
        day_short: ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"],
    },
    labels: {
        new_task: "Nueva tarea",
        icon_save: "Guardar",
        icon_cancel: "Cancelar",
        icon_details: "Detalles",
        icon_edit: "Editar",
        icon_delete: "Eliminar",
        section_description: "Descripción",
        section_time: "Periodo",
        section_type: "Tipo",
        column_wbs: "EDT",
        column_text: "Tarea",
        column_start_date: "Inicio",
        column_duration: "Duración",
        column_add: "",
        link: "Dependencia",
        type_task: "Tarea",
        type_project: "Proyecto",
        type_milestone: "Hito",
        minutes: "Minutos",
        hours: "Horas",
        days: "Días",
        weeks: "Semanas",
        months: "Meses",
        years: "Años",
        message_ok: "Aceptar",
        message_cancel: "Cancelar",
    },
};

/** Aplica el idioma español si el usuario lo usa. Devuelve el locale aplicado. */
export function applyLocale(gantt, lang) {
    if (!gantt || !gantt.i18n || !String(lang || "").toLowerCase().startsWith("es")) {
        return null;
    }
    gantt.i18n.addLocale("es", LOCALE_ES);
    gantt.i18n.setLocale("es");
    return "es";
}

/** Ruta de la librería vendorizada, para `loadJS`/`loadCSS` perezosos. */
export const GANTT_LIB = {
    js: "/al_project_gantt_base/static/lib/dhtmlx/dhtmlxgantt.js",
    css: "/al_project_gantt_base/static/lib/dhtmlx/dhtmlxgantt.css",
};
