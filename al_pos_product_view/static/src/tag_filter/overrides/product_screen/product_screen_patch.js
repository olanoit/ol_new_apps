/** @odoo-module **/

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { PosTagSelector } from "@al_pos_product_view/tag_filter/components/tag_selector/tag_selector";

// Registra el selector en ProductScreen para que la plantilla heredada
// (product_screen_patch.xml) pueda referenciarlo.
ProductScreen.components = {
    ...ProductScreen.components,
    PosTagSelector,
};
