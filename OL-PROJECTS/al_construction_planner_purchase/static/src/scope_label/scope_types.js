import { registry } from "@web/core/registry";
import { SelectMenu } from "@web/core/select_menu/select_menu";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component } from "@odoo/owl";

/**
 * Selector «Tipo de ambiente» (paquete 1.24, M124-01). Los tipos no son
 * registros: los da la vertical por un gancho del servidor, que los entrega
 * en otro campo del registro como [{key, label, count}]. El valor es la lista
 * de claves elegidas; vacía quiere decir todos.
 */
export class ConstructionScopeTypes extends Component {
    static template = "al_construction_planner_purchase.ScopeTypes";
    static components = { SelectMenu };
    static props = {
        ...standardFieldProps,
        optionsField: { type: String },
        placeholder: { type: String, optional: true },
    };

    get options() {
        return this.props.record.data[this.props.optionsField] || [];
    }

    get value() {
        const offered = new Set(this.options.map((option) => option.key));
        return (this.props.record.data[this.props.name] || []).filter((key) => offered.has(key));
    }

    get choices() {
        return this.options.map((option) => ({
            value: option.key,
            label: option.label,
            count: option.count,
        }));
    }

    get chosen() {
        const value = new Set(this.value);
        return this.options.filter((option) => value.has(option.key));
    }

    onSelect(values) {
        this.props.record.update({ [this.props.name]: values && values.length ? values : false });
    }
}

export const constructionScopeTypes = {
    component: ConstructionScopeTypes,
    supportedTypes: ["json"],
    extractProps: ({ options, placeholder }) => ({
        optionsField: options.options_field,
        placeholder,
    }),
};

registry.category("fields").add("construction_scope_types", constructionScopeTypes);
