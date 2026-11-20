import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component } from "@odoo/owl";

/**
 * Etiqueta de un selector de «¿Para qué es el material?» (paquete 1.24,
 * M124-03): el nombre del nivel sale de la plantilla de la obra y su «?»
 * muestra la orientación de ese nivel, que viene en otro campo del registro.
 * El «?» es el mismo de las etiquetas de Odoo (FormLabel): se abre al pasar
 * el mouse y, en el celular, con un toque.
 */
export class ConstructionScopeLabel extends Component {
    static template = "al_construction_planner_purchase.ScopeLabel";
    static props = {
        ...standardFieldProps,
        hintField: { type: String, optional: true },
    };

    get label() {
        return this.props.record.data[this.props.name] || "";
    }

    get hint() {
        return (this.props.hintField && this.props.record.data[this.props.hintField]) || "";
    }
}

export const constructionScopeLabel = {
    component: ConstructionScopeLabel,
    supportedTypes: ["char"],
    extractProps: ({ options }) => ({ hintField: options.hint_field }),
};

registry.category("fields").add("construction_scope_label", constructionScopeLabel);
