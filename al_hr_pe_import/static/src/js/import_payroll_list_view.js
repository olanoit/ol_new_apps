/** @odoo-module **/
/**
 * Factoría reutilizable para añadir un botón "Importar desde Excel" a
 * una list view de planillas.
 *
 * Cambio v19: web.ListView.Buttons ahora es una plantilla VACÍA que el
 * controller renderiza en el slot "layout-buttons"
 * (t-call="{{ props.buttonTemplate }}"), así que el template del botón
 * es standalone (sin t-inherit ni xpath sobre .o_list_buttons como en
 * v18).
 *
 * Uso (un archivo por importador, ej. hr_attendance_list_view.js):
 *
 *   import { attendanceListView } from "@hr_attendance/views/attendance_list_view";
 *   import { makeImportPayrollListView } from "./import_payroll_list_view";
 *   makeImportPayrollListView({
 *       baseView: attendanceListView,
 *       jsClassName: "hr_attendance_import_list",
 *       buttonTemplate: "al_hr_pe_import.HrAttendanceListView.Buttons",
 *       actionXmlId: "al_hr_pe_import.action_al_import_hr_attendance_wizard",
 *   });
 */
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";

export function makeImportPayrollListView({
    baseView = listView,
    jsClassName,
    buttonTemplate,
    actionXmlId,
}) {
    const BaseController = baseView.Controller || ListController;

    class ImportPayrollListController extends BaseController {
        async onClickImportPayroll() {
            await this.actionService.doAction(actionXmlId, {
                onClose: async () => {
                    // Recarga la list view al cerrar el wizard.
                    await this.model.load();
                },
            });
        }
    }

    const importPayrollListView = {
        ...baseView,
        Controller: ImportPayrollListController,
        buttonTemplate,
    };

    registry.category("views").add(jsClassName, importPayrollListView);
    return { ImportPayrollListController, importPayrollListView };
}
