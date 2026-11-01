import { registry } from "@web/core/registry";

/**
 * Paquete 1.16, bloque 4b (M113-04/05): «Importar Excel a la hoja» sube un
 * libro, revisa, importa y la hoja escribe el archivo ampliando sus filas.
 */
registry.category("web_tour.tours").add("al_construction_furniture_sheet_import", {
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
                await env.services.action.doAction({
                    type: "ir.actions.client",
                    tag: "action_open_spreadsheet",
                    params: { spreadsheet_id: sheet.id },
                });
            },
        },
        {
            trigger: ".o-topbar-menu:contains('Planificación de obra')",
            run: "click",
        },
        {
            trigger: ".o-menu-item[data-name='construction_furniture_import']",
            run: "click",
        },
        {
            content: "Subir el libro",
            trigger: ".modal .o_field_binary input[type=file]:not(:visible)",
            run: async () => {
                const env = odoo.__WOWL_DEBUG__.root.env;
                const [attachment] = await env.services.orm.searchRead(
                    "ir.attachment",
                    [["name", "=", "al_sheet_import_tour.xlsx"]],
                    ["datas"],
                    { limit: 1 }
                );
                const bytes = Uint8Array.from(atob(attachment.datas), (c) => c.charCodeAt(0));
                const file = new File([bytes], "carga_tour.xlsx", {
                    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                });
                const input = document.querySelector(".modal .o_field_binary input[type=file]");
                const transfer = new DataTransfer();
                transfer.items.add(file);
                input.files = transfer.files;
                input.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        {
            content: "Revisión del archivo",
            trigger: ".modal td:contains('ARBOL')",
        },
        {
            trigger: ".modal button[name='action_import']",
            run: "click",
        },
        {
            content: "La hoja escribió el archivo y validó",
            trigger: ".o_notification:contains('Importado de carga_tour.xlsx')",
        },
        {
            content: "El servidor recibió lo escrito en la hoja",
            trigger: "body",
            run: async () => {
                const orm = odoo.__WOWL_DEBUG__.root.env.services.orm;
                for (let attempt = 0; attempt < 40; attempt++) {
                    const count = await orm.searchCount("spreadsheet.revision", [
                        ["res_model", "=", "documents.document"],
                        ["commands", "ilike", "Dpto 14"],
                    ]);
                    if (count) {
                        return;
                    }
                    await new Promise((resolve) => setTimeout(resolve, 250));
                }
                throw new Error("La hoja no guardó las filas importadas");
            },
        },
    ],
});
