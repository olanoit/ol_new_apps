/** @odoo-module **/

/**
 * Formulario de tarea del diagrama (el *lightbox* de dhtmlxGantt).
 *
 * La edición MIT solo trae bloques `textarea`, `select`, `checkbox`, `radio`,
 * `time` y `duration`; con ellos el formulario queda ajeno a Odoo: las fechas se
 * editan con tres desplegables (día, mes, año) y los campos de varios valores
 * con casillas sueltas.
 *
 * Aquí se registran dos bloques propios:
 *
 * - `algantt_daterange`: un campo de fecha y hora para el inicio y otro para el
 *   fin, en vez de seis desplegables.
 * - `algantt_tokens`: valores múltiples como *badges*, al estilo del widget
 *   many2many de Odoo, con un desplegable para añadir y una «×» para quitar.
 *
 * Los valores viajan como propiedades de la tarea y `lightboxValues()` los
 * traduce al *changeset* que entiende el servidor.
 */
import { _t } from "@web/core/l10n/translation";

/** Nombre del botón propio del formulario (la librería lo usa como clase CSS). */
const OPEN_BUTTON = "algantt_open_btn";

/** Alto de una sección de badges: crece con el número de valores. */
function tokensHeight(items) {
    const rows = Math.ceil(((items || []).length || 1) / 3);
    return Math.min(52 + rows * 16, 130);
}

/** Convierte `[{id, name}]` o `[{value, label}]` en `[{key, label}]`. */
function toOptions(items, { empty = null } = {}) {
    const options = (items || []).map((item) => ({
        key: String(item.id ?? item.value),
        label: item.name ?? item.label,
    }));
    return empty === null ? options : [{ key: "", label: empty }, ...options];
}

