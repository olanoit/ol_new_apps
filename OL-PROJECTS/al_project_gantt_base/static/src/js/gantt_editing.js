/** @odoo-module **/

/**
 * Edición del diagrama, compartida por las dos interfaces.
 *
 * Traduce los eventos de dhtmlxGantt (arrastrar, redimensionar, editar, crear,
 * borrar, enlazar) al *changeset* que entiende
 * `project.project.apply_gantt_changes()`. No conoce ni OWL ni el frontend: la
 * interfaz solo aporta dos funciones, `save` y `onError`.
 *
 * Principios:
 * - **El servidor manda.** Si una escritura falla, la interfaz recarga; nunca
 *   se deja el diagrama mostrando algo que no está guardado.
 * - **Sin bucles.** Los cambios que devuelve el servidor (reprogramación en
 *   cadena, ids reales de tareas nuevas) se aplican con los eventos
 *   suspendidos.
 * - **Solo lo que cambió.** Cada tarea guarda al cargarse una foto de sus
 *   valores (`al_orig`) y se envía la diferencia. Enviarlo todo en cada
 *   arrastre pisaba cambios concurrentes y, peor, quitaba el padre a las
 *   subtareas cuyo padre quedó fuera de la vista (filtro o límite): en el
 *   diagrama cuelgan de la raíz y eso se guardaba como `parent_id: false`.
 */
import { fromUserDate, toUserDate } from "@al_project_gantt_base/js/gantt_adapter";
import { lightboxValues } from "@al_project_gantt_base/js/gantt_lightbox";

/** Prefijo de las filas que no son tareas reales (proyectos, hitos). */
function isRealTask(id) {
    return typeof id === "number" || /^\d+$/.test(String(id));
}

/** Filas de proyecto sintéticas del adaptador: `p<id>`. */
function syntheticProjectId(id) {
    const match = /^p(\d+)$/.exec(String(id ?? ""));
    return match ? Number(match[1]) : null;
}

/** Comparación estable (los many2many pueden llegar en otro orden). */
function sameValue(a, b) {
    const norm = (value) =>
        Array.isArray(value) ? [...value].map(Number).sort((x, y) => x - y) : value ?? null;
    return JSON.stringify(norm(a)) === JSON.stringify(norm(b));
}

export class GanttEditor {
    /**
     * @param {Object} gantt instancia de la librería
     * @param {Object} options
     * @param {Function} options.save async (changeset) => resultado del servidor
     * @param {Function} options.onError (error) => void
     * @param {Function} options.onSaved (result) => void
     * @param {String}   options.timeZone zona del usuario de Odoo
     * @param {Function} options.defaultProjectId () => id para las tareas nuevas
     * @param {Boolean}  options.rescheduleChain empujar sucesoras al mover
     * @param {Boolean}  options.canEditProgress el avance se puede guardar
     * @param {Function} [options.canDragRow] (id, mode, event) => bool, para
     *        filas que no son tareas (por defecto no se arrastran)
     */
    constructor(gantt, options) {
        this.gantt = gantt;
        this.options = options;
        this.suspended = false;
        this.eventIds = [];
        this.pending = Promise.resolve();
    }

    /** ¿Debe ignorarse este evento? (filas sintéticas o cambios del servidor) */
    _ignore(id) {
        return this.suspended || !isRealTask(id);
    }

    _iso(date) {
        return fromUserDate(date, this.options.timeZone);
    }

    /**
     * Valores de la tarea en el formato del changeset. El avance puede
     * cambiar por dos vías (arrastre de la barra o formulario): gana la que
     * se movió respecto de la foto, y las dos quedan sincronizadas.
     */
    _currentValues(task, orig = null) {
        const values = { name: task.text };
        if (task.start_date && task.end_date && !task.unscheduled) {
            values.start = this._iso(task.start_date);
            values.end = this._iso(task.end_date);
        }
        values.parent_id = isRealTask(task.parent) ? Number(task.parent) : false;
        const form = lightboxValues(task);
        const formProgress = form.progress;
        delete form.progress;
        Object.assign(values, form);
        const dragProgress = Math.round((task.progress || 0) * 100);
        if (orig && formProgress !== undefined && formProgress !== orig.progress) {
            values.progress = formProgress;
            task.progress = formProgress / 100;
        } else {
            values.progress = dragProgress;
            task.al_progress_pct = dragProgress;
        }
        return values;
    }

