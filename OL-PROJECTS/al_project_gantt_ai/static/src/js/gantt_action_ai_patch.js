/** @odoo-module **/

/**
 * Engancha el panel de IA a la acción de Gantt del backend.
 *
 * Se hace por parche y herencia de plantilla (`t-inherit`) en vez de tocar
 * `al_project_gantt_backend`: el asistente es opcional y desinstalarlo tiene
 * que dejar el diagrama exactamente como estaba.
 */
import { onWillStart } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { GanttAction } from "@al_project_gantt_backend/gantt_action";
import { GanttAiPanel } from "@al_project_gantt_ai/js/gantt_ai_panel";

GanttAction.components = { ...GanttAction.components, GanttAiPanel };

patch(GanttAction.prototype, {
    setup() {
        super.setup();
        this.state.showAi = false;
        this.state.aiStatus = { enabled: false };
        // Ids de las tareas realmente cargadas: es lo que define «lo que se ve»
        // y lo único que se manda al asistente.
        this.state.visibleTaskIds = [];

        onWillStart(async () => {
            // Sin clave configurada el botón no se pinta: el módulo instalado
            // pero sin configurar no debe estorbar.
            this.state.aiStatus = await this.orm.call("al.gantt.ai", "get_status", []);
        });
    },

    applyPayload(payload) {
        super.applyPayload(payload);
        this.state.visibleTaskIds = (payload.tasks || []).map((task) => task.id);
    },

    toggleAiPanel() {
        this.state.showAi = !this.state.showAi;
        // El contenedor pierde ancho al abrirse el panel; sin esto la librería
        // conserva el tamaño anterior y las barras quedan desplazadas.
        setTimeout(() => this.gantt?.setSizes(), 0);
    },

    /** Lo que el panel envía como contexto en cada pregunta. */
    aiContext() {
        return {
            task_ids: this.state.visibleTaskIds,
            project_ids: this.state.selectedIds,
        };
    },

    /**
     * Aplica las propuestas por el mismo camino que la edición manual y
     * recarga: el diagrama nunca muestra algo distinto de lo guardado.
     */
    async applyAiProposals(changeset) {
        await this.saveChanges(changeset);
        this.state.lastSavedAt = new Date().toLocaleTimeString();
        await this.reload();
    },
});
