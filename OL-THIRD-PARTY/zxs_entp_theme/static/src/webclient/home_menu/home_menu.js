import {
    Component,
    onMounted,
    onPatched,
    usePlugin,
    proxy,
    t,
    useEffect,
    signal,
    useListener,
    useProps,
} from "@odoo/owl";
import { hasTouch, isIosApp, isMacOS } from "@web/core/browser/feature_detection";
import { useDropzone } from "@web/core/dropzone/dropzone_hook";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { useSortable } from "@web/core/utils/sortable_owl";
import { OfflinePlugin } from "@web/core/offline/offline_plugin";

class FooterComponent extends Component {
    static template = "zxs_entp_theme.HomeMenu.CommandPalette.Footer";

    props = useProps({
        switchNamespace: t.function().optional(),
    });

    setup() {
        this.controlKey = isMacOS() ? "COMMAND" : "CONTROL";
    }
}

/**
 * Home menu
 *
 * Displays the application grid and opens the command palette for global search.
 */
export class HomeMenu extends Component {
    static template = "zxs_entp_theme.HomeMenu";
    static components = {};

    props = useProps({
        apps: t.array(
            t.object({
                actionID: t.number(),
                href: t.string(),
                appID: t.number(),
                id: t.number(),
                label: t.string(),
                parents: t.string(),
                webIcon: t
                    .or([
                        t.boolean(),
                        t.string(),
                        t.object({
                            icon: t.string(),
                            color: t.string(),
                            backgroundColor: t.string(),
                        }),
                    ])
                    .optional(),
                webIconData: t.string().optional(),
                xmlid: t.string(),
            })
        ),
        reorderApps: t.function().optional(),
    });
    inputRef = signal.ref();
    rootRef = signal.ref();

    setup() {
        this.command = useService("command");
        this.menus = useService("menu");
        this.homeMenuService = useService("home_menu");
        this.ui = useService("ui");
        this.shareTarget = useService("share_target");
        this.offlinePlugin = usePlugin(OfflinePlugin);
        this.state = proxy({
            focusedIndex: null,
            isIosApp: isIosApp(),
        });
        this.pressTimer;

        if (!this.ui.isSmall) {
            this._registerHotkeys();
        }

        useSortable({
            enable: this._enableAppsSorting,
            ref: this.rootRef,
            elements: ".o_draggable",
            cursor: "move",
            delay: 500,
            tolerance: 10,
            onWillStartDrag: (params) => this._sortStart(params),
            onDrop: (params) => this._sortAppDrop(params),
        });

        useEffect(() => {
            this.props.apps;
            this.state.focusedIndex = null;
        });

        onMounted(() => {
            if (hasTouch()) {
                this.rootRef().scrollTo(0, 46);
            } else {
                this._focusInput();
            }
        });

        onPatched(() => {
            if (this.state.focusedIndex !== null && !this.ui.isSmall) {
                const selectedItem = document.querySelector(".o_home_menu .o_menuitem.o_focused");
                if (selectedItem) {
                    selectedItem.scrollIntoView({ block: "center" });
                }
            }
        });
        if (this.shareTarget.hasShareTargetItems) {
            useDropzone(this.rootRef, (ev) => this.shareTarget.display(ev.dataTransfer.files));
        }
    }

    get displayedApps() {
        return this.props.apps;
    }

    get maxIconNumber() {
        const w = window.innerWidth;
        if (w < 576) {
            return 3;
        } else if (w < 768) {
            return 4;
        } else {
            return 6;
        }
    }

    get searchMenuPlaceholder() {
        return _t("Search for a menu...");
    }

    get hasTouch() {
        return hasTouch();
    }

    _openMenu(menu) {
        return this.menus.selectMenu(menu);
    }

