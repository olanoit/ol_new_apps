import { patch } from "@web/core/utils/patch";
import { PivotRenderer } from "@web/views/pivot/pivot_renderer";
import { signal, useEffect } from "@odoo/owl";

patch(PivotRenderer.prototype, {
    setup() {
        super.setup();
        this.rootRef = signal.ref();
        if (this.uiService.isSmall) {
            useEffect(() => {
                const rootEl = this.rootRef();
                if (rootEl) {
                    const tooltipElems = rootEl.querySelectorAll("*[data-tooltip]");
                    for (const el of tooltipElems) {
                        el.removeAttribute("data-tooltip");
                        el.removeAttribute("data-tooltip-position");
                    }
                }
            });
        }
    },
});
