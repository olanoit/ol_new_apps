/** @odoo-module **/

/**
 * Inicio de la aplicación (P-01).
 *
 * Obras con su plan, planificado, saldo, avance, próximo hito y estado; al
 * costado, «Pendientes de hoy» según los grupos del usuario. Cada pendiente
 * trae su acción con el filtro ya armado por el servidor
 * (`construction.planner.home.get_home_data`).
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatFloat } from "@web/core/utils/numbers";

const HOME = "construction.planner.home";
const STATE_BADGES = {
    draft: "text-bg-secondary",
    to_approve: "text-bg-warning",
    approved: "text-bg-info",
    in_progress: "text-bg-success",
    closed: "text-bg-dark",
};

export class ConstructionPlannerHome extends Component {
    static template = "al_construction_planner.Home";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null, loading: false });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(HOME, "get_home_data", []);
        } finally {
            this.state.loading = false;
        }
    }

    get works() {
        return this.state.data?.works || [];
    }

    get pending() {
        return this.state.data?.pending || [];
    }

    async openWork(work) {
        const action = await this.orm.call(HOME, "action_open_plan", [work.plan_id]);
        await this.action.doAction(action);
    }

    async openPending(item) {
        await this.action.doAction(item.action, { onClose: () => this.load() });
    }

    async openSchedule(work) {
        await this.action.doAction({
            type: "ir.actions.client",
            tag: "al_construction_planner.schedule_report",
            name: "Cronograma valorizado",
            context: { construction_project_id: work.project_id },
        });
    }

    money(value) {
        if (value === false || value === undefined) {
            return "—";
        }
        return formatFloat(value, { digits: [16, 2] });
    }

    pct(value) {
        if (value === false || value === undefined) {
            return "—";
        }
        return `${formatFloat(value * 100, { digits: [16, 1] })} %`;
    }

    badge(state) {
        return STATE_BADGES[state] || "text-bg-light";
    }
}

registry.category("actions").add("al_construction_planner.home", ConstructionPlannerHome);
