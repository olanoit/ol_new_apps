/** @odoo-module **/
import { attendanceListView } from "@hr_attendance/views/attendance_list_view";
import { makeImportPayrollListView } from "./import_payroll_list_view";

makeImportPayrollListView({
    baseView: attendanceListView,
    jsClassName: "hr_attendance_import_list",
    buttonTemplate: "al_hr_pe_import.HrAttendanceListView.Buttons",
    actionXmlId: "al_hr_pe_import.action_al_import_hr_attendance_wizard",
    // Mismos grupos que el ACL del asistente de asistencias.
    groups: [
        "hr_attendance.group_hr_attendance_officer",
        "hr_payroll.group_hr_payroll_user",
    ],
});