/** Date -> valor de un `<input type="datetime-local">` (hora local). */
function toInputValue(date) {
    if (!date) {
        return "";
    }
    const pad = (value) => String(value).padStart(2, "0");
    return (
        `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
        `T${pad(date.getHours())}:${pad(date.getMinutes())}`
    );
}

/** Valor de un `<input type="datetime-local">` -> Date. */
function fromInputValue(value) {
    if (!value) {
        return null;
    }
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
}

function escapeHtml(value) {
    const node = document.createElement("span");
    node.textContent = String(value ?? "");
    return node.innerHTML;
}

/** Opciones disponibles, leídas del propio `<select>` del bloque. */
function tokenOptions(node) {
    return [...node.querySelectorAll(".algantt-token-add option")]
        .filter((option) => option.value)
        .map((option) => ({ key: option.value, label: option.textContent }));
}

function renderTokens(node) {
    const list = node.querySelector(".algantt-token-list");
    const selected = node.$algantt_selected || [];
    const byKey = new Map(tokenOptions(node).map((option) => [option.key, option.label]));

    list.replaceChildren();
    if (!selected.length) {
        const empty = document.createElement("span");
        empty.className = "algantt-token-empty";
        empty.textContent = node.dataset.empty || "";
        list.appendChild(empty);
    }
    for (const key of selected) {
        const badge = document.createElement("span");
        badge.className = "algantt-token";
        badge.textContent = byKey.get(key) || key;
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "algantt-token-remove";
        remove.setAttribute("data-remove", key);
        remove.setAttribute("aria-label", _t("Quitar"));
        remove.textContent = "×";
        badge.appendChild(remove);
        list.appendChild(badge);
    }
    // El desplegable solo ofrece lo que aún no está puesto.
    for (const option of node.querySelectorAll(".algantt-token-add option")) {
        if (option.value) {
            option.hidden = selected.includes(option.value);
        }
    }
}

/** Registra los bloques propios una sola vez por instancia. */
function registerBlocks(gantt) {
    if (gantt.$algantt_blocks) {
        return;
    }
    gantt.$algantt_blocks = true;

    gantt.form_blocks.algantt_daterange = {
        // El HTML se devuelve sin espacios ni saltos iniciales: la librería
        // indexa los hijos del contenedor y un nodo de texto suelto la rompe.
        render: () =>
            `<div class="algantt-lb-dates">` +
            `<label class="algantt-lb-date"><span>${escapeHtml(_t("Inicio"))}</span>` +
            `<input type="datetime-local" class="algantt-lb-start"/></label>` +
            `<label class="algantt-lb-date"><span>${escapeHtml(_t("Fin"))}</span>` +
            `<input type="datetime-local" class="algantt-lb-end"/></label>` +
            `</div>`,
        set_value: (node, value, task) => {
            node.querySelector(".algantt-lb-start").value = toInputValue(task.start_date);
            node.querySelector(".algantt-lb-end").value = toInputValue(task.end_date);
        },
        get_value: (node, task) => {
            const start = fromInputValue(node.querySelector(".algantt-lb-start").value);
            const end = fromInputValue(node.querySelector(".algantt-lb-end").value);
            // Si el rango queda invertido o incompleto se conserva lo que ya
            // tenía la tarea: es preferible a guardar una fecha imposible.
            if (!start || !end || start > end) {
                return { start_date: task.start_date, end_date: task.end_date };
            }
            return { start_date: start, end_date: end };
        },
        focus: (node) => node.querySelector(".algantt-lb-start").focus(),
    };

    gantt.form_blocks.algantt_tokens = {
        render: (section) => {
            const options = toOptions(section.options, { empty: _t("Añadir…") });
            const choices = options
                .map(
                    (option) =>
                        `<option value="${escapeHtml(option.key)}">${escapeHtml(option.label)}</option>`
                )
                .join("");
            const empty = section.empty_label || _t("Sin asignar");
            return (
                `<div class="algantt-tokens" data-empty="${escapeHtml(empty)}">` +
                `<div class="algantt-token-list"></div>` +
                `<select class="algantt-token-add">${choices}</select>` +
                `</div>`
            );
        },
        set_value: (node, value) => {
            const selected = Array.isArray(value)
                ? value.map(String)
                : String(value || "").split(",").filter(Boolean);
            node.$algantt_selected = selected;
            renderTokens(node);

            if (node.$algantt_bound) {
                return;
            }
            node.$algantt_bound = true;
            node.addEventListener("click", (event) => {
                const remove = event.target.closest("[data-remove]");
                if (!remove) {
                    return;
                }
                event.preventDefault();
                const key = remove.getAttribute("data-remove");
                node.$algantt_selected = (node.$algantt_selected || []).filter(
                    (item) => item !== key
                );
                renderTokens(node);
            });
            node.addEventListener("change", (event) => {
                if (!event.target.matches(".algantt-token-add")) {
                    return;
                }
                const key = event.target.value;
                if (key && !(node.$algantt_selected || []).includes(key)) {
                    node.$algantt_selected = [...(node.$algantt_selected || []), key];
                    renderTokens(node);
                }
                event.target.value = "";
            });
        },
        get_value: (node) => node.$algantt_selected || [],
        focus: (node) => node.querySelector(".algantt-token-add")?.focus(),
    };
}

/** ¿La fila es una tarea de verdad? Las de proyecto y los hitos no lo son. */
function isTaskRow(task) {
    return Boolean(task) && !task.al_is_project && !task.al_is_milestone_record;
}

/**
 * Añade al formulario un botón que abre la ficha completa de la tarea.
 *
 * El formulario del diagrama es corto a propósito: no trae la descripción (es
 * HTML y guardarla como texto plano la destruiría), ni el chatter, ni los
 * adjuntos. Este botón es la salida a la ficha de Odoo, donde sí está todo, sin
 * obligar a buscarla por otro camino.
 *
 * El módulo base no sabe navegar —no debe—, así que quien llama pasa
 * `openRecord`: en el backend abre la acción con su miga de pan, en el website
 * abre la ficha en otra pestaña.
 */
function enableOpenButton(gantt, openRecord) {
    gantt.locale.labels[OPEN_BUTTON] = _t("Abrir en Odoo");
    if (!gantt.config.buttons_right.includes(OPEN_BUTTON)) {
        gantt.config.buttons_right = [OPEN_BUTTON, ...gantt.config.buttons_right];
    }

    // Las filas de proyecto y los hitos no son `project.task`. En vez de
    // rehacer los botones en cada apertura, se marca el contenedor y el botón
    // se esconde por CSS.
    gantt.attachEvent("onBeforeLightbox", (id) => {
        gantt.getLightbox().classList.toggle(
            "algantt-lb-no-open", !isTaskRow(gantt.getTask(id))
        );
        return true;
    });

    gantt.attachEvent("onLightboxButton", (buttonClass) => {
        if (buttonClass !== OPEN_BUTTON) {
            return true;
        }
        const id = gantt.getState().lightbox;
        // Cerrar equivale a Cancelar: lo que se hubiera tecleado aquí no se
        // guarda. Es lo esperable, porque se va a editar en la ficha completa.
        gantt.hideLightbox();
        if (id !== null && id !== undefined) {
            openRecord(id);
        }
        return true;
    });
}

/**
 * Configura las secciones del formulario y los campos que se guardan.
 *
 * @param {Object} gantt instancia
 * @param {Object} options `filters` del contrato y banderas de capacidad
 * @param {Function} [options.openRecord] `(taskId) => void`; con ella el
 *        formulario ofrece «Abrir en Odoo». Sin ella, el botón no aparece.
 */
export function configureLightbox(gantt, options = {}) {
    const { filters = {}, canEditProgress = false, openRecord = null } = options;
    const assignable = filters.assignable_users || filters.users || [];
    registerBlocks(gantt);

    gantt.locale.labels.section_description = _t("Tarea");
    gantt.locale.labels.section_time = _t("Periodo");
    gantt.locale.labels.section_stage = _t("Etapa");
    gantt.locale.labels.section_assignees = _t("Personas asignadas");
    gantt.locale.labels.section_priority = _t("Prioridad");
    gantt.locale.labels.section_progress = _t("Avance (%)");
    gantt.locale.labels.section_hours = _t("Horas asignadas");
    gantt.locale.labels.section_tags = _t("Etiquetas");

    const sections = [
        { name: "description", height: 34, map_to: "text", type: "textarea", focus: true },
        { name: "time", type: "algantt_daterange", map_to: "auto", height: 62 },
        {
            name: "stage",
            height: 32,
            map_to: "al_stage_id",
            type: "select",
            options: toOptions(filters.stages, { empty: _t("Sin etapa") }),
        },
        {
            name: "assignees",
            // El formulario ofrece **todas** las personas asignables, no solo
            // las que ya tienen tareas (eso es lo que alimenta el filtro).
            height: tokensHeight(assignable),
            map_to: "al_user_ids",
            type: "algantt_tokens",
            options: assignable,
            empty_label: _t("Sin asignar"),
        },
        {
            name: "priority",
            height: 32,
            map_to: "al_priority",
            type: "select",
            options: toOptions(filters.priorities),
        },
        { name: "hours", height: 32, map_to: "al_allocated_hours", type: "textarea" },
    ];
    if (canEditProgress) {
        sections.push({ name: "progress", height: 32, map_to: "al_progress_pct", type: "textarea" });
    }
    if ((filters.tags || []).length) {
        sections.push({
            name: "tags",
            height: tokensHeight(filters.tags),
            map_to: "al_tag_ids",
            type: "algantt_tokens",
            options: filters.tags,
            empty_label: _t("Sin etiquetas"),
        });
    }

    gantt.config.lightbox.sections = sections;
    gantt.config.lightbox.project_sections = sections;
    gantt.config.lightbox_additional_height = 90;

    if (openRecord) {
        enableOpenButton(gantt, openRecord);
    }
}

/**
 * Traduce lo que el formulario dejó en la tarea a valores del *changeset*.
 * Devuelve solo los campos presentes, para no pisar lo que no se tocó.
 */
export function lightboxValues(task) {
    const values = {};
    // La descripción no se edita aquí: es un campo HTML y guardarla como texto
    // plano destruiría su formato. Para eso está «Abrir en Odoo».
    if ("al_stage_id" in task) {
        values.stage_id = task.al_stage_id ? Number(task.al_stage_id) : false;
    }
    if ("al_user_ids" in task) {
        const raw = task.al_user_ids;
        const list = Array.isArray(raw) ? raw : String(raw || "").split(",").filter(Boolean);
        values.user_ids = list.map(Number);
    }
    if ("al_tag_ids" in task) {
        const raw = task.al_tag_ids;
        const list = Array.isArray(raw) ? raw : String(raw || "").split(",").filter(Boolean);
        values.tag_ids = list.map(Number);
    }
    if ("al_priority" in task) {
        values.priority = String(task.al_priority ?? "0");
    }
    if ("al_allocated_hours" in task) {
        const hours = parseFloat(task.al_allocated_hours);
        values.allocated_hours = Number.isFinite(hours) ? hours : 0;
    }
    if ("al_progress_pct" in task) {
        const progress = parseFloat(task.al_progress_pct);
        if (Number.isFinite(progress)) {
            values.progress = Math.max(0, Math.min(100, progress));
        }
    }
    return values;
}
