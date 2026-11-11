import { registry } from "@web/core/registry";

/**
 * Correcciones del tablero de control semanal de instalación (paquete 1.19):
 * recorre la obra elegida, el clic en una celda y en el número de un piso,
 * Producción, «Desde» y «Hasta», cada atajo y el indicador de mano de obra. El
 * recorrido falla si aparece un error.
 */
const pick = (selector, value) => ({
    trigger: selector,
    run: () => {
        const select = document.querySelector(selector);
        select.value = String(value);
        select.dispatchEvent(new Event("change", { bubbles: true }));
    },
});

registry.category("web_tour.tours").add("al_construction_installation_board", {
    steps: () => [
        {
            trigger: "body",
            run: async () => {
                const env = odoo.__WOWL_DEBUG__.root.env;
                const [project] = await env.services.orm.searchRead(
                    "project.project",
                    [["name", "=", "Obra tablero (test)"]],
                    ["id"]
                );
                await env.services.action.doAction({
                    type: "ir.actions.client",
                    tag: "al_construction_installation_board",
                    params: { project_id: project.id },
                });
            },
        },
        { content: "El edificio de la obra", trigger: ".o_cib_table .o_cib_cell" },
        {
            content: "CT-02: del piso más alto al más bajo",
            trigger: ".o_cib_table",
            run: () => {
                const floors = [...document.querySelectorAll(".o_cib_floor")].map((el) => el.textContent.trim());
                if (floors.indexOf("Piso 05") > floors.indexOf("Piso 01")) {
                    throw new Error(`Orden de los pisos: ${floors.join(", ")}`);
                }
            },
        },
        {
            content: "Clic en una celda",
            trigger: ".o_cib_table .o_cib_cell",
            run: "click",
        },
        {
            content: "CT-05: la radiografía sin «Piso Piso»",
            trigger: ".o_cib_xray_title:contains('Piso 05 ·')",
            run: () => {
                if (document.querySelector(".o_cib_xray_title").textContent.includes("Piso Piso")) {
                    throw new Error("El nombre del piso repite «Piso»");
                }
            },
        },
        {
            content: "CT-01: clic en el número del piso, sin error",
            trigger: ".o_cib_floor:contains('Piso 05')",
            run: "click",
        },
        { trigger: ".o_cib_side .o_cib_units tbody tr" },
        {
            content: "Producción prendida cambia el título (CT-03)",
            trigger: ".o_cib_toggle_production",
            run: "click",
        },
        { trigger: ".o_cib_title:contains('producción e instalación')" },
        { trigger: ".o_cib_toggle_production", run: "click" },
        { trigger: ".o_cib_title:contains('Control semanal de instalación')" },
        pick(".o_cib_from", 1),
        pick(".o_cib_to", 2),
        { trigger: ".o_cib_shortcut_one", run: "click" },
        { trigger: ".o_cib_shortcut_four", run: "click" },
        { trigger: ".o_cib_shortcut_all", run: "click" },
        { trigger: ".o_cib_shortcut_all.o_cib_active" },
        { trigger: ".o_cib_toggle_production", run: "click" },
        { trigger: ".o_cib_title:contains('producción e instalación')" },
        { trigger: ".o_cib_floor:contains('Piso 05')", run: "click" },
        { trigger: ".o_cib_floor_selected" },
        {
            content: "El indicador de mano de obra abre el control semanal",
            trigger: ".o_cib_kpi_labor",
            run: "click",
        },
        { trigger: ".o_list_view, .o_view_nocontent" },
        {
            content: "Volver por la ruta",
            trigger: ".o_breadcrumb a:first, .breadcrumb-item a:first",
            run: "click",
        },
        {
            content: "El tablero conserva el período, las etapas y el piso elegido",
            trigger: ".o_cib_title:contains('producción e instalación')",
            run: () => {
                if (!document.querySelector(".o_cib_shortcut_all.o_cib_active")) {
                    throw new Error("El tablero no conservó el período");
                }
                if (!document.querySelector(".o_cib_floor_selected")) {
                    throw new Error("El tablero no conservó el piso elegido");
                }
            },
        },
    ],
});
