/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    getVendedores() {
        if (!this.config.authorized_seller) {
            return [];
        }
        // Se descartan vendedores que llegan al frontend como proxy sin nombre
        // (p. ej. empleados archivados o fuera del alcance de carga del POS),
        // para evitar errores de orden y entradas en blanco en el selector.
        return [...this.config.seller_ids]
            .filter((v) => v && v.name)
            .sort((a, b) => a.name.localeCompare(b.name));
    },

    // Clave de almacenamiento acotada a la sesión POS abierta, de modo que el
    // vendedor predeterminado solo aplique a la sesión actual y sobreviva a
    // recargas del navegador mientras la sesión siga abierta.
    _sessionSellerStorageKey() {
        return `alv_default_seller_${this.session?.id ?? "x"}`;
    },

    getSessionDefaultSeller() {
        if (!this.config.authorized_seller) {
            return false;
        }
        const raw = localStorage.getItem(this._sessionSellerStorageKey());
        if (!raw) {
            return false;
        }
        const id = parseInt(raw, 10);
        return this.getVendedores().find((v) => v.id === id) || false;
    },

    setSessionDefaultSeller(seller) {
        const key = this._sessionSellerStorageKey();
        if (seller) {
            localStorage.setItem(key, String(seller.id));
        } else {
            localStorage.removeItem(key);
        }
    },

    createNewOrder(data = {}) {
        const order = super.createNewOrder(...arguments);
        if (this.config.authorized_seller && !order.seller_id) {
            const defaultSeller = this.getSessionDefaultSeller();
            if (defaultSeller) {
                order.seller_id = defaultSeller;
            }
        }
        return order;
    },
});
