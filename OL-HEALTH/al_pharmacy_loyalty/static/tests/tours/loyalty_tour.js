import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as PosLoyalty from "@pos_loyalty/../tests/tours/utils/pos_loyalty_util";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("al_pharmacy_loyalty_points", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickPartnerButton(),
            ProductScreen.clickCustomer("Rosa Quispe"),
            ProductScreen.addOrderline("Bloqueador solar FPS 50", "1"),
            ProductScreen.addOrderline("Amoxicilina 500 mg", "1"),
            // S/ 48 en total, pero solo los S/ 8 de venta libre suman: 2 puntos.
            PosLoyalty.pointsAwardedAre("2"),
            // El 10 % de socio no alcanza a la amoxicilina: −0,80 y no −4,80.
            PosLoyalty.claimReward("Descuento de socio"),
            PosLoyalty.hasRewardLine("Descuento de socio", "-0.80"),
            PosLoyalty.orderTotalIs("47.20"),
            PosLoyalty.finalizeOrder("Cash", "47.20"),
        ].flat(),
});
