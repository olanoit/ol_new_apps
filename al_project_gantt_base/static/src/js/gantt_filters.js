/** @odoo-module **/

/**
 * Estado de los filtros y su traducción a las `options` del contrato de datos.
 *
 * Compartido por las dos interfaces: el backend lo guarda en un `useState` de
 * OWL y el website en una propiedad de la interacción, pero las reglas (qué es
 * un filtro activo, cómo se serializa, cómo se limpia) son las mismas.
 */

/** Filtros vacíos: ningún criterio aplicado. */
export function emptyFilters() {
    return {
        userIds: [],
        states: [],
        dateFrom: "",
        dateTo: "",
        includeUndated: false,
    };
}

/**
 * Traduce el estado de filtros a las `options` que espera
 * `project.project.get_gantt_data()`. Solo se envía lo que está informado.
 */
export function filtersToOptions(filters) {
    const options = {};
    if (filters.userIds?.length) {
        options.user_ids = filters.userIds.map(Number);
    }
    if (filters.states?.length) {
        options.states = [...filters.states];
    }
    // Los <input type="date"> dan "AAAA-MM-DD"; el servidor compara contra
    // campos Datetime, así que se cubre el día completo.
    if (filters.dateFrom) {
        options.date_from = `${filters.dateFrom} 00:00:00`;
    }
    if (filters.dateTo) {
        options.date_to = `${filters.dateTo} 23:59:59`;
    }
    if (filters.includeUndated) {
        options.include_undated = true;
    }
    return options;
}

/** Número de criterios activos, para el contador del botón «Filtros». */
export function countActiveFilters(filters) {
    let count = 0;
    if (filters.userIds?.length) {
        count += 1;
    }
    if (filters.states?.length) {
        count += 1;
    }
    if (filters.dateFrom || filters.dateTo) {
        count += 1;
    }
    if (filters.includeUndated) {
        count += 1;
    }
    return count;
}

/** Valores seleccionados de un `<select multiple>`. */
export function selectedValues(selectEl) {
    if (!selectEl) {
        return [];
    }
    return [...selectEl.selectedOptions].map((option) => option.value);
}

/** ¿El rango de fechas está invertido? (desde > hasta) */
export function isInvalidRange(filters) {
    return Boolean(filters.dateFrom && filters.dateTo && filters.dateFrom > filters.dateTo);
}
