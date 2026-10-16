/** @odoo-module **/

/**
 * Filtro de etapas en árbol (v1.8, M18-02), común al árbol de recursos y al
 * cronograma. El servidor manda el árbol (`construction.stage._get_tree`):
 * cada nodo trae las hojas que cubre. El filtro guarda solo códigos hoja:
 * marcar una etapa padre marca sus sub etapas y desmarcar una sub etapa deja
 * a la padre en selección parcial.
 */

/** Estado de la casilla de un nodo: "on", "part" u "off". */
export function stageNodeState(node, selected) {
    const leaves = node.leaves || [node.code];
    const count = leaves.filter((code) => selected.includes(code)).length;
    if (!count) {
        return "off";
    }
    return count === leaves.length ? "on" : "part";
}

/** Marca o desmarca un nodo y devuelve la nueva lista de hojas marcadas. */
export function toggleStageNode(node, selected) {
    const leaves = node.leaves || [node.code];
    if (stageNodeState(node, selected) === "on") {
        return selected.filter((code) => !leaves.includes(code));
    }
    return [...selected, ...leaves.filter((code) => !selected.includes(code))];
}

/** Texto corto del filtro para el botón: «Todas las etapas» o la cantidad. */
export function stageFilterLabel(tree, selected, allLabel) {
    if (!selected.length) {
        return allLabel;
    }
    const groups = tree.filter((node) => stageNodeState(node, selected) === "on");
    // La etapa más alta totalmente marcada resume a sus hijas.
    const top = groups.filter(
        (node) => !node.parent || !groups.some((other) => other.code === node.parent)
    );
    return top.map((node) => node.label).join(", ") || allLabel;
}
