import { patch } from "@web/core/utils/patch";
import { formatCurrency } from "@web/core/currency";
import { ProductCard } from "@point_of_sale/app/components/product_card/product_card";

/**
 * Precio en la tarjeta de producto de la grilla.
 *
 * Mismo cálculo que la línea de pedido: regla de la lista de precios y
 * posición fiscal de la orden actual (`getTaxDetails`) y total con o sin
 * impuestos según `pos.config.iface_tax_included`. Si el cálculo falla
 * (impuesto o lista de precios mal configurados) se muestra `list_price`
 * para que el catálogo nunca se rompa por un producto.
 */
patch(ProductCard.prototype, {
    get alptPriceLabel() {
        const pos = this.env.services.pos;
        const product = this.props.product;
        if (!pos || !product?.getTaxDetails) {
            return "";
        }
        const config = pos.config;
        const order = pos.getOrder();
        let price;
        try {
            const taxDetails = product.getTaxDetails({
                overridedValues: {
                    pricelist: order?.pricelist_id,
                    fiscalPosition: order?.fiscal_position_id,
                },
            });
            price =
                config.iface_tax_included === "total"
                    ? taxDetails.total_included
                    : taxDetails.total_excluded;
        } catch {
            price = product.list_price || 0;
        }
        return formatCurrency(price, config.currency_id.id);
    },
});
