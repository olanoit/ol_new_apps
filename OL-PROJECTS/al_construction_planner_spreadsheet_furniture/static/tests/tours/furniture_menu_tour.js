import { registry } from "@web/core/registry";

/**
 * Paquete 1.16, bloque 4a (M113-03): el maestro de mobiliario tiene su menú
 * «Planificación de obra», sin las opciones del presupuesto; «Validar» llena
 * la pestaña ERRORES común (estado, encabezados con «Ir»).
 */
registry.category("web_tour.tours").add("al_construction_furniture_sheet_menu", {
    steps: () => [
        {
            trigger: "body",
            run: async () => {
                const env = odoo.__WOWL_DEBUG__.root.env;
                const [sheet] = await env.services.orm.searchRead(
                    "documents.document",
                    [["construction_sheet_kind", "=", "furniture"]],
                    ["id"],
                    { limit: 1, order: "id desc" }
                );
                const spreadsheet_id = sheet.id;
                await env.services.action.doAction({
                    type: "ir.actions.client",
                    tag: "action_open_spreadsheet",
                    params: { spreadsheet_id },
                });
            },
        },
        {
            content: "Menú propio del mobiliario",
            trigger: ".o-topbar-menu:contains('Planificación de obra')",
            run: "click",
        },
        {
            content: "Sin las opciones del presupuesto",
            trigger: ".o-menu-item[data-name='construction_furniture_template']",
            run: () => {
                if (document.querySelector(".o-menu-item[data-name^='construction_send_']")) {
                    throw new Error("El menú del presupuesto aparece en el maestro");
                }
            },
        },
        {
            content: "Validar",
            trigger: ".o-menu-item[data-name='construction_furniture_validate']",
            run: "click",
        },
        {
            content: "La hoja vacía no tiene errores",
            trigger: ".o_notification:contains('no tiene errores')",
        },
        {
            content: "La pestaña ERRORES existe",
            trigger: ".o-sheet-list:contains('ERRORES')",
        },
    ],
});
