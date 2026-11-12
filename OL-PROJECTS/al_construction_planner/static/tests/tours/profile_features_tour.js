import { registry } from "@web/core/registry";

/**
 * Paquete 1.20, M120-07: se apaga «Valorización por avance» en el perfil, se
 * aplica a la compañía (la aplicación se recarga) e Ingresos ya no muestra
 * las valorizaciones. Falla si un clic da error.
 */
registry.category("web_tour.tours").add("al_construction_profile_features", {
    steps: () => [
        {
            trigger: "body",
            run: async () => {
                const env = odoo.__WOWL_DEBUG__.root.env;
                const [profile] = await env.services.orm.searchRead(
                    "construction.vertical.profile",
                    [["code", "=", "construction"]],
                    ["id"]
                );
                await env.services.action.doAction({
                    type: "ir.actions.act_window",
                    res_model: "construction.vertical.profile",
                    res_id: profile.id,
                    views: [[false, "form"]],
                });
            },
        },
        {
            content: "Las seis funciones nuevas están en el perfil",
            trigger: "div[name=feature_installation_board]",
        },
        {
            content: "Apagar «Valorización por avance»",
            trigger: "div[name=feature_valuation] input:checked",
            run: "click",
        },
        { trigger: "div[name=feature_valuation] input:not(:checked)" },
        { trigger: ".o_form_button_save", run: "click" },
        { trigger: ".o_form_saved" },
        { trigger: "button[name=action_open_apply_wizard]", run: "click" },
        {
            content: "La tabla de cambios dice qué se oculta, con la ruta del menú",
            trigger: ".modal td:contains('Ingresos › Valorizaciones')",
        },
        {
            content: "Aplicar: la aplicación se recarga",
            trigger: ".modal button[name=action_confirm]",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Al recargar, Ingresos no tiene las valorizaciones",
            trigger: ".o_main_navbar",
            run: async () => {
                window.location.href = "/odoo/action-al_construction_planner.action_construction_planner_home";
            },
            expectUnloadPage: true,
        },
        { trigger: ".o_menu_sections button:contains('Ingresos')", run: "click" },
        {
            trigger: ".o-dropdown--menu .dropdown-item",
            run: () => {
                const items = [...document.querySelectorAll(".o-dropdown--menu .dropdown-item")]
                    .map((el) => el.textContent.trim());
                for (const name of ["Preparar valorización", "Valorizaciones", "Metas de valorización"]) {
                    if (items.includes(name)) {
                        throw new Error(`Ingresos todavía muestra «${name}»`);
                    }
                }
            },
        },
    ],
});
