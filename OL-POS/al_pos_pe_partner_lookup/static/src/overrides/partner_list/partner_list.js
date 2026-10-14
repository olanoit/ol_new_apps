import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";

patch(PartnerList.prototype, {
    /**
     * RUC (11 dígitos) o DNI (8 dígitos) escrito en la búsqueda, sin
     * espacios ni guiones; ``null`` si la búsqueda no tiene esa forma.
     *
     * @return {string|null}
     */
    get l10nPeDocument() {
        const digits = (this.state.query || "").replace(/[\s.-]/g, "");
        return /^(\d{8}|\d{11})$/.test(digits) ? digits : null;
    },

    /**
     * Crea (o trae, si ya existe) el cliente del documento buscado con los
     * datos de SUNAT/RENIEC y lo elige para la venta.
     */
    async l10nPeCreateFromDocument() {
        const number = this.l10nPeDocument;
        if (!number || this.state.loading) {
            return;
        }
        this.state.loading = true;
        try {
            const partnerId = await this.pos.data.call(
                "res.partner",
                "l10n_pe_pos_create_from_document",
                [number]
            );
            const [partner] = await this.pos.data.read("res.partner", [partnerId]);
            this.notification.add(_t("Cliente %s listo.", partner.name), { type: "success" });
            this.clickPartner(partner);
        } catch (error) {
            this.notification.add(error.data?.message || _t("No se pudo consultar el documento."), {
                type: "danger",
            });
        } finally {
            this.state.loading = false;
        }
    },
});
