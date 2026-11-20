import { registry } from "@web/core/registry";
import {
    Many2ManyTagsField,
    many2ManyTagsField,
} from "@web/views/fields/many2many_tags/many2many_tags_field";

/**
 * Selector de nivel de «¿Para qué es el material?» (paquete 1.24, M124-02).
 * La lista muestra cada opción con su camino («Piso 19 · 1907 · Closet 2 ·
 * CL-09», el nombre que arma el servidor con el contexto del campo) y la
 * etiqueta elegida, el texto corto («1907 · Closet 2»).
 */
export class ConstructionScopeTags extends Many2ManyTagsField {
    getTagProps(record) {
        const props = super.getTagProps(record);
        props.text = record.data.construction_scope_short_name || props.text;
        return props;
    }
}

export const constructionScopeTags = {
    ...many2ManyTagsField,
    component: ConstructionScopeTags,
    relatedFields: (fieldInfo) => [
        ...many2ManyTagsField.relatedFields(fieldInfo),
        { name: "construction_scope_short_name", type: "char" },
    ],
};

registry.category("fields").add("construction_scope_tags", constructionScopeTags);
