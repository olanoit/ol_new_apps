/** @odoo-module **/
// Botón «?» que abre la página de la documentación de la pantalla actual:
// en la barra superior (pantallas) y en la cabecera de los asistentes.
import { Component, onWillStart, onWillUpdateProps, proxy, t, usePlugin, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";
import { ActionDialog } from "@web/webclient/actions/action_dialog";
import { ActionManagerPlugin } from "@web/webclient/actions/action_plugin";

function openHelp(help) {
    window.open(help.url, "_blank", "noopener");
}

function helpTitle(help) {
    return help.section ? _t("Ayuda: %s", help.section) : _t("Ayuda de esta pantalla");
}

/** Pantalla actual del gestor de acciones: modelo de la vista o tag. */
function currentKey(action) {
    const controller = action.currentController;
    if (!controller) {
        return null;
    }
    if (controller.action.type === "ir.actions.act_window") {
        return controller.props.resModel;
    }
    if (controller.action.type === "ir.actions.client") {
        return controller.action.tag;
    }
    return null;
}

export class DocsHelpSystray extends Component {
    static template = "al_docs_help.DocsHelpSystray";
    props = useProps({});

    setup() {
        this.action = usePlugin(ActionManagerPlugin);
        this.docsHelp = useService("al_docs_help");
        this.state = proxy({ help: null });
        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", () => this.update());
        onWillStart(() => this.update());
    }

    async update() {
        this.state.help = await this.docsHelp.get(currentKey(this.action));
    }

    get title() {
        return helpTitle(this.state.help);
    }

    onClick() {
        openHelp(this.state.help);
    }
}

export class DocsHelpButton extends Component {
    static template = "al_docs_help.DocsHelpButton";
    props = useProps({
        helpKey: t.any().optional(),
    });

    setup() {
        this.docsHelp = useService("al_docs_help");
        this.state = proxy({ help: null });
        onWillStart(() => this.load(this.props.helpKey));
        onWillUpdateProps((next) => this.load(next.helpKey));
    }

    async load(key) {
        this.state.help = await this.docsHelp.get(key);
    }

    get title() {
        return helpTitle(this.state.help);
    }

    onClick() {
        openHelp(this.state.help);
    }
}

ActionDialog.components = { ...ActionDialog.components, DocsHelpButton };

registry.category("systray").add("al_docs_help", { Component: DocsHelpSystray }, { sequence: 2 });
