/** @odoo-module **/

import { formatCurrency } from "@web/core/currency";

/**
 * Formatea el precio unitario de un product.template igual que la línea de
 * pedido nativa: resuelve la regla de tarifa del pedido actual vía
 * `getTaxDetails()` (que internamente llama a `getPrice()`) y luego escoge
 * el total con o sin impuestos según `pos.config.iface_tax_included` —
 * exactamente el mismo switch que usan de forma nativa
 * `ProductTemplateAccounting.displayPriceUnit` y
 * `PosOrderlineAccounting.displayPriceUnit`, así la cifra coincide con lo
 * que acaba en la línea de pedido al añadir el producto.
 *
 * Recurre al `list_price` crudo (sin impuestos, sin tarifa) si el cálculo
 * de impuestos/tarifa lanza una excepción — p.ej. una tarifa o impuesto
 * mal configurado en el producto — para que el catálogo siga usable en
 * lugar de romperse.
 */
export function getTaxAwareProductPrice(pos, product) {
    const config = pos.config;
    const order = pos.getOrder();
    try {
        const taxDetails = product.getTaxDetails({
            overridedValues: {
                pricelist: order?.pricelist_id,
                fiscalPosition: order?.fiscal_position_id,
            },
        });
        const price =
            config.iface_tax_included === "total"
                ? taxDetails.total_included
                : taxDetails.total_excluded;
        return formatCurrency(price, config.currency_id.id);
    } catch {
        return formatCurrency(product.list_price || 0, config.currency_id.id);
    }
}
