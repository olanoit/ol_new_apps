/**
 * Paquete 1.20, M120-08: los botones de acción del plan de recursos en dos
 * grupos, «Programar ▾» y «Ejecutar ▾», como en el Cronograma. Las opciones las
 * manda el servidor (``construction_header_actions``) con su grupo, su estado y
 * las de cada puente; un grupo sin opciones no se muestra.
 */
import { Component } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

export class ConstructionPlanActions extends Component {
    static template = "al_construction_planner.ConstructionPlanActions";
    static components = { Dropdown, DropdownItem };
    static props = { ...standardWidgetProps };

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.menus = [
            { key: "program", label: _t("Programar") },
            { key: "execute", label: _t("Ejecutar") },
        ];
    }

    items(menu) {
        return (this.props.record.data.construction_header_actions || []).filter(
            (item) => item.menu === menu
        );
    }

    async run(item) {
        const record = this.props.record;
        if (!(await record.save())) {
            return;
        }
        const reload = () => record.load();
        if (item.kind === "object") {
            const result = await this.orm.call(record.resModel, item.target, [[record.resId]]);
            if (result && typeof result === "object") {
                await this.action.doAction(result, { onClose: reload });
            } else {
                await reload();
            }
            return;
        }
        await this.action.doAction(item.action_id, {
            additionalContext: {
                default_plan_id: record.resId,
                active_id: record.resId,
                active_ids: [record.resId],
                active_model: record.resModel,
            },
            onClose: reload,
        });
    }
}

registry.category("view_widgets").add("construction_plan_actions", {
    component: ConstructionPlanActions,
});
