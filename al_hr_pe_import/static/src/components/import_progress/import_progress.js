/** @odoo-module **/
/**
 * Widget OWL de barra de progreso para importaciones de planillas.
 *
 * Registrado en "view_widgets" (no "fields") para que el componente NO
 * quede envuelto en .o_field_widget y ocupe todo el ancho disponible
 * del diálogo. Se usa en la vista form como:
 *   <widget name="al_import_payroll_progress_widget"/>
 *
 * Hace polling cada segundo via ORM hasta que status === 'done' | 'error'.
 * (Port v18 → v19: la API de useService("orm")/doAction no cambió.)
 */
import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class ImportPayrollProgressWidget extends Component {
    static template = "al_hr_pe_import.ImportPayrollProgressWidget";
    static props = {
        record: { type: Object },
        "*": true,
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            total: 0,
            current: 0,
            created: 0,
            updated: 0,
            skipped: 0,
            errors: 0,
            status: "pending",
            message: "Preparando importación...",
            percent: 0,
            error_detail: "",
            has_report: false,
            has_records: false,
            wizard_model: false,
            wizard_id: false,
            target_model: false,
        });

        this._pollInterval = null;

        onMounted(() => this._startPolling());
        onWillUnmount(() => this._stopPolling());
    }

    get recordId() {
        return this.props.record.resId;
    }

    _startPolling() {
        this._fetchProgress();
        this._pollInterval = setInterval(() => this._fetchProgress(), 1000);
    }

    _stopPolling() {
        if (this._pollInterval) {
            clearInterval(this._pollInterval);
            this._pollInterval = null;
        }
    }

    async _fetchProgress() {
        if (!this.recordId) return;
        try {
            const data = await this.orm.call(
                "al.import.payroll.progress",
                "get_progress_data",
                [this.recordId],
            );
            Object.assign(this.state, data);
            if (data.status === "done" || data.status === "error") {
                this._stopPolling();
            }
        } catch (err) {
            console.error("ImportPayrollProgressWidget polling error:", err);
            this._stopPolling();
        }
    }

    async onDownloadReport() {
        if (!this.state.has_report) return;
        await this.action.doAction(
            await this.orm.call(
                "al.import.payroll.progress",
                "action_download_report",
                [this.recordId],
            ),
        );
    }

    async onViewRecords() {
        if (!this.state.has_records) return;
        const action = await this.orm.call(
            "al.import.payroll.progress",
            "action_view_target_records",
            [this.recordId],
        );
        if (action) {
            await this.action.doAction(action);
        }
    }

    async onClose() {
        await this.action.doAction({ type: "ir.actions.act_window_close" });
    }
}

registry.category("view_widgets").add("al_import_payroll_progress_widget", {
    component: ImportPayrollProgressWidget,
});
