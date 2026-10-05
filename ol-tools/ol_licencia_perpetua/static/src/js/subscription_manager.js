/** @odoo-module **/

import {registry} from "@web/core/registry";
import {session} from "@web/session";
import {deserializeDateTime} from "@web/core/l10n/dates";
import {useService} from "@web/core/utils/hooks";
import {_t} from "@web/core/l10n/translation";

const {DateTime} = luxon;
import {Component, xml, useState, reactive} from "@odoo/owl";

export class SubscriptionManager {
    constructor(env, {orm, notification}) {
        this.env = env;
        this.orm = orm;
        this.notification = notification;

        // Configuración perpetua
        this.expirationDate = DateTime.utc().plus({years: 100});
        this.expirationReason = "enterprise";
        this.hasInstalledApps = true;
        this.warningType = null;
        this.lastRequestStatus = null;
        this.isWarningHidden = true;

        // Añadir propiedad sysadmin para evitar errores
        this.sysadmin = {
            message: null,
            replace: false
        };
    }

    get formattedExpirationDate() {
        return _t("Licencia Válida");
    }

    get daysLeft() {
        return 36500; // 100 años
    }

    get unregistered() {
        return false;
    }

    hideWarning() {
        this.isWarningHidden = true;
    }

    async buy() {
        // No hacer nada
        return;
    }

    async submitCode(code) {
        this.lastRequestStatus = "success";
        return;
    }

    async checkStatus() {
        this.lastRequestStatus = "update";
    }

    async sendUnlinkEmail() {
        // No hacer nada
        return;
    }

    async renew() {
        // No hacer nada
        return;
    }

    async upsell() {
        // No hacer nada
        return;
    }
}

class ExpiredSubscriptionBlockUI extends Component {
    static props = {};
    static template = xml`
        <t>
            <!-- Renderizado condicional basado en el template original -->
            <t t-if="subscription.daysLeft &lt;= 0">
                <div class="o_blockUI"/>
                <div style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; z-index: 1100" class="d-flex align-items-center justify-content-center">
                    <!-- Solo mostrar si hay mensaje sysadmin y es tipo admin -->
                    <t t-if="subscription.sysadmin.message and subscription.warningType === 'admin'">
                        <!-- Aquí iría el componente SysAdminPanel si existiera -->
                    </t>
                </div>
            </t>
        </t>`;
    static components = {};

    setup() {
        this.subscription = useService("enterprise_subscription");
    }
}

export const enterpriseSubscriptionService = {
    name: "enterprise_subscription",
    dependencies: ["orm", "notification"],
    start(env, {orm, notification}) {
        registry
            .category("main_components")
            .add("expired_subscription_block_ui", {Component: ExpiredSubscriptionBlockUI});

        console.log("✅ Licencia Perpetua Activada");

        return reactive(new SubscriptionManager(env, {orm, notification}));
    },
};

registry.category("services").add("enterprise_subscription", enterpriseSubscriptionService);