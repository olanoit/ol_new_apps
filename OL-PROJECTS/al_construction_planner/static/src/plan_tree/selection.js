/** @odoo-module **/

/**
 * Selección en cascada del árbol de recursos (P-02), sin dependencias de OWL
 * para poder probarla aparte.
 *
 * `selected` guarda solo los nodos marcados «de más arriba»: marcar un nodo
 * marca implícitamente todos sus descendientes, aunque aún no estén cargados.
 * El servidor expande esa lista con `child_of`.
 *
 * Cada nodo conoce su `path` (claves de sus ancestros, de la obra hacia
 * abajo) y, si ya se cargaron, sus `children`.
 */

/** Estado de la casilla de un nodo: "on", "part" u "off". */
export function checkState(nodes, selected, key) {
    const node = nodes[key];
    if (!node) {
        return "off";
    }
    if (selected[key] || node.path.some((ancestor) => selected[ancestor])) {
        return "on";
    }
    for (const other of Object.keys(selected)) {
        if (nodes[other]?.path.includes(key)) {
            return "part";
        }
    }
    return "off";
}

/**
 * Marca o desmarca un nodo y devuelve la nueva selección.
 * - Marcar: el nodo entra y salen sus descendientes marcados; si con eso
 *   todos los hermanos quedan marcados, se marca el padre (y así hacia arriba).
 * - Desmarcar un nodo cubierto por un ancestro marcado: el ancestro sale y
 *   entran los hermanos de cada nivel del camino hasta el nodo.
 */
export function toggleNode(nodes, selected, key) {
    const result = { ...selected };
    const node = nodes[key];
    if (!node) {
        return result;
    }
    if (checkState(nodes, result, key) === "on") {
        const chain = [...node.path, key];
        const owner = chain.find((k) => result[k]);
        delete result[owner];
        const start = chain.indexOf(owner);
        for (let i = start; i < chain.length - 1; i++) {
            const keep = chain[i + 1];
            for (const child of nodes[chain[i]].children || []) {
                if (child !== keep) {
                    result[child] = true;
                }
            }
        }
        return result;
    }
    for (const other of Object.keys(result)) {
        if (nodes[other]?.path.includes(key)) {
            delete result[other];
        }
    }
    result[key] = true;
    // Si todos los hijos de un padre quedan marcados, se marca el padre.
    let parentKey = node.path[node.path.length - 1];
    while (parentKey) {
        const parent = nodes[parentKey];
        const children = parent?.children || [];
        if (!children.length || !children.every((child) => result[child])) {
            break;
        }
        for (const child of children) {
            delete result[child];
        }
        result[parentKey] = true;
        parentKey = parent.path[parent.path.length - 1];
    }
    return result;
}

/** Claves de la selección efectiva (las de más arriba). */
export function effectiveSelection(nodes, selected) {
    return Object.keys(selected).filter(
        (key) => !nodes[key]?.path.some((ancestor) => selected[ancestor])
    );
}
