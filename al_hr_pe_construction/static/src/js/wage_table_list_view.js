/** @odoo-module **/
/**
 * Lista de tablas salariales con el botón «Importar tabla del convenio».
 *
 * Mismo patrón que al_hr_pe_import (hr_salary_rule_list_buttons.xml): en
 * v19 web.ListView.Buttons es una plantilla vacía que el controller llama
 * en el slot layout-buttons, así que el botón va en una plantilla propia.
 */
import { onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";

export class WageTableListController extends ListController {
    setup() {
        super.setup();
        onWillStart(async () => {
            this.canImportWageTable = await user.hasGroup("hr_payroll.group_hr_payroll_manager");
        });
    }

    async onClickImportWageTable() {
        await this.actionService.doAction(
            "al_hr_pe_construction.action_construction_wage_import",
            {
                onClose: async () => {
                    // La tabla nueva llega archivada: se recarga igual por si
                    // el filtro muestra las archivadas.
                    await this.model.load();
                },
            }
        );
    }
}

registry.category("views").add("construction_wage_table_list", {
    ...listView,
    Controller: WageTableListController,
    buttonTemplate: "al_hr_pe_construction.WageTableListView.Buttons",
});