    /** Foto de referencia de una tarea (al cargar o tras guardarla). */
    _remember(task) {
        task.al_orig = this._currentValues(task);
    }

    /** Diferencia contra la foto; `null` si no cambió nada que guardar. */
    _diff(id, task) {
        const orig = task.al_orig || {};
        const current = this._currentValues(task, task.al_orig || null);
        const values = {};
        for (const [key, value] of Object.entries(current)) {
            if (!sameValue(value, orig[key])) {
                values[key] = value;
            }
        }
        // Sin foto (no debería pasar), una huérfana nunca pierde su padre real.
        if (!task.al_orig && task.al_orphaned) {
            delete values.parent_id;
        }
        // Sin campo de avance editable el valor es derivado: no se envía.
        if (!this.options.canEditProgress) {
            delete values.progress;
        }
        task.al_orig = current;
        return Object.keys(values).length ? { id: Number(id), ...values } : null;
    }

    /** Encola la escritura: evita carreras entre dos arrastres seguidos. */
    _enqueue(changeset) {
        this.pending = this.pending
            .then(() => this.options.save(changeset))
            .then((result) => {
                this._applyServerResult(result);
                this.options.onSaved?.(result);
                return result;
            })
            .catch((error) => {
                this.options.onError?.(error);
            });
        return this.pending;
    }

    /**
     * Aplica al diagrama lo que decidió el servidor: ids reales de las tareas
     * nuevas y fechas de las tareas reprogramadas en cadena.
     */
    _applyServerResult(result) {
        if (!result) {
            return;
        }
        this.suspended = true;
        try {
            for (const [tempId, realId] of Object.entries(result.created || {})) {
                if (this.gantt.isTaskExists(tempId)) {
                    this.gantt.changeTaskId(tempId, realId);
                }
            }
            for (const moved of result.rescheduled || []) {
                if (!this.gantt.isTaskExists(moved.id)) {
                    continue;
                }
                const task = this.gantt.getTask(moved.id);
                // Hora de pared del usuario de Odoo, igual que en la carga.
                task.start_date = toUserDate(moved.start, this.options.timeZone);
                task.end_date = toUserDate(moved.end, this.options.timeZone);
                this.gantt.updateTask(moved.id);
                this._remember(task);
            }
            if ((result.rescheduled || []).length) {
                this.gantt.render();
            }
        } finally {
            this.suspended = false;
        }
    }

