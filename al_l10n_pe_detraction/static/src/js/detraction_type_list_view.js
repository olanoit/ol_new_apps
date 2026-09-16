/** @odoo-module **/
/**
 * Catálogo de detracciones con el botón «Contrastar con SUNAT».
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

export class DetractionTypeListController extends ListController {
    setup() {
        super.setup();
        onWillStart(async () => {
            this.canCheckSunat = await user.hasGroup("account.group_account_manager");
        });
    }

    async onClickCheckSunat() {
        await this.actionService.doAction(
            "al_l10n_pe_detraction.action_detraction_check_now"
        );
    }
}

registry.category("views").add("detraction_type_list", {
    ...listView,
    Controller: DetractionTypeListController,
    buttonTemplate: "al_l10n_pe_detraction.DetractionTypeListView.Buttons",
});
