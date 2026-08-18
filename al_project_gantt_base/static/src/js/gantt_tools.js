/** @odoo-module **/

/**
 * Herramientas del diagrama compartidas por las dos interfaces.
 *
 * Cubren funciones que las alternativas comerciales dan por sentadas y que la
 * edición MIT de dhtmlxGantt no trae hechas: búsqueda rápida, código EDT (WBS),
 * sombreado de días no laborables, plegado del árbol, pantalla completa,
 * indentar/desindentar y menú contextual.
 *
 * Los únicos plugins disponibles en la edición MIT son `tooltip`, `marker` y
 * `fullscreen`; el resto está implementado aquí sobre la API pública.
 */
import { _t } from "@web/core/l10n/translation";

/** Marca vertical con el día de hoy. Requiere el plugin `marker`. */
export function addTodayMarker(gantt) {
    if (!gantt.addMarker) {
        return null;
    }
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return gantt.addMarker({
        start_date: today,
        css: "algantt-today-marker",
        text: _t("Hoy"),
        title: gantt.templates.date_grid ? gantt.templates.date_grid(today) : "",
    });
}

/**
 * Sombrea los días no laborables según el calendario del proyecto.
 *
 * Solo cambia el dibujo: la reprogramación en cadena sigue en tiempo natural.
 * El sombreado se aprecia en la escala **Día**; en semana, mes o trimestre cada
 * celda agrupa varios días y no hay nada que distinguir.
 */
export function applyWorkingCalendar(gantt, calendar) {
    const workingDays = new Set(calendar?.working_days ?? [0, 1, 2, 3, 4]);
    const holidays = (calendar?.holidays || []).map((holiday) => ({
        start: new Date(holiday.start),
        end: new Date(holiday.end),
        name: holiday.name,
    }));

    const isHoliday = (date) =>
        holidays.some((holiday) => date >= holiday.start && date <= holiday.end);
    // Odoo numera los días 0 = lunes; JavaScript, 0 = domingo.
    const odooDay = (date) => (date.getDay() + 6) % 7;

    gantt.templates.timeline_cell_class = (task, date) =>
        !workingDays.has(odooDay(date)) || isHoliday(date) ? "algantt-nonworking" : "";
    gantt.templates.scale_cell_class = (date) =>
        !workingDays.has(odooDay(date)) || isHoliday(date) ? "algantt-nonworking-scale" : "";
}

/**
 * Calcula el código EDT (1, 1.1, 1.2…) de cada tarea y lo cachea en la
 * instancia. `getWBSCode` es de la versión de pago, así que se numera aquí
 * recorriendo el árbol; las filas de proyecto no numeran y sus hijas empiezan
 * de nuevo, que es lo que espera quien lee una EDT por obra.
 */
export function computeWbsCodes(gantt) {
    const codes = new Map();
    const walk = (parentId, prefix) => {
        let index = 0;
        for (const childId of gantt.getChildren(parentId) || []) {
            const task = gantt.getTask(childId);
            if (task.al_is_project) {
                walk(childId, "");
                continue;
            }
            index += 1;
            const code = prefix ? `${prefix}.${index}` : String(index);
            codes.set(String(childId), code);
            walk(childId, code);
        }
    };
    walk(gantt.config.root_id ?? 0, "");
    gantt.$algantt_wbs = codes;
    return codes;
}

/** Columna de código EDT. Se alimenta de `computeWbsCodes`. */
export function wbsColumn(gantt) {
    return {
        name: "wbs",
        label: _t("EDT"),
        align: "left",
        width: 70,
        resize: true,
        template: (task) =>
            task.al_is_project ? "" : gantt.$algantt_wbs?.get(String(task.id)) || "",
    };
}

/**
 * Búsqueda rápida: deja visibles las tareas que coinciden y sus ancestros,
 * para no perder el contexto jerárquico. Con texto vacío se muestra todo.
 *
 * La edición MIT no tiene `filterTask` (es de la versión de pago): el filtrado
 * se hace con el evento `onBeforeTaskDisplay`, que se engancha una sola vez.
 *
 * @returns {Number} coincidencias reales (sin contar los ancestros añadidos).
 */
