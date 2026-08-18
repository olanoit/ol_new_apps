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
 */
import { fromUserDate } from "@al_project_gantt_base/js/gantt_adapter";
import { lightboxValues } from "@al_project_gantt_base/js/gantt_lightbox";

/** Prefijo de las filas que no son tareas reales (proyectos, hitos). */
function isRealTask(id) {
    return typeof id === "number" || /^\d+$/.test(String(id));
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
                task.start_date = new Date(moved.start);
                task.end_date = new Date(moved.end);
                this.gantt.updateTask(moved.id);
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

        this.eventIds.push(
            gantt.attachEvent("onAfterTaskUpdate", (id, task) => {
                if (this._ignore(id)) {
                    return true;
                }
                const values = { id: Number(id), name: task.text };
                if (task.start_date && task.end_date) {
                    values.start = this._iso(task.start_date);
                    values.end = this._iso(task.end_date);
                }
                if (typeof task.progress === "number") {
                    values.progress = Math.round(task.progress * 100);
                }
                values.parent_id = isRealTask(task.parent) ? Number(task.parent) : false;
                // Campos del formulario (etapa, responsables, prioridad…).
                Object.assign(values, lightboxValues(task));
                this._enqueue({
                    tasks: { update: [values] },
                    reschedule_chain: Boolean(this.options.rescheduleChain?.()),
                });
                return true;
            })
        );

        this.eventIds.push(
            gantt.attachEvent("onAfterTaskAdd", (id, task) => {
                if (this.suspended) {
                    return true;
                }
                const projectId =
                    (isRealTask(task.parent) && this.gantt.getTask(task.parent)?.al_project_id) ||
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
        this.eventIds.push(
            gantt.attachEvent("onBeforeTaskDrag", (id) => isRealTask(id))
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
    gantt.config.drag_progress = true;
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
