import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

/**
 * Serie fija por caja y tipo de comprobante (patrón del vendedor
 * predeterminado por sesión: localStorage, no persiste en BD).
 */
patch(PosStore.prototype, {
    _peSeriesStorageKey(docType) {
        return `alpe_fixed_series_${this.config.id}_${docType}`;
    },

    /** Series publicadas de la caja para el tipo dado (registros). */
    getPeSeries(docType) {
        const series =
            docType === "factura"
                ? this.config.l10n_pe_factura_series_ids
                : this.config.l10n_pe_boleta_series_ids;
        return (series || []).filter(Boolean);
    },

    getPeFixedSeries(docType) {
        const id = parseInt(localStorage.getItem(this._peSeriesStorageKey(docType)));
        if (!id) {
            return null;
        }
        return this.getPeSeries(docType).find((s) => s.id === id) || null;
    },

    setPeFixedSeries(docType, serie) {
        const key = this._peSeriesStorageKey(docType);
        if (serie) {
            localStorage.setItem(key, String(serie.id));
        } else {
            localStorage.removeItem(key);
        }
    },
});