export function applySearch(gantt, term) {
    if (!gantt.$algantt_searchAttached) {
        gantt.attachEvent("onBeforeTaskDisplay", (id) =>
            !gantt.$algantt_matches || gantt.$algantt_matches.has(id)
        );
        gantt.$algantt_searchAttached = true;
    }

    const needle = (term || "").trim().toLowerCase();
    if (!needle) {
        gantt.$algantt_matches = null;
        gantt.render();
        return 0;
    }

    const matches = new Set();
    let hits = 0;
    gantt.eachTask((task) => {
        const haystack = `${task.text || ""} ${task.al_users || ""} ${task.al_stage || ""}`;
        if (!haystack.toLowerCase().includes(needle)) {
            return;
        }
        hits += 1;
        matches.add(task.id);
        // Los ancestros se mantienen para conservar el árbol.
        let parent = gantt.getParent(task.id);
        while (parent && gantt.isTaskExists(parent)) {
            matches.add(parent);
            parent = gantt.getParent(parent);
        }
    });
    gantt.$algantt_matches = matches;
    gantt.render();
    return hits;
}

/** Despliega o pliega todas las ramas del árbol. */
export function toggleAllBranches(gantt, open) {
    gantt.eachTask((task) => {
        task.$open = open;
    });
    gantt.render();
}

/** Pantalla completa (plugin `fullscreen` de la edición MIT). */
export function toggleFullscreen(gantt) {
    if (!gantt.expand || !gantt.collapse) {
        return false;
    }
    if (gantt.getState().fullscreen) {
        gantt.collapse();
        return false;
    }
    gantt.expand();
    return true;
}

/**
 * Indenta la tarea seleccionada: pasa a ser hija del hermano anterior.
 * @returns {Object|null} `{id, parent_id}` a guardar, o null si no aplica.
 */
export function indentTask(gantt, taskId) {
    if (!taskId || !gantt.isTaskExists(taskId)) {
        return null;
    }
    const previous = gantt.getPrevSibling(taskId);
    if (!previous || !gantt.isTaskExists(previous)) {
        return null;
    }
    const previousTask = gantt.getTask(previous);
    if (previousTask.al_is_project || previousTask.al_is_milestone_record) {
        return null;
    }
    return { id: Number(taskId), parent_id: Number(previous) };
}

/** Desindenta: pasa a ser hermana de su padre. */
export function outdentTask(gantt, taskId) {
    if (!taskId || !gantt.isTaskExists(taskId)) {
        return null;
    }
    const parent = gantt.getParent(taskId);
    if (!parent || !gantt.isTaskExists(parent)) {
        return null;
    }
    const grandParent = gantt.getParent(parent);
    const parentTask = gantt.getTask(parent);
    if (parentTask.al_is_project) {
        return null; // ya está en la raíz de su proyecto
    }
    const newParent = grandParent && gantt.isTaskExists(grandParent) ? grandParent : 0;
    const newParentTask = newParent ? gantt.getTask(newParent) : null;
    return {
        id: Number(taskId),
        parent_id: newParentTask && !newParentTask.al_is_project ? Number(newParent) : false,
    };
}

/**
 * Menú contextual sobre una tarea. `actions` es una lista de
 * `{label, icon, disabled, run}`; devuelve una función para desmontarlo.
 */
export function attachContextMenu(gantt, containerEl, buildActions) {
    let menuEl = null;

    const close = () => {
        menuEl?.remove();
        menuEl = null;
    };

    const onContextMenu = (event) => {
        const row = event.target.closest("[task_id], [data-task-id]");
        if (!row) {
            return;
        }
        const taskId = row.getAttribute("task_id") || row.getAttribute("data-task-id");
        if (!taskId || !gantt.isTaskExists(taskId)) {
            return;
        }
        event.preventDefault();
        close();

        const actions = buildActions(taskId, gantt.getTask(taskId));
        if (!actions.length) {
            return;
        }
        menuEl = document.createElement("div");
        menuEl.className = "algantt-context-menu";
        menuEl.style.left = `${event.clientX}px`;
        menuEl.style.top = `${event.clientY}px`;
        for (const action of actions) {
            const item = document.createElement("button");
            item.type = "button";
            item.className = "algantt-context-item";
            item.disabled = Boolean(action.disabled);
            item.textContent = action.label;
            if (action.icon) {
                const icon = document.createElement("i");
                icon.className = `fa ${action.icon} me-2`;
                item.prepend(icon);
            }
            item.addEventListener("click", () => {
                close();
                action.run();
            });
            menuEl.appendChild(item);
        }
        document.body.appendChild(menuEl);
    };

    containerEl.addEventListener("contextmenu", onContextMenu);
    document.addEventListener("click", close);
    document.addEventListener("scroll", close, true);

    return () => {
        containerEl.removeEventListener("contextmenu", onContextMenu);
        document.removeEventListener("click", close);
        document.removeEventListener("scroll", close, true);
        close();
    };
}