    // ------------------------------------------------------------------
    // Enganche de eventos
    // ------------------------------------------------------------------
    attach() {
        const gantt = this.gantt;

        // Foto de cada tarea tal como llega del servidor (en cada carga).
        this.eventIds.push(
            gantt.attachEvent("onTaskLoading", (task) => {
                if (isRealTask(task.id)) {
                    this._remember(task);
                }
                return true;
            })
        );

        this.eventIds.push(
            gantt.attachEvent("onAfterTaskUpdate", (id, task) => {
                if (this._ignore(id)) {
                    return true;
                }
                const values = this._diff(id, task);
                if (!values) {
                    return true;
                }
                this._enqueue({
                    tasks: { update: [values] },
                    reschedule_chain: Boolean(
                        ("start" in values || "end" in values) && this.options.rescheduleChain?.()
                    ),
                });
                return true;
            })
        );

        this.eventIds.push(
            gantt.attachEvent("onAfterTaskAdd", (id, task) => {
                if (this.suspended) {
                    return true;
                }
                // Proyecto de la tarea nueva: el de su padre real, el de la fila
                // de proyecto donde se creó (`p<id>`), el que traiga la propia
                // tarea y, solo en último caso, el primero seleccionado.
                const projectId =
                    (isRealTask(task.parent) && this.gantt.getTask(task.parent)?.al_project_id) ||
                    syntheticProjectId(task.parent) ||
                    task.al_project_id ||
                    this.options.defaultProjectId?.();
                if (!projectId) {
                    this.options.onError?.(
                        new Error("No se pudo determinar el proyecto de la tarea nueva.")
                    );
                    return true;
                }
                this._enqueue({
                    tasks: {
                        create: [
                            {
                                temp_id: String(id),
                                project_id: projectId,
                                name: task.text,
                                start: task.start_date ? this._iso(task.start_date) : null,
                                end: task.end_date ? this._iso(task.end_date) : null,
                                parent_id: isRealTask(task.parent) ? Number(task.parent) : false,
                                ...lightboxValues(task),
                            },
                        ],
                    },
                });
                this._remember(task);
                return true;
            })
        );

        this.eventIds.push(
            gantt.attachEvent("onAfterTaskDelete", (id) => {
                if (this._ignore(id)) {
                    return true;
                }
                this._enqueue({ tasks: { delete: [Number(id)] } });
                return true;
            })
        );

        this.eventIds.push(
            gantt.attachEvent("onAfterLinkAdd", (id, link) => {
                if (this.suspended || !isRealTask(link.source) || !isRealTask(link.target)) {
                    return true;
                }
                this._enqueue({
                    links: { create: [{ source: Number(link.source), target: Number(link.target) }] },
                });
                return true;
            })
        );

        this.eventIds.push(
            gantt.attachEvent("onAfterLinkDelete", (id, link) => {
                if (this.suspended || !isRealTask(link.source) || !isRealTask(link.target)) {
                    return true;
                }
                this._enqueue({
                    links: { delete: [{ source: Number(link.source), target: Number(link.target) }] },
                });
                return true;
            })
        );

        // Las filas de proyecto y los hitos de `project.milestone` no son
        // tareas: no se pueden arrastrar ni borrar desde aquí.
        // `canDragRow` deja a la interfaz arrastrar filas propias que no son
        // tareas (p. ej. etapas de otro modelo); el guardado lo hace ella con
        // su propio `onAfterTaskUpdate`, porque aquí esas filas se ignoran.
        this.eventIds.push(
            gantt.attachEvent("onBeforeTaskDrag", (id, mode, event) =>
                isRealTask(id) || Boolean(this.options.canDragRow?.(id, mode, event))
            )
        );
        this.eventIds.push(
            gantt.attachEvent("onBeforeTaskDelete", (id) => isRealTask(id))
        );
        this.eventIds.push(
            gantt.attachEvent("onBeforeLinkAdd", (id, link) =>
                isRealTask(link.source) && isRealTask(link.target)
            )
        );
    }

    detach() {
        for (const eventId of this.eventIds) {
            this.gantt.detachEvent(eventId);
        }
        this.eventIds = [];
    }
}

/**
 * Activa la edición sobre una instancia ya configurada.
 * Devuelve el editor (para poder desengancharlo al desmontar).
 */
export function enableEditing(gantt, options) {
    gantt.config.readonly = false;
    // Arrastrar el avance solo si se puede guardar (campo real y escribible).
    gantt.config.drag_progress = Boolean(options.canEditProgress);
    gantt.config.drag_links = true;
    gantt.config.details_on_dblclick = true;
    gantt.config.order_branch = false;
    // La columna «+» añade subtareas; el botón de la barra crea tareas raíz.
    const columns = gantt.config.columns || [];
    if (!columns.some((column) => column.name === "add")) {
        columns.push({ name: "add", label: "", width: 36 });
        gantt.config.columns = columns;
    }
    const editor = new GanttEditor(gantt, options);
    editor.attach();
    return editor;
}
