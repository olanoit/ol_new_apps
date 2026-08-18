/** @odoo-module **/

/**
 * Panel de chat del asistente de IA.
 *
 * No sabe nada del diagrama: recibe por props una función que le dice qué
 * tareas se están viendo y otra para aplicar un changeset. Toda la lógica de
 * datos, prompt y validación está en el servidor (`al.gantt.ai`); aquí solo hay
 * conversación y revisión de propuestas.
 */
import { Component, onPatched, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class GanttAiPanel extends Component {
    static template = "al_project_gantt_ai.GanttAiPanel";
    static props = {
        // () => ({ task_ids, project_ids }) — lo que se está viendo ahora mismo.
        getContext: Function,
        // (changeset) => Promise — reutiliza la escritura del módulo base.
        applyProposals: Function,
        close: Function,
        status: { type: Object, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.scrollRef = useRef("scroll");
        this.inputRef = useRef("input");

        this.state = useState({
            messages: [],
            input: "",
            loading: false,
        });

        // Al llegar una respuesta el panel debe quedar abajo del todo.
        onPatched(() => {
            if (this.pendingScroll && this.scrollRef.el) {
                this.scrollRef.el.scrollTop = this.scrollRef.el.scrollHeight;
                this.pendingScroll = false;
            }
        });
    }

    get modelLabel() {
        const status = this.props.status || {};
        return status.model ? `${status.provider} · ${status.model}` : "";
    }

    get suggestions() {
        return [
            _t("¿Qué tareas van con retraso?"),
            _t("¿Hay solapamientos en la ruta crítica?"),
            _t("Reparte mejor la carga del próximo mes"),
        ];
    }

    onInput(event) {
        this.state.input = event.target.value;
    }

    onKeydown(event) {
        // Enter envía; Mayús+Enter salta de línea, como en cualquier chat.
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            this.send();
        }
    }

    useSuggestion(text) {
        this.state.input = text;
        this.inputRef.el?.focus();
    }

    /**
     * Historial que se reenvía al servidor: solo texto, sin propuestas.
     *
     * Las propuestas ya aplicadas no se repiten: la siguiente pregunta llevará
     * el estado real de las tareas en el contexto, que es más fiable que el
     * recuerdo de lo que se propuso.
     */
    buildHistory() {
        return this.state.messages
            .filter((message) => !message.error && message.text)
            .map((message) => ({ role: message.role, content: message.text }));
    }

    async send() {
        const question = this.state.input.trim();
        if (!question || this.state.loading) {
            return;
        }
        const history = this.buildHistory();
        this.state.messages.push({ role: "user", text: question });
        this.state.input = "";
        this.state.loading = true;
        this.pendingScroll = true;

        try {
            const context = this.props.getContext();
            const result = await this.orm.call("al.gantt.ai", "ask", [
                {
                    question,
                    history,
                    task_ids: context.task_ids,
                    project_ids: context.project_ids,
                },
            ]);
            this.state.messages.push({
                role: "assistant",
                text: result.answer || "",
                summary: result.summary || "",
                proposals: (result.proposals || []).map((proposal) => ({
                    ...proposal,
                    selected: true,
                })),
                warnings: result.warnings || [],
                applied: false,
            });
        } catch (error) {
            // El error se muestra dentro de la conversación en lugar de abrir el
            // diálogo de Odoo: no es un fallo de la vista, es una respuesta.
            this.state.messages.push({
                role: "assistant",
                error: true,
                text: error?.data?.message || error?.message || _t("No se pudo consultar al asistente."),
                proposals: [],
                warnings: [],
            });
        } finally {
            this.state.loading = false;
            this.pendingScroll = true;
        }
    }

    toggleProposal(proposal) {
        proposal.selected = !proposal.selected;
    }

    selectedCount(message) {
        return (message.proposals || []).filter((proposal) => proposal.selected).length;
    }

    /**
     * Aplica lo marcado a través del contrato de escritura del módulo base:
     * el servidor vuelve a comprobar los permisos de cada tarea, así que una
     * propuesta sobre algo que el usuario no puede tocar se rechaza aquí igual
     * que si hubiera arrastrado la barra.
     */
    async applySelected(message) {
        const selected = (message.proposals || []).filter((proposal) => proposal.selected);
        if (!selected.length) {
            this.notification.add(_t("Marque al menos una propuesta."), { type: "warning" });
            return;
        }
        this.state.loading = true;
        try {
            await this.props.applyProposals({
                tasks: { update: selected.map((proposal) => proposal.values) },
            });
            message.applied = true;
            this.notification.add(
                selected.length === 1
                    ? _t("Se aplicó 1 cambio.")
                    : _t("Se aplicaron %s cambios.", selected.length),
                { type: "success" }
            );
        } finally {
            this.state.loading = false;
        }
    }

    clear() {
        this.state.messages = [];
    }
}
