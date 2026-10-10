/** @odoo-module **/

import { registry } from "@web/core/registry";

const row = (name) => `.o_cp_tree_row[data-name="${name}"]`;

/**
 * Árbol de recursos (P-02) con el piso 05 de demostración: marcar el piso
 * marca a sus hijos; desmarcar un módulo deja a sus padres en parcial.
 */
registry.category("web_tour.tours").add("al_construction_planner_plan_tree", {
    steps: () => [
        { trigger: `${row("Piso 05")}[data-level="floor"]` },
        { trigger: `${row("Piso 05")} .o_cp_caret`, run: "click" },
        { trigger: `${row("Dpto 501")} .o_cp_caret`, run: "click" },
        { trigger: `${row("Cocina")} .o_cp_caret`, run: "click" },
        { trigger: `.o_cp_tree_row[data-level="module"]` },
        // Marcar el piso marca todo lo que cuelga de él.
        { trigger: `${row("Piso 05")} .o_cp_check`, run: "click" },
        { trigger: `${row("Piso 05")} .o_cp_check.o_cp_on` },
        { trigger: `${row("Dpto 508")} .o_cp_check.o_cp_on` },
        { trigger: `.o_cp_tree_row[data-level="module"] .o_cp_check.o_cp_on` },
        { trigger: `.o_cp_summary_modules:contains(66)` },
        { trigger: `.o_cp_panel_table tbody tr` },
        // Desmarcar un módulo deja al ambiente, al departamento y al piso en parcial.
        { trigger: `.o_cp_tree_row[data-level="module"] .o_cp_check`, run: "click" },
        { trigger: `.o_cp_summary_modules:contains(65)` },
        { trigger: `${row("Dpto 501")} .o_cp_check.o_cp_part` },
        { trigger: `${row("Piso 05")} .o_cp_check.o_cp_part` },
        { trigger: `${row("Dpto 502")} .o_cp_check.o_cp_on` },
        // Quitar la selección deja todo vacío.
        { trigger: `.o_cp_clear`, run: "click" },
        { trigger: `${row("Piso 05")} .o_cp_check.o_cp_off` },
        { trigger: `.o_cp_panel:contains(Marque una obra)` },
    ],
});