    _updateFocusedIndex(cmd) {
        const nbrApps = this.displayedApps.length;
        const lastIndex = nbrApps - 1;
        const focusedIndex = this.state.focusedIndex;
        if (lastIndex < 0) {
            return;
        }
        if (focusedIndex === null) {
            this.state.focusedIndex = 0;
            return;
        }
        const lineNumber = Math.ceil(nbrApps / this.maxIconNumber);
        const currentLine = Math.ceil((focusedIndex + 1) / this.maxIconNumber);
        let newIndex;
        switch (cmd) {
            case "previousElem":
                newIndex = focusedIndex - 1;
                break;
            case "nextElem":
                newIndex = focusedIndex + 1;
                break;
            case "previousColumn":
                if (focusedIndex % this.maxIconNumber) {
                    newIndex = focusedIndex - 1;
                } else {
                    newIndex =
                        focusedIndex + Math.min(lastIndex - focusedIndex, this.maxIconNumber - 1);
                }
                break;
            case "nextColumn":
                if (focusedIndex === lastIndex || (focusedIndex + 1) % this.maxIconNumber === 0) {
                    newIndex = (currentLine - 1) * this.maxIconNumber;
                } else {
                    newIndex = focusedIndex + 1;
                }
                break;
            case "previousLine":
                if (currentLine === 1) {
                    newIndex = focusedIndex + (lineNumber - 1) * this.maxIconNumber;
                    if (newIndex > lastIndex) {
                        newIndex = lastIndex;
                    }
                } else {
                    newIndex = focusedIndex - this.maxIconNumber;
                }
                break;
            case "nextLine":
                if (currentLine === lineNumber) {
                    newIndex = focusedIndex % this.maxIconNumber;
                } else {
                    newIndex =
                        focusedIndex + Math.min(this.maxIconNumber, lastIndex - focusedIndex);
                }
                break;
        }
        if (newIndex < 0) {
            newIndex = lastIndex;
        } else if (newIndex > lastIndex) {
            newIndex = 0;
        }
        this.state.focusedIndex = newIndex;
    }

    _focusInput() {
        if (!this.ui.isSmall && this.inputRef()) {
            this.inputRef().focus({ preventScroll: true });
        }
    }

    _enableAppsSorting() {
        return true;
    }

    _isAvailable(app) {
        return (
            !this.offlinePlugin.isOffline() ||
            !app.actionID ||
            this.offlinePlugin.isAvailableOffline(app.actionID)
        );
    }

    _sortAppDrop({ element, previous }) {
        const order = this.props.apps.map((app) => app.xmlid);
        const elementId = element.children[0].dataset.menuXmlid;
        const elementIndex = order.indexOf(elementId);
        order.splice(elementIndex, 1);
        if (previous) {
            const prevIndex = order.indexOf(previous.children[0].dataset.menuXmlid);
            order.splice(prevIndex + 1, 0, elementId);
        } else {
            order.splice(0, 0, elementId);
        }
        this.props.reorderApps(order);
        user.setUserSettings("homemenu_config", JSON.stringify(order));
    }

    _sortStart({ element, addClass }) {
        addClass(element.children[0], "o_dragged_app");
    }

    _onAppClick(app) {
        this._openMenu(app);
    }

    _registerHotkeys() {
        const hotkeys = [
            ["ArrowDown", () => this._updateFocusedIndex("nextLine")],
            ["ArrowRight", () => this._updateFocusedIndex("nextColumn")],
            ["ArrowUp", () => this._updateFocusedIndex("previousLine")],
            ["ArrowLeft", () => this._updateFocusedIndex("previousColumn")],
            ["Tab", () => this._updateFocusedIndex("nextElem")],
            ["shift+Tab", () => this._updateFocusedIndex("previousElem")],
            [
                "Enter",
                () => {
                    const menu = this.displayedApps[this.state.focusedIndex];
                    if (menu) {
                        this._openMenu(menu);
                    }
                },
            ],
            ["Escape", () => this.homeMenuService.toggle(false)],
        ];
        hotkeys.forEach((hotkey) => {
            useHotkey(...hotkey, {
                allowRepeat: true,
            });
        });
        useListener(window, "keydown", this._onKeydownFocusInput.bind(this));
    }

    _onKeydownFocusInput() {
        if (
            document.activeElement !== this.inputRef() &&
            this.ui.activeElement === document &&
            !["TEXTAREA", "INPUT"].includes(document.activeElement.tagName)
        ) {
            this._focusInput();
        }
    }

    _onInputClick() {
        this.command.openMainPalette({ searchValue: "/", FooterComponent });
    }

    _onInputSearch() {
        const onClose = () => {
            this._focusInput();
        };
        const searchValue = this.compositionStart ? "/" : `/${this.inputRef().value.trim()}`;
        this.compositionStart = false;
        this.command.openMainPalette({ searchValue, FooterComponent }, onClose);
        this.inputRef().value = "";
    }

    _onInputBlur() {
        if (hasTouch()) {
            return;
        }
        setTimeout(() => {
            if (document.activeElement === document.body && this.ui.activeElement === document) {
                this._focusInput();
            }
        }, 0);
    }

    _onCompositionStart() {
        this.compositionStart = true;
    }
}
