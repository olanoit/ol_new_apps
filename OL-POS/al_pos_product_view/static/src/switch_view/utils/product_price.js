/** @odoo-module **/

import { formatCurrency } from "@web/core/currency";
import { _t } from "@web/core/l10n/translation";
import { formatFloat } from "@web/core/utils/numbers";

/**
 * Precio unitario de un product.template para el catálogo (filas de la lista
 * y tarjetas de opcionales del popup), igual que la línea de pedido nativa:
 *
 * - Tarifa: la del pedido actual (la que se cobrará) y, si no hay pedido,
 *   la de la caja.
 * - Variante: las plantillas de una sola variante se tarifican a través de
 *   ella. `getPrice()` sobre la plantilla pelada se salta las reglas por
 *   variante (`0_product_variant`), así que una tarifa cargada por variante
 *   mostraba el `list_price` crudo en la lista.
 * - Impuestos: total con o sin impuestos según `pos.config.iface_tax_included`,
 *   el mismo switch de los `displayPriceUnit` nativos.
 *
 * Si el cálculo lanza una excepción (tarifa o impuesto mal configurado)
 * recurre al `list_price` crudo para que el catálogo siga usable.
 */
export function getTaxAwareProductPrice(pos, product) {
    const config = pos.config;
    try {
        const price = computeTaxAwarePrice(pos, getPricedRecord(product), {
            pricelist: getCatalogPricelist(pos),
        });
        return formatCurrency(price, config.currency_id.id);
    } catch {
        return formatCurrency(product.list_price || 0, config.currency_id.id);
    }
}

/**
 * Desglose corto bajo el precio en las filas de la lista: qué hizo la tarifa
 * con el precio de venta del producto, sea cual sea el tipo de regla
 * (porcentaje, precio fijo o fórmula):
 *
 * - precio menor → «20% de descuento sobre S/ 10,00»;
 * - precio mayor → «12,5% de recargo sobre S/ 10,00».
 *
 * Las dos cifras pasan por los mismos impuestos y posición fiscal, así que
 * el porcentaje es la diferencia real. Devuelve "" si la tarifa no cambia el
 * precio o si el cálculo falla.
 */
export function getProductPriceDetail(pos, product) {
    const pricelist = getCatalogPricelist(pos);
    if (!pricelist) {
        return "";
    }
    try {
        const priced = getPricedRecord(product);
        const originalPrice = computeTaxAwarePrice(pos, priced, { pricelist: false });
        const finalPrice = computeTaxAwarePrice(pos, priced, { pricelist });
        if (!originalPrice) {
            return "";
        }
        const percent = (Math.abs(originalPrice - finalPrice) / originalPrice) * 100;
        // Por debajo de 0,005 % la etiqueta diría «0 %»: se trata como igual.
        if (percent < 0.005) {
            return "";
        }
        const values = {
            percent: formatFloat(percent, { digits: [16, 2], trailingZeros: false }),
            price: formatCurrency(originalPrice, pos.config.currency_id.id),
        };
        return finalPrice < originalPrice
            ? _t("%(percent)s% de descuento sobre %(price)s", values)
            : _t("%(percent)s% de recargo sobre %(price)s", values);
    } catch {
        return "";
    }
}

// Tarifa del pedido actual; la de la caja si no hay pedido.
function getCatalogPricelist(pos) {
    return pos.getOrder()?.pricelist_id || pos.config.pricelist_id;
}

// Las plantillas de una sola variante se tarifican a través de ella.
function getPricedRecord(product) {
    const variants = product.product_variant_ids || [];
    return variants.length === 1 ? variants[0] : product;
}

// Precio unitario con o sin impuestos según `pos.config.iface_tax_included`.
function computeTaxAwarePrice(pos, priced, overridedValues) {
    const taxDetails = priced.getTaxDetails({
        overridedValues: {
            fiscalPosition: pos.getOrder()?.fiscal_position_id,
            ...overridedValues,
        },
    });
    return pos.config.iface_tax_included === "total"
        ? taxDetails.total_included
        : taxDetails.total_excluded;
}
